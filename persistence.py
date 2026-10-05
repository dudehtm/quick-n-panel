"""Sidecar persistence for settings Blender removes when disabling an add-on."""

import json
import math
import os
from pathlib import Path
import struct
import tempfile
import time
import zipfile

from .constants import (
    ADDON_PACKAGE,
    BUILTIN_ICON_ITEMS,
    DEFAULT_COMPACT_POPUP_WIDTH,
    DEFAULT_ICON_COLOR_MODE,
    DISPLAY_MODE_ITEMS,
    ICON_COLOR_MODE_ITEMS,
    MAX_FAVORITE_RECORDS,
)


FORMAT_NAME = "quick_n_panel.preferences"
FORMAT_VERSION = 9
SIDECAR_FILENAME = "preferences.json"
LEGACY_SIDECAR_FILENAMES = ("preferences-v1.json",)
MAX_SIDECAR_BYTES = 8 * 1024 * 1024
MAX_PORTABLE_BACKUP_BYTES = 64 * 1024 * 1024
MAX_PORTABLE_ARCHIVE_BYTES = MAX_PORTABLE_BACKUP_BYTES + 1024 * 1024
MAX_PORTABLE_ARCHIVE_ENTRIES = 5000
MAX_GROUP_RECORDS = 256
MAX_TARGET_RECORDS = 4096
MAX_NEW_ADDON_RECORDS = 256
MAX_OBSERVED_ADDON_RECORDS = 4096
SAVE_DEBOUNCE_SECONDS = 0.75
PORTABLE_PREFERENCES_FILENAME = "preferences.json"

_preferences_dirty = False
_save_timer_registered = False


class UnsupportedPreferenceVersion(ValueError):
    pass

ROOT_FIELDS = (
    "target_index",
    "group_index",
    "default_groups_initialized",
    "default_group_icons_initialized",
    "icon_enum_schema_version",
    "favorite_index",
    "new_addons_initialized",
    "observed_addons_initialized",
    "favorites_schema_version",
    "favorite_1",
    "favorite_2",
    "favorite_3",
    "last_target_key",
    "last_observed_target_key",
    "activity_schema_version",
    "starter_recents_pending",
    "compact_popup_width",
    "display_mode",
    "icon_color_mode",
    "icon_tint_color",
    "max_search_results",
    "include_builtin_tabs",
    "auto_open_library",
    "auto_open_categories",
)

COLLECTION_FIELDS = {
    "groups": (
        "name",
        "group_id",
        "display_name",
        "icon_name",
        "bundled_icon",
        "icon_path",
    ),
    "targets": (
        "name",
        "native_key",
        "native_category",
        "origin_key",
        "panel_identifiers",
        "display_name",
        "panel_labels",
        "source_modules",
        "open_count",
        "first_opened_at",
        "last_opened_at",
        "group_id",
        "group_order",
        "group_memberships",
        "hidden",
        "icon_name",
        "bundled_icon",
        "icon_path",
    ),
    "favorites": (
        "name",
        "target_key",
    ),
    "new_addons": (
        "name",
        "addon_key",
        "target_key",
        "discovered_at",
    ),
    "observed_addons": (
        "name",
        "addon_key",
    ),
}

_ROOT_BOOL_FIELDS = {
    "default_groups_initialized",
    "default_group_icons_initialized",
    "starter_recents_pending",
    "include_builtin_tabs",
    "auto_open_library",
    "auto_open_categories",
    "new_addons_initialized",
    "observed_addons_initialized",
}
_ROOT_INT_FIELDS = {
    "target_index",
    "group_index",
    "icon_enum_schema_version",
    "favorite_index",
    "favorites_schema_version",
    "activity_schema_version",
    "compact_popup_width",
    "max_search_results",
}
_ROOT_STRING_FIELDS = {
    "favorite_1",
    "favorite_2",
    "favorite_3",
    "last_target_key",
    "last_observed_target_key",
}
_RECORD_STRING_FIELDS = {
    "name",
    "group_id",
    "group_memberships",
    "display_name",
    "icon_name",
    "bundled_icon",
    "icon_path",
    "native_key",
    "native_category",
    "origin_key",
    "panel_identifiers",
    "panel_labels",
    "source_modules",
    "first_opened_at",
    "last_opened_at",
    "target_key",
    "addon_key",
    "discovered_at",
}
_BUILTIN_ICON_IDS = {item[0] for item in BUILTIN_ICON_ITEMS}
_DISPLAY_MODE_IDS = {item[0] for item in DISPLAY_MODE_ITEMS}
_ICON_COLOR_MODE_IDS = {item[0] for item in ICON_COLOR_MODE_ITEMS}

