import unittest

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


if __name__ == "__main__":
    unittest.main()
