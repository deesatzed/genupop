"""Framing linter (GOAL §12, design §4).

Scan ``src/`` and ``tests/`` for clinician-blame lexemes. Allowed language
is *fidelity*, *adherence to policy*, and *deviation*.

A result key ``resistance`` is forbidden unless ``rounds_to_effective`` is
a sibling. Slice-0 writers must emit the frequency series next to
``rounds_to_effective``. A resistance-only figure writer is a defect.
"""

from __future__ import annotations

import ast
import inspect
import json
from pathlib import Path

from stewardsim.runner import _write_results
from stewardsim.simulate import SimulateResult

_SRC = Path("src")
_TESTS = Path("tests")
_SKIP_DIR_NAMES = frozenset({"__pycache__", ".pytest_cache"})
_TEXT_SUFFIXES = frozenset({".py", ".yaml", ".yml", ".csv", ".md", ".json", ".txt"})

# Concatenated so this file does not contain the banned lexemes.
_BANNED = (
    "inappropriate" + " prescribing",
    "prescriber" + " error",
    "compl" + "iance",
    "mis" + "use",
)

_RESISTANCE_KEY = "resistance"
_ROUNDS_KEY = "rounds_to_effective"
_FREQ_KEYS = frozenset({"frequencies", "determinant_trajectories"})
_FIGURE_TOKENS = ("figure", "plot", "chart")


def _iter_text_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if any(part in _SKIP_DIR_NAMES for part in path.parts):
            continue
        if path.suffix not in _TEXT_SUFFIXES:
            continue
        files.append(path)
    return files


def _iter_py_files(root: Path) -> list[Path]:
    return [path for path in _iter_text_files(root) if path.suffix == ".py"]


def _string_constant(node: ast.AST | None) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _dict_keys(node: ast.AST) -> set[str]:
    keys: set[str] = set()
    if isinstance(node, ast.Dict):
        for key in node.keys:
            name = _string_constant(key)
            if name is not None:
                keys.add(name)
    elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
        if node.func.id == "dict":
            for keyword in node.keywords:
                if keyword.arg is not None:
                    keys.add(keyword.arg)
    return keys


def _collect_string_keys(node: ast.AST) -> set[str]:
    keys: set[str] = set()
    for child in ast.walk(node):
        keys.update(_dict_keys(child))
        if isinstance(child, ast.Subscript):
            name = _string_constant(child.slice)
            if name is not None:
                keys.add(name)
    return keys


def _annotated_fields(node: ast.ClassDef) -> set[str]:
    names: set[str] = set()
    for stmt in node.body:
        if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
            names.add(stmt.target.id)
        elif isinstance(stmt, ast.Assign):
            for target in stmt.targets:
                if isinstance(target, ast.Name):
                    names.add(target.id)
    return names


def _is_figure_name(name: str) -> bool:
    lowered = name.lower()
    return any(token in lowered for token in _FIGURE_TOKENS)


def test_src_and_tests_have_no_banned_framing_lexemes() -> None:
    hits: list[str] = []
    for root in (_SRC, _TESTS):
        for path in _iter_text_files(root):
            text = path.read_text(encoding="utf-8").lower()
            for phrase in _BANNED:
                if phrase in text:
                    hits.append(f"{path}: {phrase!r}")
    assert not hits, "GOAL §12 banned lexeme(s): " + "; ".join(hits)


def test_result_key_resistance_has_sibling_rounds_to_effective() -> None:
    hits: list[str] = []
    for path in _iter_py_files(_SRC):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            keys = _dict_keys(node)
            if _RESISTANCE_KEY in keys and _ROUNDS_KEY not in keys:
                hits.append(f"{path}: dict keys {sorted(keys)}")
            if isinstance(node, ast.ClassDef):
                fields = _annotated_fields(node)
                if _RESISTANCE_KEY in fields and _ROUNDS_KEY not in fields:
                    hits.append(f"{path}::{node.name}: fields {sorted(fields)}")
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                keys = _collect_string_keys(node)
                if _RESISTANCE_KEY in keys and _ROUNDS_KEY not in keys:
                    hits.append(f"{path}::{node.name}: keys {sorted(keys)}")
    assert not hits, (
        f"{_RESISTANCE_KEY!r} without sibling {_ROUNDS_KEY!r}: " + "; ".join(hits)
    )


def test_no_resistance_only_figure_writer() -> None:
    hits: list[str] = []
    for path in _iter_py_files(_SRC):
        text = path.read_text(encoding="utf-8")
        if _is_figure_name(path.stem) and (
            _RESISTANCE_KEY in text and _ROUNDS_KEY not in text
        ):
            hits.append(str(path))
        tree = ast.parse(text, filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if not _is_figure_name(node.name):
                continue
            source = ast.unparse(node)
            if _RESISTANCE_KEY in source and _ROUNDS_KEY not in source:
                hits.append(f"{path}::{node.name}")
    assert not hits, "resistance-only figure writer: " + "; ".join(hits)


def test_slice0_results_writer_pairs_frequencies_with_rounds_to_effective() -> None:
    source = inspect.getsource(_write_results)
    tree = ast.parse(source)
    keys = _collect_string_keys(tree)
    assert _ROUNDS_KEY in keys
    assert keys & _FREQ_KEYS, f"frequency series missing from writer keys {sorted(keys)}"
    if _RESISTANCE_KEY in keys:
        assert _ROUNDS_KEY in keys

    fields = set(SimulateResult.model_fields)
    assert "frequencies" in fields
    assert _ROUNDS_KEY in fields
    if _RESISTANCE_KEY in fields:
        assert _ROUNDS_KEY in fields


def test_written_results_json_pairs_resistance_with_rounds_to_effective() -> None:
    root = Path("output")
    if not root.is_dir():
        return
    for path in sorted(root.rglob("results.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        assert isinstance(payload, dict), path
        keys = set(payload)
        if _RESISTANCE_KEY in keys:
            assert _ROUNDS_KEY in keys, path
        if keys & _FREQ_KEYS:
            assert _ROUNDS_KEY in keys, path