_ROOT_DEFAULTS = {
    "target_index": 0,
    "group_index": 0,
    "default_groups_initialized": False,
    "default_group_icons_initialized": False,
    "icon_enum_schema_version": 0,
    "favorite_index": 0,
    "new_addons_initialized": False,
    "observed_addons_initialized": False,
    "favorites_schema_version": 0,
    "favorite_1": "",
    "favorite_2": "",
    "favorite_3": "",
    "last_target_key": "",
    "last_observed_target_key": "",
    "activity_schema_version": 0,
    "starter_recents_pending": False,
    "compact_popup_width": DEFAULT_COMPACT_POPUP_WIDTH,
    "display_mode": "BOTH",
    "icon_color_mode": DEFAULT_ICON_COLOR_MODE,
    "icon_tint_color": (1.0, 1.0, 1.0),
    "max_search_results": 128,
    "include_builtin_tabs": False,
    "auto_open_library": False,
    "auto_open_categories": False,
}


def data_directory(*, create=False, path="") -> Path:
    import bpy

    directory = bpy.utils.extension_path_user(
        ADDON_PACKAGE,
        path=path,
        create=create,
    )
    if not directory:
        raise OSError("Blender did not provide an extension data directory")
    return Path(directory)


def sidecar_path(*, create=False) -> Path:
    return data_directory(create=create) / SIDECAR_FILENAME


def request_save(*_args) -> None:
    """Mark preferences dirty and save once Blender becomes idle."""
    global _preferences_dirty, _save_timer_registered

    _preferences_dirty = True
    if _save_timer_registered:
        return

    try:
        import bpy

        timers = getattr(getattr(bpy, "app", None), "timers", None)
        if timers is None or not hasattr(timers, "register"):
            return
        timers.register(_save_timer_callback, first_interval=SAVE_DEBOUNCE_SECONDS)
        _save_timer_registered = True
    except (AttributeError, RuntimeError, ValueError):
        pass


def flush_pending_save(preferences=None) -> bool:
    """Cancel the debounce timer and durably save the current preferences."""
    global _preferences_dirty

    cancel_pending_save(clear_dirty=False)
    if preferences is None:
        try:
            from .preferences import get_preferences

            preferences = get_preferences()
        except (AttributeError, KeyError, ReferenceError, RuntimeError):
            preferences = None
    if preferences is None:
        return not _preferences_dirty

    if not _preferences_dirty:
        try:
            target = sidecar_path()
            if target.is_file():
                stored = _read_payload(target)
                live = _validate_payload(snapshot_preferences(preferences))
                if stored == live:
                    return True
        except UnsupportedPreferenceVersion:
            return True
        except (OSError, ValueError):
            pass

    saved = save_preferences(preferences)
    if saved:
        _preferences_dirty = False
    return saved


def cancel_pending_save(*, clear_dirty=True) -> None:
    global _preferences_dirty, _save_timer_registered

    if _save_timer_registered:
        try:
            import bpy

            timers = getattr(getattr(bpy, "app", None), "timers", None)
            if timers is not None and hasattr(timers, "unregister"):
                is_registered = getattr(timers, "is_registered", None)
                if not callable(is_registered) or is_registered(_save_timer_callback):
                    timers.unregister(_save_timer_callback)
        except (AttributeError, RuntimeError, ValueError):
            pass
    _save_timer_registered = False
    if clear_dirty:
        _preferences_dirty = False


def _save_timer_callback():
    global _preferences_dirty, _save_timer_registered

    if not _preferences_dirty:
        _save_timer_registered = False
        return None

    try:
        from .preferences import get_preferences

        preferences = get_preferences()
    except (AttributeError, KeyError, ReferenceError, RuntimeError):
        preferences = None
    if preferences is None:
        _save_timer_registered = False
        return None

    if save_preferences(preferences):
        _preferences_dirty = False
        _save_timer_registered = False
        return None
    return 5.0


