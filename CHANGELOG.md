# Changelog

## 1.1.0 - 2026-10-04

- Added a Blender-managed update status notice in the configuration header and
  detailed update information in Diagnostics. The extension only reads
  Blender's cached repository index and never installs updates itself.
- Added experimental automatic opening for the Library and Categories popovers
  when the configured launcher shortcut is used. The options are mutually
  exclusive and displayed as compact one-line controls.
- Updated the configuration labels to show the effective launcher shortcut after
  a user changes the default `F5` binding in Blender's Keymap preferences.
- Removed the duplicated `Quick N-panel` label from the configuration header.
- Reworked `New` detection to use Blender's enabled add-on registry instead of
  inferring add-on owners from retained panel targets.
- Added exact module matching for legacy add-ons and Blender Extensions, including
  `bl_ext.<repository>.<package>`, to reduce false positives and missed installs.
- Added a persistent enabled-add-on baseline, enable/disable transition handling,
  same-session panel incarnation tracking, and sidecar migration to schema `v8`.
- Added the migration from schema `v8` to `v9` for the experimental Library and
  Categories startup options.
- Added coverage for baseline creation, extension keys, re-enablement,
  reinstalls, expiration, dismissal, and Blender lifecycle detection.

## 1.0.1 - 2026-09-01

- Added the public GitHub repository and issue tracker to the extension metadata.
- Simplified shortcut management: Quick N-panel registers and unregisters its
  default `F5` shortcut, while users customize it through Blender's native
  `Preferences > Keymap` editor.
- Removed the obsolete extension tag and retained `User Interface`.
- Added public bug-report templates and automated unit tests.
