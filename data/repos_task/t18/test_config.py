import unittest
from config import (get_nested, merge_dicts, flatten_dict, env_int,
                    validate_port)


class TestConfig(unittest.TestCase):
    def test_get_nested(self):
        self.assertEqual(get_nested({"a": {"b": 5}}, ["a", "b"]), 5)
        self.assertEqual(get_nested({"a": {}}, ["a", "x"], 7), 7)

    def test_merge_dicts(self):
        self.assertEqual(merge_dicts({"a": {"x": 1, "y": 2}}, {"a": {"y": 3}}),
                         {"a": {"x": 1, "y": 3}})

    def test_flatten_dict(self):
        self.assertEqual(flatten_dict({"a": {"b": 1}}), {"a.b": 1})

    def test_env_int(self):
        self.assertEqual(env_int("42"), 42)
        self.assertIsInstance(env_int("42"), int)

    def test_validate_port(self):
        self.assertTrue(validate_port(8080))
        self.assertFalse(validate_port(0))
        self.assertFalse(validate_port(70000))


if __name__ == "__main__":
    unittest.main()
