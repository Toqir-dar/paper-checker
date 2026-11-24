"""Batch EDA helpers including Bonferroni-aware correlation warnings."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class CorrelationFinding:
    feature_a: str
    feature_b: str
    pearson_r: float
    p_value_approx: float
    significant_raw: bool
    significant_bonferroni: bool


@dataclass
class EdaMetrics:
    n_students: int
    mean_score: float | None
    std_score: float | None
    correlations: list[CorrelationFinding]
    warnings: list[str]


def _pearson(x: np.ndarray, y: np.ndarray) -> float:
    if x.size < 2:
        return 0.0
    if np.std(x) == 0 or np.std(y) == 0:
        return 0.0
    return float(np.corrcoef(x, y)[0, 1])


def _approx_p_value(r: float, n: int) -> float:
    """Two-sided p-value approximation via t = r sqrt((n-2)/(1-r^2))."""
    if n < 3 or abs(r) >= 1.0:
        return 0.0 if abs(r) >= 1.0 and n >= 3 else 1.0
    t = abs(r) * ((n - 2) / (1 - r * r)) ** 0.5
    # Rough survival function using erfc for a Normal approx of t when n is moderate.
    from math import erfc, sqrt

    return float(erfc(t / sqrt(2)))


def analyze_batch_scores(
    scores: list[float],
    roll_numeric: list[float | None],
    *,
    alpha: float = 0.05,
) -> EdaMetrics:
    """Flag spurious score↔roll_number correlations with a Bonferroni note."""
    warnings: list[str] = []
    correlations: list[CorrelationFinding] = []
    n = len(scores)
    if n == 0:
        return EdaMetrics(
            n_students=0,
            mean_score=None,
            std_score=None,
            correlations=[],
            warnings=["No graded students available for EDA."],
        )

    arr = np.asarray(scores, dtype=float)
    mean_score = float(arr.mean())
    std_score = float(arr.std(ddof=0))

    paired_scores: list[float] = []
    paired_rolls: list[float] = []
    for s, r in zip(scores, roll_numeric):
        if r is not None:
            paired_scores.append(s)
            paired_rolls.append(r)

    tests = 1  # score vs roll — extend if more features are added
    if len(paired_scores) >= 3:
        r = _pearson(np.asarray(paired_scores), np.asarray(paired_rolls))
        p = _approx_p_value(r, len(paired_scores))
        raw_sig = p < alpha
        bonf_sig = p < (alpha / tests)
        correlations.append(
            CorrelationFinding(
                feature_a="total_score_fraction",
                feature_b="roll_number_numeric",
                pearson_r=round(r, 4),
                p_value_approx=round(p, 6),
                significant_raw=raw_sig,
                significant_bonferroni=bonf_sig,
            )
        )
        if raw_sig and not bonf_sig:
            warnings.append(
                "Score vs roll_number looked significant before Bonferroni correction — "
                "treat as a spurious multiple-testing risk, not a real effect."
            )
        elif bonf_sig:
            warnings.append(
                "Score vs roll_number remains significant after Bonferroni correction; "
                "investigate data entry bias before interpreting."
            )

    return EdaMetrics(
        n_students=n,
        mean_score=round(mean_score, 4),
        std_score=round(std_score, 4),
        correlations=correlations,
        warnings=warnings,
    )


def parse_roll_numeric(roll: str) -> float | None:
    digits = "".join(ch for ch in roll if ch.isdigit())
    if not digits:
        return None
    try:
        return float(digits)
    except ValueError:
        return None
