import importlib
import unittest
from pathlib import Path
from unittest import mock

from cachetap import config


class ConfigTest(unittest.TestCase):
    def test_root_contains_tap_py(self):
        self.assertTrue((config.ROOT / "tap.py").is_file())

    def test_ui_and_data_live_under_root(self):
        self.assertEqual(config.UI, config.ROOT / "ui")
        self.assertEqual(config.DATA, config.ROOT / "data")

    def test_max_is_300(self):
        self.assertEqual(config.MAX, 300)

    def test_ttl_s_follows_forced_ttl(self):
        self.assertEqual(config.TTL_S, config.TTL_FORCED or 300)

    def test_reload_does_not_create_directories(self):
        original_log = config.LOG
        try:
            with mock.patch.object(Path, "mkdir") as mkdir:
                importlib.reload(config)
            mkdir.assert_not_called()
        finally:
            config.LOG = original_log


if __name__ == "__main__":
    unittest.main()
