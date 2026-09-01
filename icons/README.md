# Icons

Included icons live under `Custom/` and are discovered when the extension is
enabled. Files must be RGBA PNG images with unique names beginning with `QNP_`.
The current visual set uses a 96 x 96 pixel transparent canvas.

Examples:

```text
Custom/QNP_Favorites.png
Custom/QNP_Modeling.png
Custom/QNP_Rigging.png
```

The filename without `QNP_` becomes the label in the visual icon selector.
User-selected external PNG files are imported as managed 96 x 96 copies under
Blender's user data directory, so moving or deleting the source does not break
the assignment. Sources larger than 1024 x 1024 pixels or 16 MB are rejected.
Blender icons are used as the final fallback.

## License and provenance

Copyright (C) 2026 Dudehtm.

All PNG files under `Custom/` are original assets created by Dudehtm using
Photopea and GIMP. No third-party logos, trademarks, or source artwork are
included.

The artwork is dedicated to the public domain under CC0 1.0 Universal. See
`../LICENSES/CC0-1.0.txt` for the complete legal code.
