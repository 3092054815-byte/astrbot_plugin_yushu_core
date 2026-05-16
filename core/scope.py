"""Pure scope helpers for yushu_core.

These functions do not read or write runtime state. They only normalize input
values and answer whether the current context belongs to owner/private/group
scope.
"""

from __future__ import annotations

from collections.abc import Iterable


PRIVATE_SESSION_TYPES = {"private", "friend", "friendmessage", "privatemessage"}
GROUP_SESSION_TYPES = {"group", "groupmessage"}


def _normalize_id(value: object) -> str:
    return str(value or "").strip()


def normalize_session_type(session_type: object) -> str:
    value = str(session_type or "").strip().lower().replace(" ", "")
    if "." in value:
        value = value.rsplit(".", 1)[-1]
    return value.replace("_", "").replace("-", "")


def _normalize_session_type(session_type: object) -> str:
    return normalize_session_type(session_type)


def _owner_set(owner_user_ids: Iterable[object] | None) -> set[str]:
    if not owner_user_ids:
        return set()
    return {_normalize_id(item) for item in owner_user_ids if _normalize_id(item)}


def is_owner(user_id: object, owner_user_ids: Iterable[object] | None) -> bool:
    """Return whether user_id is listed as an owner."""

    normalized = _normalize_id(user_id)
    return bool(normalized) and normalized in _owner_set(owner_user_ids)


def is_private_owner(
    session_type: object,
    user_id: object,
    owner_user_ids: Iterable[object] | None,
) -> bool:
    """Return whether the context is an owner private/friend session."""

    return _normalize_session_type(session_type) in PRIVATE_SESSION_TYPES and is_owner(
        user_id, owner_user_ids
    )


def is_group_scope(session_type: object) -> bool:
    """Return whether the context is a group session."""

    return _normalize_session_type(session_type) in GROUP_SESSION_TYPES
