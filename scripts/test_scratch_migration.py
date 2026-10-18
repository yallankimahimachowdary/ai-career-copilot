"""Test alembic migration round trip on scratch database ai_career_copilot_scratch."""

import os
import subprocess
import sys
import psycopg2

SCRATCH_DB_NAME = "ai_career_copilot_scratch"
ADMIN_URL = "postgresql://postgres:postgres@localhost:5432/postgres"
SCRATCH_URL = f"postgresql+asyncpg://postgres:postgres@localhost:5432/{SCRATCH_DB_NAME}"
SCRATCH_SYNC_URL = f"postgresql://postgres:postgres@localhost:5432/{SCRATCH_DB_NAME}"


def main():
    print(f"Connecting to Postgres to prepare {SCRATCH_DB_NAME}...")
    conn = psycopg2.connect(ADMIN_URL)
    conn.autocommit = True
    cur = conn.cursor()

    cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (SCRATCH_DB_NAME,))
    if cur.fetchone():
        print(f"Dropping existing {SCRATCH_DB_NAME}...")
        # Terminate any existing connections to scratch db
        cur.execute(
            """
            SELECT pg_terminate_backend(pg_stat_activity.pid)
            FROM pg_stat_activity
            WHERE pg_stat_activity.datname = %s
              AND pid <> pg_backend_pid()
            """,
            (SCRATCH_DB_NAME,)
        )
        cur.execute(f'DROP DATABASE "{SCRATCH_DB_NAME}"')

    print(f"Creating fresh database {SCRATCH_DB_NAME}...")
    cur.execute(f'CREATE DATABASE "{SCRATCH_DB_NAME}"')
    cur.close()
    conn.close()

    # Enable pgvector extension on scratch DB
    s_conn = psycopg2.connect(SCRATCH_SYNC_URL)
    s_conn.autocommit = True
    s_cur = s_conn.cursor()
    s_cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
    s_cur.close()
    s_conn.close()

    env = os.environ.copy()
    env["DATABASE_URL"] = SCRATCH_URL

    print("\n--- 1. Running alembic upgrade head ---")
    res1 = subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], env=env, capture_output=True, text=True)
    print("STDOUT:", res1.stdout)
    if res1.stderr:
        print("STDERR:", res1.stderr)
    assert res1.returncode == 0, "alembic upgrade head failed"

    print("\n--- 2. Running alembic downgrade -1 ---")
    res2 = subprocess.run([sys.executable, "-m", "alembic", "downgrade", "-1"], env=env, capture_output=True, text=True)
    print("STDOUT:", res2.stdout)
    if res2.stderr:
        print("STDERR:", res2.stderr)
    assert res2.returncode == 0, "alembic downgrade -1 failed"

    print("\n--- 3. Running alembic upgrade head again ---")
    res3 = subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], env=env, capture_output=True, text=True)
    print("STDOUT:", res3.stdout)
    if res3.stderr:
        print("STDERR:", res3.stderr)
    assert res3.returncode == 0, "alembic upgrade head (second pass) failed"

    print("\nSUCCESS: Scratch database migration round trip verified cleanly!")


if __name__ == "__main__":
    main()
