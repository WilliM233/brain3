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

"""Migrate activity log content to artifacts.

Reads activity log entries tagged with document-type tags and creates
corresponding artifacts via the BRAIN 3.0 API. Does NOT delete source
entries — they remain as historical record.

Usage:
    python scripts/migrate_to_artifacts.py --api-url http://localhost:8000 --dry-run
    python scripts/migrate_to_artifacts.py --api-url http://localhost:8000
    python scripts/migrate_to_artifacts.py --api-url http://localhost:8000 --tag claude-md
"""

from __future__ import annotations

import argparse
import sys

import httpx

# Tags whose activity entries contain document content worth migrating
TAG_TO_ARTIFACT_TYPE: dict[str, str] = {
    "claude-md": "document",
    "process-decision": "document",
    "stellan-blueprint": "brief",
}

DEFAULT_API_URL = "http://localhost:8000"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(
        description="Migrate activity log entries to artifacts",
    )
    parser.add_argument(
        "--api-url",
        default=DEFAULT_API_URL,
        help=f"BRAIN 3.0 API base URL (default: {DEFAULT_API_URL})",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be migrated without creating artifacts",
    )
    parser.add_argument(
        "--tag",
        help="Migrate only entries with a specific tag (for incremental migration)",
    )
    return parser.parse_args(argv)


def fetch_tags(client: httpx.Client, api_url: str) -> list[dict]:
    """Fetch all tags from the API."""
    resp = client.get(f"{api_url}/api/tags")
    resp.raise_for_status()
    return resp.json()


def find_tag_by_name(tags: list[dict], name: str) -> dict | None:
    """Find a tag by name (case-insensitive)."""
    for tag in tags:
        if tag["name"].lower() == name.lower():
            return tag
    return None


def fetch_activity_entries_by_tag(
    client: httpx.Client, api_url: str, tag_name: str,
) -> list[dict]:
    """Fetch activity log entries filtered by tag name."""
    resp = client.get(f"{api_url}/api/activity", params={"tag": tag_name})
    resp.raise_for_status()
    return resp.json()


def check_artifact_exists(
    client: httpx.Client, api_url: str, title: str,
) -> bool:
    """Check if an artifact with this title already exists."""
    resp = client.get(f"{api_url}/api/artifacts", params={"search": title})
    resp.raise_for_status()
    for artifact in resp.json():
        if artifact["title"].lower() == title.lower():
            return True
    return False


def create_artifact(
    client: httpx.Client,
    api_url: str,
    title: str,
    artifact_type: str,
    content: str,
    tag_ids: list[str] | None = None,
    parent_id: str | None = None,
) -> dict:
    """Create an artifact via the API."""
    payload: dict = {
        "title": title,
        "artifact_type": artifact_type,
        "content": content,
    }
    if tag_ids:
        payload["tag_ids"] = tag_ids
    if parent_id:
        payload["parent_id"] = parent_id

    resp = client.post(f"{api_url}/api/artifacts", json=payload)
    resp.raise_for_status()
    return resp.json()


def build_artifact_title(entry: dict, tag_name: str) -> str:
    """Build a descriptive artifact title from an activity entry."""
    notes = entry.get("notes") or ""
    # Try to extract a title from the first line of notes
    first_line = notes.split("\n")[0].strip()
    # Strip common prefixes like [CLAUDE.md], [Process Decision], etc.
    for prefix in ("[CLAUDE.md]", "[Process Decision]", "[Brief]"):
        if first_line.startswith(prefix):
            first_line = first_line[len(prefix):].strip()
            break

    if first_line and len(first_line) <= 200:
        return first_line
    # Fallback: use tag name + entry ID
    return f"Migrated from {tag_name} — {entry['id'][:8]}"