def preferences_are_fresh(preferences) -> bool:
    if any(len(getattr(preferences, name, ())) for name in COLLECTION_FIELDS):
        return False
    return all(
        _matches_default(getattr(preferences, field), default)
        for field, default in _ROOT_DEFAULTS.items()
    )


def _matches_default(value, default) -> bool:
    if type(default) is float:
        try:
            return math.isclose(float(value), default, rel_tol=1e-6, abs_tol=1e-6)
        except (TypeError, ValueError):
            return False
    if isinstance(default, (list, tuple)):
        try:
            current = tuple(float(channel) for channel in value)
            expected = tuple(float(channel) for channel in default)
        except (TypeError, ValueError):
            return False
        return len(current) == len(expected) and all(
            math.isclose(left, right, rel_tol=1e-6, abs_tol=1e-6)
            for left, right in zip(current, expected)
        )
    return value == default


def snapshot_preferences(preferences) -> dict:
    root = {
        field: _json_value(getattr(preferences, field))
        for field in ROOT_FIELDS
    }
    payload = {
        "format": FORMAT_NAME,
        "version": FORMAT_VERSION,
        "root": root,
    }
    for collection_name, fields in COLLECTION_FIELDS.items():
        payload[collection_name] = [
            {field: _json_value(getattr(item, field)) for field in fields}
            for item in getattr(preferences, collection_name)
        ]
    return payload


def save_preferences(preferences, *, path=None) -> bool:
    temp_path = None
    try:
        target = Path(path) if path is not None else sidecar_path(create=True)
        target.parent.mkdir(parents=True, exist_ok=True)
        payload = _validate_payload(snapshot_preferences(preferences))
        encoded = json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
            allow_nan=False,
        ) + "\n"
        if len(encoded.encode("utf-8")) > MAX_SIDECAR_BYTES:
            raise ValueError("preference data is too large")

        _preserve_existing_snapshot(target)

        descriptor, temp_name = tempfile.mkstemp(
            prefix=f".{target.name}.",
            suffix=".tmp",
            dir=target.parent,
        )
        temp_path = Path(temp_name)
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            _replace_with_retry(temp_path, target)
        except OSError as replace_error:
            pending = _pending_path(target)
            try:
                os.replace(temp_path, pending)
                temp_path = None
            except OSError:
                pass
            raise replace_error
        temp_path = None
        try:
            _pending_path(target).unlink(missing_ok=True)
        except OSError:
            pass
        if _is_primary_sidecar(target):
            _cleanup_managed_icons(payload, target)
        return True
    except Exception as error:
        _warn(f"could not save preferences: {error}")
        return False
    finally:
        if temp_path is not None:
            try:
                temp_path.unlink(missing_ok=True)
            except OSError:
                pass


def export_configuration(preferences, filepath) -> int:
    """Write a portable ZIP containing preferences and managed custom icons."""
    from .core import icons

    target = Path(filepath)
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = _validate_payload(snapshot_preferences(preferences))
    archived_icons = {}
    icon_data = {}

    for collection_name in ("groups", "targets"):
        for record in payload[collection_name]:
            source_path = record.get("icon_path", "")
            if not source_path:
                continue
            archive_path = archived_icons.get(source_path)
            if archive_path is None:
                data = icons.read_portable_icon(source_path)
                if data is None:
                    raise ValueError(
                        f"custom icon is missing or invalid: {source_path}"
                    )
                archive_path = f"icons/icon-{len(archived_icons) + 1}.png"
                archived_icons[source_path] = archive_path
                icon_data[archive_path] = data
            record["icon_path"] = archive_path

    encoded = (
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False)
        + "\n"
    ).encode("utf-8")
    if len(encoded) > MAX_SIDECAR_BYTES:
        raise ValueError("preference data is too large")
    if len(encoded) + sum(len(data) for data in icon_data.values()) > MAX_PORTABLE_BACKUP_BYTES:
        raise ValueError("configuration backup is too large")

    descriptor, temp_name = tempfile.mkstemp(
        prefix=f".{target.name}.",
        suffix=".tmp",
        dir=target.parent,
    )
    os.close(descriptor)
    temp_path = Path(temp_name)
    try:
        with zipfile.ZipFile(
            temp_path,
            mode="w",
            compression=zipfile.ZIP_DEFLATED,
            compresslevel=9,
        ) as archive:
            archive.writestr(PORTABLE_PREFERENCES_FILENAME, encoded)
            for archive_path, data in icon_data.items():
                archive.writestr(archive_path, data)
        with temp_path.open("rb+") as handle:
            os.fsync(handle.fileno())
        _replace_with_retry(temp_path, target)
    finally:
        try:
            temp_path.unlink(missing_ok=True)
        except OSError:
            pass
    return len(icon_data)


