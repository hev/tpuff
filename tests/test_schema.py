"""Tests for schema commands."""

import json
from io import StringIO
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner
from rich.console import Console

from tpuff.commands.schema import (
    SchemaDiff,
    compute_schema_diff,
    display_schema_diff,
    load_schema_file,
    normalize_schema_type,
    schema,
    schema_type_for_display,
    validate_schema,
    validate_schema_type,
)


class TestNormalizeSchemaType:
    """Tests for normalize_schema_type function."""

    def test_simple_string_type(self):
        assert normalize_schema_type("string") == "string"
        assert normalize_schema_type("uint64") == "uint64"

    def test_dict_type(self):
        result = normalize_schema_type({"type": "string", "full_text_search": True})
        # Should be JSON with sorted keys
        assert result == '{"full_text_search": true, "type": "string"}'

    def test_pydantic_model(self):
        mock_model = MagicMock()
        mock_model.model_dump.return_value = {"type": "string", "filterable": False}
        result = normalize_schema_type(mock_model)
        assert result == '{"filterable": false, "type": "string"}'


class TestSchemaTypeForDisplay:
    """Tests for schema_type_for_display function."""

    def test_simple_string(self):
        assert schema_type_for_display("string") == "string"
        assert schema_type_for_display("[1536]f32") == "[1536]f32"

    def test_simple_dict_with_only_type(self):
        result = schema_type_for_display({"type": "string"})
        assert result == "string"

    def test_complex_dict(self):
        result = schema_type_for_display({"type": "string", "full_text_search": True})
        assert "string" in result
        assert "full_text_search" in result


class TestValidateSchemaType:
    """Tests for validate_schema_type function."""

    def test_valid_simple_types(self):
        for type_name in ["string", "uint64", "uuid", "bool"]:
            errors = validate_schema_type("test_attr", type_name)
            assert errors == [], f"Expected no errors for {type_name}"

    def test_valid_vector_types(self):
        errors = validate_schema_type("vec", "[1536]f32")
        assert errors == []
        errors = validate_schema_type("vec", "[768]f16")
        assert errors == []

    def test_invalid_simple_type(self):
        errors = validate_schema_type("test_attr", "invalid_type")
        assert len(errors) == 1
        assert "invalid type" in errors[0].lower()

    def test_valid_complex_type(self):
        errors = validate_schema_type("content", {"type": "string", "full_text_search": True})
        assert errors == []

    def test_complex_type_missing_type_key(self):
        errors = validate_schema_type("content", {"full_text_search": True})
        assert len(errors) == 1
        assert "'type' key" in errors[0]

    def test_complex_type_unknown_keys(self):
        errors = validate_schema_type("content", {"type": "string", "unknown_key": True})
        assert len(errors) == 1
        assert "unknown keys" in errors[0].lower()


class TestValidateSchema:
    """Tests for validate_schema function."""

    def test_valid_schema(self):
        schema = {
            "content": "string",
            "vector": "[1536]f32",
            "timestamp": "uint64",
        }
        errors = validate_schema(schema)
        assert errors == []

    def test_invalid_attribute_type(self):
        schema = {"content": "invalid"}
        errors = validate_schema(schema)
        assert len(errors) == 1

    def test_empty_attribute_name(self):
        schema = {"": "string"}
        errors = validate_schema(schema)
        assert len(errors) == 1
        assert "empty" in errors[0].lower()


class TestComputeSchemaDiff:
    """Tests for compute_schema_diff function."""

    def test_all_new_attributes(self):
        diff = compute_schema_diff(None, {"field1": "string", "field2": "uint64"})
        assert len(diff.additions) == 2
        assert len(diff.unchanged) == 0
        assert len(diff.conflicts) == 0

    def test_all_unchanged(self):
        current = {"field1": "string", "field2": "uint64"}
        new = {"field1": "string", "field2": "uint64"}
        diff = compute_schema_diff(current, new)
        assert len(diff.additions) == 0
        assert len(diff.unchanged) == 2
        assert len(diff.conflicts) == 0

    def test_mixed_changes(self):
        current = {"field1": "string"}
        new = {"field1": "string", "field2": "uint64"}
        diff = compute_schema_diff(current, new)
        assert len(diff.additions) == 1
        assert "field2" in diff.additions
        assert len(diff.unchanged) == 1
        assert "field1" in diff.unchanged

    def test_type_conflict(self):
        current = {"field1": "string"}
        new = {"field1": "uint64"}
        diff = compute_schema_diff(current, new)
        assert len(diff.conflicts) == 1
        assert "field1" in diff.conflicts
        assert diff.has_conflicts

    def test_has_changes_property(self):
        # No changes
        diff = SchemaDiff(unchanged={"a": "string"})
        assert not diff.has_changes

        # With additions
        diff = SchemaDiff(additions={"a": "string"})
        assert diff.has_changes

        # With conflicts
        diff = SchemaDiff(conflicts={"a": ("string", "uint64")})
        assert diff.has_changes


