#!/bin/sh
set -e

# Run Alembic migrations if using PostgreSQL
case "${SETTINGS_DATABASE_URL:-}" in
  postgresql*)
    echo "PostgreSQL detected, running migrations..."
    cd /app/packages/shared
    alembic upgrade head
    cd /app/apps/telegram-bot
    echo "Migrations complete."
    ;;
esac

exec "$@"
