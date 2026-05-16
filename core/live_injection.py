"""Stage 5B disabled/dry-run live injection helpers.

This module intentionally does not mutate ProviderRequest. It only decides
whether a future live injection would be eligible and, in dry-run mode, builds
the same fragment Stage 5A preview uses.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .memory_injection import build_memory_injection
from .prompt_fragments import build_coach_review_fragment, build_owner_private_fragment
from .scope import is_owner, is_private_owner, normalize_session_type
from .yushu_state import (
    DEFAULT_YUSHU_STATE,
    get_coach_review_exit_keywords,
    get_coach_review_trigger_keywords,
    is_coach_review_requested,
    is_in_character_requested,
    normalize_state,
)


REQUEST_FIELD_CANDIDATES = (
    "system_prompt",
    "prompt",
    "context",
    "system",
    "messages",
)


@dataclass(frozen=True)
class LiveInjectionDryRunResult:
    should_inject: bool
    skip_reason: str
    mode: str
    memory_count: int
    char_count: int
    request_fields: tuple[str, ...]
    scope_fields: tuple[str, ...] = ()
    message_type: str = ""
    session_type: str = ""
    fragment: str = ""


class LiveInjectionError(Exception):
    """Raised when Stage 5B live injection cannot safely apply."""


def _get_bool(config: dict[str, Any], key: str, default: bool = False) -> bool:
    return bool(config.get(key, default))


def _owners(config: dict[str, Any]) -> list[str]:
    owners = config.get("owner_user_ids", [])
    if not isinstance(owners, list):
        return []
    return [str(item or "").strip() for item in owners if str(item or "").strip()]


def _sender_id(event: Any) -> str:
    try:
        return str(event.get_sender_id() or "").strip()
    except Exception:
        return ""


def _message_text(event: Any) -> str:
    for attr_name in ("get_message_str", "get_message_text"):
        method = getattr(event, attr_name, None)
        if callable(method):
            try:
                return str(method() or "")
            except Exception:
                return ""
    return ""


def _normalize_session_type(value: object) -> str:
    return normalize_session_type(value)


def _umo_session_type(event: Any) -> str:
    umo = str(getattr(event, "unified_msg_origin", "") or "").strip()
    parts = umo.split(":")
    if len(parts) >= 2:
        return parts[1]
    return ""


def _session_type(event: Any) -> str:
    message_obj = getattr(event, "message_obj", None)
    for attr_name in ("type", "message_type"):
        value = getattr(message_obj, attr_name, None)
        if value:
            return str(value)
    session_id = str(getattr(message_obj, "session_id", "") or "")
    parts = session_id.split(":")
    if len(parts) >= 2:
        return parts[1]
    umo_session_type = _umo_session_type(event)
    if umo_session_type:
        return umo_session_type
    return ""


def _scope_fields(event: Any) -> tuple[str, ...]:
    fields: list[str] = []
    message_obj = getattr(event, "message_obj", None)
    if callable(getattr(event, "is_private_chat", None)):
        fields.append("event.is_private_chat")
    if callable(getattr(event, "get_sender_id", None)):
        fields.append("event.get_sender_id")
    if getattr(event, "unified_msg_origin", None):
        fields.append("event.unified_msg_origin")
    if getattr(message_obj, "type", None):
        fields.append("message_obj.type")
    if getattr(message_obj, "message_type", None):
        fields.append("message_obj.message_type")
    if getattr(message_obj, "session_id", None):
        fields.append("message_obj.session_id")
    return tuple(fields)


def _message_type_label(event: Any) -> str:
    session_type = _session_type(event)
    return _normalize_session_type(session_type) or "unknown"


def _private_owner_sender(event: Any, owners: list[str]) -> str | None:
    sender_id = _sender_id(event)
    if not sender_id:
        return None
    session_type = _session_type(event)
    if is_private_owner(session_type, sender_id, owners):
        return sender_id
    message_obj = getattr(event, "message_obj", None)
    session_id = str(getattr(message_obj, "session_id", "") or "").strip()
    if session_id and is_private_owner(session_type, session_id, owners):
        return sender_id
    umo = str(getattr(event, "unified_msg_origin", "") or "").strip()
    if umo and is_private_owner(session_type, umo, owners):
        return sender_id
    return None


def _is_private_scope(event: Any) -> bool:
    method = getattr(event, "is_private_chat", None)
    if callable(method):
        try:
            if bool(method()):
                return True
        except Exception:
            pass
    return _normalize_session_type(_session_type(event)) in {
        "private",
        "friend",
        "friendmessage",
        "private_message",
    }


def detect_request_fields(req: Any) -> tuple[str, ...]:
    if req is None:
        return ()
    return tuple(name for name in REQUEST_FIELD_CANDIDATES if hasattr(req, name))


def format_dry_run_log_summary(result: LiveInjectionDryRunResult) -> str:
    fields = ",".join(result.request_fields) or "none"
    scope_fields = ",".join(result.scope_fields) or "none"
    return (
        "yushu_live_injection_dry_run "
        f"skip_reason={result.skip_reason} "
        f"mode={result.mode} "
        f"memory_count={result.memory_count} "
        f"char_count={result.char_count} "
        f"fields={fields} "
        f"message_type={result.message_type or 'unknown'} "
        f"session_type={result.session_type or 'unknown'} "
        f"source_fields={scope_fields}"
    )


def format_applied_log_summary(result: LiveInjectionDryRunResult) -> str:
    return (
        "yushu_live_injection_applied "
        f"mode={result.mode} "
        f"memory_count={result.memory_count} "
        f"char_count={result.char_count} "
        "target=system_prompt"
    )


def apply_live_injection_to_system_prompt(
    req: Any,
    result: LiveInjectionDryRunResult,
) -> bool:
    """Append the dry-run fragment to req.system_prompt for Stage 5B live modes.

    Stage 5B live injection is owner-private normal/coach mode only. Group
    chats stay as ordinary AstrBot group/tool conversations: no owner private
    memory, no group live prompt injection. A future group-light fragment must
    use a separate switch such as group_light_prompt_enabled and default it to
    false.
    """

    if not result.should_inject or result.mode not in {"normal", "coach"}:
        return False
    if not result.fragment:
        return False
    if not hasattr(req, "system_prompt"):
        raise LiveInjectionError("missing_system_prompt")

    try:
        current = getattr(req, "system_prompt")
        new_value = (current or "") + "\n\n" + result.fragment
        setattr(req, "system_prompt", new_value)
    except Exception as exc:
        raise LiveInjectionError(type(exc).__name__) from exc
    return True


def _skip(reason: str, req: Any) -> LiveInjectionDryRunResult:
    return LiveInjectionDryRunResult(
        should_inject=False,
        skip_reason=reason,
        mode="skip",
        memory_count=0,
        char_count=0,
        request_fields=detect_request_fields(req),
        scope_fields=(),
    )


def _with_scope(
    result: LiveInjectionDryRunResult,
    event: Any,
) -> LiveInjectionDryRunResult:
    return LiveInjectionDryRunResult(
        should_inject=result.should_inject,
        skip_reason=result.skip_reason,
        mode=result.mode,
        memory_count=result.memory_count,
        char_count=result.char_count,
        request_fields=result.request_fields,
        scope_fields=_scope_fields(event),
        message_type=_message_type_label(event),
        session_type=_normalize_session_type(_session_type(event)) or "unknown",
        fragment=result.fragment,
    )


def build_live_injection_dry_run(
    event: Any,
    req: Any,
    store: Any,
    config: dict[str, Any] | None,
) -> LiveInjectionDryRunResult:
    """Build a Stage 5B dry-run decision without mutating req."""

    cfg = config or {}
    try:
        if not _get_bool(cfg, "prompt_injection_enabled", False):
            return _with_scope(_skip("prompt_injection_disabled", req), event)

        request_fields = detect_request_fields(req)
        if not request_fields:
            return _with_scope(_skip("request_api_unknown", req), event)

        owners = _owners(cfg)
        if not owners:
            return _with_scope(_skip("owner_not_configured", req), event)

        # Group messages must not receive owner private memories or any Stage
        # 5B-3 live prompt fragment, even when prompt_injection_enabled is true.
        if not _is_private_scope(event):
            return _with_scope(_skip("not_private", req), event)

        owner_user_id = _private_owner_sender(event, owners)
        if owner_user_id is None:
            if is_owner(_sender_id(event), owners):
                return _with_scope(_skip("not_private", req), event)
            return _with_scope(_skip("not_owner", req), event)

        injected = build_memory_injection(store, owner_user_id, cfg)
        items = injected["items"] if injected.get("enabled") else []

        state = normalize_state(DEFAULT_YUSHU_STATE)
        message_text = _message_text(event)
        trigger_keywords = get_coach_review_trigger_keywords(cfg)
        exit_keywords = get_coach_review_exit_keywords(cfg)
        if (
            _get_bool(cfg, "coach_review_enabled", True)
            and not is_in_character_requested(message_text, exit_keywords)
            and is_coach_review_requested(message_text, trigger_keywords)
        ):
            mode = "coach"
            fragment = build_coach_review_fragment(items, state)
        else:
            mode = "normal"
            fragment = build_owner_private_fragment(items, state)

        return _with_scope(
            LiveInjectionDryRunResult(
                should_inject=True,
                skip_reason="",
                mode=mode,
                memory_count=len(items),
                char_count=len(fragment),
                request_fields=request_fields,
                fragment=fragment,
            ),
            event,
        )
    except Exception:
        return _with_scope(_skip("fail_closed", req), event)