def import_configuration(preferences, filepath) -> int:
    """Restore a portable ZIP transactionally and install its custom icons."""
    from .core import icons

    source = Path(filepath)
    if source.stat().st_size > MAX_PORTABLE_ARCHIVE_BYTES:
        raise ValueError("configuration backup is too large")
    _preflight_portable_archive(source)

    installed_paths = []
    previous = snapshot_preferences(preferences)
    with zipfile.ZipFile(source, mode="r") as archive:
        infos = archive.infolist()
        if len(infos) > MAX_PORTABLE_ARCHIVE_ENTRIES:
            raise ValueError("configuration backup contains too many files")
        if len({info.filename for info in infos}) != len(infos):
            raise ValueError("configuration backup contains duplicate files")
        total_size = sum(info.file_size for info in infos)
        if total_size > MAX_PORTABLE_BACKUP_BYTES:
            raise ValueError("configuration backup expands beyond the size limit")
        manifest_info = archive.getinfo(PORTABLE_PREFERENCES_FILENAME)
        if manifest_info.file_size > MAX_SIDECAR_BYTES:
            raise ValueError("preference data is too large")
        payload = _validate_payload(
            json.loads(archive.read(manifest_info).decode("utf-8"))
        )

        imported_icons = {}
        try:
            for collection_name in ("groups", "targets"):
                for record in payload[collection_name]:
                    archive_path = record.get("icon_path", "")
                    if not archive_path:
                        continue
                    if _valid_bundled_icon(record.get("bundled_icon", "NONE")) != "NONE":
                        record["icon_path"] = ""
                        continue
                    if not _is_portable_icon_path(archive_path):
                        raise ValueError("configuration backup contains an invalid icon path")
                    managed_path = imported_icons.get(archive_path)
                    if managed_path is None:
                        info = archive.getinfo(archive_path)
                        if info.file_size > 16 * 1024 * 1024:
                            raise ValueError("configuration backup contains an oversized icon")
                        managed_path = icons.install_managed_icon_bytes(archive.read(info))
                        imported_icons[archive_path] = managed_path
                        installed_paths.append(managed_path)
                    record["icon_path"] = managed_path

            payload = _validate_payload(payload)
            _apply_payload(preferences, payload)
            _run_application_migrations(preferences)
            request_save()
            if not flush_pending_save(preferences):
                raise OSError("could not save the imported configuration")
        except Exception:
            try:
                _apply_payload(preferences, previous)
                request_save()
                flush_pending_save(preferences)
            finally:
                for installed_path in installed_paths:
                    icons.discard_managed_icon(installed_path)
            raise
    return len(installed_paths)


def _is_portable_icon_path(filepath: str) -> bool:
    path = filepath.replace("\\", "/")
    return (
        path.startswith("icons/")
        and path.endswith(".png")
        and "/../" not in f"/{path}/"
        and not path.startswith("/")
    )


