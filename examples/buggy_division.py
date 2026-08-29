"""Sample input for manual testing.

Known problems, deliberately left in place:

1. ``average`` divides by ``len(values)`` without guarding the empty case, so
   an empty list raises ``ZeroDivisionError``.
2. ``last_n`` uses ``n - 1``, an off-by-one that silently returns one item
   fewer than asked for.
3. Neither function documents or validates its preconditions.

This file is analysed, never executed.
"""


def average(values: list[float]) -> float:
    return sum(values) / len(values)


def last_n(values: list[float], n: int) -> list[float]:
    return values[-(n - 1) :]
