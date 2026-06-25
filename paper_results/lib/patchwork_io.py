"""Shared IO and path helpers for the paper_results build scripts.

The three build scripts under ``paper_results`` (build_fixation_buggy_method.py,
build_ide_navigation.py, build_patch_usage.py) all need the same things: the repo
root, the gaze-data directory, the timing CSV path, the study-PID-to-disk-name
mapping, and the project-Java path filtering. Those helpers live here so each
build script imports them rather than redefining them.
"""

from __future__ import annotations

import os
from pathlib import Path


def find_root() -> Path:
    """Repo root. PATCHWORK_ROOT env var if set, else the parent of the nearest
    ancestor directory named 'patchwork_analysis'."""
    env = os.environ.get("PATCHWORK_ROOT")
    if env:
        return Path(env)
    for parent in Path(__file__).resolve().parents:
        if parent.name == "patchwork_analysis":
            return parent.parent
    raise RuntimeError(
        "Could not locate a 'patchwork_analysis' directory above "
        f"{__file__}; set PATCHWORK_ROOT to the repo root."
    )


ROOT = find_root()
DATA = Path(os.environ.get("PATCHWORK_DATA", ROOT / "patchwork_data"))
TIMING_CSV = ROOT / "patchwork_analysis" / "timing_correctness_data.csv"


def disk_pid(pid: str) -> str:
    """Study PID (P3_0) to on-disk directory name (P3-0)."""
    return pid.replace("_", "-")


def _is_library_path(path: str) -> bool:
    """True for JDK / library / archive paths that are not project files.

    Excludes absolute drive-letter paths (e.g. C:/Users/.../temurin.../
    lib/src.zip!/...), archive members (`src.zip!`, `.jar!`), and compiled
    `.class` files. These are JDK internals or dependencies a participant
    navigated into, never edits of the project under repair.
    """
    if not path:
        return True
    if len(path) >= 2 and path[1] == ":":  # drive-letter absolute (C:/...)
        return True
    if "src.zip!" in path or ".jar!" in path:
        return True
    if path.endswith(".class"):
        return True
    return False


def is_project_java(path: str) -> bool:
    """A real, editable project Java file (not a JDK/library path, not .backup)."""
    return path.endswith(".java") and not _is_library_path(path)
