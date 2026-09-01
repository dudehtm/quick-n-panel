"""Load the source tree under its Blender package ID from any checkout path."""

import importlib.util
from pathlib import Path
import sys


PACKAGE_NAME = "quick_n_panel"
PROJECT_ROOT = Path(__file__).resolve().parents[2]


def ensure_source_package():
    if PACKAGE_NAME in sys.modules:
        return

    spec = importlib.util.spec_from_file_location(
        PACKAGE_NAME,
        PROJECT_ROOT / "__init__.py",
        submodule_search_locations=[str(PROJECT_ROOT)],
    )
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load {PACKAGE_NAME} from {PROJECT_ROOT}")

    module = importlib.util.module_from_spec(spec)
    sys.modules[PACKAGE_NAME] = module
    spec.loader.exec_module(module)
