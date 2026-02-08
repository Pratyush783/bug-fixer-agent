from __future__ import annotations

from src.calculator import add, subtract, multiply, divide

def run():
    print("Calculator demo")
    print("10 / 2 =", divide(10, 2))
    print("10 / 0 =", divide(10, 0))  # will crash before fix

if __name__ == "__main__":
    run()
