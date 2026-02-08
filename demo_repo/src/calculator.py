from __future__ import annotations

def add(a: float, b: float) -> float:
    return a + b

def subtract(a: float, b: float) -> float:
    return a - b

def multiply(a: float, b: float) -> float:
    return a * b

# BUG: division by zero crashes the app (ZeroDivisionError)
def divide(a: float, b: float) -> float:
    return a / b
