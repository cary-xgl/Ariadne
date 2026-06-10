from ariadne.api import _first


def test_first_reads_top_level_value() -> None:
    payload = {"item_id": "item-1", "action": "useful"}

    assert _first(payload, "item_id") == "item-1"
    assert _first(payload, "action") == "useful"


def test_first_reads_feishu_action_value() -> None:
    payload = {
        "action": {
            "value": {
                "item_id": "item-1",
                "push_event_id": "push-1",
                "action": "save_obsidian",
            }
        }
    }

    assert _first(payload, "item_id", "itemId") == "item-1"
    assert _first(payload, "push_event_id", "pushEventId") == "push-1"
    assert _first(payload, "action", "value") == "save_obsidian"


def test_first_reads_event_payload_value() -> None:
    payload = {"event": {"open_id": "user-1", "itemId": "item-1"}}

    assert _first(payload, "open_id", "openId") == "user-1"
    assert _first(payload, "item_id", "itemId") == "item-1"
