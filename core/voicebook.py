"""Read-only Voicebook helpers."""

from __future__ import annotations

from pathlib import Path


VOICEBOOK_PATH = Path("/root/astrbot/data/patch_work/yushu_design/voicebook_v2.md")
CONTAINER_VOICEBOOK_PATH = Path("/AstrBot/data/patch_work/yushu_design/voicebook_v2.md")


def _resolve_voicebook_path(path: Path | str) -> Path:
    voicebook_path = Path(path)
    if voicebook_path.exists():
        return voicebook_path
    if voicebook_path == VOICEBOOK_PATH and CONTAINER_VOICEBOOK_PATH.exists():
        return CONTAINER_VOICEBOOK_PATH
    return voicebook_path


def read_voicebook(path: Path | str = VOICEBOOK_PATH) -> str:
    """Read the Voicebook v2 markdown file without modifying it."""

    voicebook_path = _resolve_voicebook_path(path)
    if not voicebook_path.exists():
        return ""
    return voicebook_path.read_text(encoding="utf-8")


def voicebook_status(path: Path | str = VOICEBOOK_PATH) -> dict[str, object]:
    """Return a small read-only status summary for the Voicebook file."""

    voicebook_path = _resolve_voicebook_path(path)
    if not voicebook_path.exists():
        return {"exists": False, "chars": 0}
    text = voicebook_path.read_text(encoding="utf-8")
    return {"exists": True, "chars": len(text)}
