"""State-machine defaults for the yushu_core skeleton."""

from __future__ import annotations


DEFAULT_STATE = {
    "mode": "in_character",
    "warmth": 0.45,
    "boundary": 0.65,
    "coach_review": False,
    "last_signal": "none",
}


def clamp(value: object, lower: float = 0.0, upper: float = 1.0) -> float:
    """Clamp a numeric value into [lower, upper]."""

    try:
        number = float(value)
    except (TypeError, ValueError):
        number = lower
    return max(lower, min(upper, number))


def normalize_state(state: dict[str, object] | None) -> dict[str, object]:
    """Return a normalized state dict without mutating the input."""

    result = dict(DEFAULT_STATE)
    if state:
        result.update(state)
    result["warmth"] = clamp(result.get("warmth"))
    result["boundary"] = clamp(result.get("boundary"))
    result["coach_review"] = bool(result.get("coach_review"))
    result["mode"] = str(result.get("mode") or DEFAULT_STATE["mode"])
    result["last_signal"] = str(result.get("last_signal") or "none")
    return result
