#!/usr/bin/env bash
set -euo pipefail

repository_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${repository_root}"

if [[ "$#" -eq 0 ]]; then
  set -- --working-tree ../core
fi

uv sync --locked --dev
uv run ruff format --check scripts tests
uv run ruff check scripts tests
uv run pytest -q
uv run scripts/update_navigation.py --check
uv run scripts/render_walkthrough.py --check
uv run scripts/check_site.py "$@"