class TestDisplaySchemaDiff:
    """Tests for display_schema_diff function."""

    def test_no_schema(self):
        diff = SchemaDiff()
        console = Console(file=StringIO(), force_terminal=True)
        with patch("tpuff.commands.schema.console", console):
            display_schema_diff(diff, "test-ns")
        output = console.file.getvalue()
        assert "No schema attributes" in output

    def test_displays_additions_in_green(self):
        diff = SchemaDiff(additions={"new_field": "string"})
        console = Console(file=StringIO(), force_terminal=True)
        with patch("tpuff.commands.schema.console", console):
            display_schema_diff(diff, "test-ns")
        output = console.file.getvalue()
        assert "new_field" in output
        # Rich adds ANSI codes around (new), so check for "new" instead
        assert "new" in output

    def test_displays_conflicts_in_red(self):
        diff = SchemaDiff(conflicts={"conflict_field": ("string", "uint64")})
        console = Console(file=StringIO(), force_terminal=True)
        with patch("tpuff.commands.schema.console", console):
            display_schema_diff(diff, "test-ns")
        output = console.file.getvalue()
        assert "conflict_field" in output
        assert "type change not allowed" in output


class TestLoadSchemaFile:
    """Tests for load_schema_file function."""

    def test_file_not_found(self, tmp_path):
        from click import ClickException

        with pytest.raises(ClickException) as exc_info:
            load_schema_file(str(tmp_path / "nonexistent.json"))
        assert "not found" in str(exc_info.value)

    def test_invalid_json(self, tmp_path):
        from click import ClickException

        schema_file = tmp_path / "invalid.json"
        schema_file.write_text("{ not valid json }")
        with pytest.raises(ClickException) as exc_info:
            load_schema_file(str(schema_file))
        assert "Invalid JSON" in str(exc_info.value)

    def test_not_an_object(self, tmp_path):
        from click import ClickException

        schema_file = tmp_path / "array.json"
        schema_file.write_text('["a", "b"]')
        with pytest.raises(ClickException) as exc_info:
            load_schema_file(str(schema_file))
        assert "JSON object" in str(exc_info.value)

    def test_valid_schema_file(self, tmp_path):
        schema_file = tmp_path / "schema.json"
        schema_file.write_text('{"content": "string", "timestamp": "uint64"}')
        result = load_schema_file(str(schema_file))
        assert result == {"content": "string", "timestamp": "uint64"}


