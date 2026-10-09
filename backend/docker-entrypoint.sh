#!/bin/sh
# Applies migrations, then seeds the supplied CSVs and demo users on start-up.
# Each Django migration runs in its own transaction on PostgreSQL, so a failing migration
# rolls back cleanly and the container exits non-zero instead of serving a half-migrated schema.
set -e

echo "Waiting for PostgreSQL..."
python - <<'PY'
import os, sys, time
import psycopg
for attempt in range(30):
    try:
        psycopg.connect(host=os.environ.get("POSTGRES_HOST", "db"), port=os.environ.get("POSTGRES_PORT", "5432"),
                        dbname=os.environ["POSTGRES_DB"], user=os.environ["POSTGRES_USER"],
                        password=os.environ["POSTGRES_PASSWORD"], connect_timeout=3).close()
        sys.exit(0)
    except psycopg.OperationalError:
        time.sleep(2)
sys.exit("PostgreSQL did not become ready")
PY

python manage.py migrate --noinput
if [ "${SEED_ON_START:-true}" = "true" ]; then
  python manage.py seed_data --data-dir "${SEED_DATA_DIR:-/data}"
  python manage.py create_demo_users
fi
exec "$@"
