"""Read Blender's cached repository state for update notifications."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re
import time

import bpy

from ..constants import ADDON_ID, ADDON_PACKAGE


STATUS_UNKNOWN = "UNKNOWN"
STATUS_CURRENT = "CURRENT"
STATUS_UPDATE_AVAILABLE = "UPDATE_AVAILABLE"
STATUS_MANUAL = "MANUAL"
STATUS_UNAVAILABLE = "UNAVAILABLE"
STATUS_ERROR = "ERROR"

_MAX_INDEX_BYTES = 16 * 1024 * 1024
_VERSION_PATTERN = re.compile(
    r"^v?(?P<core>[0-9]+(?:\.[0-9]+)*)(?:-(?P<pre>[0-9A-Za-z.-]+))?(?:\+[0-9A-Za-z.-]+)?$",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class UpdateStatus:
    status: str = STATUS_UNKNOWN
    local_version: str = ""
    remote_version: str = ""
    repository_name: str = ""
    repository_module: str = ""
    repository_url: str = ""
    index_path: str = ""
    index_mtime: float = 0.0
    message: str = ""

    @property
    def update_available(self) -> bool:
        return self.status == STATUS_UPDATE_AVAILABLE


_cached_signature = None
_cached_status = None


def get_update_status(context=None, *, force=False) -> UpdateStatus:
    """Return update information without performing network or install actions."""
    global _cached_signature, _cached_status

    context = context or bpy.context
    manifest_path = _manifest_path()
    repository, repository_path = _find_repository(context, manifest_path)
    index_path = (
        repository_path / ".blender_ext" / "index.json"
        if repository_path is not None
        else None
    )
    signature = _cache_signature(manifest_path, index_path, repository)
    if not force and signature == _cached_signature and _cached_status is not None:
        return _cached_status

    status = _build_status(
        manifest_path,
        repository,
        repository_path,
        index_path,
    )
    _cached_signature = signature
    _cached_status = status
    return status


def reset_cache() -> None:
    global _cached_signature, _cached_status

    _cached_signature = None
    _cached_status = None


def online_access_enabled() -> bool:
    return bool(getattr(getattr(bpy, "app", None), "online_access", False))


def compare_versions(left: str, right: str):
    """Compare two Blender extension versions, returning -1, 0, 1, or None."""
    left_key = _version_key(left)
    right_key = _version_key(right)
    if left_key is None or right_key is None:
        return None

    left_core, left_pre = left_key
    right_core, right_pre = right_key
    if left_core != right_core:
        return -1 if left_core < right_core else 1
    if left_pre == right_pre:
        return 0
    if left_pre is None:
        return 1
    if right_pre is None:
        return -1

    for left_part, right_part in zip(left_pre, right_pre):
        if left_part == right_part:
            continue
        return -1 if left_part < right_part else 1
    return -1 if len(left_pre) < len(right_pre) else 1


def _manifest_path() -> Path:
    return Path(__file__).resolve().parents[1] / "blender_manifest.toml"


def _build_status(manifest_path, repository, repository_path, index_path):
    local_version, manifest_error = _read_local_version(manifest_path)
    if manifest_error:
        return UpdateStatus(
            status=STATUS_ERROR,
            local_version=local_version,
            message=manifest_error,
        )

    repository_name = str(getattr(repository, "name", "")) if repository else ""
    repository_module = str(getattr(repository, "module", "")) if repository else ""
    repository_url = str(getattr(repository, "remote_url", "")) if repository else ""
    common = {
        "local_version": local_version,
        "repository_name": repository_name,
        "repository_module": repository_module,
        "repository_url": repository_url,
        "index_path": str(index_path) if index_path else "",
    }

    if repository is None or repository_path is None:
        return UpdateStatus(
            status=STATUS_MANUAL,
            message="This installation is not associated with a Blender extension repository.",
            **common,
        )
    if not bool(getattr(repository, "use_remote_url", False)) or not repository_url:
        return UpdateStatus(
            status=STATUS_MANUAL,
            message="This repository has no remote source managed by Blender.",
            **common,
        )
    if not index_path.is_file():
        return UpdateStatus(
            status=STATUS_UNAVAILABLE,
            message="Blender has not cached the remote repository index yet.",
            **common,
        )

    try:
        index_mtime = index_path.stat().st_mtime
        remote_version = _read_remote_version(index_path)
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        return UpdateStatus(
            status=STATUS_ERROR,
            message=f"Blender's repository index could not be read: {exc}",
            **common,
        )

    if remote_version is None:
        return UpdateStatus(
            status=STATUS_UNAVAILABLE,
            index_mtime=index_mtime,
            message="The cached repository index does not contain Quick N-panel.",
            **common,
        )

    comparison = compare_versions(local_version, remote_version)
    if comparison is None:
        return UpdateStatus(
            status=STATUS_ERROR,
            remote_version=remote_version,
            index_mtime=index_mtime,
            message="The installed or cached version is not a valid extension version.",
            **common,
        )

    if comparison < 0:
        status = STATUS_UPDATE_AVAILABLE
        message = "A newer Quick N-panel version is available in Blender Extensions."
    elif comparison > 0:
        status = STATUS_CURRENT
        message = "The installed version is newer than Blender's cached repository version."
    else:
        status = STATUS_CURRENT
        message = "Quick N-panel is up to date according to Blender's cached repository index."

    return UpdateStatus(
        status=status,
        remote_version=remote_version,
        index_mtime=index_mtime,
        message=message,
        **common,
    )


def _read_local_version(manifest_path):
    try:
        raw = manifest_path.read_text(encoding="utf-8")
        try:
            import tomllib

            manifest = tomllib.loads(raw)
        except ImportError:
            match = re.search(r'^version\s*=\s*["\']([^"\']+)["\']', raw, re.MULTILINE)
            manifest = {"version": match.group(1)} if match else {}
    except (OSError, ValueError, TypeError) as exc:
        return "", f"The extension manifest could not be read: {exc}"

    version = str(manifest.get("version", "")).strip()
    if not version or _version_key(version) is None:
        return version, "The extension manifest does not contain a valid version."
    return version, ""


def _read_remote_version(index_path):
    if index_path.stat().st_size > _MAX_INDEX_BYTES:
        raise ValueError("repository index exceeds the safety limit")
    payload = json.loads(index_path.read_text(encoding="utf-8"))
    entries = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(entries, list):
        raise ValueError("repository index has no data list")

    versions = []
    for entry in entries:
        if not isinstance(entry, dict) or entry.get("id") != ADDON_ID:
            continue
        version = str(entry.get("version", "")).strip()
        if _version_key(version) is not None:
            versions.append(version)

    if not versions:
        return None
    return max(versions, key=_VersionSortKey)


class _VersionSortKey:
    def __init__(self, version):
        self.version = version

    def __lt__(self, other):
        return compare_versions(self.version, other.version) < 0


def _version_key(version):
    if not isinstance(version, str):
        return None
    match = _VERSION_PATTERN.fullmatch(version.strip())
    if match is None:
        return None

    core = tuple(int(part) for part in match.group("core").split("."))
    pre = match.group("pre")
    if pre is None:
        return core, None

    identifiers = []
    for identifier in pre.split("."):
        if not identifier:
            return None
        if identifier.isdigit():
            identifiers.append((0, int(identifier)))
        else:
            identifiers.append((1, identifier.casefold()))
    return core, tuple(identifiers)


def _find_repository(context, manifest_path):
    preferences = getattr(context, "preferences", None)
    extensions = getattr(preferences, "extensions", None)
    repositories = getattr(extensions, "repos", ())
    install_root = manifest_path.parent.resolve()

    for repository in repositories:
        repository_directory = str(getattr(repository, "directory", ""))
        if not repository_directory:
            continue
        try:
            if install_root == (Path(repository_directory).resolve() / ADDON_ID):
                return repository, Path(repository_directory).resolve()
        except OSError:
            continue

    package_parts = ADDON_PACKAGE.split(".")
    if len(package_parts) >= 3 and package_parts[0] == "bl_ext":
        repository_module = package_parts[1]
        for repository in repositories:
            if getattr(repository, "module", "") == repository_module:
                directory = str(getattr(repository, "directory", ""))
                if directory:
                    return repository, Path(directory).resolve()
    return None, None


def _cache_signature(manifest_path, index_path, repository):
    return (
        _file_signature(manifest_path),
        _file_signature(index_path),
        str(getattr(repository, "module", "")) if repository else "",
        str(getattr(repository, "directory", "")) if repository else "",
        str(getattr(repository, "remote_url", "")) if repository else "",
        bool(getattr(repository, "use_remote_url", False)) if repository else False,
    )


def _file_signature(path):
    if path is None:
        return None
    try:
        stat = path.stat()
    except OSError:
        return None
    return stat.st_mtime_ns, stat.st_size


def format_index_time(timestamp):
    if not timestamp:
        return "Unknown"
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(timestamp))
