from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import psycopg


@dataclass(frozen=True)
class Job:
    id: str
    type: str
    payload: dict[str, Any]
    attempts: int
    max_attempts: int


def enqueue(
    conn: psycopg.Connection,
    job_type: str,
    payload: dict[str, Any] | None = None,
    run_after_seconds: int = 0,
) -> str:
    row = conn.execute(
        """
        INSERT INTO jobs (type, payload, run_after)
        VALUES (%s, %s::jsonb, now() + (%s || ' seconds')::interval)
        RETURNING id
        """,
        (job_type, json.dumps(payload or {}), run_after_seconds),
    ).fetchone()
    return str(row["id"])


def claim_next(conn: psycopg.Connection) -> Job | None:
    row = conn.execute(
        """
        WITH next_job AS (
          SELECT id
          FROM jobs
          WHERE status = 'pending'
            AND run_after <= now()
          ORDER BY created_at
          FOR UPDATE SKIP LOCKED
          LIMIT 1
        )
        UPDATE jobs
        SET status = 'running',
            attempts = attempts + 1,
            updated_at = now()
        WHERE id IN (SELECT id FROM next_job)
        RETURNING id, type, payload, attempts, max_attempts
        """
    ).fetchone()
    if row is None:
        return None
    return Job(
        id=str(row["id"]),
        type=row["type"],
        payload=row["payload"] or {},
        attempts=row["attempts"],
        max_attempts=row["max_attempts"],
    )


def complete(conn: psycopg.Connection, job_id: str) -> None:
    conn.execute(
        "UPDATE jobs SET status = 'succeeded', updated_at = now(), last_error = NULL WHERE id = %s",
        (job_id,),
    )


def fail(conn: psycopg.Connection, job: Job, error: Exception) -> None:
    if job.attempts >= job.max_attempts:
        conn.execute(
            """
            UPDATE jobs
            SET status = 'failed',
                last_error = %s,
                updated_at = now()
            WHERE id = %s
            """,
            (str(error), job.id),
        )
        return

    delay_seconds = min(300, 5 * (2 ** max(job.attempts - 1, 0)))
    conn.execute(
        """
        UPDATE jobs
        SET status = 'pending',
            run_after = now() + (%s || ' seconds')::interval,
            last_error = %s,
            updated_at = now()
        WHERE id = %s
        """,
        (delay_seconds, str(error), job.id),
    )
