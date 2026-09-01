"""Pure catalog models and normalization helpers."""

from dataclasses import dataclass
import hashlib
from typing import Iterable

from ..constants import TARGET_KEY_SEPARATOR


@dataclass(frozen=True, slots=True)
class PanelDescriptor:
    identifier: str
    label: str
    module: str
    parent_id: str = ""
    order: int = 0


@dataclass(frozen=True, slots=True)
class TargetDescriptor:
    native_key: str
    native_category: str
    panels: tuple[PanelDescriptor, ...]
    space_type: str = "VIEW_3D"
    region_type: str = "UI"

    @property
    def panel_labels(self) -> tuple[str, ...]:
        return tuple(panel.label for panel in self.panels if panel.label)

    @property
    def source_modules(self) -> tuple[str, ...]:
        return tuple(sorted({panel.module for panel in self.panels if panel.module}))

    @property
    def source_owners(self) -> tuple[str, ...]:
        owners = {module_owner_key(module) for module in self.source_modules}
        owners.discard("")
        return tuple(sorted(owners))

    @property
    def panel_identifiers(self) -> tuple[str, ...]:
        return tuple(sorted({panel.identifier for panel in self.panels if panel.identifier}))

    @property
    def identity_panel_identifiers(self) -> tuple[str, ...]:
        identifiers = {
            panel.identifier
            for panel in self.panels
            if panel.identifier and not panel.parent_id
        }
        return tuple(sorted(identifiers)) or self.panel_identifiers

    @property
    def origin_key(self) -> str:
        return make_origin_key(
            self.space_type,
            self.region_type,
            self.source_owners,
            self.identity_panel_identifiers,
        )

    @property
    def inferred_source_names(self) -> tuple[str, ...]:
        names = {module_display_name(module) for module in self.source_modules}
        names.discard("")
        return tuple(sorted(names))


def make_target_key(space_type: str, region_type: str, category: str) -> str:
    """Build the persistent locator for a native sidebar category."""

    safe_parts = (
        _safe_key_part(space_type),
        _safe_key_part(region_type),
        _safe_key_part(category),
    )
    return TARGET_KEY_SEPARATOR.join(safe_parts)


def make_origin_key(
    space_type: str,
    region_type: str,
    source_owners: Iterable[str],
    panel_identifiers: Iterable[str],
) -> str:
    """Build an identity that is independent from a panel's visible category."""

    components = (
        "v1",
        str(space_type),
        str(region_type),
        *sorted({str(value) for value in source_owners if value}),
        "",
        *sorted({str(value) for value in panel_identifiers if value}),
    )
    digest = hashlib.sha256("\0".join(components).encode("utf-8")).hexdigest()
    return f"panel:{digest[:32]}"


def module_owner_key(module: str) -> str:
    """Return the add-on package portion of a registered panel module."""

    parts = [part for part in str(module or "").split(".") if part]
    if len(parts) >= 3 and parts[0] == "bl_ext":
        return ".".join(parts[:3])
    return parts[0] if parts else ""


def module_display_name(module: str) -> str:
    """Return a readable source hint without claiming an add-on identity."""

    if not module:
        return ""

    parts = [part for part in module.split(".") if part]
    if len(parts) >= 3 and parts[0] == "bl_ext":
        source = parts[2]
    else:
        source = parts[0]

    return source.replace("_", " ").replace("-", " ").strip().title()


def join_metadata(values: Iterable[str]) -> str:
    return "\n".join(value for value in values if value)


def split_metadata(value: str) -> tuple[str, ...]:
    return tuple(part for part in value.splitlines() if part)


def _safe_key_part(value: str) -> str:
    return str(value).replace(TARGET_KEY_SEPARATOR, " ").strip()
