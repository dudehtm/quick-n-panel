"""Custom preview and generated accent icon lifecycle."""

import hashlib
import os
import shutil
import struct
import uuid
import zlib
from pathlib import Path

import bpy

from ..constants import DEFAULT_ICON_COLOR_MODE


_custom_previews = None
_accent_previews = None
_retired_preview_collections = []
_preview_cleanup_timer_registered = False
_preview_cleanup_waiting_for_redraw = False
_bundled_icon_paths = {}
_bundled_icon_choice_cache = [
    ("NONE", "Blender Icon", "Use the selected Blender fallback icon", "BLENDER", 0)
]

_BUNDLED_ICON_DIRECTORY = Path(__file__).resolve().parents[1] / "icons" / "Custom"
_ICON_SIZE = 96
_MAX_SOURCE_DIMENSION = 1024
_MAX_SOURCE_BYTES = 16 * 1024 * 1024
_DEFAULT_ICON_TINT_COLOR = (1.0, 1.0, 1.0)
_ICON_COLOR_MODES = {"ORIGINAL", "WHITE", "CUSTOM"}
ICON_ENUM_SCHEMA_VERSION = 2
_BUNDLED_ICON_ALIASES = {
    "QNP_FIles": "QNP_Files",
}


def register():
    global _custom_previews, _accent_previews

    if _custom_previews is not None and _accent_previews is not None:
        return

    import bpy.utils.previews

    _remove_preview_collections((_custom_previews, _accent_previews))
    _custom_previews = None
    _accent_previews = None
    new_custom = bpy.utils.previews.new()
    try:
        new_accent = bpy.utils.previews.new()
    except Exception:
        _remove_preview_collections((new_custom,))
        raise

    _custom_previews = new_custom
    _accent_previews = new_accent
    try:
        _refresh_bundled_icons()
    except Exception:
        _custom_previews = None
        _accent_previews = None
        _remove_preview_collections((new_custom, new_accent))
        _bundled_icon_paths.clear()
        _bundled_icon_choice_cache[:] = [
            ("NONE", "Blender Icon", "Use the selected Blender fallback icon", "BLENDER", 0)
        ]
        raise


def unregister():
    global _custom_previews, _accent_previews

    _cancel_preview_cleanup()
    _remove_preview_collections(
        (_custom_previews, _accent_previews, *_retired_preview_collections)
    )

    _custom_previews = None
    _accent_previews = None
    _retired_preview_collections.clear()
    _bundled_icon_paths.clear()
    _bundled_icon_choice_cache[:] = [
        ("NONE", "Blender Icon", "Use the selected Blender fallback icon", "BLENDER", 0)
    ]


def refresh_icon_previews():
    global _custom_previews, _accent_previews

    if _custom_previews is None or _accent_previews is None:
        return

    import bpy.utils.previews

    previous_collections = (_custom_previews, _accent_previews)
    previous_paths = dict(_bundled_icon_paths)
    previous_choices = list(_bundled_icon_choice_cache)
    new_custom = bpy.utils.previews.new()
    try:
        new_accent = bpy.utils.previews.new()
    except Exception:
        _remove_preview_collections((new_custom,))
        raise

    _custom_previews = new_custom
    _accent_previews = new_accent
    try:
        _refresh_bundled_icons()
    except Exception:
        _custom_previews, _accent_previews = previous_collections
        _bundled_icon_paths.clear()
        _bundled_icon_paths.update(previous_paths)
        _bundled_icon_choice_cache[:] = previous_choices
        _remove_preview_collections((new_custom, new_accent))
        raise

    _retire_preview_collections(previous_collections)


def _retire_preview_collections(collections) -> None:
    global _preview_cleanup_timer_registered, _preview_cleanup_waiting_for_redraw

    for collection in collections:
        if collection is not None and all(
            existing is not collection for existing in _retired_preview_collections
        ):
            _retired_preview_collections.append(collection)

    _tag_redraw_all()
    _preview_cleanup_waiting_for_redraw = True
    if not _retired_preview_collections or _preview_cleanup_timer_registered:
        return

    timers = getattr(getattr(bpy, "app", None), "timers", None)
    if timers is None or not hasattr(timers, "register"):
        return
    try:
        timers.register(_cleanup_retired_previews, first_interval=0.1)
        _preview_cleanup_timer_registered = True
    except (AttributeError, RuntimeError, ValueError):
        pass


