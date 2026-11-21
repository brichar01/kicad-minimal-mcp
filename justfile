# kicad-minimal-mcp development tasks.

set shell := ["bash", "-uc"]

default: check

# Typecheck and apply Ruff's fixes/formatting in place.
check:
    uv run ruff check --fix .
    uv run ruff format .
    uv run pyright

# Run the fixture-backed IPC integration tests.
test:
    uv run pytest -m integration