def _preflight_portable_archive(source: Path) -> None:
    """Reject multi-disk, ZIP64, or excessive-entry archives before ZipFile parses them."""
    file_size = source.stat().st_size
    tail_size = min(file_size, 65_557)
    with source.open("rb") as handle:
        handle.seek(file_size - tail_size)
        tail = handle.read(tail_size)

    offset = tail.rfind(b"PK\x05\x06")
    if offset < 0 or offset + 22 > len(tail):
        raise ValueError("configuration backup has no valid ZIP directory")
    (
        signature,
        disk_number,
        directory_disk,
        entries_on_disk,
        entry_count,
        directory_size,
        directory_offset,
        comment_size,
    ) = struct.unpack("<4s4H2LH", tail[offset : offset + 22])
    if signature != b"PK\x05\x06" or offset + 22 + comment_size != len(tail):
        raise ValueError("configuration backup has an invalid ZIP directory")
    if disk_number or directory_disk or entries_on_disk != entry_count:
        raise ValueError("multi-disk configuration backups are not supported")
    if entry_count == 0xFFFF or directory_size == 0xFFFFFFFF:
        raise ValueError("ZIP64 configuration backups are not supported")
    if entry_count > MAX_PORTABLE_ARCHIVE_ENTRIES:
        raise ValueError("configuration backup contains too many files")
    directory_end = directory_offset + directory_size
    eocd_offset = file_size - tail_size + offset
    if directory_end != eocd_offset:
        raise ValueError("configuration backup has an invalid ZIP directory")

    actual_entry_count = 0
    with source.open("rb") as handle:
        handle.seek(directory_offset)
        while handle.tell() < directory_end:
            header = handle.read(46)
            if len(header) != 46 or header[:4] != b"PK\x01\x02":
                raise ValueError("configuration backup has an invalid ZIP directory")
            name_size, extra_size, entry_comment_size = struct.unpack(
                "<HHH",
                header[28:34],
            )
            next_entry = handle.tell() + name_size + extra_size + entry_comment_size
            if next_entry > directory_end:
                raise ValueError("configuration backup has an invalid ZIP directory")
            handle.seek(next_entry)
            actual_entry_count += 1
            if actual_entry_count > MAX_PORTABLE_ARCHIVE_ENTRIES:
                raise ValueError("configuration backup contains too many files")
    if actual_entry_count != entry_count:
        raise ValueError("configuration backup entry count is inconsistent")


def restore_preferences_if_fresh(preferences, *, path=None) -> bool:
    if not preferences_are_fresh(preferences):
        return False

    try:
        target = Path(path) if path is not None else sidecar_path()
        candidates = _restore_candidates(target, include_legacy=path is None)
        if not candidates:
            return False
        candidates.sort(key=lambda candidate: candidate.stat().st_mtime_ns, reverse=True)

        errors = []
        for source in candidates:
            try:
                payload = _read_payload(source)
                _apply_payload(preferences, payload)
                return True
            except Exception as error:
                errors.append(f"{source.name}: {error}")
        raise ValueError("; ".join(errors))
    except Exception as error:
        _warn(f"could not restore preferences: {error}")
        return False


def _validate_payload(payload) -> dict:
    if not isinstance(payload, dict):
        raise ValueError("preference data must be an object")
    payload = _migrate_payload(payload)
    if payload.get("format") != FORMAT_NAME or payload.get("version") != FORMAT_VERSION:
        raise ValueError("unsupported preference format")

    source_root = payload.get("root")
    if not isinstance(source_root, dict):
        raise ValueError("preference root must be an object")
    root = {}
    for field in ROOT_FIELDS:
        if field in source_root:
            root[field] = _validate_root_value(field, source_root[field])

    validated = {
        "format": FORMAT_NAME,
        "version": FORMAT_VERSION,
        "root": root,
    }
    identities = {
        "groups": "group_id",
        "targets": "native_key",
        "favorites": "target_key",
        "new_addons": "addon_key",
        "observed_addons": "addon_key",
    }
    for collection_name, fields in COLLECTION_FIELDS.items():
        records = payload.get(collection_name)
        if not isinstance(records, list):
            raise ValueError(f"invalid {collection_name} collection")
        limits = {
            "groups": MAX_GROUP_RECORDS,
            "targets": MAX_TARGET_RECORDS,
            "favorites": MAX_FAVORITE_RECORDS,
            "new_addons": MAX_NEW_ADDON_RECORDS,
            "observed_addons": MAX_OBSERVED_ADDON_RECORDS,
        }
        if len(records) > limits[collection_name]:
            raise ValueError(f"too many {collection_name} records")

        identity_field = identities[collection_name]
        seen = set()
        clean_records = []
        for record in records:
            if not isinstance(record, dict):
                raise ValueError(f"invalid {collection_name} record")
            clean = {
                field: _validate_record_value(field, record[field])
                for field in fields
                if field in record
            }
            identity = clean.get(identity_field)
            if not identity or identity in seen:
                raise ValueError(f"invalid or duplicate {identity_field}")
            seen.add(identity)
            clean["name"] = identity
            clean_records.append(clean)
        validated[collection_name] = clean_records
    return validated