class TestSchemaApplyCommand:
    """Tests for schema apply CLI command."""

    @pytest.fixture
    def runner(self):
        return CliRunner()

    @pytest.fixture
    def valid_schema_file(self, tmp_path):
        schema_file = tmp_path / "schema.json"
        schema_file.write_text('{"content": "string", "new_field": "uint64"}')
        return str(schema_file)

    def test_dry_run_new_namespace(self, runner, valid_schema_file):
        """Test dry-run on a namespace that doesn't exist (all additions)."""
        mock_ns = MagicMock()
        mock_ns.metadata.side_effect = Exception("Namespace not found")

        with patch("tpuff.commands.schema.get_namespace", return_value=mock_ns):
            result = runner.invoke(
                schema, ["apply", "-n", "test-ns", "-f", valid_schema_file, "--dry-run"]
            )

        assert result.exit_code == 0
        assert "test-ns" in result.output
        assert "content" in result.output
        assert "new_field" in result.output
        assert "(new)" in result.output
        assert "Dry run mode" in result.output

    def test_dry_run_existing_namespace(self, runner, valid_schema_file):
        """Test dry-run on an existing namespace (mixed changes)."""
        mock_metadata = MagicMock()
        mock_metadata.schema = {"content": "string"}  # existing field
        mock_ns = MagicMock()
        mock_ns.metadata.return_value = mock_metadata

        with patch("tpuff.commands.schema.get_namespace", return_value=mock_ns):
            result = runner.invoke(
                schema, ["apply", "-n", "test-ns", "-f", valid_schema_file, "--dry-run"]
            )

        assert result.exit_code == 0
        # content should be unchanged, new_field should be new
        assert "content" in result.output
        assert "new_field" in result.output
        assert "(new)" in result.output
        assert "Dry run mode" in result.output

    def test_dry_run_no_changes(self, runner, tmp_path):
        """Test dry-run when schema is already up to date."""
        schema_file = tmp_path / "schema.json"
        schema_file.write_text('{"content": "string"}')

        mock_metadata = MagicMock()
        mock_metadata.schema = {"content": "string"}
        mock_ns = MagicMock()
        mock_ns.metadata.return_value = mock_metadata

        with patch("tpuff.commands.schema.get_namespace", return_value=mock_ns):
            result = runner.invoke(
                schema, ["apply", "-n", "test-ns", "-f", str(schema_file), "--dry-run"]
            )

        assert result.exit_code == 0
        assert "already up to date" in result.output

    def test_type_conflict_exits_with_error(self, runner, tmp_path):
        """Test that type conflicts cause the command to exit with error."""
        schema_file = tmp_path / "schema.json"
        schema_file.write_text('{"content": "uint64"}')  # trying to change string to uint64

        mock_metadata = MagicMock()
        mock_metadata.schema = {"content": "string"}  # existing type is string
        mock_ns = MagicMock()
        mock_ns.metadata.return_value = mock_metadata

        with patch("tpuff.commands.schema.get_namespace", return_value=mock_ns):
            result = runner.invoke(
                schema, ["apply", "-n", "test-ns", "-f", str(schema_file), "--dry-run"]
            )

        assert result.exit_code == 1
        assert "type change not allowed" in result.output.lower()
        assert "conflict" in result.output.lower()

    def test_invalid_schema_file_exits_with_error(self, runner, tmp_path):
        """Test that invalid schema files cause proper error messages."""
        schema_file = tmp_path / "schema.json"
        schema_file.write_text('{"content": "invalid_type"}')

        result = runner.invoke(
            schema, ["apply", "-n", "test-ns", "-f", str(schema_file), "--dry-run"]
        )

        assert result.exit_code != 0
        assert "invalid" in result.output.lower()

    def test_apply_with_yes_flag(self, runner, valid_schema_file):
        """Test that --yes flag skips confirmation prompt."""
        mock_metadata = MagicMock()
        mock_metadata.schema = {}
        mock_ns = MagicMock()
        mock_ns.metadata.return_value = mock_metadata

        with patch("tpuff.commands.schema.get_namespace", return_value=mock_ns):
            result = runner.invoke(
                schema, ["apply", "-n", "test-ns", "-f", valid_schema_file, "--yes"]
            )

        assert result.exit_code == 0
        assert "Successfully applied" in result.output
        mock_ns.write.assert_called_once()

    def test_apply_without_yes_aborts_on_no(self, runner, valid_schema_file):
        """Test that confirmation prompt works (user says no)."""
        mock_metadata = MagicMock()
        mock_metadata.schema = {}
        mock_ns = MagicMock()
        mock_ns.metadata.return_value = mock_metadata

        with patch("tpuff.commands.schema.get_namespace", return_value=mock_ns):
            result = runner.invoke(
                schema, ["apply", "-n", "test-ns", "-f", valid_schema_file], input="n\n"
            )

        assert result.exit_code == 0
        assert "Aborted" in result.output
        mock_ns.write.assert_not_called()


