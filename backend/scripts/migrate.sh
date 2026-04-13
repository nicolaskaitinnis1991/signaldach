#!/usr/bin/env bash
# SignalDACH Database Migration Helper
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/.."

case "${1:-}" in
  upgrade)
    echo "Running migrations..."
    alembic upgrade head
    echo "Done."
    ;;
  downgrade)
    echo "Reverting last migration..."
    alembic downgrade -1
    echo "Done."
    ;;
  current)
    alembic current
    ;;
  history)
    alembic history
    ;;
  generate)
    if [ -z "${2:-}" ]; then
      echo "Usage: $0 generate <migration_message>"
      exit 1
    fi
    alembic revision -m "$2"
    ;;
  *)
    echo "Usage: $0 {upgrade|downgrade|current|history|generate <msg>}"
    exit 1
    ;;
esac
