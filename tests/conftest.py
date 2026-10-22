import importlib.util
import sys
from pathlib import Path

# Drivers import as 'devices.instruments.<name>', the path deployment repos mount
# this library at. Register this checkout under that name so the tests run the
# same way whether it is a submodule at devices/ or a standalone clone.
ROOT = Path(__file__).resolve().parents[1]

spec = importlib.util.spec_from_file_location(
    'devices', ROOT / '__init__.py', submodule_search_locations=[str(ROOT)])
module = importlib.util.module_from_spec(spec)
sys.modules['devices'] = module
spec.loader.exec_module(module)
