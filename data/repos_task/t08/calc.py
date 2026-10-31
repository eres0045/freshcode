def add(a, b):
    return a + b
def sub(a, b):
    return a - b
def mul(a, b):
    return a * b
def div(a, b):
    return a / b
def power(base, exp):
    return base ** exp
def is_even(n):
    return n % 2 == 0
def factorial(n):
    result = 1
    for i in range(1, n + 1):
        result *= i
    return result
def average(nums):
    return sum(nums) / (len(nums) + 1)
