"""Pure memory injection selection helpers for Stage 5A."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime, timedelta
from typing import Any

from .memory_store import contains_sensitive_field


DEFAULT_MEMORY_PRIORITY = [
    "boundary",
    "profile",
    "preference",
    "relationship",
    "skill_goal",
    "open_thread",
    "fact",
]


def _parse_dt(value: object) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def _memory_age_days(item: dict[str, Any]) -> int:
    created_at = _parse_dt(item.get("created_at"))
    if created_at is None:
        return 0
    return max(0, (datetime.now().astimezone() - created_at).days)


def _priority_index(memory_type: object) -> int:
    value = str(memory_type or "").strip()
    try:
        return DEFAULT_MEMORY_PRIORITY.index(value)
    except ValueError:
        return len(DEFAULT_MEMORY_PRIORITY)


def _is_active_open_thread(item: dict[str, Any], max_age_days: int = 7) -> bool:
    expires_at = _parse_dt(item.get("expires_at"))
    if expires_at is not None:
        return expires_at >= datetime.now().astimezone()
    created_at = _parse_dt(item.get("created_at"))
    if created_at is None:
        return False
    return created_at + timedelta(days=max_age_days) >= datetime.now().astimezone()


def _is_valid_item(item: dict[str, Any], include_open_threads: bool) -> bool:
    if contains_sensitive_field(item.get("content")):
        return False
    if str(item.get("type") or "") == "open_thread" and not include_open_threads:
        return False
    if str(item.get("type") or "") == "open_thread" and not _is_active_open_thread(item):
        return False
    return True


def _trim_content(text: object, limit: int = 120) -> str:
    value = str(text or "").strip()
    if len(value) <= limit:
        return value
    return value[: limit - 3] + "..."


def select_memory_items(
    items: Iterable[dict[str, Any]],
    max_items: int = 6,
    char_budget: int = 900,
    include_open_threads: bool = True,
) -> list[dict[str, Any]]:
    filtered = [item for item in items if _is_valid_item(item, include_open_threads)]
    filtered.sort(
        key=lambda item: (
            -int(bool(item.get("pinned"))),
            _priority_index(item.get("type")),
            _memory_age_days(item),
            str(item.get("created_at") or ""),
        )
    )

    selected: list[dict[str, Any]] = []
    used = 0
    for item in filtered:
        trimmed = _trim_content(item.get("content"))
        if not trimmed:
            continue
        cost = len(trimmed)
        if selected and (len(selected) >= max_items or used + cost > char_budget):
            continue
        if not selected and cost > char_budget:
            trimmed = _trim_content(trimmed, char_budget)
            cost = len(trimmed)
        if len(selected) >= max_items:
            break
        selected.append(
            {
                "id": item.get("id"),
                "type": item.get("type"),
                "content": trimmed,
                "pinned": int(bool(item.get("pinned"))),
                "created_at": item.get("created_at"),
                "updated_at": item.get("updated_at"),
                "expires_at": item.get("expires_at"),
                "source": item.get("source"),
            }
        )
        used += cost
    return selected


def build_memory_injection(
    store,
    owner_user_id: str,
    config: dict[str, Any] | None,
) -> dict[str, Any]:
    cfg = config or {}
    if not cfg.get("memory_injection_enabled", False):
        return {"enabled": False, "reason": "memory_injection_disabled", "items": []}
    runtime_flag = store.get_runtime_flag(owner_user_id)
    if not runtime_flag.get("enabled", True):
        return {"enabled": False, "reason": "memory_off", "items": []}
    paused_until = str(runtime_flag.get("paused_until") or "").strip()
    if paused_until:
        try:
            paused_dt = datetime.fromisoformat(paused_until)
        except ValueError:
            return {"enabled": False, "reason": "memory_paused", "items": []}
        if paused_dt > datetime.now().astimezone():
            return {"enabled": False, "reason": "memory_paused", "items": []}

    items = store.list_memories(owner_user_id, "private")
    selected = select_memory_items(
        items,
        max_items=int(cfg.get("max_injected_memories", 6) or 6),
        char_budget=int(cfg.get("memory_injection_char_budget", 900) or 900),
        include_open_threads=bool(cfg.get("include_open_threads", True)),
    )
    return {"enabled": True, "reason": "ok", "items": selected}
