"""SQLite schema and query layer for the tooling index."""

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from .models import ScanResult


class ToolingDatabase:
    """SQLite database for component metadata and analytics."""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or (
            Path.home() / ".claude" / "data" / "tooling_index.db"
        )
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self):
        """Initialize database schema."""
        cursor = self.conn.cursor()

        self._ensure_components_schema(cursor)

        # Invocations table (usage tracking)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS invocations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                component_id INTEGER NOT NULL,
                session_id TEXT,
                timestamp DATETIME NOT NULL,
                duration_ms INTEGER,
                success BOOLEAN,
                error_message TEXT,
                FOREIGN KEY (component_id) REFERENCES components(id)
            )
        """)

        # Installation timeline
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS installation_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                component_id INTEGER NOT NULL,
                event_type TEXT NOT NULL,
                timestamp DATETIME NOT NULL,
                version TEXT,
                metadata_json TEXT,
                FOREIGN KEY (component_id) REFERENCES components(id)
            )
        """)

        self._ensure_components_fts_schema(cursor)

        # Indexes for fast queries
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_invocations_timestamp
            ON invocations(timestamp)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_invocations_component
            ON invocations(component_id)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_components_type
            ON components(type)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_components_origin
            ON components(origin)
        """)

        self.conn.commit()

    def _ensure_components_schema(self, cursor: sqlite3.Cursor) -> None:
        """Ensure components table exists and is on the latest schema."""
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='components'"
        )
        has_components = cursor.fetchone() is not None

        if not has_components:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS components (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    platform TEXT NOT NULL DEFAULT 'claude',
                    name TEXT NOT NULL,
                    type TEXT NOT NULL,
                    origin TEXT,
                    status TEXT,
                    version TEXT,
                    install_path TEXT,
                    first_seen DATETIME NOT NULL,
                    last_seen DATETIME NOT NULL,
                    metadata_json TEXT,
                    UNIQUE(platform, name, type)
                )
                """
            )
            return

        cursor.execute("PRAGMA table_info(components)")
        columns = {row["name"] for row in cursor.fetchall()}
        if "platform" not in columns:
            self._migrate_components_add_platform(cursor)

    def _migrate_components_add_platform(self, cursor: sqlite3.Cursor) -> None:
        """One-time migration: add platform dimension and adjust uniqueness.

        Old: UNIQUE(name, type)
        New: UNIQUE(platform, name, type)
        """
        cursor.execute("PRAGMA foreign_keys=OFF")
        cursor.execute("BEGIN")
        try:
            cursor.execute("ALTER TABLE components RENAME TO components_old")
            cursor.execute("DROP TABLE IF EXISTS components_fts")

            cursor.execute(
                """
                CREATE TABLE components (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    platform TEXT NOT NULL DEFAULT 'claude',
                    name TEXT NOT NULL,
                    type TEXT NOT NULL,
                    origin TEXT,
                    status TEXT,
                    version TEXT,
                    install_path TEXT,
                    first_seen DATETIME NOT NULL,
                    last_seen DATETIME NOT NULL,
                    metadata_json TEXT,
                    UNIQUE(platform, name, type)
                )
                """
            )

            cursor.execute(
                """
                INSERT INTO components (
                    id, platform, name, type, origin, status, version,
                    install_path, first_seen, last_seen, metadata_json
                )
                SELECT
                    id, 'claude', name, type, origin, status, version,
                    install_path, first_seen, last_seen, metadata_json
                FROM components_old
                """
            )

            cursor.execute("DROP TABLE components_old")

            cursor.execute(
                """
                CREATE VIRTUAL TABLE components_fts USING fts5(
                    name,
                    description,
                    keywords
                )
                """
            )

            # Rebuild FTS rows from existing metadata (best-effort).
            cursor.execute(
                "SELECT id, platform, name, type, metadata_json FROM components"
            )
            for row in cursor.fetchall():
                description = ""
                try:
                    meta = json.loads(row["metadata_json"] or "{}")
                    description = meta.get("description") or ""
                except (json.JSONDecodeError, TypeError):
                    description = ""

                keywords = f"{row['platform']} {row['type']}"
                cursor.execute(
                    """
                    INSERT OR REPLACE INTO components_fts
                    (rowid, name, description, keywords)
                    VALUES (?, ?, ?, ?)
                    """,
                    (row["id"], row["name"], description, keywords),
                )

            cursor.execute("COMMIT")
        except Exception:
            cursor.execute("ROLLBACK")
            raise
        finally:
            cursor.execute("PRAGMA foreign_keys=ON")

    def _ensure_components_fts_schema(self, cursor: sqlite3.Cursor) -> None:
        """Ensure the FTS table exists and matches the expected schema."""
        cursor.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='components_fts'"
        )
        row = cursor.fetchone()
        ddl = (row["sql"] or "") if row else ""

        # Older versions used external-content FTS pointing at `components`, but the
        # components table doesn't have matching columns. Rebuild as standalone.
        if row and "content=components" in ddl:
            cursor.execute("DROP TABLE IF EXISTS components_fts")
            row = None

        if not row:
            cursor.execute(
                """
                CREATE VIRTUAL TABLE components_fts USING fts5(
                    name,
                    description,
                    keywords
                )
                """
            )
            self._rebuild_components_fts(cursor)

    def _rebuild_components_fts(self, cursor: sqlite3.Cursor) -> None:
        """Best-effort rebuild of FTS data from `components`."""
        cursor.execute("DELETE FROM components_fts")
        cursor.execute("SELECT id, platform, name, type, metadata_json FROM components")
        for row in cursor.fetchall():
            description = ""
            try:
                meta = json.loads(row["metadata_json"] or "{}")
                description = meta.get("description") or ""
            except (json.JSONDecodeError, TypeError):
                description = ""

            keywords = f"{row['platform']} {row['type']}"
            cursor.execute(
                """
                INSERT OR REPLACE INTO components_fts
                (rowid, name, description, keywords)
                VALUES (?, ?, ?, ?)
                """,
                (row["id"], row["name"], description, keywords),
            )

    def update_components(self, scan_result: ScanResult):
        """Update components table from scan result."""
        cursor = self.conn.cursor()
        current_time = datetime.now()

        for component in scan_result.all_components:
            # Serialize full metadata to JSON
            metadata_dict = {
                "name": component.name,
                "type": component.type,
                "platform": getattr(component, "platform", "claude"),
                "origin": component.origin,
                "status": component.status,
                "last_modified": component.last_modified.isoformat(),
                "install_path": str(component.install_path),
            }

            # Add type-specific fields
            if hasattr(component, "version"):
                metadata_dict["version"] = component.version
            if hasattr(component, "description"):
                metadata_dict["description"] = component.description
            if hasattr(component, "file_count"):
                metadata_dict["file_count"] = component.file_count
            if hasattr(component, "total_lines"):
                metadata_dict["total_lines"] = component.total_lines
            if hasattr(component, "performance_notes"):
                metadata_dict["performance_notes"] = component.performance_notes
            if hasattr(component, "marketplace"):
                metadata_dict["marketplace"] = component.marketplace

            metadata_json = json.dumps(metadata_dict)

            # Check if component exists
            cursor.execute(
                "SELECT id, first_seen FROM components WHERE platform = ? AND name = ? AND type = ?",
                (
                    getattr(component, "platform", "claude"),
                    component.name,
                    component.type,
                ),
            )
            existing = cursor.fetchone()

            if existing:
                # Update existing component
                component_id = existing["id"]
                existing["first_seen"]

                cursor.execute(
                    """
                    UPDATE components
                    SET origin = ?, status = ?, version = ?,
                        install_path = ?, last_seen = ?, metadata_json = ?
                    WHERE id = ?
                    """,
                    (
                        component.origin,
                        component.status,
                        getattr(component, "version", None),
                        str(component.install_path),
                        current_time,
                        metadata_json,
                        component_id,
                    ),
                )

                # Track update event
                cursor.execute(
                    """
                    INSERT INTO installation_events
                    (component_id, event_type, timestamp, version, metadata_json)
                    VALUES (?, 'updated', ?, ?, ?)
                    """,
                    (
                        component_id,
                        current_time,
                        getattr(component, "version", None),
                        metadata_json,
                    ),
                )
            else:
                # Insert new component
                cursor.execute(
                    """
                    INSERT INTO components
                    (platform, name, type, origin, status, version, install_path,
                     first_seen, last_seen, metadata_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        getattr(component, "platform", "claude"),
                        component.name,
                        component.type,
                        component.origin,
                        component.status,
                        getattr(component, "version", None),
                        str(component.install_path),
                        current_time,
                        current_time,
                        metadata_json,
                    ),
                )

                component_id = cursor.lastrowid

                # Track installation event
                cursor.execute(
                    """
                    INSERT INTO installation_events
                    (component_id, event_type, timestamp, version, metadata_json)
                    VALUES (?, 'installed', ?, ?, ?)
                    """,
                    (
                        component_id,
                        current_time,
                        getattr(component, "version", None),
                        metadata_json,
                    ),
                )

            # Update FTS index
            description = metadata_dict.get("description", "")
            cursor.execute(
                """
                INSERT OR REPLACE INTO components_fts (rowid, name, description, keywords)
                VALUES (?, ?, ?, ?)
                """,
                (
                    component_id,
                    component.name,
                    description,
                    f"{getattr(component, 'platform', 'claude')} {component.type}",
                ),
            )

        self.conn.commit()

    def track_invocation(
        self,
        component_name: str,
        component_type: str,
        session_id: str,
        platform: str = "claude",
        duration_ms: Optional[int] = None,
        success: bool = True,
        error_message: Optional[str] = None,
    ):
        """Record a component invocation."""
        cursor = self.conn.cursor()

        # Get component ID
        cursor.execute(
            "SELECT id FROM components WHERE platform = ? AND name = ? AND type = ?",
            (platform, component_name, component_type),
        )
        row = cursor.fetchone()

        if not row:
            # Component not in database yet, skip tracking
            return

        component_id = row["id"]

        # Insert invocation record
        cursor.execute(
            """
            INSERT INTO invocations
            (component_id, session_id, timestamp, duration_ms, success, error_message)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                component_id,
                session_id,
                datetime.now(),
                duration_ms,
                success,
                error_message,
            ),
        )

        self.conn.commit()

    def get_usage_stats(self, days: int = 30) -> Dict[str, Any]:
        """Get usage statistics for dashboard."""
        cursor = self.conn.cursor()

        # Total invocations in time period
        cursor.execute(
            """
            SELECT COUNT(*) as count
            FROM invocations
            WHERE timestamp >= datetime('now', '-' || ? || ' days')
            """,
            (days,),
        )
        total_invocations = cursor.fetchone()["count"]

        # Most used components
        cursor.execute(
            """
            SELECT c.platform, c.name, c.type, COUNT(*) as invocation_count
            FROM invocations i
            JOIN components c ON i.component_id = c.id
            WHERE i.timestamp >= datetime('now', '-' || ? || ' days')
            GROUP BY c.id
            ORDER BY invocation_count DESC
            LIMIT 10
            """,
            (days,),
        )
        most_used = [
            {
                "platform": row["platform"],
                "name": row["name"],
                "type": row["type"],
                "count": row["invocation_count"],
            }
            for row in cursor.fetchall()
        ]

        # Recent installations
        cursor.execute(
            """
            SELECT c.platform, c.name, c.type, e.timestamp, e.version
            FROM installation_events e
            JOIN components c ON e.component_id = c.id
            WHERE e.event_type = 'installed'
            ORDER BY e.timestamp DESC
            LIMIT 10
            """,
        )
        recent_installs = [
            {
                "platform": row["platform"],
                "name": row["name"],
                "type": row["type"],
                "installed_at": row["timestamp"],
                "version": row["version"],
            }
            for row in cursor.fetchall()
        ]

        # Average performance by component
        cursor.execute(
            """
            SELECT c.platform, c.name, c.type, AVG(i.duration_ms) as avg_duration_ms
            FROM invocations i
            JOIN components c ON i.component_id = c.id
            WHERE i.duration_ms IS NOT NULL
            AND i.timestamp >= datetime('now', '-' || ? || ' days')
            GROUP BY c.id
            HAVING COUNT(*) >= 3
            ORDER BY avg_duration_ms DESC
            """,
            (days,),
        )
        performance_avg = {
            f"{row['platform']}:{row['type']}:{row['name']}": row["avg_duration_ms"]
            for row in cursor.fetchall()
        }

        return {
            "total_invocations": total_invocations,
            "most_used": most_used,
            "recent_installs": recent_installs,
            "performance_avg": performance_avg,
        }

    def search_components(self, query: str) -> List[Dict[str, Any]]:
        """Full-text search for components."""
        cursor = self.conn.cursor()

        cursor.execute(
            """
            SELECT c.*
            FROM components c
            JOIN components_fts fts ON c.id = fts.rowid
            WHERE components_fts MATCH ?
            ORDER BY rank
            """,
            (query,),
        )

        return [dict(row) for row in cursor.fetchall()]

    def get_components(
        self,
        platform: Optional[str] = None,
        type: Optional[str] = None,
        origin: Optional[str] = None,
        status: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Query components with filters."""
        cursor = self.conn.cursor()

        query = "SELECT * FROM components WHERE 1=1"
        params = []

        if platform:
            query += " AND platform = ?"
            params.append(platform)

        if type:
            query += " AND type = ?"
            params.append(type)

        if origin:
            query += " AND origin = ?"
            params.append(origin)

        if status:
            query += " AND status = ?"
            params.append(status)

        query += " ORDER BY name"

        cursor.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]

    def close(self):
        """Close database connection."""
        self.conn.close()
