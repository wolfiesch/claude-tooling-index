"""Unit tests for CodexMCPScanner."""

from pathlib import Path

from claude_tooling_index.scanners.codex_mcps import CodexMCPScanner, _redact_env_vars


class TestRedactEnvVars:
    """Tests for _redact_env_vars helper function."""

    def test_redacts_plain_values(self):
        env = {"API_KEY": "secret123", "TOKEN": "abc"}
        result = _redact_env_vars(env)
        assert result == {"API_KEY": "<redacted>", "TOKEN": "<redacted>"}

    def test_preserves_placeholders(self):
        env = {"API_KEY": "${API_KEY}", "OTHER": "${ENV_VAR}"}
        result = _redact_env_vars(env, keep_placeholders=True)
        assert result == {"API_KEY": "${API_KEY}", "OTHER": "${ENV_VAR}"}

    def test_redacts_placeholders_when_disabled(self):
        env = {"API_KEY": "${API_KEY}"}
        result = _redact_env_vars(env, keep_placeholders=False)
        assert result == {"API_KEY": "<redacted>"}

    def test_handles_none_values(self):
        env = {"EMPTY": None, "VALID": "value"}
        result = _redact_env_vars(env)
        assert result == {"EMPTY": "", "VALID": "<redacted>"}

    def test_handles_empty_dict(self):
        assert _redact_env_vars({}) == {}

    def test_handles_none_input(self):
        assert _redact_env_vars(None) == {}


class TestCodexMCPScanner:
    """Tests for CodexMCPScanner."""

    def test_scan_parses_valid_config(self, sample_config_toml: Path):
        scanner = CodexMCPScanner(config_toml_path=sample_config_toml)
        mcps = scanner.scan()

        assert len(mcps) == 2

        # Find test-server
        test_server = next(m for m in mcps if m.name == "test-server")
        assert test_server.command == "python3"
        assert test_server.args == ["-m", "test_mcp"]
        assert test_server.platform == "codex"
        assert test_server.status == "active"
        assert test_server.transport == "stdio"

        # Env vars should be redacted
        assert test_server.env_vars["API_KEY"] == "${API_KEY}"  # Placeholder preserved
        assert test_server.env_vars["DEBUG"] == "<redacted>"  # Plain value redacted

        # Find another-server
        another_server = next(m for m in mcps if m.name == "another-server")
        assert another_server.command == "npx"
        assert another_server.args == ["@modelcontextprotocol/server-test"]
        assert another_server.env_vars == {}

    def test_scan_returns_empty_for_missing_file(self, tmp_path: Path):
        scanner = CodexMCPScanner(config_toml_path=tmp_path / "nonexistent.toml")
        mcps = scanner.scan()
        assert mcps == []

    def test_scan_returns_empty_for_no_mcp_servers(self, tmp_path: Path):
        config_path = tmp_path / "config.toml"
        config_path.write_text("[some_other_section]\nkey = 'value'\n")

        scanner = CodexMCPScanner(config_toml_path=config_path)
        mcps = scanner.scan()
        assert mcps == []

    def test_scan_handles_empty_config(self, tmp_path: Path):
        config_path = tmp_path / "config.toml"
        config_path.write_text("")

        scanner = CodexMCPScanner(config_toml_path=config_path)
        mcps = scanner.scan()
        assert mcps == []

    def test_scan_skips_invalid_mcp_entries(self, tmp_path: Path):
        config_path = tmp_path / "config.toml"
        config_path.write_text("""
[mcp_servers]
invalid_entry = "not a table"

[mcp_servers.valid-server]
command = "python3"
""")

        scanner = CodexMCPScanner(config_toml_path=config_path)
        mcps = scanner.scan()

        # Should only have the valid server
        assert len(mcps) == 1
        assert mcps[0].name == "valid-server"

    def test_scan_handles_non_list_args(self, tmp_path: Path):
        config_path = tmp_path / "config.toml"
        config_path.write_text("""
[mcp_servers.test]
command = "echo"
args = "single-arg"
""")

        scanner = CodexMCPScanner(config_toml_path=config_path)
        mcps = scanner.scan()

        assert len(mcps) == 1
        assert mcps[0].args == ["single-arg"]

    def test_scan_without_redaction(self, tmp_path: Path):
        config_path = tmp_path / "config.toml"
        config_path.write_text("""
[mcp_servers.test]
command = "cmd"
env = { SECRET = "my-secret" }
""")

        scanner = CodexMCPScanner(config_toml_path=config_path, redact_env=False)
        mcps = scanner.scan()

        assert mcps[0].env_vars["SECRET"] == "my-secret"

    def test_scan_sets_correct_metadata(self, sample_config_toml: Path):
        scanner = CodexMCPScanner(
            config_toml_path=sample_config_toml,
            platform="codex",
            origin="custom-origin"
        )
        mcps = scanner.scan()

        for mcp in mcps:
            assert mcp.platform == "codex"
            assert mcp.origin == "custom-origin"
            assert mcp.install_path == sample_config_toml
            assert mcp.last_modified is not None
