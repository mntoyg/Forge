"""Sample input with nothing wrong with it, deliberately.

This is the control case. `buggy_division.py` shows that Forge can find a real
defect; this file shows whether Forge can say there is none. A model asked to
find problems will find them whether they exist or not, so a run over correct
code is the only way to tell a useful report apart from a plausible one.

The two functions here are the ones `buggy_division.py` gets wrong, written
correctly: the empty case is guarded, the boundary is stated, and each
precondition is documented rather than assumed.

A finding against this file is worth reading closely. It is either a real
subtlety worth knowing about, or exactly the noise this file exists to measure.

This file is analysed, never executed.
"""


def average(values: list[float]) -> float | None:
    """The arithmetic mean of ``values``, or ``None`` when there are none.

    ``None`` rather than ``0.0`` because "there was no data" and "the data
    averages to zero" are different answers, and a caller that cannot tell them
    apart will eventually act on the wrong one.
    """
    if not values:
        return None
    return sum(values) / len(values)


def last_n(values: list[float], n: int) -> list[float]:
    """The last ``n`` items of ``values``, or all of them if there are fewer.

    ``n == 0`` is handled before the slice on purpose: ``values[-0:]`` is
    ``values[0:]``, which returns the whole list rather than nothing.

    Raises:
        ValueError: ``n`` is negative, which asks for a length that cannot
            exist.
    """
    if n < 0:
        raise ValueError(f"n must not be negative, got {n}.")
    if n == 0:
        return []
    return values[-n:]
