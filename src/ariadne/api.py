from __future__ import annotations

import json
from typing import Any

from fastapi import FastAPI, Header, HTTPException, Request
from pydantic import BaseModel, Field

from ariadne.config import get_settings
from ariadne.db import connect
from ariadne.jobs import enqueue

app = FastAPI(title="Ariadne API", version="0.1.0")


class CreateJobRequest(BaseModel):
    type: str
    payload: dict[str, Any] = Field(default_factory=dict)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/internal/jobs")
def create_job(request: CreateJobRequest) -> dict[str, str]:
    with connect() as conn:
        job_id = enqueue(conn, request.type, request.payload)
    return {"id": job_id}


@app.post("/feishu/events")
async def feishu_events(
    request: Request,
    x_ariadne_token: str | None = Header(default=None),
) -> dict[str, str]:
    settings = get_settings()
    if settings.feishu_callback_token and x_ariadne_token != settings.feishu_callback_token:
        raise HTTPException(status_code=401, detail="invalid callback token")

    payload = await request.json()
    item_id = _first(payload, "item_id", "itemId")
    action = _first(payload, "action", "value")
    push_event_id = _first(payload, "push_event_id", "pushEventId")
    user_id = _first(payload, "user_id", "userId", "open_id", "openId")

    if not item_id or not action:
        raise HTTPException(status_code=400, detail="item_id and action are required")

    if action not in {"useful", "not_useful", "read_later", "save_obsidian", "wrong_tag"}:
        raise HTTPException(status_code=400, detail="invalid feedback action")

    with connect() as conn:
        conn.execute(
            """
            INSERT INTO feedback (item_id, push_event_id, user_id, action, metadata)
            VALUES (%s, %s, %s, %s, %s::jsonb)
            """,
            (item_id, push_event_id, user_id, action, json.dumps(payload)),
        )
        if action == "save_obsidian":
            enqueue(conn, "export_obsidian", {"item_id": item_id})

    return {"status": "accepted"}


def _first(payload: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in payload and not isinstance(payload[key], dict | list):
            return payload[key]
    event = payload.get("event")
    if isinstance(event, dict):
        for key in keys:
            if key in event and not isinstance(event[key], dict | list):
                return event[key]
    action = payload.get("action")
    if isinstance(action, dict):
        value = action.get("value")
        if isinstance(value, dict):
            for key in keys:
                if key in value and not isinstance(value[key], dict | list):
                    return value[key]
    return None