def migrate(args: argparse.Namespace) -> None:
    """Run the migration."""
    api_url = args.api_url.rstrip("/")

    with httpx.Client(timeout=30) as client:
        # Verify API is reachable
        try:
            health = client.get(f"{api_url}/health")
            health.raise_for_status()
        except httpx.HTTPError as exc:
            print(f"ERROR: Cannot reach BRAIN 3.0 API at {api_url}: {exc}")
            sys.exit(1)

        # Fetch all tags for reference
        all_tags = fetch_tags(client, api_url)

        # Determine which tags to process
        tags_to_process: dict[str, str] = {}
        if args.tag:
            if args.tag in TAG_TO_ARTIFACT_TYPE:
                tags_to_process[args.tag] = TAG_TO_ARTIFACT_TYPE[args.tag]
            else:
                # Unknown tag — default to document type
                tags_to_process[args.tag] = "document"
        else:
            tags_to_process = dict(TAG_TO_ARTIFACT_TYPE)

        # Stats
        total_entries = 0
        total_created = 0
        total_skipped = 0
        errors: list[str] = []

        for tag_name, artifact_type in tags_to_process.items():
            tag = find_tag_by_name(all_tags, tag_name)
            if not tag:
                print(f"  SKIP: Tag '{tag_name}' not found in BRAIN")
                continue

            print(f"\n--- Processing tag: {tag_name} → artifact_type: {artifact_type} ---")

            entries = fetch_activity_entries_by_tag(client, api_url, tag_name)
            print(f"  Found {len(entries)} activity entries")

            # Group entries that share a common prefix (for multi-part content)
            parent_map: dict[str, str] = {}  # prefix → parent artifact ID

            for entry in entries:
                total_entries += 1
                notes = entry.get("notes") or ""
                if not notes.strip():
                    print(f"  SKIP (empty): {entry['id'][:8]}")
                    total_skipped += 1
                    continue

                title = build_artifact_title(entry, tag_name)

                # Check for existing artifact with this title
                if check_artifact_exists(client, api_url, title):
                    print(f"  SKIP (exists): {title}")
                    total_skipped += 1
                    continue

                if args.dry_run:
                    print(f"  WOULD CREATE: [{artifact_type}] {title}")
                    total_created += 1
                    continue

                # Detect multi-part content (e.g., "Part 1 of 2", "Part 2 of 2")
                parent_id = None
                first_line = notes.split("\n")[0]
                if "Part " in first_line and " of " in first_line:
                    # Extract the base prefix before "Part X of Y"
                    part_idx = first_line.index("Part ")
                    prefix = first_line[:part_idx].strip().rstrip("(—-– ")
                    if prefix in parent_map:
                        parent_id = parent_map[prefix]

                # Get tag IDs from the entry
                entry_tag_ids = [t["id"] for t in entry.get("tags", [])]

                try:
                    artifact = create_artifact(
                        client,
                        api_url,
                        title=title,
                        artifact_type=artifact_type,
                        content=notes,
                        tag_ids=entry_tag_ids,
                        parent_id=parent_id,
                    )
                    print(f"  CREATED: [{artifact_type}] {title}")
                    total_created += 1

                    # Track as potential parent for multi-part content
                    if "Part 1 of" in first_line:
                        part_idx = first_line.index("Part ")
                        prefix = first_line[:part_idx].strip().rstrip("(—-– ")
                        parent_map[prefix] = artifact["id"]

                except httpx.HTTPStatusError as exc:
                    error_msg = (
                        f"  ERROR creating artifact for {entry['id'][:8]}:"
                        f" {exc.response.text}"
                    )
                    print(error_msg)
                    errors.append(error_msg)

        # Summary
        print("\n" + "=" * 60)
        print("Migration Summary")
        print("=" * 60)
        action = "Would create" if args.dry_run else "Created"
        print(f"  Entries processed: {total_entries}")
        print(f"  {action}: {total_created}")
        print(f"  Skipped: {total_skipped}")
        if errors:
            print(f"  Errors: {len(errors)}")
            for err in errors:
                print(f"    {err}")
        if args.dry_run:
            print("\n  (Dry run — no changes made)")


def main() -> None:
    """Entry point."""
    args = parse_args()
    migrate(args)


if __name__ == "__main__":
    main()
