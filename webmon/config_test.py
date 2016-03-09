import unittest

import config


class TestApplyDefaults(unittest.TestCase):
    def test_empty_defaults(self):
        defaults = {}
        conf = {
            "a": "a",
            "b": [1, [1, 2, 3], {"12": 12}],
            "c": {
                "c1": 123,
                "c2": 234,
                "c3": [1, 2, 3, 4, 5],
                "c5": {"a1": "a1"}
            }
        }
        res = config.apply_defaults(defaults, conf)
        self.assertDictEqual(res, conf)

    def test_noempty_defaults(self):
        defaults = {
            "a": "123",
            "c": {
                "c5": {
                    "a1": "a0",
                    "a2": "a2",
                },
                "c6": [1, 2, 3],
            },
            "d": 12,
        }
        conf = {
            "a": "a",
            "b": [1, [1, 2, 3], {"12": 12}],
            "c": {
                "c1": 123,
                "c2": 234,
                "c3": [1, 2, 3, 4, 5],
                "c5": {"a1": "a1"}
            }
        }
        res = config.apply_defaults(defaults, conf)
        self.assertEqual(res["a"], "a")
        self.assertEqual(res["b"], [1, [1, 2, 3], {"12": 12}])
        self.assertEqual(res["c"]["c1"], 123)
        self.assertEqual(res["c"]["c2"], 234)
        self.assertEqual(res["c"]["c3"], [1, 2, 3, 4, 5])
        self.assertEqual(res["c"]["c5"]["a1"], "a1")
        self.assertEqual(res["c"]["c5"]["a2"], "a2")
        self.assertEqual(res["c"]["c6"], [1, 2, 3])
        self.assertEqual(res["d"], 12)


if __name__ == '__main__':
    unittest.main()
