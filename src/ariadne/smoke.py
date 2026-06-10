from __future__ import annotations

from ariadne.db import connect


REQUIRED_TABLES = {
    "analysis_results",
    "dedupe_groups",
    "feedback",
    "items",
    "jobs",
    "notes",
    "push_events",
    "raw_items",
    "sources",
}


def main() -> None:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
            """
        ).fetchall()
        tables = {row["table_name"] for row in rows}
        missing = sorted(REQUIRED_TABLES - tables)
        if missing:
            raise SystemExit(f"Missing tables: {', '.join(missing)}")

        job_count = conn.execute("SELECT count(*) AS count FROM jobs").fetchone()["count"]
        print(f"database ok: {len(REQUIRED_TABLES)} tables, {job_count} jobs")


if __name__ == "__main__":
    main()
