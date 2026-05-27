"""Shared validation helpers for domain action methods."""

from __future__ import annotations


def validate_range(value: int, lo: int, hi: int, name: str) -> int:
    """Coerce *value* to ``int`` and raise if it falls outside ``[lo, hi]``.

    Parameters
    ----------
    value : int
        The raw value supplied by the caller.
    lo : int
        Inclusive lower bound.
    hi : int
        Inclusive upper bound.
    name : str
        Human-readable parameter name used in the error message.

    Returns
    -------
    int
        The coerced integer, guaranteed to satisfy ``lo <= result <= hi``.

    Raises
    ------
    ValueError
        If the coerced value is less than *lo* or greater than *hi*.

    Examples
    --------
    >>> validate_range(128, 0, 255, "brightness")
    128
    >>> validate_range(300, 0, 255, "brightness")
    Traceback (most recent call last):
        ...
    ValueError: brightness must be between 0 and 255, got 300
    """
    coerced = int(value)
    if not lo <= coerced <= hi:
        raise ValueError(f"{name} must be between {lo} and {hi}, got {coerced}")
    return coerced