def _validate_root_value(field, value):
    if field in _ROOT_BOOL_FIELDS:
        if type(value) is not bool:
            raise ValueError(f"{field} must be a boolean")
        return value
    if field in _ROOT_INT_FIELDS:
        if type(value) is not int or not 0 <= value <= 2_147_483_647:
            raise ValueError(f"{field} must be a non-negative integer")
        if field == "compact_popup_width" and not 360 <= value <= 700:
            raise ValueError("compact_popup_width is out of range")
        if field == "max_search_results" and not 10 <= value <= 512:
            raise ValueError("max_search_results is out of range")
        return value
    if field in _ROOT_STRING_FIELDS:
        if not isinstance(value, str):
            raise ValueError(f"{field} must be a string")
        return value
    if field == "display_mode":
        if value == "ICON":
            return "BOTH"
        if value not in _DISPLAY_MODE_IDS:
            raise ValueError("invalid display_mode")
        return value
    if field == "icon_color_mode":
        if value not in _ICON_COLOR_MODE_IDS:
            raise ValueError("invalid icon_color_mode")
        return value
    if field == "icon_tint_color":
        if (
            not isinstance(value, (list, tuple))
            or len(value) != 3
            or any(not _is_finite_number(channel) for channel in value)
            or any(not 0.0 <= channel <= 1.0 for channel in value)
        ):
            raise ValueError("icon_tint_color is invalid")
        return [float(channel) for channel in value]
    raise ValueError(f"unsupported root field: {field}")


def _validate_record_value(field, value):
    if field == "group_memberships":
        return _validate_group_memberships(value)
    if field in _RECORD_STRING_FIELDS:
        if not isinstance(value, str):
            raise ValueError(f"{field} must be a string")
        if field == "icon_name" and value not in _BUILTIN_ICON_IDS:
            raise ValueError("invalid Blender icon")
        return value
    if field in {"open_count", "group_order"}:
        if type(value) is not int or not 0 <= value <= 2_147_483_647:
            raise ValueError(f"{field} must be a non-negative integer")
        return value
    if field == "hidden":
        if type(value) is not bool:
            raise ValueError("hidden must be a boolean")
        return value
    raise ValueError(f"unsupported record field: {field}")


def _validate_group_memberships(value):
    if not isinstance(value, str):
        raise ValueError("group_memberships must be a string")
    if not value:
        return ""
    try:
        decoded = json.loads(value)
    except (TypeError, ValueError) as error:
        raise ValueError("group_memberships must contain valid JSON") from error
    if not isinstance(decoded, dict) or len(decoded) > MAX_GROUP_RECORDS:
        raise ValueError("group_memberships must be an object")

    normalized = {}
    for group_id, order in decoded.items():
        if not isinstance(group_id, str) or not group_id:
            raise ValueError("group_memberships contains an invalid category")
        if type(order) is not int or not 0 <= order <= 2_147_483_647:
            raise ValueError("group_memberships contains an invalid order")
        normalized[group_id] = order
    return json.dumps(normalized, sort_keys=True, separators=(",", ":"))


def _apply_payload(preferences, payload):
    previous_root = {field: getattr(preferences, field) for field in ROOT_FIELDS}
    try:
        for collection_name, fields in COLLECTION_FIELDS.items():
            collection = getattr(preferences, collection_name)
            collection.clear()
            for record in payload[collection_name]:
                item = collection.add()
                _apply_record(item, fields, record)

        for field in ROOT_FIELDS:
            setattr(
                preferences,
                field,
                payload["root"].get(field, _ROOT_DEFAULTS[field]),
            )
    except Exception:
        for collection_name in COLLECTION_FIELDS:
            getattr(preferences, collection_name).clear()
        for field, value in previous_root.items():
            try:
                setattr(preferences, field, value)
            except (AttributeError, RuntimeError, TypeError, ValueError):
                pass
        raise


def _apply_record(item, fields, record):
    deferred = {"bundled_icon", "icon_path"}
    for field in fields:
        if field in deferred or field not in record:
            continue
        setattr(item, field, record[field])

    bundled_icon = _valid_bundled_icon(record.get("bundled_icon", "NONE"))
    if "bundled_icon" in fields:
        item.bundled_icon = bundled_icon
    if "icon_path" in fields and bundled_icon == "NONE":
        item.icon_path = record.get("icon_path", "")


def _valid_bundled_icon(identifier: str) -> str:
    if identifier in {"", "NONE"}:
        return "NONE"
    from .core import icons

    identifier = icons.canonical_bundled_icon(identifier)
    return identifier if icons.has_bundled_icon(identifier) else "NONE"