class TestSchemaCopyCommand:
    """Tests for schema copy CLI command."""

    @pytest.fixture
    def runner(self):
        return CliRunner()

    def test_copy_source_not_found(self, runner):
        """Test error when source namespace doesn't exist."""
        mock_ns = MagicMock()
        mock_ns.metadata.side_effect = Exception("Namespace not found")

        with patch("tpuff.commands.schema.get_namespace", return_value=mock_ns):
            result = runner.invoke(
                schema, ["copy", "-n", "source-ns", "--to", "target-ns"]
            )

        assert result.exit_code == 1
        assert "no schema or does not exist" in result.output.lower()

    def test_copy_target_has_data(self, runner):
        """Test error when target namespace already has data."""
        # Source namespace has schema
        source_metadata = MagicMock()
        source_metadata.schema = {"content": "string"}

        # Target namespace has data
        target_metadata = MagicMock()
        target_metadata.schema = {"content": "string"}
        target_metadata.approx_count = 100

        def get_ns(name, region=None):
            mock = MagicMock()
            if name == "source-ns":
                mock.metadata.return_value = source_metadata
            else:
                mock.metadata.return_value = target_metadata
            return mock

        with patch("tpuff.commands.schema.get_namespace", side_effect=get_ns):
            result = runner.invoke(
                schema, ["copy", "-n", "source-ns", "--to", "target-ns"]
            )

        assert result.exit_code == 1
        assert "already has" in result.output.lower()
        assert "100" in result.output

    def test_copy_success_with_yes(self, runner):
        """Test successful copy with --yes flag."""
        source_metadata = MagicMock()
        source_metadata.schema = {"content": "string", "timestamp": "uint64"}

        # Target namespace doesn't exist (metadata raises exception)
        target_mock = MagicMock()
        target_mock.metadata.side_effect = Exception("Namespace not found")

        def get_ns(name, region=None):
            if name == "source-ns":
                mock = MagicMock()
                mock.metadata.return_value = source_metadata
                return mock
            else:
                return target_mock

        with patch("tpuff.commands.schema.get_namespace", side_effect=get_ns):
            result = runner.invoke(
                schema, ["copy", "-n", "source-ns", "--to", "target-ns", "--yes"]
            )

        assert result.exit_code == 0
        assert "Successfully created" in result.output
        target_mock.write.assert_called_once()
        call_kwargs = target_mock.write.call_args[1]
        assert call_kwargs["schema"] == {"content": "string", "timestamp": "uint64"}
        assert call_kwargs["upsert_rows"] == [{"id": "__schema_placeholder__"}]

    def test_copy_aborts_on_no(self, runner):
        """Test that copy aborts when user says no."""
        source_metadata = MagicMock()
        source_metadata.schema = {"content": "string"}

        # Target namespace doesn't exist
        target_mock = MagicMock()
        target_mock.metadata.side_effect = Exception("Namespace not found")

        def get_ns(name, region=None):
            if name == "source-ns":
                mock = MagicMock()
                mock.metadata.return_value = source_metadata
                return mock
            else:
                return target_mock

        with patch("tpuff.commands.schema.get_namespace", side_effect=get_ns):
            result = runner.invoke(
                schema, ["copy", "-n", "source-ns", "--to", "target-ns"], input="n\n"
            )

        assert result.exit_code == 0
        assert "Aborted" in result.output
        target_mock.write.assert_not_called()

    def test_copy_displays_schema(self, runner):
        """Test that copy displays the schema being copied."""
        source_metadata = MagicMock()
        source_metadata.schema = {"content": "string", "vector": "[1536]f32"}

        # Target namespace doesn't exist
        target_mock = MagicMock()
        target_mock.metadata.side_effect = Exception("Namespace not found")

        def get_ns(name, region=None):
            if name == "source-ns":
                mock = MagicMock()
                mock.metadata.return_value = source_metadata
                return mock
            else:
                return target_mock

        with patch("tpuff.commands.schema.get_namespace", side_effect=get_ns):
            result = runner.invoke(
                schema, ["copy", "-n", "source-ns", "--to", "target-ns"], input="n\n"
            )

        assert "source-ns" in result.output
        assert "target-ns" in result.output
        assert "content" in result.output
        assert "vector" in result.output
        assert "placeholder row" in result.output.lower()

    def test_copy_target_does_not_exist(self, runner):
        """Test copy when target namespace doesn't exist (metadata fails)."""
        source_metadata = MagicMock()
        source_metadata.schema = {"content": "string"}

        target_mock = MagicMock()
        target_mock.metadata.side_effect = Exception("Namespace not found")

        def get_ns(name, region=None):
            if name == "source-ns":
                mock = MagicMock()
                mock.metadata.return_value = source_metadata
                return mock
            else:
                return target_mock

        with patch("tpuff.commands.schema.get_namespace", side_effect=get_ns):
            result = runner.invoke(
                schema, ["copy", "-n", "source-ns", "--to", "target-ns", "--yes"]
            )

        assert result.exit_code == 0
        assert "Successfully created" in result.output
        target_mock.write.assert_called_once()


