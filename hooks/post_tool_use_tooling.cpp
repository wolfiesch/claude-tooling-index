/**
 * post_tool_use_tooling.cpp
 *
 * High-performance C++ hook for tracking skill and command invocations
 * in the Claude Code Tooling Index database.
 *
 * Performance target: <1ms execution time (vs ~50ms for Python equivalent)
 *
 * Build: See CMakeLists.txt or build_hook.sh
 * Install: Copy binary to ~/.claude/hooks/post_tool_use_tooling
 *
 * Dependencies:
 *   - SQLite3 (libsqlite3-dev on Ubuntu, sqlite on macOS)
 *   - C++17 compiler (g++, clang++)
 */

#include <string>
#include <cstdlib>
#include <cstring>

// SQLite3
#include <sqlite3.h>

// POSIX for file existence check
#include <sys/stat.h>
#include <unistd.h>

// Minimal JSON parser for our specific use case
namespace json_mini {
    std::string get_string(const std::string& json, const std::string& key) {
        std::string search = "\"" + key + "\"";
        size_t pos = json.find(search);
        if (pos == std::string::npos) return "";

        // Find the colon after the key
        pos = json.find(':', pos);
        if (pos == std::string::npos) return "";

        // Skip whitespace
        pos++;
        while (pos < json.size() && (json[pos] == ' ' || json[pos] == '\t')) pos++;

        // Check if value is a string (starts with quote)
        if (pos >= json.size() || json[pos] != '"') return "";

        // Find the closing quote
        size_t start = pos + 1;
        size_t end = json.find('"', start);
        if (end == std::string::npos) return "";

        return json.substr(start, end - start);
    }

    int get_int(const std::string& json, const std::string& key, int default_val = 0) {
        std::string search = "\"" + key + "\"";
        size_t pos = json.find(search);
        if (pos == std::string::npos) return default_val;

        pos = json.find(':', pos);
        if (pos == std::string::npos) return default_val;

        pos++;
        while (pos < json.size() && (json[pos] == ' ' || json[pos] == '\t')) pos++;

        // Parse integer
        std::string num;
        while (pos < json.size() && (json[pos] >= '0' && json[pos] <= '9')) {
            num += json[pos++];
        }

        if (num.empty()) return default_val;
        return std::stoi(num);
    }

    bool get_bool(const std::string& json, const std::string& key, bool default_val = true) {
        std::string search = "\"" + key + "\"";
        size_t pos = json.find(search);
        if (pos == std::string::npos) return default_val;

        pos = json.find(':', pos);
        if (pos == std::string::npos) return default_val;

        pos++;
        while (pos < json.size() && (json[pos] == ' ' || json[pos] == '\t')) pos++;

        if (json.substr(pos, 4) == "true") return true;
        if (json.substr(pos, 5) == "false") return false;
        return default_val;
    }
}

// Check if file exists using POSIX
bool file_exists(const std::string& path) {
    struct stat buffer;
    return (stat(path.c_str(), &buffer) == 0);
}

// Get home directory
std::string get_home() {
    const char* home = std::getenv("HOME");
    return home ? std::string(home) : "";
}

// Get database path
std::string get_db_path() {
    std::string home = get_home();
    if (home.empty()) return "";
    return home + "/.claude/data/tooling_index.db";
}

class ToolingIndexTracker {
private:
    std::string db_path;

public:
    ToolingIndexTracker() : db_path(get_db_path()) {}

    bool database_exists() {
        return !db_path.empty() && file_exists(db_path);
    }

    void track_invocation(const std::string& component_name,
                         const std::string& component_type,
                         const std::string& session_id,
                         int duration_ms,
                         bool success) {
        // Check if database exists
        if (!database_exists()) {
            // Silently skip if tooling-index not installed
            return;
        }

        sqlite3* db;
        if (sqlite3_open(db_path.c_str(), &db) != SQLITE_OK) {
            // Silent failure - don't break hooks
            sqlite3_close(db);
            return;
        }

        // Get component_id from components table
        const char* get_id_sql =
            "SELECT id FROM components WHERE name = ? AND type = ? LIMIT 1";
        sqlite3_stmt* stmt;

        if (sqlite3_prepare_v2(db, get_id_sql, -1, &stmt, nullptr) != SQLITE_OK) {
            sqlite3_close(db);
            return;
        }

        sqlite3_bind_text(stmt, 1, component_name.c_str(), -1, SQLITE_STATIC);
        sqlite3_bind_text(stmt, 2, component_type.c_str(), -1, SQLITE_STATIC);

        int component_id = -1;
        if (sqlite3_step(stmt) == SQLITE_ROW) {
            component_id = sqlite3_column_int(stmt, 0);
        }
        sqlite3_finalize(stmt);

        // If component not found in database, skip (not yet indexed)
        if (component_id == -1) {
            sqlite3_close(db);
            return;
        }

        // Insert invocation record
        const char* insert_sql =
            "INSERT INTO invocations (component_id, session_id, timestamp, duration_ms, success) "
            "VALUES (?, ?, datetime('now'), ?, ?)";

        if (sqlite3_prepare_v2(db, insert_sql, -1, &stmt, nullptr) == SQLITE_OK) {
            sqlite3_bind_int(stmt, 1, component_id);
            sqlite3_bind_text(stmt, 2, session_id.c_str(), -1, SQLITE_STATIC);
            sqlite3_bind_int(stmt, 3, duration_ms);
            sqlite3_bind_int(stmt, 4, success ? 1 : 0);

            sqlite3_step(stmt);
            sqlite3_finalize(stmt);
        }

        sqlite3_close(db);
    }
};

std::string trim(const std::string& str) {
    size_t first = str.find_first_not_of(" \t\n\r");
    if (first == std::string::npos) return "";
    size_t last = str.find_last_not_of(" \t\n\r");
    return str.substr(first, last - first + 1);
}

int main(int argc, char* argv[]) {
    // Parse environment variables
    const char* tool_data_str = std::getenv("TOOL_DATA");
    if (!tool_data_str) {
        return 0;  // No tool data, exit silently
    }

    std::string tool_data(tool_data_str);

    // Parse tool name from JSON
    std::string tool_name = json_mini::get_string(tool_data, "name");

    if (tool_name.empty()) {
        return 0;
    }

    // Detect component type and extract name
    std::string component_type;
    std::string component_name;

    // Check for Skill invocation: "Skill: <name>" or "Skill:<name>"
    if (tool_name.rfind("Skill:", 0) == 0 || tool_name.rfind("Skill :", 0) == 0) {
        component_type = "skill";
        size_t colon_pos = tool_name.find(':');
        if (colon_pos != std::string::npos) {
            component_name = trim(tool_name.substr(colon_pos + 1));
        }
    }
    // Check for Command invocation: "/<name>"
    else if (!tool_name.empty() && tool_name[0] == '/') {
        component_type = "command";
        component_name = trim(tool_name.substr(1));
    }
    else {
        // Not a tracked component type
        return 0;
    }

    if (component_name.empty()) {
        return 0;
    }

    // Get session ID
    const char* session_id_str = std::getenv("SESSION_ID");
    std::string session_id = session_id_str ? session_id_str : "unknown";

    // Get duration and success from JSON
    int duration_ms = json_mini::get_int(tool_data, "duration_ms", 0);
    bool success = json_mini::get_bool(tool_data, "success", true);

    // Track invocation
    ToolingIndexTracker tracker;
    tracker.track_invocation(component_name, component_type, session_id, duration_ms, success);

    return 0;
}
