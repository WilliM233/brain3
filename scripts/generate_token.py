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

"""Generate a BRAIN 3.0 app-API bearer token.

Prints a URL-safe 48-byte random token to stdout. The companion app and the
scheduler authenticate to ``/api/app/*`` with this token, so it should be
treated as a shared secret. After generating, set::

    BRAIN3_APP_BEARER_TOKEN=<value>

in the ``.env`` file (or your deployment secret store), then restart the API.

The token is the shared secret itself — there is no DB write, no user
record, no per-device state. Rotation = generate a new token, update the
env, restart the API. (Per-device tokens and rotation tooling are Phase 3.)

Usage:
    python -m scripts.generate_token
"""

from __future__ import annotations

import secrets
import sys

TOKEN_BYTES = 48


def main() -> None:
    """Print a fresh URL-safe token to stdout, with a hint to stderr."""
    token = secrets.token_urlsafe(TOKEN_BYTES)
    # Token-only on stdout so it captures cleanly:
    #     TOKEN=$(python -m scripts.generate_token)
    print(token)
    # Operator hint goes to stderr so it doesn't pollute the captured value.
    print(
        f"Set BRAIN3_APP_BEARER_TOKEN={token} in your .env file "
        "(or secret store) and restart the API to enable /api/app/* auth.",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