def _cleanup_retired_previews():
    global _preview_cleanup_timer_registered, _preview_cleanup_waiting_for_redraw

    if _preview_cleanup_waiting_for_redraw:
        _preview_cleanup_waiting_for_redraw = False
        _tag_redraw_all()
        return 0.05

    collections = tuple(_retired_preview_collections)
    _retired_preview_collections.clear()
    _preview_cleanup_timer_registered = False
    _remove_preview_collections(collections)
    _tag_redraw_all()
    return None


def _cancel_preview_cleanup() -> None:
    global _preview_cleanup_timer_registered, _preview_cleanup_waiting_for_redraw

    timers = getattr(getattr(bpy, "app", None), "timers", None)
    try:
        if (
            timers is not None
            and hasattr(timers, "is_registered")
            and timers.is_registered(_cleanup_retired_previews)
        ):
            timers.unregister(_cleanup_retired_previews)
    except (AttributeError, RuntimeError, ValueError):
        pass
    _preview_cleanup_timer_registered = False
    _preview_cleanup_waiting_for_redraw = False


def _remove_preview_collections(collections) -> None:
    import bpy.utils.previews

    removed = set()
    for collection in collections:
        if collection is None or id(collection) in removed:
            continue
        removed.add(id(collection))
        try:
            bpy.utils.previews.remove(collection)
        except (KeyError, ReferenceError, RuntimeError):
            pass


def _tag_redraw_all() -> None:
    try:
        window_manager = getattr(bpy.context, "window_manager", None)
        for window in getattr(window_manager, "windows", ()):
            for area in window.screen.areas:
                area.tag_redraw()
    except (AttributeError, ReferenceError, RuntimeError):
        pass


def resolve_icon(
    icon_name: str,
    icon_path: str = "",
    bundled_icon: str = "NONE",
) -> tuple[str, int]:
    icon_value = bundled_icon_value(bundled_icon)
    if not icon_value:
        icon_value = custom_icon_value(icon_path)
    if icon_value:
        return "NONE", icon_value
    return icon_name or "PLUGIN", 0


def bundled_icon_choices():
    return _bundled_icon_choice_cache


def bundled_icon_value(identifier: str) -> int:
    filepath = _bundled_icon_paths.get(identifier)
    return custom_icon_value(str(filepath)) if filepath else 0


def has_bundled_icon(identifier: str) -> bool:
    return identifier in _bundled_icon_paths


def canonical_bundled_icon(identifier: str) -> str:
    return _BUNDLED_ICON_ALIASES.get(identifier, identifier)


def migrate_bundled_icon_values(preferences) -> None:
    """Repair legacy enum numbers, including values rounded by template_icon_view."""
    if getattr(preferences, "icon_enum_schema_version", 0) >= ICON_ENUM_SCHEMA_VERSION:
        return

    identifiers_by_number = {0: "NONE"}
    for filepath in _bundled_icon_files():
        identifier = filepath.stem
        legacy_number = _legacy_icon_number(identifier)
        for number in (
            legacy_number,
            _float32_rounded_int(legacy_number),
            _stable_icon_number(identifier),
        ):
            previous = identifiers_by_number.setdefault(number, identifier)
            if previous != identifier:
                raise RuntimeError(f"Bundled icon migration collision: {identifier}")

    for old_identifier, identifier in _BUNDLED_ICON_ALIASES.items():
        legacy_number = _legacy_icon_number(old_identifier)
        for number in (
            legacy_number,
            _float32_rounded_int(legacy_number),
            _stable_icon_number(old_identifier),
        ):
            identifiers_by_number[number] = identifier

    for collection_name in ("groups", "targets"):
        for owner in getattr(preferences, collection_name, ()):
            getter = getattr(owner, "get", None)
            raw_value = getter("bundled_icon", 0) if callable(getter) else 0
            identifier = identifiers_by_number.get(raw_value)
            if identifier is not None:
                owner.bundled_icon = identifier

    preferences.icon_enum_schema_version = ICON_ENUM_SCHEMA_VERSION


def custom_icon_value(filepath: str) -> int:
    color_mode, tint_color = _current_icon_style()
    return _styled_icon_value(filepath, color_mode, tint_color)


def _styled_icon_value(
    filepath: str,
    color_mode: str,
    tint_color: tuple[float, float, float],
) -> int:
    if not filepath or _custom_previews is None:
        return 0

    absolute_path = bpy.path.abspath(filepath)
    if not os.path.isfile(absolute_path):
        return 0
    if not _is_safe_png(absolute_path):
        return 0

    try:
        modified = os.path.getmtime(absolute_path)
        tint_fingerprint = ":".join(f"{channel:.4f}" for channel in tint_color)
        cache_key = hashlib.sha1(
            (
                f"{os.path.normcase(absolute_path)}:{modified}:"
                f"{color_mode}:{tint_fingerprint}"
            ).encode("utf-8")
        ).hexdigest()
        preview = _custom_previews.get(cache_key)
        icon_id = _preview_icon_id(preview)
        if preview is not None and not icon_id:
            _discard_custom_preview(cache_key)
            preview = None
        if preview is None:
            preview = _load_styled_preview(
                cache_key,
                absolute_path,
                color_mode,
                tint_color,
            )
            icon_id = _preview_icon_id(preview)
        if not icon_id:
            _discard_custom_preview(cache_key)
        return icon_id
    except (AttributeError, KeyError, OSError, RuntimeError, TypeError, ValueError):
        return 0


