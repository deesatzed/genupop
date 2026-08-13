"""AT-12 plug-in gate (design §3).

Required user-supplied artifacts, all present or the gate returns BLOCK:

1. ``configs/locks/at12_<id>.yaml``
2. ``data/derived/event_<id>/restriction_tape.csv``
3. ``data/derived/event_<id>/observed_series.json`` with citation and hash
4. ``data/derived/event_<id>/cohort.json`` with citation and hash

The gate never writes a results directory and never invents an event.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

_BLOCK = "BLOCK"
_READY = "READY"
_FABRICATED = ("mock", "dummy", "fake", "placeholder")
_EVENT_ID_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_.-]*$")


def _root() -> Path:
    return Path.cwd()


def _required_paths(event_id: str, root: Path) -> dict[str, Path]:
    derived = root / "data" / "derived" / f"event_{event_id}"
    return {
        "lock": root / "configs" / "locks" / f"at12_{event_id}.yaml",
        "tape": derived / "restriction_tape.csv",
        "observed_series": derived / "observed_series.json",
        "cohort": derived / "cohort.json",
    }


def _relative_path_text(event_id: str) -> tuple[str, ...]:
    derived = f"data/derived/event_{event_id}"
    return (
        f"configs/locks/at12_{event_id}.yaml",
        f"{derived}/restriction_tape.csv",
        f"{derived}/observed_series.json",
        f"{derived}/cohort.json",
    )


def _contains_fabricated(text: str) -> bool:
    lowered = text.lower()
    return any(token in lowered for token in _FABRICATED)


def _string_leaves(obj: Any) -> list[str]:
    if isinstance(obj, str):
        return [obj]
    if isinstance(obj, dict):
        found: list[str] = []
        for key, value in obj.items():
            found.extend(_string_leaves(key))
            found.extend(_string_leaves(value))
        return found
    if isinstance(obj, (list, tuple)):
        found = []
        for item in obj:
            found.extend(_string_leaves(item))
        return found
    return []


def _load_mapping(path: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    return payload


def _has_citation_and_hash(payload: dict[str, Any]) -> bool:
    citation = payload.get("citation")
    digest = payload.get("hash")
    if not isinstance(citation, str) or not citation.strip():
        return False
    if not isinstance(digest, str) or not digest.strip():
        return False
    return True


def validate_at12(event_id: str) -> str:
    """Return 'BLOCK' if any required file is missing or looks fabricated.
    Return 'READY' only if all four exist and observed series has citation+hash
    and does not use mock/dummy/fake/placeholder in the path or payload.
    Never write a results directory.
    """
    if not isinstance(event_id, str):
        return _BLOCK
    event_id = event_id.strip()
    if not event_id or not _EVENT_ID_RE.fullmatch(event_id):
        return _BLOCK
    if _contains_fabricated(event_id):
        return _BLOCK
    if any(_contains_fabricated(text) for text in _relative_path_text(event_id)):
        return _BLOCK

    paths = _required_paths(event_id, _root())
    for path in paths.values():
        if not path.is_file():
            return _BLOCK

    for key in ("observed_series", "cohort"):
        payload = _load_mapping(paths[key])
        if payload is None or not _has_citation_and_hash(payload):
            return _BLOCK
        if any(_contains_fabricated(text) for text in _string_leaves(payload)):
            return _BLOCK

    return _READY
