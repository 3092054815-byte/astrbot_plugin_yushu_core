"""State helpers for Stage 5 prompt hinting."""

from __future__ import annotations

from typing import Any


DEFAULT_YUSHU_STATE: dict[str, Any] = {
    "relationship_warmth": 0,
    "boundary_pressure": 0,
    "trust": 0,
    "playfulness": 0,
    "proactive_desire": 0,
    "unanswered_count": 0,
    "user_autonomy": 0,
    "real_world_transfer": 0,
    "practice_focus": "in_character",
}

DEFAULT_COACH_REVIEW_TRIGGER_KEYWORDS = (
    "复盘",
    "分析",
    "哪里不对",
    "帮我改",
    "评分",
    "现实里怎么练",
)

DEFAULT_COACH_REVIEW_EXIT_KEYWORDS = (
    "正常聊",
    "别复盘了",
    "继续角色内",
)


def _clamp_int(value: object, minimum: int = 0, maximum: int = 5) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return minimum
    return max(minimum, min(maximum, parsed))


def normalize_state(state: dict[str, Any] | None) -> dict[str, Any]:
    data = dict(DEFAULT_YUSHU_STATE)
    source = state or {}
    for key in (
        "relationship_warmth",
        "boundary_pressure",
        "trust",
        "playfulness",
        "proactive_desire",
        "unanswered_count",
        "user_autonomy",
        "real_world_transfer",
    ):
        data[key] = _clamp_int(source.get(key, data[key]))
    focus = str(source.get("practice_focus", data["practice_focus"]) or "").strip()
    data["practice_focus"] = focus if focus else data["practice_focus"]
    return data


def _normalize_keyword_list(
    keywords: object,
    default_keywords: tuple[str, ...],
) -> list[str]:
    source = keywords if isinstance(keywords, list) else list(default_keywords)
    normalized: list[str] = []
    seen: set[str] = set()
    for item in source:
        value = str(item or "").strip()
        if not value or value in seen:
            continue
        seen.add(value)
        normalized.append(value)
    return normalized


def get_coach_review_trigger_keywords(config: dict[str, Any] | None) -> list[str]:
    source = config or {}
    return _normalize_keyword_list(
        source.get("coach_review_trigger_keywords"),
        DEFAULT_COACH_REVIEW_TRIGGER_KEYWORDS,
    )


def get_coach_review_exit_keywords(config: dict[str, Any] | None) -> list[str]:
    source = config or {}
    return _normalize_keyword_list(
        source.get("coach_review_exit_keywords"),
        DEFAULT_COACH_REVIEW_EXIT_KEYWORDS,
    )


def summarize_keywords(keywords: list[str], preview_limit: int = 3) -> str:
    if not keywords:
        return "none"
    head = ", ".join(keywords[:preview_limit])
    return f"{head}..." if len(keywords) > preview_limit else head


def _keyword_hit(text: object, keywords: list[str]) -> bool:
    lowered = str(text or "")
    return any(trigger in lowered for trigger in keywords)


def is_coach_review_requested(text: object, keywords: list[str] | None = None) -> bool:
    return _keyword_hit(text, keywords or list(DEFAULT_COACH_REVIEW_TRIGGER_KEYWORDS))


def is_in_character_requested(text: object, keywords: list[str] | None = None) -> bool:
    return _keyword_hit(text, keywords or list(DEFAULT_COACH_REVIEW_EXIT_KEYWORDS))
