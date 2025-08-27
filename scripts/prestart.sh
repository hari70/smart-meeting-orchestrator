#!/usr/bin/env bash
set -euo pipefail
echo "[prestart] Running database initialization..."
python - <<'PYCODE'
from database.connection import create_tables
create_tables()
print('[prestart] Tables ensured.')
PYCODE

echo "[prestart] Done."