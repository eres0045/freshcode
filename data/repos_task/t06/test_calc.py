import unittest
from calc import add, sub, mul, div, power, is_even, factorial, average


class TestCalc(unittest.TestCase):
    def test_add(self):
        self.assertEqual(add(2, 3), 5)

    def test_sub(self):
        self.assertEqual(sub(5, 3), 2)

    def test_mul(self):
        self.assertEqual(mul(2, 3), 6)

    def test_div(self):
        self.assertEqual(div(6, 3), 2)

    def test_power(self):
        self.assertEqual(power(2, 3), 8)

    def test_is_even(self):
        self.assertTrue(is_even(4))
        self.assertFalse(is_even(5))

    def test_factorial(self):
        self.assertEqual(factorial(5), 120)

    def test_average(self):
        self.assertEqual(average([2, 4]), 3)


if __name__ == "__main__":
    unittest.main()