def _run_application_migrations(preferences) -> None:
    from .core import icons
    from .preferences import (
        ensure_activity_history,
        ensure_default_groups,
        ensure_display_mode,
        ensure_favorites,
        ensure_group_memberships,
    )

    ensure_display_mode(preferences)
    icons.migrate_bundled_icon_values(preferences)
    ensure_default_groups(preferences)
    ensure_group_memberships(preferences)
    ensure_favorites(preferences)
    ensure_activity_history(preferences)


def _json_value(value):
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    if isinstance(value, (str, bool, int, float)) or value is None:
        return value
    try:
        return [_json_value(item) for item in value]
    except TypeError:
        return str(value)


def _is_finite_number(value) -> bool:
    return type(value) in {int, float} and math.isfinite(value)


def _pending_path(target: Path) -> Path:
    return target.with_name(f"{target.name}.pending")


def _backup_path(target: Path) -> Path:
    return target.with_name(f"{target.name}.bak")


def _restore_candidates(target: Path, *, include_legacy: bool) -> list[Path]:
    targets = [target]
    if include_legacy:
        targets.extend(target.with_name(name) for name in LEGACY_SIDECAR_FILENAMES)

    candidates = []
    for candidate_target in targets:
        for candidate in (
            _pending_path(candidate_target),
            candidate_target,
            _backup_path(candidate_target),
        ):
            if candidate.is_file() and candidate not in candidates:
                candidates.append(candidate)
    return candidates


def _migrate_payload(payload: dict) -> dict:
    if payload.get("format") != FORMAT_NAME:
        raise ValueError("unsupported preference format")
    version = payload.get("version")
    if type(version) is int and version > FORMAT_VERSION:
        raise UnsupportedPreferenceVersion(
            f"preference version {version} is newer than supported version {FORMAT_VERSION}"
        )
    if type(version) is not int or version < 1:
        raise ValueError("unsupported preference format")

    migrated = payload
    while version < FORMAT_VERSION:
        migration = _FORMAT_MIGRATIONS.get(version)
        if migration is None:
            raise ValueError(f"no preference migration from version {version}")
        migrated = migration(migrated)
        version = migrated.get("version")
    return migrated


def _migrate_v1_to_v2(payload: dict) -> dict:
    """Move the first released sidecar to the stable filename-era format."""
    migrated = dict(payload)
    migrated["version"] = 2
    return migrated


def _migrate_v2_to_v3(payload: dict) -> dict:
    """Add category-independent panel identity metadata."""

    migrated = dict(payload)
    migrated["targets"] = [
        {
            **record,
            "origin_key": record.get("origin_key", ""),
            "panel_identifiers": record.get("panel_identifiers", ""),
        }
        if isinstance(record, dict)
        else record
        for record in payload.get("targets", ())
    ]
    migrated["version"] = 3
    return migrated


def _migrate_v3_to_v4(payload: dict) -> dict:
    """Add non-destructive uniform custom icon coloring."""

    migrated = dict(payload)
    source_root = payload.get("root")
    if isinstance(source_root, dict):
        root = dict(source_root)
        root.setdefault("icon_color_mode", "ORIGINAL")
        root.setdefault("icon_tint_color", [1.0, 1.0, 1.0])
        migrated["root"] = root
    migrated["version"] = 4
    return migrated


def _migrate_v4_to_v5(payload: dict) -> dict:
    """Remove icon intensity so source alpha and edge sharpness stay intact."""

    migrated = dict(payload)
    source_root = payload.get("root")
    if isinstance(source_root, dict):
        root = dict(source_root)
        root.pop("icon_intensity", None)
        migrated["root"] = root
    migrated["version"] = 5
    return migrated


def _migrate_v5_to_v6(payload: dict) -> dict:
    """Allow one target to belong to multiple categories."""
    migrated = dict(payload)
    migrated["targets"] = [
        {
            **record,
            "group_memberships": record.get("group_memberships")
            or _legacy_group_memberships(record),
        }
        if isinstance(record, dict)
        else record
        for record in payload.get("targets", ())
    ]
    migrated["version"] = 6
    return migrated


