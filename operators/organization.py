"""Registration facade for organization operators."""

from .favorites import CLASSES as FAVORITE_CLASSES
from .groups import CLASSES as GROUP_CLASSES
from .library import CLASSES as LIBRARY_CLASSES


CLASSES = (
    *LIBRARY_CLASSES,
    *FAVORITE_CLASSES,
    *GROUP_CLASSES,
)
