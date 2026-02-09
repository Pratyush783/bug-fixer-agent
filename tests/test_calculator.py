from demo_repo.src.calculator import add, subtract, multiply, divide
import pytest

def test_add():
    assert add(2, 3) == 5

def test_subtract():
    assert subtract(5, 3) == 2

def test_multiply():
    assert multiply(2, 4) == 8

def test_divide_normal():
    assert divide(10, 2) == 5



# def test_divide_by_zero():
#     with pytest.raises(ValueError, match="divide by zero"):
#         divide(10, 0)
