from pathlib import Path

import pytest

from termagent.sandbox import SandboxError, resolve_in_workspace


def test_relative_file_inside_workspace(tmp_path: Path) -> None:
    resolved = resolve_in_workspace(tmp_path, "foo.txt")
    assert resolved == (tmp_path / "foo.txt").resolve()


def test_absolute_path_inside_workspace(tmp_path: Path) -> None:
    target = (tmp_path / "foo.txt").resolve()
    assert resolve_in_workspace(tmp_path, str(target)) == target


def test_parent_escape_rejected(tmp_path: Path) -> None:
    with pytest.raises(SandboxError, match="workspace"):
        resolve_in_workspace(tmp_path, "../etc/passwd")


def test_absolute_path_outside_workspace_rejected(tmp_path: Path) -> None:
    with pytest.raises(SandboxError, match="workspace"):
        resolve_in_workspace(tmp_path, "/etc/passwd")
