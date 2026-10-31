import unittest
from strings import (reverse, is_palindrome, count_vowels, title_case,
                     slugify, truncate, repeat)


class TestStrings(unittest.TestCase):
    def test_reverse(self):
        self.assertEqual(reverse("abc"), "cba")

    def test_is_palindrome(self):
        self.assertTrue(is_palindrome("Madam"))

    def test_count_vowels(self):
        self.assertEqual(count_vowels("education"), 5)

    def test_title_case(self):
        self.assertEqual(title_case("hello world"), "Hello World")

    def test_slugify(self):
        self.assertEqual(slugify("Hello World"), "hello-world")

    def test_truncate(self):
        self.assertEqual(truncate("abcdef", 3), "abc")

    def test_repeat(self):
        self.assertEqual(repeat("ab", 3), "ababab")


if __name__ == "__main__":
    unittest.main()