def _preview_icon_id(preview) -> int:
    try:
        return max(0, int(preview.icon_id)) if preview is not None else 0
    except (AttributeError, ReferenceError, RuntimeError, TypeError, ValueError):
        return 0


def _discard_custom_preview(cache_key: str) -> None:
    if _custom_previews is None:
        return
    try:
        del _custom_previews[cache_key]
    except (KeyError, ReferenceError, RuntimeError):
        pass


def _load_styled_preview(
    cache_key: str,
    filepath: str,
    color_mode: str,
    tint_color: tuple[float, float, float],
):
    image = None
    preview = None
    try:
        image = bpy.data.images.load(filepath, check_existing=False)
        width, height = (int(dimension) for dimension in image.size)
        pixels = list(image.pixels[:])
        styled_pixels = _style_pixels(
            pixels,
            color_mode,
            tint_color,
        )
        preview = _custom_previews.new(cache_key)
        preview.icon_size = (width, height)
        preview.icon_pixels_float = styled_pixels
        preview.image_size = (width, height)
        preview.image_pixels_float = styled_pixels
        return preview
    except (AttributeError, KeyError, OSError, RuntimeError, TypeError, ValueError):
        if preview is not None:
            try:
                del _custom_previews[cache_key]
            except (KeyError, RuntimeError):
                pass
        return _custom_previews.load(cache_key, filepath, "IMAGE")
    finally:
        if image is not None:
            try:
                bpy.data.images.remove(image)
            except (ReferenceError, RuntimeError):
                pass


def _style_pixels(
    pixels,
    color_mode: str,
    tint_color,
) -> list[float]:
    uniform_color = _uniform_icon_color(color_mode, tint_color)
    result = []

    for index in range(0, len(pixels), 4):
        red, green, blue, alpha = pixels[index : index + 4]
        if alpha <= 0.0:
            result.extend((0.0, 0.0, 0.0, 0.0))
            continue

        if uniform_color is not None:
            red, green, blue = uniform_color

        result.extend(
            (
                max(0.0, min(red, 1.0)),
                max(0.0, min(green, 1.0)),
                max(0.0, min(blue, 1.0)),
                max(0.0, min(alpha, 1.0)),
            )
        )
    return result


def _current_icon_style() -> tuple[str, tuple[float, float, float]]:
    color_mode = DEFAULT_ICON_COLOR_MODE
    tint_color = _DEFAULT_ICON_TINT_COLOR
    try:
        from ..preferences import get_preferences

        preferences = get_preferences(bpy.context)
        if preferences is not None:
            requested_mode = str(preferences.icon_color_mode)
            if requested_mode in _ICON_COLOR_MODES:
                color_mode = requested_mode
            tint_color = _clamped_color(preferences.icon_tint_color)
    except (AttributeError, KeyError, ReferenceError, RuntimeError, TypeError, ValueError):
        pass
    return color_mode, tint_color


def _uniform_icon_color(color_mode: str, tint_color):
    if color_mode == "WHITE":
        return _DEFAULT_ICON_TINT_COLOR
    if color_mode == "CUSTOM":
        return _clamped_color(tint_color)
    return None


def _clamped_color(color) -> tuple[float, float, float]:
    if len(color) != 3:
        raise ValueError("icon colors require three channels")
    return tuple(max(0.0, min(float(channel), 1.0)) for channel in color)