class TestSchemaApplyBatchCommand:
    """Tests for schema apply CLI command with --prefix option."""

    @pytest.fixture
    def runner(self):
        return CliRunner()

    @pytest.fixture
    def valid_schema_file(self, tmp_path):
        """Create a valid schema file for testing."""
        schema_file = tmp_path / "schema.json"
        schema_file.write_text('{"content": "string", "category": "string"}')
        return str(schema_file)

    def test_prefix_requires_no_namespace(self, runner, valid_schema_file):
        """Test that --prefix and --namespace cannot be used together."""
        result = runner.invoke(
            schema,
            ["apply", "-n", "test-ns", "--prefix", "prod", "-f", valid_schema_file],
        )

        assert result.exit_code == 1
        assert "Cannot use more than one" in result.output

    def test_requires_namespace_or_prefix_or_all(self, runner, valid_schema_file):
        """Test that --namespace, --prefix, or --all is required."""
        result = runner.invoke(
            schema, ["apply", "-f", valid_schema_file]
        )

        assert result.exit_code == 1
        assert "Must specify one of" in result.output

    def test_prefix_no_matching_namespaces(self, runner, valid_schema_file):
        """Test that prefix with no matches shows appropriate message."""
        mock_client = MagicMock()
        mock_client.namespaces.return_value = []

        with patch("tpuff.commands.schema.get_turbopuffer_client", return_value=mock_client):
            result = runner.invoke(
                schema, ["apply", "--prefix", "nonexistent", "-f", valid_schema_file]
            )

        assert result.exit_code == 0
        assert "No namespaces found matching prefix" in result.output

    def test_prefix_dry_run_multiple_namespaces(self, runner, valid_schema_file):
        """Test dry run with prefix showing summary of multiple namespaces."""
        # Mock namespaces
        mock_ns1 = MagicMock()
        mock_ns1.id = "prod-users"
        mock_ns2 = MagicMock()
        mock_ns2.id = "prod-orders"
        mock_ns3 = MagicMock()
        mock_ns3.id = "test-ns"  # Won't match prefix

        mock_client = MagicMock()
        mock_client.namespaces.return_value = [mock_ns1, mock_ns2, mock_ns3]

        # Mock metadata for each namespace
        def mock_get_ns(name, region=None):
            mock = MagicMock()
            mock_metadata = MagicMock()
            mock_metadata.schema = {"content": "string"}  # Existing schema
            mock.metadata.return_value = mock_metadata
            return mock

        with patch("tpuff.commands.schema.get_turbopuffer_client", return_value=mock_client):
            with patch("tpuff.commands.schema.get_namespace", side_effect=mock_get_ns):
                result = runner.invoke(
                    schema, ["apply", "--prefix", "prod", "-f", valid_schema_file, "--dry-run"]
                )

        assert result.exit_code == 0
        assert "Found 2 namespace(s)" in result.output
        assert "prod-users" in result.output
        assert "prod-orders" in result.output
        assert "test-ns" not in result.output
        assert "Dry run mode" in result.output

    def test_prefix_apply_with_yes(self, runner, valid_schema_file):
        """Test batch apply with --yes flag."""
        mock_ns1 = MagicMock()
        mock_ns1.id = "prod-users"
        mock_ns2 = MagicMock()
        mock_ns2.id = "prod-orders"

        mock_client = MagicMock()
        mock_client.namespaces.return_value = [mock_ns1, mock_ns2]

        namespace_mocks = {}

        def mock_get_ns(name, region=None):
            if name not in namespace_mocks:
                mock = MagicMock()
                mock_metadata = MagicMock()
                mock_metadata.schema = {}  # Empty schema (new namespaces)
                mock.metadata.return_value = mock_metadata
                namespace_mocks[name] = mock
            return namespace_mocks[name]

        with patch("tpuff.commands.schema.get_turbopuffer_client", return_value=mock_client):
            with patch("tpuff.commands.schema.get_namespace", side_effect=mock_get_ns):
                result = runner.invoke(
                    schema, ["apply", "--prefix", "prod", "-f", valid_schema_file, "--yes"]
                )

        assert result.exit_code == 0
        assert "Successfully applied schema to 2 namespace(s)" in result.output
        # Verify both namespaces had write called
        for mock in namespace_mocks.values():
            mock.write.assert_called_once()

    def test_prefix_conflicts_block_all(self, runner, tmp_path):
        """Test that conflicts in any namespace prevent all applies."""
        schema_file = tmp_path / "schema.json"
        schema_file.write_text('{"content": "uint64"}')  # Change type

        mock_ns1 = MagicMock()
        mock_ns1.id = "prod-users"

        mock_client = MagicMock()
        mock_client.namespaces.return_value = [mock_ns1]

        def mock_get_ns(name, region=None):
            mock = MagicMock()
            mock_metadata = MagicMock()
            mock_metadata.schema = {"content": "string"}  # Existing type differs
            mock.metadata.return_value = mock_metadata
            return mock

        with patch("tpuff.commands.schema.get_turbopuffer_client", return_value=mock_client):
            with patch("tpuff.commands.schema.get_namespace", side_effect=mock_get_ns):
                result = runner.invoke(
                    schema, ["apply", "--prefix", "prod", "-f", str(schema_file), "--yes"]
                )

        assert result.exit_code == 1
        assert "type conflict" in result.output.lower()

    def test_prefix_some_namespaces_up_to_date(self, runner, valid_schema_file):
        """Test batch apply where some namespaces are already up to date."""
        mock_ns1 = MagicMock()
        mock_ns1.id = "prod-users"
        mock_ns2 = MagicMock()
        mock_ns2.id = "prod-orders"

        mock_client = MagicMock()
        mock_client.namespaces.return_value = [mock_ns1, mock_ns2]

        namespace_mocks = {}

        def mock_get_ns(name, region=None):
            if name not in namespace_mocks:
                mock = MagicMock()
                mock_metadata = MagicMock()
                # prod-users already has the schema
                if name == "prod-users":
                    mock_metadata.schema = {"content": "string", "category": "string"}
                else:
                    mock_metadata.schema = {}  # prod-orders needs update
                mock.metadata.return_value = mock_metadata
                namespace_mocks[name] = mock
            return namespace_mocks[name]

        with patch("tpuff.commands.schema.get_turbopuffer_client", return_value=mock_client):
            with patch("tpuff.commands.schema.get_namespace", side_effect=mock_get_ns):
                result = runner.invoke(
                    schema, ["apply", "--prefix", "prod", "-f", valid_schema_file, "--yes"]
                )

        assert result.exit_code == 0
        # Only prod-orders should have write called (1 namespace updated)
        assert "Successfully applied schema to 1 namespace(s)" in result.output
        namespace_mocks["prod-orders"].write.assert_called_once()
        namespace_mocks["prod-users"].write.assert_not_called()


