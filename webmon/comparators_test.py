import unittest

import comparators


class TestComaratorAdded(unittest.TestCase):
    def test_empty_prev(self):
        curr = [1, 2, 3, 4]
        prev = []
        diff = comparators.added(prev, None, curr, None)
        self.assertEqual(diff, "1\n2\n3\n4")

    def test_empty_curr(self):
        curr = []
        prev = [1, 2, 3, 4]
        diff = comparators.added(prev, None, curr, None)
        self.assertEqual(diff, "")

    def test_added_1(self):
        curr = [1, 2, 3, 4, 5]
        prev = [1, 2, 3]
        diff = comparators.added(prev, None, curr, None)
        self.assertEqual(diff, "4\n5")

    def test_added_2(self):
        curr = [1, 2, 3, 4, 5]
        prev = [2, 3]
        diff = comparators.added(prev, None, curr, None)
        self.assertEqual(diff, "1\n4\n5")

    def test_added_3(self):
        curr = [1, 2, 3, 4, 5]
        prev = [2, 4, 5]
        diff = comparators.added(prev, None, curr, None)
        self.assertEqual(diff, "1\n3")

    def test_added_4(self):
        curr = [1, 2, 3, 4, 5]
        prev = [2, 4]
        diff = comparators.added(prev, None, curr, None)
        self.assertEqual(diff, "1\n3\n5")

    def test_added_5(self):
        curr = [1, 6]
        prev = [1, 2, 3, 4, 5]
        diff = comparators.added(prev, None, curr, None)
        self.assertEqual(diff, "6")

    def test_added_6(self):
        curr = [6, 7]
        prev = [1, 2, 3, 4, 5]
        diff = comparators.added(prev, None, curr, None)
        self.assertEqual(diff, "6\n7")


class TestComaratorDeleted(unittest.TestCase):
    def test_empty_prev(self):
        curr = [1, 2, 3, 4]
        prev = []
        diff = comparators.deleted(prev, None, curr, None)
        self.assertEqual(diff, "")

    def test_empty_curr(self):
        curr = []
        prev = [1, 2, 3, 4]
        diff = comparators.deleted(prev, None, curr, None)
        self.assertEqual(diff, "1\n2\n3\n4")

    def test_deleted_1(self):
        curr = [1, 2, 3, 4, 5]
        prev = [1, 2, 3]
        diff = comparators.deleted(prev, None, curr, None)
        self.assertEqual(diff, "")

    def test_deleted_2(self):
        curr = [1, 2, 3, 4, 5]
        prev = [2, 3]
        diff = comparators.deleted(prev, None, curr, None)
        self.assertEqual(diff, "")

    def test_deleted_3(self):
        curr = [1, 2, 3, 4, 5]
        prev = [2, 4, 5]
        diff = comparators.deleted(prev, None, curr, None)
        self.assertEqual(diff, "")

    def test_deleted_4(self):
        curr = [1, 2, 3, 4, 5]
        prev = [2, 4]
        diff = comparators.deleted(prev, None, curr, None)
        self.assertEqual(diff, "")

    def test_deleted_5(self):
        curr = [1, 6]
        prev = [1, 2, 3, 4, 5]
        diff = comparators.deleted(prev, None, curr, None)
        self.assertEqual(diff, "2\n3\n4\n5")

    def test_deleted_6(self):
        curr = [6, 7]
        prev = [1, 2, 3, 4, 5]
        diff = comparators.deleted(prev, None, curr, None)
        self.assertEqual(diff, "1\n2\n3\n4\n5")

    def test_deleted_7(self):
        curr = [1, 5]
        prev = [1, 2, 3, 4, 5]
        diff = comparators.deleted(prev, None, curr, None)
        self.assertEqual(diff, "2\n3\n4")

if __name__ == '__main__':
    unittest.main()
