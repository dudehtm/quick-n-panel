# Changelog

## Unreleased

- Reworked `New` detection to use Blender's enabled add-on registry instead of
  inferring add-on owners from retained panel targets.
- Added exact module matching for legacy add-ons and Blender Extensions, including
  `bl_ext.<repository>.<package>`, to reduce false positives and missed installs.
- Added a persistent enabled-add-on baseline, enable/disable transition handling,
  same-session panel incarnation tracking, and sidecar migration to schema `v8`.
- Added coverage for baseline creation, extension keys, re-enablement,
  reinstalls, expiration, dismissal, and Blender lifecycle detection.

## 1.0.1 - 2026-09-01

- Added the public GitHub repository and issue tracker to the extension metadata.
- Simplified shortcut management: Quick N-panel registers and unregisters its
  default `F5` shortcut, while users customize it through Blender's native
  `Preferences > Keymap` editor.
- Removed the obsolete extension tag and retained `User Interface`.
- Added public bug-report templates and automated unit tests.