class TestSchemaApplyAllCommand:
    """Tests for schema apply CLI command with --all option."""

    @pytest.fixture
    def runner(self):
        return CliRunner()

    @pytest.fixture
    def valid_schema_file(self, tmp_path):
        """Create a valid schema file for testing."""
        schema_file = tmp_path / "schema.json"
        schema_file.write_text('{"content": "string", "category": "string"}')
        return str(schema_file)

    def test_all_cannot_be_used_with_namespace(self, runner, valid_schema_file):
        """Test that --all and --namespace cannot be used together."""
        result = runner.invoke(
            schema,
            ["apply", "-n", "test-ns", "--all", "-f", valid_schema_file],
        )

        assert result.exit_code == 1
        assert "Cannot use more than one" in result.output

    def test_all_cannot_be_used_with_prefix(self, runner, valid_schema_file):
        """Test that --all and --prefix cannot be used together."""
        result = runner.invoke(
            schema,
            ["apply", "--prefix", "prod", "--all", "-f", valid_schema_file],
        )

        assert result.exit_code == 1
        assert "Cannot use more than one" in result.output

    def test_all_no_namespaces(self, runner, valid_schema_file):
        """Test that --all with no namespaces shows appropriate message."""
        mock_client = MagicMock()
        mock_client.namespaces.return_value = []

        with patch("tpuff.commands.schema.get_turbopuffer_client", return_value=mock_client):
            result = runner.invoke(
                schema, ["apply", "--all", "-f", valid_schema_file]
            )

        assert result.exit_code == 0
        assert "No namespaces found" in result.output

    def test_all_dry_run_multiple_namespaces(self, runner, valid_schema_file):
        """Test dry run with --all showing summary of all namespaces."""
        # Mock namespaces
        mock_ns1 = MagicMock()
        mock_ns1.id = "prod-users"
        mock_ns2 = MagicMock()
        mock_ns2.id = "test-ns"
        mock_ns3 = MagicMock()
        mock_ns3.id = "dev-orders"

        mock_client = MagicMock()
        mock_client.namespaces.return_value = [mock_ns1, mock_ns2, mock_ns3]

        # Mock metadata for each namespace
        def mock_get_ns(name, region=None):
            mock = MagicMock()
            mock_metadata = MagicMock()
            mock_metadata.schema = {"content": "string"}  # Existing schema
            mock.metadata.return_value = mock_metadata
            return mock

        with patch("tpuff.commands.schema.get_turbopuffer_client", return_value=mock_client):
            with patch("tpuff.commands.schema.get_namespace", side_effect=mock_get_ns):
                result = runner.invoke(
                    schema, ["apply", "--all", "-f", valid_schema_file, "--dry-run"]
                )

        assert result.exit_code == 0
        assert "Found 3 namespace(s)" in result.output
        assert "prod-users" in result.output
        assert "test-ns" in result.output
        assert "dev-orders" in result.output
        assert "Dry run mode" in result.output

    def test_all_apply_with_yes(self, runner, valid_schema_file):
        """Test batch apply with --all and --yes flag."""
        mock_ns1 = MagicMock()
        mock_ns1.id = "prod-users"
        mock_ns2 = MagicMock()
        mock_ns2.id = "test-ns"

        mock_client = MagicMock()
        mock_client.namespaces.return_value = [mock_ns1, mock_ns2]

        namespace_mocks = {}

        def mock_get_ns(name, region=None):
            if name not in namespace_mocks:
                mock = MagicMock()
                mock_metadata = MagicMock()
                mock_metadata.schema = {}  # Empty schema (new namespaces)
                mock.metadata.return_value = mock_metadata
                namespace_mocks[name] = mock
            return namespace_mocks[name]

        with patch("tpuff.commands.schema.get_turbopuffer_client", return_value=mock_client):
            with patch("tpuff.commands.schema.get_namespace", side_effect=mock_get_ns):
                result = runner.invoke(
                    schema, ["apply", "--all", "-f", valid_schema_file, "--yes"]
                )

        assert result.exit_code == 0
        assert "Successfully applied schema to 2 namespace(s)" in result.output
        namespace_mocks["prod-users"].write.assert_called_once()
        namespace_mocks["test-ns"].write.assert_called_once()


