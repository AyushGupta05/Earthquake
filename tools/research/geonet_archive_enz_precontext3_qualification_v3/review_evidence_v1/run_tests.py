"""Only invented fixture tests in this source packet."""
from pathlib import Path
import unittest

if __name__ == '__main__':
    root = Path(__file__).resolve().parent
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.discover(str(root), pattern='test*.py'))
    raise SystemExit(not result.wasSuccessful())
