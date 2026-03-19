"""Tests for Aritech diagnostics."""
from __future__ import annotations

import sys
from pathlib import Path

# Add custom_components directory to path for proper package imports
_custom_components_dir = Path(__file__).parent.parent.parent
sys.path.insert(0, str(_custom_components_dir))

from aritech_ats.diagnostics import _redact_entity_names


class TestRedactEntityNames:
    """Tests for _redact_entity_names function."""

    def test_redacts_names(self) -> None:
        """Test that entity names are redacted."""
        entities = [
            {"number": 1, "name": "Front Door"},
            {"number": 2, "name": "Living Room PIR"},
        ]
        result = _redact_entity_names(entities)
        assert result[0]["name"] == "**REDACTED**"
        assert result[1]["name"] == "**REDACTED**"
        assert result[0]["number"] == 1
        assert result[1]["number"] == 2

    def test_preserves_entities_without_name(self) -> None:
        """Test that entities without name field are unchanged."""
        entities = [{"number": 1}]
        result = _redact_entity_names(entities)
        assert result == [{"number": 1}]

    def test_empty_list(self) -> None:
        """Test with empty list."""
        assert _redact_entity_names([]) == []