class TestSchemaApplyContinueOnError:
    """Tests for schema apply CLI command with --continue-on-error option."""

    @pytest.fixture
    def runner(self):
        return CliRunner()

    def test_conflicts_without_continue_on_error_exits(self, runner, tmp_path):
        """Test that conflicts cause exit without --continue-on-error."""
        schema_file = tmp_path / "schema.json"
        schema_file.write_text('{"content": "uint64"}')  # Type change

        mock_ns1 = MagicMock()
        mock_ns1.id = "prod-users"

        mock_client = MagicMock()
        mock_client.namespaces.return_value = [mock_ns1]

        def mock_get_ns(name, region=None):
            mock = MagicMock()
            mock_metadata = MagicMock()
            mock_metadata.schema = {"content": "string"}  # Existing type differs
            mock.metadata.return_value = mock_metadata
            return mock

        with patch("tpuff.commands.schema.get_turbopuffer_client", return_value=mock_client):
            with patch("tpuff.commands.schema.get_namespace", side_effect=mock_get_ns):
                result = runner.invoke(
                    schema, ["apply", "--prefix", "prod", "-f", str(schema_file), "--yes"]
                )

        assert result.exit_code == 1
        assert "type conflict" in result.output.lower()
        assert "continue-on-error" in result.output.lower()

    def test_conflicts_with_continue_on_error_skips_conflicted(self, runner, tmp_path):
        """Test that --continue-on-error skips namespaces with conflicts."""
        schema_file = tmp_path / "schema.json"
        schema_file.write_text('{"content": "uint64", "new_field": "string"}')

        mock_ns1 = MagicMock()
        mock_ns1.id = "prod-users"  # Will have conflict
        mock_ns2 = MagicMock()
        mock_ns2.id = "prod-orders"  # Will be applied

        mock_client = MagicMock()
        mock_client.namespaces.return_value = [mock_ns1, mock_ns2]

        namespace_mocks = {}

        def mock_get_ns(name, region=None):
            if name not in namespace_mocks:
                mock = MagicMock()
                mock_metadata = MagicMock()
                if name == "prod-users":
                    # This namespace has a type conflict (content: string -> uint64)
                    mock_metadata.schema = {"content": "string"}
                else:
                    # This namespace has no conflicts (new namespace)
                    mock_metadata.schema = {}
                mock.metadata.return_value = mock_metadata
                namespace_mocks[name] = mock
            return namespace_mocks[name]

        with patch("tpuff.commands.schema.get_turbopuffer_client", return_value=mock_client):
            with patch("tpuff.commands.schema.get_namespace", side_effect=mock_get_ns):
                result = runner.invoke(
                    schema, ["apply", "--prefix", "prod", "-f", str(schema_file), "--yes", "--continue-on-error"]
                )

        assert result.exit_code == 0
        assert "Warning" in result.output  # Warning about conflicts
        assert "Successfully applied schema to 1 namespace(s)" in result.output
        # Only prod-orders should have write called
        namespace_mocks["prod-orders"].write.assert_called_once()
        namespace_mocks["prod-users"].write.assert_not_called()

    def test_continue_on_error_with_all_flag(self, runner, tmp_path):
        """Test --continue-on-error works with --all flag."""
        schema_file = tmp_path / "schema.json"
        schema_file.write_text('{"content": "uint64"}')

        mock_ns1 = MagicMock()
        mock_ns1.id = "ns-with-conflict"
        mock_ns2 = MagicMock()
        mock_ns2.id = "ns-new"

        mock_client = MagicMock()
        mock_client.namespaces.return_value = [mock_ns1, mock_ns2]

        namespace_mocks = {}

        def mock_get_ns(name, region=None):
            if name not in namespace_mocks:
                mock = MagicMock()
                mock_metadata = MagicMock()
                if name == "ns-with-conflict":
                    mock_metadata.schema = {"content": "string"}  # Conflict
                else:
                    mock_metadata.schema = {}  # No conflict
                mock.metadata.return_value = mock_metadata
                namespace_mocks[name] = mock
            return namespace_mocks[name]

        with patch("tpuff.commands.schema.get_turbopuffer_client", return_value=mock_client):
            with patch("tpuff.commands.schema.get_namespace", side_effect=mock_get_ns):
                result = runner.invoke(
                    schema, ["apply", "--all", "-f", str(schema_file), "--yes", "--continue-on-error"]
                )

        assert result.exit_code == 0
        assert "Warning" in result.output
        namespace_mocks["ns-new"].write.assert_called_once()
        namespace_mocks["ns-with-conflict"].write.assert_not_called()

    def test_continue_on_error_all_have_conflicts(self, runner, tmp_path):
        """Test --continue-on-error when all namespaces have conflicts."""
        schema_file = tmp_path / "schema.json"
        schema_file.write_text('{"content": "uint64"}')

        mock_ns1 = MagicMock()
        mock_ns1.id = "ns1"
        mock_ns2 = MagicMock()
        mock_ns2.id = "ns2"

        mock_client = MagicMock()
        mock_client.namespaces.return_value = [mock_ns1, mock_ns2]

        def mock_get_ns(name, region=None):
            mock = MagicMock()
            mock_metadata = MagicMock()
            mock_metadata.schema = {"content": "string"}  # All have conflicts
            mock.metadata.return_value = mock_metadata
            return mock

        with patch("tpuff.commands.schema.get_turbopuffer_client", return_value=mock_client):
            with patch("tpuff.commands.schema.get_namespace", side_effect=mock_get_ns):
                result = runner.invoke(
                    schema, ["apply", "--prefix", "ns", "-f", str(schema_file), "--yes", "--continue-on-error"]
                )

        # Should exit successfully but with no updates
        assert result.exit_code == 0
        assert "Warning" in result.output
        assert "No namespaces need updates" in result.output

    def test_continue_on_error_ignored_for_single_namespace(self, runner, tmp_path):
        """Test that --continue-on-error has no effect for single namespace mode."""
        schema_file = tmp_path / "schema.json"
        schema_file.write_text('{"content": "uint64"}')

        mock_ns = MagicMock()
        mock_metadata = MagicMock()
        mock_metadata.schema = {"content": "string"}  # Type conflict
        mock_ns.metadata.return_value = mock_metadata

        with patch("tpuff.commands.schema.get_namespace", return_value=mock_ns):
            result = runner.invoke(
                schema, ["apply", "-n", "test-ns", "-f", str(schema_file), "--continue-on-error"]
            )

        # Single namespace mode should still fail on conflicts
        assert result.exit_code == 1
        assert "type change not allowed" in result.output.lower()
