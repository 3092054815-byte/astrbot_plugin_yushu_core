"""Pure proactive reason-gate helpers.

This module never calls proactive_chat and never sends messages. It only
returns a structured decision preview for later integration stages.
"""

from __future__ import annotations

from dataclasses import dataclass


OPENING_DO_NOT_SEND = "do_not_send"
OPENING_CONTINUE_THREAD = "continue_thread"
OPENING_CHECK_PROGRESS = "check_progress"


@dataclass(frozen=True)
class OpeningDecision:
    send_allowed: bool
    opening_reason: str
    reason_text: str

    def as_dict(self) -> dict[str, object]:
        return {
            "send_allowed": self.send_allowed,
            "opening_reason": self.opening_reason,
            "reason_text": self.reason_text,
        }


def decide_opening_reason(
    unanswered_count: int = 0,
    open_thread_exists: bool = False,
) -> OpeningDecision:
    """Return a pure preview decision for a possible proactive opening."""

    try:
        unanswered = int(unanswered_count)
    except (TypeError, ValueError):
        unanswered = 0

    if unanswered >= 3:
        return OpeningDecision(
            send_allowed=False,
            opening_reason=OPENING_DO_NOT_SEND,
            reason_text="unanswered_count_reached_pause_threshold",
        )

    if open_thread_exists:
        return OpeningDecision(
            send_allowed=True,
            opening_reason=OPENING_CONTINUE_THREAD,
            reason_text="open_thread_exists",
        )

    if unanswered == 0:
        return OpeningDecision(
            send_allowed=True,
            opening_reason=OPENING_CHECK_PROGRESS,
            reason_text="low_pressure_check_progress",
        )

    return OpeningDecision(
        send_allowed=False,
        opening_reason=OPENING_DO_NOT_SEND,
        reason_text="no_natural_opening_reason",
    )