def import_external_icon(filepath: str) -> str:
    """Create a small managed copy of a user-selected PNG and return its path."""
    absolute_path = bpy.path.abspath(filepath)
    if not _is_safe_png(absolute_path):
        raise ValueError(
            f"Choose a PNG no larger than {_MAX_SOURCE_DIMENSION} x "
            f"{_MAX_SOURCE_DIMENSION} pixels and {_MAX_SOURCE_BYTES // (1024 * 1024)} MB"
        )

    icon_directory = _managed_icon_directory(create=True)
    if not icon_directory:
        raise OSError("Blender could not create the Quick N-panel icon directory")

    destination = Path(icon_directory) / f"qnp_{uuid.uuid4().hex}.png"
    image = None
    try:
        image = bpy.data.images.load(absolute_path, check_existing=False)
        image.scale(_ICON_SIZE, _ICON_SIZE)
        image.filepath_raw = str(destination)
        image.file_format = "PNG"
        image.save()
    except (OSError, RuntimeError, ValueError) as error:
        try:
            destination.unlink(missing_ok=True)
        except OSError:
            pass
        raise ValueError(f"Could not import this PNG: {error}") from error
    finally:
        if image is not None:
            try:
                bpy.data.images.remove(image)
            except (ReferenceError, RuntimeError):
                pass

    return str(destination)


def remove_managed_icon(filepath: str) -> None:
    """Defer deletion until a snapshot and its backup no longer reference the file."""
    return None


def migrate_managed_icon_paths(preferences) -> bool:
    """Copy icons from the legacy shared directory into extension-owned storage."""
    legacy_directory = _legacy_managed_icon_directory(create=False)
    if not legacy_directory:
        return False
    try:
        legacy_directory = Path(legacy_directory).resolve()
    except OSError:
        return False

    changed = False
    for collection_name in ("groups", "targets"):
        for owner in getattr(preferences, collection_name, ()):
            filepath = getattr(owner, "icon_path", "")
            if not filepath:
                continue
            try:
                source = Path(bpy.path.abspath(filepath)).resolve()
            except OSError:
                continue
            if source.parent != legacy_directory or not _is_safe_png(str(source)):
                continue

            try:
                icon_directory = Path(_managed_icon_directory(create=True))
                destination = icon_directory / source.name
                if destination.exists() and destination.read_bytes() != source.read_bytes():
                    destination = icon_directory / f"qnp_{uuid.uuid4().hex}.png"
                if not destination.exists():
                    shutil.copy2(source, destination)
                owner.icon_path = str(destination)
                changed = True
            except OSError:
                continue
    return changed


def cleanup_managed_icons(protected_paths) -> None:
    """Delete only managed files absent from both current and backup snapshots."""
    icon_directory = _managed_icon_directory(create=False)
    if not icon_directory:
        return
    try:
        directory = Path(icon_directory).resolve()
        protected = {
            Path(bpy.path.abspath(filepath)).resolve()
            for filepath in protected_paths
            if filepath
        }
        for candidate in directory.glob("qnp_*.png"):
            if candidate.is_symlink():
                candidate.unlink(missing_ok=True)
                continue
            resolved = candidate.resolve()
            if resolved not in protected:
                candidate.unlink(missing_ok=True)
    except OSError:
        pass


def read_portable_icon(filepath: str) -> bytes | None:
    try:
        absolute_path = bpy.path.abspath(filepath)
        if not _is_safe_png(absolute_path):
            return None
        data = Path(absolute_path).read_bytes()
        return data if _is_managed_png_bytes(data) else None
    except OSError:
        return None


