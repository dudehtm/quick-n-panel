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
- On a clean profile, open the launcher once with `F5` and confirm the first
  scan creates no `New` notifications.
- Install and enable an add-on from a ZIP that registers a `VIEW_3D` / `UI` panel,
  refresh with `F5`, and confirm it appears in `New` below `Recent`.
- Install and enable an extension from `Get Extensions`, refresh, and confirm its
  `bl_ext.<repository>.<package>` module key is recognized.
- Install a package without enabling it and confirm it does not appear in `New`.
- Register or enable an add-on whose panels do not belong to an enabled module and
  confirm it does not create a false `New` entry.
- Confirm no more than three `New` entries are visible and each shows a dismiss
  control.
- Open a `New` target and confirm it disappears immediately from the block.
- Dismiss a `New` target with `X`, reopen the launcher, and confirm it stays hidden.
- Disable a detected add-on and confirm its saved entry becomes unavailable.
- Re-enable that add-on, refresh, and confirm it can appear as a new enable
  transition while its saved customization is recovered.
- Uninstall and reinstall an enabled add-on while Blender remains open, refresh,
  and confirm the same-key reinstallation is detected when its panel classes are
  recreated.

## Navigation

- Invoke the launcher with `F5` over a 3D View.
- Confirm `F5` opens the launcher with Library and Categories closed.
- Confirm Library is not opened automatically in the current release.
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
- Add, replace, and remove at least 30 favorites.
- Reorder favorites in the scrollable configuration list and confirm the popup stays clean.
- Confirm the launcher shows ten favorite rows and scrolls internally to reach later entries.
- Confirm the configuration list scrolls internally and keeps its actions available.
- Confirm the launcher shows separate `Library` and `Categories` buttons with
  matching visual treatment.
- Confirm populated categories follow the order configured in Categories, not
  the number of assigned tabs.
- Confirm every populated category displays all assigned tabs, including 20 or
  more targets, without a `+N more` limit.
- Confirm categories of different sizes are packed into two columns without
  unnecessary vertical gaps.
- Use the `+` in populated and empty category rows to assign or move a tab.
- Confirm `Empty Categories (N)` starts collapsed and can be expanded temporarily.
- Reopen with `F5` and confirm the empty-category section returns to collapsed.
- Confirm `Library` contains all tabs and `Categories` contains no `All Tabs` list.
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
- Confirm the compact popup shows Search, Favorites, Library, Categories, and
  Configure.
- Open Library and Categories separately and confirm the compact launcher remains
  behind each popover.
- Confirm categories use two columns and as many rows as required.
- In `All Tabs`, confirm each target keeps its own icon and also shows its
  category icon, including unassigned or deleted-category targets.
- Test large category counts near all four screen edges and record the first
  scale where content becomes inaccessible.
- Test 30 or more favorites near all four screen edges and confirm the ten-row
  list remains usable.

## Cleanup

- Confirm the add-on preferences and Diagnostics contain no keymap controls.
- Edit or disable the shortcut only under Blender's Preferences > Keymap.
- Disable the extension and confirm its shortcut disappears.
- Confirm no load handlers or preview collections produce console errors.
- Trigger navigation while the sidebar is opening, immediately disable the
  extension, and confirm no deferred timer runs afterward.
- Re-enable it and confirm the launcher works without restarting Blender.

## Update and Recovery

- Update from an older configuration snapshot and confirm it is restored into
  the current schema without losing groups, favorites, history, hidden tabs,
  appearance, or icon assignments.
- Corrupt the current snapshot in an isolated test profile and confirm the `.bak`
  generation restores it.
- Simulate a locked destination and confirm a `.pending` snapshot remains
  restorable.
- Replace, remove, and reassign managed icons; confirm an icon referenced by the
  backup survives one generation and is cleaned only after it is unreferenced by
  both generations.
- Export before uninstalling, reinstall from a different repository, import, and
  confirm settings and managed icons transfer correctly.
