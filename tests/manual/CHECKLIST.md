# Manual Blender 5.x Checklist

Run every release candidate in Blender 5.0, 5.1, and 5.2.

## Installation

- Validate and build from `blender_manifest.toml`.
- Install the generated ZIP into a clean Blender profile.
- Enable and disable the extension twice without console errors.
- Configure a group, favorite, target name, icon, and appearance setting, then
  disable and re-enable the extension twice and confirm all values survive.
- Disable the configured extension, restart Blender, enable it, and confirm the
  saved configuration is restored.
- Restart Blender and confirm preferences remain available.
- Change a setting, wait one second, force-close Blender, restart, and confirm the
  latest automatic snapshot can be restored after recreating the add-on record.
- Export a configuration ZIP, change groups, favorites, and icons, import it, and
  confirm the exported state is restored.
- Confirm `preferences.json`, `.bak`, and `.pending` never appear inside the
  installed extension directory.

## Detection

- Confirm third-party `VIEW_3D` / `UI` tabs appear in Library.
- Confirm built-in tabs are hidden by default.
- Enable "Include Blender Tabs", refresh, and confirm they appear.
- Disable a detected add-on and confirm its saved entry becomes unavailable.
- Re-enable that add-on and confirm customization is recovered.

## Navigation

- Invoke the launcher with `F5` over a 3D View.
- Open a target while the sidebar is closed.
- Confirm the native tab becomes active and the popup closes.
- Repeat with two 3D Views and verify only the invoking area changes.
- Repeat in Object, Edit, Sculpt, and Pose modes.
- Confirm unavailable context-specific tabs are disabled.
- Confirm the compact row keeps the order View, Tool, Edit, Item and omits
  unavailable entries without leaving gaps.
- Confirm Item disappears without an active object and returns with one.
- Confirm Edit appears only while another add-on provides it in the current mode.
- Toggle "Include Blender Tabs" and confirm the compact row does not change.

## Organization

- Migrate three legacy favorites and confirm their order is preserved.
- Add, replace, and remove up to eight favorites.
- Reorder favorites in the configuration panel and confirm the popup stays clean.
- Confirm a ninth favorite is rejected without changing the collection.
- Confirm populated categories are ordered by available tab count in Library.
- Confirm empty categories use compact labels and all available tabs remain accessible.
- Use the `+` in populated and empty popup categories to assign or move a tab.
- Assign more than five targets and confirm the popup shows five plus `+N more`.
- With four populated categories, confirm `All Tabs` opens by default. Populate a
  fifth category, reopen Library, and confirm `All Tabs` starts closed but expands.
- Select a category in the configuration panel and use its compact tab list to
  add, reorder, open, and remove members.
- Remove a category member and confirm the tab remains available in Library.
- Delete a group and verify library entries remain unassigned.
- Confirm Library's `Detected Panels` details start closed and can be expanded.
- Confirm the latest opened target appears under Search with its open count.
- On a genuinely fresh installation, confirm Recent initially shows up to three
  available sample tabs with no artificial open counts.
- Open a real target and confirm all sample recents are replaced by real history.
- Open a sidebar tab manually, invoke the launcher, and confirm Recent updates once.

## Search

- Search by displayed name.
- Search by native tab name.
- Confirm panel labels and module names are not appended to result names.
- Navigate with arrows and confirm with Enter.
- Hide an entry and confirm it is excluded from search.

## Appearance

- On a fresh profile, confirm the popup width starts at 400 and icon color at Original.
- Test Blender light and dark themes.
- Test UI scales 0.75, 1.0, 1.5, and 2.0.
- Invoke near all four screen edges.
- Test name-only and combined icon-and-name modes.
- Load valid and missing custom PNG icons.
- Confirm missing icons use a safe fallback.
- Confirm all 16 included `QNP_*` icons appear in both icon selectors.
- Confirm category and library icon selectors remain beside their name fields.
- Assign an included icon to a group and to a library tab, then restart Blender.
- Switch repeatedly between Original, White, and Custom; confirm popup icons and
  large selector thumbnails refresh without becoming empty or requiring a restart.
- Confirm Favorites opens by default and the other configuration panels collapse.
- Confirm the compact popup shows Search, Favorites, Library, and Configure.
- Open Library and confirm the compact launcher remains behind the popover.
- Confirm categories use two columns and as many rows as required.

## Cleanup

- Confirm the add-on preferences and Diagnostics contain no keymap controls.
- Edit or disable the shortcut only under Blender's Preferences > Keymap.
- Disable the extension and confirm its shortcut disappears.
- Confirm no load handlers or preview collections produce console errors.
- Trigger navigation while the sidebar is opening, immediately disable the
  extension, and confirm no deferred timer runs afterward.
- Re-enable it and confirm the launcher works without restarting Blender.

## Update and Recovery

- Update from a package that created `preferences-v1.json` and confirm it is
  restored into the current v2 schema without losing groups, favorites, history,
  hidden tabs, appearance, or icon assignments.
- Corrupt the current snapshot in an isolated test profile and confirm the `.bak`
  generation restores it.
- Simulate a locked destination and confirm a `.pending` snapshot remains
  restorable.
- Replace, remove, and reassign managed icons; confirm an icon referenced by the
  backup survives one generation and is cleaned only after it is unreferenced by
  both generations.
- Export before uninstalling, reinstall from a different repository, import, and
  confirm settings and managed icons transfer correctly.