def install_managed_icon_bytes(data: bytes) -> str:
    if not _is_managed_png_bytes(data):
        raise ValueError("configuration backup contains an invalid PNG icon")
    directory = Path(_managed_icon_directory(create=True))
    destination = directory / f"qnp_{uuid.uuid4().hex}.png"
    try:
        with destination.open("xb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
    except Exception:
        try:
            destination.unlink(missing_ok=True)
        except OSError:
            pass
        raise
    return str(destination)


def discard_managed_icon(filepath: str) -> None:
    """Immediately remove a newly imported file while rolling back a transaction."""
    if not filepath:
        return
    try:
        directory = Path(_managed_icon_directory(create=False)).resolve()
        candidate = Path(bpy.path.abspath(filepath)).resolve()
        if candidate.parent == directory:
            candidate.unlink(missing_ok=True)
    except OSError:
        pass


def _managed_icon_directory(*, create: bool) -> str:
    from .. import persistence

    return str(
        persistence.data_directory(
            create=create,
            path="icons",
        )
    )


def _legacy_managed_icon_directory(*, create: bool) -> str:
    return bpy.utils.user_resource(
        "DATAFILES",
        path="quick_n_panel/icons",
        create=create,
    )


def _is_safe_png(filepath: str) -> bool:
    """Validate the PNG header before Blender allocates its decoded pixels."""
    try:
        if os.path.getsize(filepath) > _MAX_SOURCE_BYTES:
            return False
        with open(filepath, "rb") as source:
            header = source.read(24)
        if header[:8] != b"\x89PNG\r\n\x1a\n" or header[12:16] != b"IHDR":
            return False
        width, height = struct.unpack(">II", header[16:24])
        return 0 < width <= _MAX_SOURCE_DIMENSION and 0 < height <= _MAX_SOURCE_DIMENSION
    except (OSError, struct.error):
        return False


def _is_managed_png_bytes(data: bytes) -> bool:
    if len(data) > _MAX_SOURCE_BYTES or len(data) < 45:
        return False
    try:
        if data[:8] != b"\x89PNG\r\n\x1a\n":
            return False
        offset = 8
        saw_header = False
        saw_data = False
        while offset + 12 <= len(data):
            length = struct.unpack(">I", data[offset : offset + 4])[0]
            chunk_end = offset + 12 + length
            if chunk_end > len(data):
                return False
            chunk_type = data[offset + 4 : offset + 8]
            chunk_data = data[offset + 8 : offset + 8 + length]
            expected_crc = struct.unpack(">I", data[offset + 8 + length : chunk_end])[0]
            actual_crc = zlib.crc32(chunk_type + chunk_data) & 0xFFFFFFFF
            if actual_crc != expected_crc:
                return False
            if not saw_header:
                if chunk_type != b"IHDR" or length != 13:
                    return False
                width, height, depth, color_type = struct.unpack(">IIBB", chunk_data[:10])
                if (width, height, depth, color_type) != (_ICON_SIZE, _ICON_SIZE, 8, 6):
                    return False
                saw_header = True
            elif chunk_type == b"IDAT":
                saw_data = True
            elif chunk_type == b"IEND":
                return length == 0 and saw_data and chunk_end == len(data)
            offset = chunk_end
        return False
    except struct.error:
        return False


def _refresh_bundled_icons():
    _bundled_icon_paths.clear()
    choices = [
        ("NONE", "Blender Icon", "Use the selected Blender fallback icon", "BLENDER", 0)
    ]
    used_numbers = {0}

    for filepath in _bundled_icon_files():
        identifier = filepath.stem
        label = _bundled_icon_label(identifier)
        _bundled_icon_paths[identifier] = filepath
        icon_value = custom_icon_value(str(filepath))
        number = _stable_icon_number(identifier)
        if number in used_numbers:
            raise RuntimeError(f"Bundled icon number collision: {identifier}")
        used_numbers.add(number)
        choices.append(
            (
                identifier,
                label,
                f"Use the included {label} icon",
                icon_value or "IMAGE_DATA",
                number,
            )
        )

    _bundled_icon_choice_cache[:] = choices


def _bundled_icon_files() -> tuple[Path, ...]:
    if not _BUNDLED_ICON_DIRECTORY.is_dir():
        return ()
    return tuple(
        sorted(
            _BUNDLED_ICON_DIRECTORY.glob("QNP_*.png"),
            key=lambda filepath: filepath.stem.casefold(),
        )
    )


def _bundled_icon_label(identifier: str) -> str:
    words = identifier.removeprefix("QNP_").split("_")
    return " ".join(word if word.isupper() else word.capitalize() for word in words)


def _stable_icon_number(identifier: str) -> int:
    digest = hashlib.sha1(identifier.encode("utf-8")).digest()
    # template_icon_view passes enum numbers through float32. Integers below
    # 2^24 remain exact, while the previous 31-bit values were rounded.
    return (int.from_bytes(digest[:3], "big") & 0x007FFFFF) or 1


def _legacy_icon_number(identifier: str) -> int:
    digest = hashlib.sha1(identifier.encode("utf-8")).digest()
    return (int.from_bytes(digest[:4], "big") & 0x7FFFFFFF) or 1


def _float32_rounded_int(value: int) -> int:
    return int(struct.unpack(">f", struct.pack(">f", value))[0])


_SEARCH_ACCENT_COLOR = (0.20, 0.58, 1.0, 1.0)


def search_accent_icon_value() -> int:
    if _accent_previews is None:
        return 0

    color_mode, tint_color = _current_icon_style()
    uniform_color = _uniform_icon_color(color_mode, tint_color)
    rgba = (*uniform_color, 1.0) if uniform_color is not None else _SEARCH_ACCENT_COLOR
    fingerprint = ":".join(f"{channel:.3f}" for channel in rgba)
    cache_key = hashlib.sha1(f"__search_accent__:{fingerprint}".encode("utf-8")).hexdigest()

    try:
        preview = _accent_previews.get(cache_key)
        if preview is None:
            preview = _accent_previews.new(cache_key)
            preview.icon_size = (128, 2)
            preview.icon_pixels_float = list(rgba) * (128 * 2)
        return preview.icon_id
    except (AttributeError, KeyError, RuntimeError, TypeError, ValueError):
        return 0
