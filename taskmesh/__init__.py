# Compatibility shim to expose the src.taskmesh package as taskmesh
import importlib.util
import sys
import os

# Determine the path to the actual src/taskmesh package
src_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src', 'taskmesh'))
if src_path not in sys.path:
    sys.path.insert(0, src_path)

# Import the src.taskmesh package as taskmesh
module_name = 'taskmesh'
spec = importlib.util.find_spec(module_name)
if spec is None:
    from importlib import import_module
    module = import_module('src.taskmesh')
    sys.modules['taskmesh'] = module