def _migrate_v6_to_v7(payload: dict) -> dict:
    """Add the persistent queue for newly detected add-ons."""
    migrated = dict(payload)
    source_root = payload.get("root")
    root = dict(source_root) if isinstance(source_root, dict) else {}
    root.setdefault("new_addons_initialized", bool(payload.get("targets")))
    migrated["root"] = root
    migrated["new_addons"] = list(payload.get("new_addons", ()))
    migrated["version"] = 7
    return migrated


def _migrate_v7_to_v8(payload: dict) -> dict:
    """Track enabled add-ons independently from retained catalog targets."""
    migrated = dict(payload)
    source_root = payload.get("root")
    root = dict(source_root) if isinstance(source_root, dict) else {}
    root.setdefault("observed_addons_initialized", False)
    migrated["root"] = root
    migrated["observed_addons"] = list(payload.get("observed_addons", ()))
    migrated["version"] = 8
    return migrated


def _migrate_v8_to_v9(payload: dict) -> dict:
    """Add the opt-in experimental startup popover choices."""
    migrated = dict(payload)
    source_root = payload.get("root")
    root = dict(source_root) if isinstance(source_root, dict) else {}
    root.setdefault("auto_open_library", False)
    root.setdefault("auto_open_categories", False)
    migrated["root"] = root
    migrated["version"] = 9
    return migrated


def _legacy_group_memberships(record):
    group_id = record.get("group_id", "")
    if not group_id:
        return ""
    return json.dumps(
        {group_id: record.get("group_order", 0)},
        sort_keys=True,
        separators=(",", ":"),
    )


_FORMAT_MIGRATIONS = {
    1: _migrate_v1_to_v2,
    2: _migrate_v2_to_v3,
    3: _migrate_v3_to_v4,
    4: _migrate_v4_to_v5,
    5: _migrate_v5_to_v6,
    6: _migrate_v6_to_v7,
    7: _migrate_v7_to_v8,
    8: _migrate_v8_to_v9,
}


def _preserve_existing_snapshot(target: Path) -> None:
    if not target.is_file():
        return
    try:
        _read_payload(target)
    except UnsupportedPreferenceVersion:
        raise
    except Exception:
        quarantine = target.with_name(f"{target.name}.corrupt-{time.time_ns()}")
        os.replace(target, quarantine)
        return

    encoded = target.read_bytes()
    backup = _backup_path(target)
    descriptor, temp_name = tempfile.mkstemp(
        prefix=f".{backup.name}.",
        suffix=".tmp",
        dir=backup.parent,
    )
    temp_path = Path(temp_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        _replace_with_retry(temp_path, backup)
    finally:
        try:
            temp_path.unlink(missing_ok=True)
        except OSError:
            pass


def _cleanup_managed_icons(payload: dict, target: Path) -> None:
    protected_paths = _payload_icon_paths(payload)
    for recovery_snapshot in (_pending_path(target), _backup_path(target)):
        if not recovery_snapshot.is_file():
            continue
        try:
            protected_paths.update(_payload_icon_paths(_read_payload(recovery_snapshot)))
        except Exception:
            return
    try:
        from .core import icons

        icons.cleanup_managed_icons(protected_paths)
    except Exception:
        pass


def _is_primary_sidecar(target: Path) -> bool:
    try:
        expected = data_directory(create=False) / SIDECAR_FILENAME
        return target.resolve() == expected.resolve()
    except (AttributeError, OSError, RuntimeError, ValueError):
        return False


def _payload_icon_paths(payload: dict) -> set[str]:
    return {
        record.get("icon_path", "")
        for collection_name in ("groups", "targets")
        for record in payload.get(collection_name, ())
        if record.get("icon_path")
    }


def _replace_with_retry(source: Path, target: Path):
    for attempt in range(3):
        try:
            os.replace(source, target)
            return
        except PermissionError:
            if attempt == 2:
                raise
            time.sleep(0.05 * (attempt + 1))


def _read_payload(source: Path) -> dict:
    for attempt in range(3):
        try:
            if source.stat().st_size > MAX_SIDECAR_BYTES:
                raise ValueError("preference file is too large")
            encoded = source.read_bytes()
            break
        except PermissionError:
            if attempt == 2:
                raise
            time.sleep(0.05 * (attempt + 1))
    if len(encoded) > MAX_SIDECAR_BYTES:
        raise ValueError("preference file is too large")
    return _validate_payload(json.loads(encoded.decode("utf-8")))


def _warn(message: str):
    print(f"Quick N-panel: {message}")
