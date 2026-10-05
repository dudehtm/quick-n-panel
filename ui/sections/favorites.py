"""Ordered favorite configuration section."""

from ...constants import FAVORITES_VISIBLE_ROWS, MAX_FAVORITE_RECORDS


def draw(layout, _context, preferences):
    if not preferences.favorites:
        layout.label(text="No favorites configured", icon="INFO")
    else:
        visible_rows = min(FAVORITES_VISIBLE_ROWS, len(preferences.favorites))
        layout.template_list(
            "QNP_UL_launcher_favorite_config",
            "configuration",
            preferences,
            "favorites",
            preferences,
            "favorite_index",
            rows=visible_rows,
            maxrows=FAVORITES_VISIBLE_ROWS,
        )

    layout.separator()
    add_row = layout.row(align=True)
    add_row.enabled = len(preferences.favorites) < MAX_FAVORITE_RECORDS
    add = add_row.operator(
        "quick_n_panel.assign_favorite",
        text="Add Favorite",
        icon="ADD",
    )
    add.index = -1
