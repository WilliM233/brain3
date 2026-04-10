# BRAIN 3.0 — AI-powered personal operating system for ADHD
# Copyright (C) 2026 L (WilliM233)
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.

"""Tests for seed data structure and script logic."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.schemas.directives import DirectiveCreate
from app.schemas.protocols import ProtocolCreate
from scripts.migrate_to_artifacts import (
    build_artifact_title,
)
from scripts.migrate_to_artifacts import (
    parse_args as parse_migrate_args,
)
from scripts.seed_data import (
    load_seed_file,
    resolve_skill_references,
)
from scripts.seed_data import (
    parse_args as parse_seed_args,
)

SEEDS_PATH = Path(__file__).parent.parent / "scripts" / "seeds"


# ---------------------------------------------------------------------------
# Seed JSON parsing tests
# ---------------------------------------------------------------------------


class TestSeedFileParsing:
    """Verify seed JSON files load and parse correctly."""

    def test_protocols_json_loads(self):
        with open(SEEDS_PATH / "protocols.json") as f:
            data = json.load(f)
        assert "items" in data
        assert len(data["items"]) > 0

    def test_directives_json_loads(self):
        with open(SEEDS_PATH / "directives.json") as f:
            data = json.load(f)
        assert "items" in data
        assert len(data["items"]) > 0

    def test_skills_json_loads(self):
        with open(SEEDS_PATH / "skills.json") as f:
            data = json.load(f)
        assert "items" in data
        assert len(data["items"]) > 0


# ---------------------------------------------------------------------------
# Seed data schema validation tests
# ---------------------------------------------------------------------------


class TestSeedDataSchemaValidation:
    """Verify seed data matches Pydantic schemas."""

    def test_protocols_match_schema(self):
        with open(SEEDS_PATH / "protocols.json") as f:
            data = json.load(f)
        for item in data["items"]:
            protocol = ProtocolCreate(**item)
            assert protocol.name
            assert protocol.is_seedable is True

    def test_directives_match_schema(self):
        with open(SEEDS_PATH / "directives.json") as f:
            data = json.load(f)
        for item in data["items"]:
            directive = DirectiveCreate(**item)
            assert directive.name
            assert directive.is_seedable is True

    def test_skills_seed_has_required_fields(self):
        """Skills use name-based references, so we validate structure not schema."""
        with open(SEEDS_PATH / "skills.json") as f:
            data = json.load(f)
        for item in data["items"]:
            assert "name" in item
            assert "is_seedable" in item
            assert item["is_seedable"] is True
            # Name-based references must be lists
            assert isinstance(item.get("protocol_names", []), list)
            assert isinstance(item.get("directive_names", []), list)

    def test_protocols_have_meaningful_steps(self):
        with open(SEEDS_PATH / "protocols.json") as f:
            data = json.load(f)
        for item in data["items"]:
            if item.get("steps"):
                for step in item["steps"]:
                    assert step["title"].strip()
                    assert step["instruction"].strip()
                    assert step["order"] >= 1

    def test_directives_have_correct_scope(self):
        with open(SEEDS_PATH / "directives.json") as f:
            data = json.load(f)
        for item in data["items"]:
            assert item["scope"] in ("global", "skill", "agent")
            if item["scope"] == "global":
                assert item.get("scope_ref") is None

    def test_exactly_one_default_skill(self):
        with open(SEEDS_PATH / "skills.json") as f:
            data = json.load(f)
        defaults = [i for i in data["items"] if i.get("is_default")]
        assert len(defaults) == 1, f"Expected 1 default skill, found {len(defaults)}"

    def test_all_seed_items_are_seedable(self):
        """Every item in every seed file must have is_seedable=true."""
        for filename in ("protocols.json", "directives.json", "skills.json"):
            with open(SEEDS_PATH / filename) as f:
                data = json.load(f)
            for item in data["items"]:
                assert item.get("is_seedable") is True, (
                    f"{filename}: {item['name']} missing is_seedable=true"
                )


# ---------------------------------------------------------------------------
# Seed data cross-reference tests
# ---------------------------------------------------------------------------


class TestSeedCrossReferences:
    """Verify skills reference protocols/directives that exist in seed data."""

    def test_skill_protocol_references_are_valid(self):
        with open(SEEDS_PATH / "protocols.json") as f:
            protocol_names = {p["name"] for p in json.load(f)["items"]}
        with open(SEEDS_PATH / "skills.json") as f:
            skills = json.load(f)["items"]

        for skill in skills:
            for ref in skill.get("protocol_names", []):
                assert ref in protocol_names, (
                    f"Skill '{skill['name']}' references unknown protocol '{ref}'"
                )

    def test_skill_directive_references_are_valid(self):
        with open(SEEDS_PATH / "directives.json") as f:
            directive_names = {d["name"] for d in json.load(f)["items"]}
        with open(SEEDS_PATH / "skills.json") as f:
            skills = json.load(f)["items"]

        for skill in skills:
            for ref in skill.get("directive_names", []):
                assert ref in directive_names, (
                    f"Skill '{skill['name']}' references unknown directive '{ref}'"
                )


# ---------------------------------------------------------------------------
# Script logic tests
# ---------------------------------------------------------------------------


class TestSeedScriptLogic:
    """Test seed_data.py functions with mocked API calls."""

    def test_load_seed_file_returns_items(self):
        data = load_seed_file("protocols")
        assert "items" in data
        assert len(data["items"]) > 0

    def test_load_seed_file_missing_returns_empty(self):
        data = load_seed_file("nonexistent_entity")
        assert data == {"items": []}

    def test_resolve_skill_references_success(self):
        item = {
            "name": "test-skill",
            "description": "Test",
            "is_seedable": True,
            "is_default": False,
            "protocol_names": ["session-startup"],
            "directive_names": ["log-it-dont-fix-it"],
        }
        protocols = {"session-startup": {"id": "proto-uuid-1", "name": "session-startup"}}
        directives = {"log-it-dont-fix-it": {"id": "dir-uuid-1", "name": "log-it-dont-fix-it"}}

        resolved = resolve_skill_references(item, protocols, directives)
        assert resolved["protocol_ids"] == ["proto-uuid-1"]
        assert resolved["directive_ids"] == ["dir-uuid-1"]
        assert "protocol_names" not in resolved
        assert "directive_names" not in resolved

    def test_resolve_skill_references_missing_protocol(self):
        item = {
            "name": "test-skill",
            "protocol_names": ["nonexistent"],
            "directive_names": [],
        }
        with pytest.raises(ValueError, match="Protocol 'nonexistent' not found"):
            resolve_skill_references(item, {}, {})

    def test_resolve_skill_references_missing_directive(self):
        item = {
            "name": "test-skill",
            "protocol_names": [],
            "directive_names": ["nonexistent"],
        }
        with pytest.raises(ValueError, match="Directive 'nonexistent' not found"):
            resolve_skill_references(item, {}, {})

    def test_parse_args_defaults(self):
        args = parse_seed_args([])
        assert args.api_url == "http://localhost:8000"
        assert args.dry_run is False
        assert args.only is None

    def test_parse_args_all_flags(self):
        args = parse_seed_args([
            "--api-url", "http://example.com:9000",
            "--dry-run",
            "--only", "protocols",
        ])
        assert args.api_url == "http://example.com:9000"
        assert args.dry_run is True
        assert args.only == "protocols"


class TestMigrateScriptLogic:
    """Test migrate_to_artifacts.py functions."""

    def test_build_artifact_title_from_claude_md(self):
        entry = {
            "id": "abcdef12-3456-7890-abcd-ef1234567890",
            "notes": "[CLAUDE.md] brain3/CLAUDE.md — Core API\nContent here...",
        }
        title = build_artifact_title(entry, "claude-md")
        assert title == "brain3/CLAUDE.md — Core API"

    def test_build_artifact_title_from_process_decision(self):
        entry = {
            "id": "abcdef12-3456-7890-abcd-ef1234567890",
            "notes": "[Process Decision] Some decision\nDetails...",
        }
        title = build_artifact_title(entry, "process-decision")
        assert title == "Some decision"

    def test_build_artifact_title_fallback(self):
        entry = {
            "id": "abcdef12-3456-7890-abcd-ef1234567890",
            "notes": "A" * 250 + "\nContent",
        }
        title = build_artifact_title(entry, "some-tag")
        assert title.startswith("Migrated from some-tag")

    def test_build_artifact_title_empty_notes(self):
        entry = {
            "id": "abcdef12-3456-7890-abcd-ef1234567890",
            "notes": "",
        }
        title = build_artifact_title(entry, "some-tag")
        assert title.startswith("Migrated from some-tag")

    def test_parse_migrate_args_defaults(self):
        args = parse_migrate_args([])
        assert args.api_url == "http://localhost:8000"
        assert args.dry_run is False
        assert args.tag is None

    def test_parse_migrate_args_all_flags(self):
        args = parse_migrate_args([
            "--api-url", "http://example.com:9000",
            "--dry-run",
            "--tag", "claude-md",
        ])
        assert args.api_url == "http://example.com:9000"
        assert args.dry_run is True
        assert args.tag == "claude-md"
