#!/usr/bin/env bash
set -euo pipefail
echo "[prestart] Running database initialization..."

# Check if DATABASE_URL is set
if [ -z "${DATABASE_URL:-}" ]; then
    echo "[prestart] Warning: DATABASE_URL not set, using SQLite fallback"
    export DATABASE_URL="sqlite:///./app.db"
fi

python - <<'PYCODE'
import os
print(f"[prestart] Using DATABASE_URL: {os.getenv('DATABASE_URL', 'NOT_SET')}")
try:
    from database.connection import create_tables
    create_tables()
    print('[prestart] Tables ensured successfully.')
except Exception as e:
    print(f'[prestart] Error creating tables: {e}')
    # Don't fail the script, just warn
    print('[prestart] Continuing without table creation...')
PYCODE

echo "[prestart] Done."