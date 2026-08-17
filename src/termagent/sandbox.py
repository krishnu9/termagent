from pathlib import Path


class SandboxError(ValueError):
    """Raised when a path resolves outside the workspace."""


def resolve_in_workspace(workspace: Path, path: str) -> Path:
    root = workspace.resolve()
    candidate = Path(path)
    resolved = (candidate if candidate.is_absolute() else root / candidate).resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise SandboxError(f"path {path!r} is outside the workspace {root}") from exc
    return resolved
