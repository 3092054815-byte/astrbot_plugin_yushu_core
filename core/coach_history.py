"""Coach review history isolation helpers."""

from __future__ import annotations

from typing import Any


COACH_LIVE_MODE = "coach"


def mark_live_mode_history_flags(
    event: Any,
    mode: str,
    config: dict[str, Any] | None,
) -> None:
    if mode not in {"normal", COACH_LIVE_MODE}:
        return
    set_extra = getattr(event, "set_extra", None)
    if not callable(set_extra):
        return
    set_extra("yushu_live_mode", mode)
    set_extra(
        "yushu_coach_review_no_history",
        mode == COACH_LIVE_MODE
        and bool((config or {}).get("coach_review_no_history_enabled", True)),
    )


def should_mark_coach_response_no_history(
    config: dict[str, Any] | None,
    event: Any,
) -> bool:
    data = config or {}
    if not bool(data.get("coach_review_no_history_enabled", True)):
        return False
    get_extra = getattr(event, "get_extra", None)
    if not callable(get_extra):
        return False
    return (
        get_extra("yushu_live_mode") == COACH_LIVE_MODE
        and bool(get_extra("yushu_coach_review_no_history"))
    )


def mark_final_assistant_message_no_save(messages: Any) -> bool:
    if not isinstance(messages, list):
        return False
    for message in reversed(messages):
        if getattr(message, "role", None) != "assistant":
            continue
        marker = getattr(message, "mark_as_temp", None)
        if callable(marker):
            marker()
        else:
            setattr(message, "_no_save", True)
        return True
    return False
