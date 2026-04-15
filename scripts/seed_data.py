#!/usr/bin/env python3
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

"""Load seed data into BRAIN 3.0 via the batch API.

Reads JSON seed files from scripts/seeds/ and loads them in dependency
order: protocols → directives → skills. Idempotent — checks by name
before creating and skips existing entities.

Usage:
    python scripts/seed_data.py --api-url http://localhost:8000 --dry-run
    python scripts/seed_data.py --api-url http://localhost:8000
    python scripts/seed_data.py --api-url http://localhost:8000 --only protocols
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import httpx

DEFAULT_API_URL = "http://localhost:8000"
SEEDS_DIR = Path(__file__).parent / "seeds"

# Load order matters — skills reference protocols and directives by name.
# Rules are independent and loaded last.
ENTITY_ORDER = ["protocols", "directives", "skills", "rules"]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(
        description="Load seed data into BRAIN 3.0",
    )
    parser.add_argument(
        "--api-url",
        default=DEFAULT_API_URL,
        help=f"BRAIN 3.0 API base URL (default: {DEFAULT_API_URL})",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be loaded without creating entities",
    )
    parser.add_argument(
        "--only",
        choices=ENTITY_ORDER,
        help="Load only a specific entity type",
    )
    return parser.parse_args(argv)


def load_seed_file(entity_type: str) -> dict:
    """Load and parse a seed JSON file."""
    path = SEEDS_DIR / f"{entity_type}.json"
    if not path.exists():
        print(f"  WARNING: Seed file not found: {path}")
        return {"items": []}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def fetch_existing_by_name(
    client: httpx.Client, api_url: str, entity_type: str,
) -> dict[str, dict]:
    """Fetch all existing entities of a type, keyed by name."""
    resp = client.get(f"{api_url}/api/{entity_type}")
    resp.raise_for_status()
    return {item["name"]: item for item in resp.json()}


def resolve_skill_references(
    item: dict,
    existing_protocols: dict[str, dict],
    existing_directives: dict[str, dict],
) -> dict:
    """Resolve protocol_names and directive_names to IDs for skill creation.

    Returns a new dict with protocol_ids and directive_ids replacing
    the name-based references. Raises ValueError if a referenced name
    is not found.
    """
    resolved = dict(item)

    protocol_names = resolved.pop("protocol_names", [])
    directive_names = resolved.pop("directive_names", [])

    protocol_ids = []
    for name in protocol_names:
        if name not in existing_protocols:
            msg = f"Protocol '{name}' not found — load protocols first"
            raise ValueError(msg)
        protocol_ids.append(existing_protocols[name]["id"])

    directive_ids = []
    for name in directive_names:
        if name not in existing_directives:
            msg = f"Directive '{name}' not found — load directives first"
            raise ValueError(msg)
        directive_ids.append(existing_directives[name]["id"])

    if protocol_ids:
        resolved["protocol_ids"] = protocol_ids
    if directive_ids:
        resolved["directive_ids"] = directive_ids

    return resolved


def load_entity_type(
    client: httpx.Client,
    api_url: str,
    entity_type: str,
    dry_run: bool,
    existing_protocols: dict[str, dict] | None = None,
    existing_directives: dict[str, dict] | None = None,
) -> tuple[int, int, list[str]]:
    """Load seed data for a single entity type.

    Returns (created_count, skipped_count, errors).
    """
    seed_data = load_seed_file(entity_type)
    items = seed_data.get("items", [])
    if not items:
        return 0, 0, []

    # Check existing entities for idempotency
    existing = fetch_existing_by_name(client, api_url, entity_type)

    created = 0
    skipped = 0
    errors: list[str] = []

    # Filter to only new items
    to_create = []
    for item in items:
        name = item["name"]
        if name in existing:
            print(f"    SKIP (exists): {name}")
            skipped += 1
            continue

        # Skills need name→ID resolution
        if entity_type == "skills":
            try:
                item = resolve_skill_references(
                    item,
                    existing_protocols or {},
                    existing_directives or {},
                )
            except ValueError as exc:
                error_msg = f"    ERROR resolving references for '{name}': {exc}"
                print(error_msg)
                errors.append(error_msg)
                continue

        if dry_run:
            print(f"    WOULD CREATE: {name}")
            created += 1
            continue

        to_create.append(item)

    # Create new items — batch endpoint for most types, individual for rules
    if to_create and not dry_run:
        if entity_type == "rules":
            for item in to_create:
                try:
                    resp = client.post(
                        f"{api_url}/api/{entity_type}",
                        json=item,
                    )
                    resp.raise_for_status()
                    print(f"    CREATED: {item['name']}")
                    created += 1
                except httpx.HTTPStatusError as exc:
                    error_msg = (
                        f"    ERROR creating '{item['name']}': "
                        f"{exc.response.text}"
                    )
                    print(error_msg)
                    errors.append(error_msg)
        else:
            try:
                resp = client.post(
                    f"{api_url}/api/{entity_type}/batch",
                    json={"items": to_create},
                )
                resp.raise_for_status()
                result = resp.json()
                batch_count = result.get("count", len(to_create))
                for item in to_create:
                    print(f"    CREATED: {item['name']}")
                created += batch_count
            except httpx.HTTPStatusError as exc:
                error_msg = f"    ERROR in batch create: {exc.response.text}"
                print(error_msg)
                errors.append(error_msg)

    return created, skipped, errors


def seed(args: argparse.Namespace) -> None:
    """Run the seed loading."""
    api_url = args.api_url.rstrip("/")

    with httpx.Client(timeout=30) as client:
        # Verify API is reachable
        try:
            health = client.get(f"{api_url}/health")
            health.raise_for_status()
        except httpx.HTTPError as exc:
            print(f"ERROR: Cannot reach BRAIN 3.0 API at {api_url}: {exc}")
            sys.exit(1)

        entities_to_load = [args.only] if args.only else ENTITY_ORDER

        total_created = 0
        total_skipped = 0
        all_errors: list[str] = []

        # We need to track what exists for skill reference resolution
        existing_protocols: dict[str, dict] = {}
        existing_directives: dict[str, dict] = {}

        for entity_type in entities_to_load:
            print(f"\n--- Loading {entity_type} ---")

            # Refresh protocol/directive maps before loading skills
            if entity_type == "skills":
                existing_protocols = fetch_existing_by_name(
                    client, api_url, "protocols",
                )
                existing_directives = fetch_existing_by_name(
                    client, api_url, "directives",
                )

            created, skipped, errors = load_entity_type(
                client,
                api_url,
                entity_type,
                args.dry_run,
                existing_protocols=existing_protocols,
                existing_directives=existing_directives,
            )
            total_created += created
            total_skipped += skipped
            all_errors.extend(errors)

            # Update maps after loading (for subsequent skill resolution)
            if entity_type == "protocols" and not args.dry_run:
                existing_protocols = fetch_existing_by_name(
                    client, api_url, "protocols",
                )
            elif entity_type == "directives" and not args.dry_run:
                existing_directives = fetch_existing_by_name(
                    client, api_url, "directives",
                )

        # Summary
        print("\n" + "=" * 60)
        print("Seed Loading Summary")
        print("=" * 60)
        action = "Would create" if args.dry_run else "Created"
        print(f"  {action}: {total_created}")
        print(f"  Skipped (already exist): {total_skipped}")
        if all_errors:
            print(f"  Errors: {len(all_errors)}")
            for err in all_errors:
                print(f"    {err}")
        if args.dry_run:
            print("\n  (Dry run — no changes made)")


def main() -> None:
    """Entry point."""
    args = parse_args()
    seed(args)


if __name__ == "__main__":
    main()
