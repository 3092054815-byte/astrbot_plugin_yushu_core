from __future__ import annotations

import unittest

from core.coach_history import (
    COACH_LIVE_MODE,
    mark_final_assistant_message_no_save,
    mark_live_mode_history_flags,
    should_mark_coach_response_no_history,
)


class DummyEvent:
    def __init__(self):
        self.extras = {}

    def get_extra(self, key):
        return self.extras.get(key)

    def set_extra(self, key, value):
        self.extras[key] = value


class DummyMessage:
    def __init__(self, role: str, content: str = ""):
        self.role = role
        self.content = content
        self._no_save = False


class TempMessage(DummyMessage):
    def __init__(self, role: str, content: str = ""):
        super().__init__(role, content)
        self.mark_as_temp_called = False

    def mark_as_temp(self):
        self.mark_as_temp_called = True
        self._no_save = True


class CoachHistoryTest(unittest.TestCase):
    def test_should_mark_coach_response_when_enabled_and_event_marked(self) -> None:
        event = DummyEvent()
        event.set_extra("yushu_live_mode", COACH_LIVE_MODE)
        event.set_extra("yushu_coach_review_no_history", True)

        self.assertTrue(
            should_mark_coach_response_no_history(
                {"coach_review_no_history_enabled": True},
                event,
            )
        )

    def test_mark_live_mode_flags_sets_coach_no_history_when_enabled(self) -> None:
        event = DummyEvent()

        mark_live_mode_history_flags(
            event,
            "coach",
            {"coach_review_no_history_enabled": True},
        )

        self.assertEqual(event.get_extra("yushu_live_mode"), "coach")
        self.assertTrue(event.get_extra("yushu_coach_review_no_history"))

    def test_mark_live_mode_flags_sets_normal_without_no_history(self) -> None:
        event = DummyEvent()

        mark_live_mode_history_flags(
            event,
            "normal",
            {"coach_review_no_history_enabled": True},
        )

        self.assertEqual(event.get_extra("yushu_live_mode"), "normal")
        self.assertFalse(event.get_extra("yushu_coach_review_no_history"))

    def test_mark_live_mode_flags_respects_disabled_switch(self) -> None:
        event = DummyEvent()

        mark_live_mode_history_flags(
            event,
            "coach",
            {"coach_review_no_history_enabled": False},
        )

        self.assertEqual(event.get_extra("yushu_live_mode"), "coach")
        self.assertFalse(event.get_extra("yushu_coach_review_no_history"))

    def test_mark_live_mode_flags_ignores_non_applied_group_skip(self) -> None:
        event = DummyEvent()

        mark_live_mode_history_flags(
            event,
            "skip",
            {"coach_review_no_history_enabled": True},
        )

        self.assertIsNone(event.get_extra("yushu_live_mode"))
        self.assertIsNone(event.get_extra("yushu_coach_review_no_history"))

    def test_should_not_mark_normal_mode(self) -> None:
        event = DummyEvent()
        event.set_extra("yushu_live_mode", "normal")
        event.set_extra("yushu_coach_review_no_history", False)

        self.assertFalse(
            should_mark_coach_response_no_history(
                {"coach_review_no_history_enabled": True},
                event,
            )
        )

    def test_should_not_mark_when_switch_disabled(self) -> None:
        event = DummyEvent()
        event.set_extra("yushu_live_mode", COACH_LIVE_MODE)
        event.set_extra("yushu_coach_review_no_history", True)

        self.assertFalse(
            should_mark_coach_response_no_history(
                {"coach_review_no_history_enabled": False},
                event,
            )
        )

    def test_mark_final_assistant_uses_mark_as_temp_when_available(self) -> None:
        first = TempMessage("assistant", "old assistant")
        user = DummyMessage("user", "user")
        final = TempMessage("assistant", "coach reply")

        marked = mark_final_assistant_message_no_save([first, user, final])

        self.assertTrue(marked)
        self.assertFalse(first._no_save)
        self.assertTrue(final._no_save)
        self.assertTrue(final.mark_as_temp_called)

    def test_mark_final_assistant_falls_back_to_no_save_attr(self) -> None:
        final = DummyMessage("assistant", "coach reply")

        marked = mark_final_assistant_message_no_save([DummyMessage("user"), final])

        self.assertTrue(marked)
        self.assertTrue(final._no_save)

    def test_mark_final_assistant_returns_false_without_assistant(self) -> None:
        self.assertFalse(mark_final_assistant_message_no_save([DummyMessage("user")]))


if __name__ == "__main__":
    unittest.main()
