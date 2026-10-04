# Performance Audit

This document is the performance baseline for Quick N-panel. Read it before
changing the launcher, scanner, icon previews, persistence, or UI lists.

## Symptoms

- The cursor remains responsive, but launcher buttons react late on hover.
- The delay is visible in an empty scene and becomes clearer in a heavy scene.
- The delay disappears when the launcher closes.
- Library and Categories are not required to reproduce the base-popup delay.

## Root Cause

The launcher is redrawn by Blender for hover, selection, and other UI events.
The redraw path used to call `scanner.refresh_catalog()` from
`ui/popup.py`. Before returning a fresh snapshot, the scanner enumerated
enabled add-ons and recursively inspected registered `Panel` classes. This
made a cache hit expensive and repeated global work while the popup was open.

The scanner was also called again by direct-category discovery. Individual
buttons then rebuilt `CatalogSnapshot.by_key`, checked target availability,
possibly executed third-party `Panel.poll()`, and resolved icons.

The main regression was introduced by commit `67f3a65`, which added reliable
add-on reincarnation detection before the existing cache check. The favorites
UIList in `f3a70e3` added a smaller cost: ten visible rows instead of eight and
additional redraws when its active row changes. Reverting the UIList would not
remove the scanner cost.

## Hot Paths

| Priority | Location | Problem |
| --- | --- | --- |
| P0 | `core/scanner.py:67` | Panel/add-on signature work happens before the cache return. |
| P0 | `ui/popup.py:29` | The launcher redraw refreshes the catalog. |
| P0 | `core/scanner.py:345` | Direct categories refresh the catalog again. |
| P0 | `core/scanner.py:25` | `by_key` is rebuilt on every property access. |
| P1 | `core/scanner.py:329` | Context availability can execute third-party `poll()`. |
| P1 | `core/icons.py:270` | Icon resolution can touch the filesystem per redraw. |
| P1 | `ui/popup.py:430` | `favorite_keys()` is rebuilt for every category row. |
| P1 | `core/memberships.py:6` | Category membership JSON is parsed repeatedly. |
| P2 | `persistence.py:280` | Synchronous sidecar writes can cause separate interaction stalls. |

## Required Design

Separate the launcher lifecycle into three levels:

1. **Open or explicit refresh:** scan panels, detect add-on transitions,
   reconcile preferences, and prepare the catalog.
2. **UI redraw:** read prepared snapshots and draw controls only. No global
   panel enumeration, catalog scan, or filesystem probing for known icons.
3. **Real data change:** invalidate only the affected runtime cache.

New add-on tabs are allowed to appear when the launcher is opened again or
when the user explicitly presses Refresh. The launcher does not need live
catalog updates while it remains open.

## Implemented Critical Phases

The following phases are implemented after this audit:

- scanner fast path before panel/add-on signature work;
- catalog scan removed from launcher redraw;
- direct categories reuse the current snapshot;
- materialized `by_key` and `panel_count` snapshot indexes;
- one per-redraw availability/favorite state for launcher buttons;
- native/icon-name fast paths before custom preview work;
- tests protecting the no-refresh redraw contract and snapshot indexes.

## Deferred Phases

These remain intentionally deferred until the critical changes are measured:

- full Library/Categories membership model caching;
- post-last-change persistence debounce and payload deduplication;
- preview rebuild coalescing while editing appearance;
- reconciliation indexes for large stale catalogs;
- removal of low-impact dead helpers and unused fuzzy-search code.

## Measurement Checklist

Compare the following with the same Blender profile and catalog:

- main branch, pre-optimization secondary branch, and optimized branch;
- empty and heavy scenes;
- popup closed and popup open for five seconds;
- 0, 8, 10, and 30 favorites;
- native icons, bundled icons, and `NAME` display mode;
- Object, Edit, Sculpt, and Pose modes;
- Blender 5.0, 5.1, and 5.2.

Record:

- launcher draw time and p95 draw time;
- number of catalog refreshes during redraw;
- registered-panel enumeration count;
- `by_key` allocations/builds;
- third-party `Panel.poll()` count and time;
- icon filesystem checks;
- redraw count during hover and UIList scrolling.

Targets:

- zero catalog scans during hover or scroll;
- zero panel enumeration during a hot redraw;
- zero filesystem reads for known native/bundled icons;
- one availability check per target per redraw at most;
- launcher draw normally below 2-4 ms in a warm popup.

## Review Rule

Any future launcher feature must state whether its work runs during open,
redraw, or explicit data change. Work that enumerates all panels, sorts the
full catalog, parses all membership JSON, runs third-party polls, or touches
the filesystem must not be added to the hot redraw path without a benchmark.
