def reverse(s):
    return s[::-1]
def is_palindrome(s):
    return s == s[::-1]
def count_vowels(s):
    return sum(1 for c in s.lower() if c in "aeiou")
def title_case(s):
    return s.title()
def slugify(s):
    return s.lower().replace(" ", "-")
def truncate(s, n):
    return s[:n]
def repeat(s, n):
    return "".join([s] * n)
