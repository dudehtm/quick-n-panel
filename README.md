<img width="256" height="256" alt="icon QNP" src="https://github.com/user-attachments/assets/80e4ef1f-bf25-4234-bc7d-126b12283519" />
# Quick N-panel

Quick N-panel is a Dudehtm extension for Blender 5.0 or newer, tested through
Blender 5.2. It detects add-on tabs in the 3D Viewport N-panel and lets you open
them from a quick launcher. It does not copy panels, register third-party
interfaces, or manage installations.

## Features

<img width="1919" height="985" alt="Captura de pantalla 2026-08-23 172606" src="https://github.com/user-attachments/assets/0a49ec8d-6301-48bb-9025-7e9dcde0913a" />

Quick N-panel is packaged as a modern Blender extension and provides:

- detection of `VIEW_3D` / `UI` panels;
- grouping by native `bl_category` tab;
- navigation through `Region.active_panel_category`;
- compact popup with search, recent access, and up to eight favorites;
- new-install defaults of a 400 px popup and original custom icon colors;
- compact contextual shortcuts for View, Tool, Edit, and Item;
- compact Library popover with categories, quick assignment, and a collapsible list
  of every available tab;
- compact category-member management in the configuration panel;
- six general-purpose groups created during initial setup;
- bundled library of `QNP_*` icons for groups and tabs;
- self-refreshing small and large icon previews without restarting Blender;
- configuration panel organized into collapsible sections;
- dynamic, ordered favorites limited to eight entries;
- recent access with persistent counters and timestamps;
- starter Recent entries on a fresh installation, replaced by real activity;
- native search with simplified tab names;
- persistent configuration in `AddonPreferences`;
- previews for custom icons and accents;
- `F5` launcher shortcut registered in the `3D View` keymap and customizable
  through Blender's standard `Preferences > Keymap` editor;
- recovery of targets that disappear and are registered again;
- configuration recovery after disabling and re-enabling the extension;
- atomic, versioned configuration snapshots with backup recovery;
- portable ZIP export and import, including user-selected managed icons.

## Installation

Release packages can be installed from Blender with
`Edit > Preferences > Get Extensions > Install from Disk`.

To build the extension from a source checkout:

1. Clone the repository:

   ```text
   git clone https://github.com/dudehtm/quick-n-panel.git
   cd quick-n-panel
   ```

2. Build the extension with Blender 5.x:

   ```text
   blender --command extension validate
   blender --command extension build
   ```

3. Open Blender and select `Edit > Preferences > Get Extensions > Install from Disk`.
4. Select the generated ZIP file and enable Quick N-panel.
5. Open a 3D Viewport and press `F5`.

Management controls are available under `3D View > Sidebar > Quick N-panel`.

Because it uses `blender_manifest.toml`, Blender installs it under
`extensions/<repository>/quick_n_panel`. This is the correct location for a
modern extension; do not move it to `scripts/addons`.

## Shortcut

Quick N-panel registers `F5` in Blender's `3D View` keymap. To change or disable
it, open `Edit > Preferences > Keymap` and search for `Quick N-panel` or
`quick_n_panel.show_launcher`. The extension intentionally does not modify user
keymaps or provide a separate shortcut editor.
<img width="1920" height="1080" alt="QNP F" src="https://github.com/user-attachments/assets/98993f37-0bb5-4b70-b883-f1fe395d6298" />

## Included Icons

Bundled PNG files are discovered automatically under `icons/Custom/`. They must
use the `QNP_` prefix, RGBA format, and unique names, such as
`QNP_Modeling.png`. The filename becomes the label shown in the visual selector.

Icons can be assigned to groups from `Categories` and to detected tabs from
`Library`. A bundled icon takes precedence over an external PNG file. If neither
is available, the configured native Blender icon is used as a fallback.

The included PNG assets are original works by Dudehtm, created using Photopea
and GIMP, and dedicated to the public domain under CC0-1.0. See
`icons/README.md` for provenance.

## Configuration Safety

Blender stores the live model in `AddonPreferences`. Quick N-panel also writes a
debounced, atomic `preferences.json` snapshot under Blender's extension user-data
directory. The previous valid generation is retained as `.bak`, interrupted
writes can recover from `.pending`, and unreadable snapshots are quarantined
instead of overwritten.

Sidecar format migrations are sequential. The current reader migrates the
original v1 format to v2 before validation. Managed external icons are stored in
the same extension-owned user-data directory and are deleted only after neither
the current snapshot nor its backup references them.

Use `Diagnostics > Configuration Backup > Export` before uninstalling, changing
extension repositories, moving to another profile, or transferring to another
computer. The resulting ZIP contains settings and managed custom icons and can
be restored with `Import`.

## Architecture

```text
core/catalog.py             Pure models and stable identity
core/scanner.py             Detection and runtime cache
core/navigation.py          Tab opening, activation, and history
core/search.py              Normalization and approximate ranking
core/icons.py               Previews, QNP_* library, and accents
core/compatibility.py       Blender feature probes
persistence.py              Versioned snapshots and portable backups
operators/favorites.py      Ordered favorites collection
operators/groups.py         Categories, memberships, and ordering
operators/library.py        Refresh and customization
operators/launcher.py       Popup and native search
ui/popup.py                 Compact and expanded layouts
ui/sections/                Collapsible configuration panel content
preferences.py              Persistent user settings root
registration.py             Transactional, reversible registration
keymap.py                    Default shortcut registration and cleanup
```

A target's persistent identity has the following form:

```text
VIEW_3D|UI|<bl_category>
```

An entry represents a native tab, not an inferred add-on identity. This avoids
ambiguity when multiple panels or add-ons share a tab.

## Testing

From a source checkout, run the pure tests without Blender:

```text
python -m unittest discover -s tests/unit -v
```

Smoke test after installing the extension:

```text
blender --background --python tests/blender/smoke_test.py
```

Without `--background`, the smoke test also checks actual tab activation. The
manual test matrix is available in `tests/manual/CHECKLIST.md`. Tests are
development files and are intentionally excluded from the published ZIP.

## Reporting Issues

Please report reproducible bugs through [GitHub Issues](../../issues). Include
your Blender version, Quick N-panel version, operating system, reproduction
steps, and relevant console output. Remove private information before attaching
logs or screenshots.

## Known Limitations

- Blender does not expose a universal add-on identity for every panel.
- Search uses `invoke_search_popup`; Blender controls its width and visible row
  count.
- Native mode does not support animating the side popover as it opens.
- Manually opened tabs are captured the next time the launcher is invoked,
  without a permanent background observer.
- Interactive release tests currently require actual Blender 5.0-5.2
  installations.

## License

Copyright (C) 2026 Dudehtm.

Python source and documentation: GPL-3.0-or-later. Original PNG artwork:
CC0-1.0. See `LICENSE` and `LICENSES/`.
