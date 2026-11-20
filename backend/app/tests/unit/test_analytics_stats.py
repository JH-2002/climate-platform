"""T075 — estatísticas descritivas contra valores calculados à mão (AC-082)."""

from __future__ import annotations

import pytest

from app.analytics.stats import coverage, describe, percentile


def test_percentile_matches_linear_method() -> None:
    values = [1.0, 2.0, 3.0, 4.0, 5.0]
    assert percentile(values, 0) == 1.0
    assert percentile(values, 50) == 3.0
    assert percentile(values, 25) == 2.0
    assert percentile(values, 90) == pytest.approx(4.6)  # 4 + 0,6 × (5 − 4)
    assert percentile([10.0], 95) == 10.0
    with pytest.raises(ValueError):
        percentile([], 50)
    with pytest.raises(ValueError):
        percentile(values, 101)


def test_describe_with_known_outlier_and_missing() -> None:
    values: list[float | None] = [2.0, 4.0, 4.0, 4.0, 5.0, 5.0, 7.0, 9.0, 100.0, None, None]
    d = describe(values)
    assert (d.n, d.missing) == (9, 2)
    assert d.mean == pytest.approx(140 / 9)
    assert d.median == 5.0
    assert (d.minimum, d.maximum) == (2.0, 100.0)
    assert (d.p25, d.p75) == (4.0, 7.0)
    # IQR = 3 → limites 4 − 4,5 = −0,5 e 7 + 4,5 = 11,5: só 100 é atípico
    assert d.outlier_count == 1
    assert d.outliers == (100.0,)
    assert d.std == pytest.approx(31.73, abs=0.01)  # √(8054,2 / 8)
    assert d.coverage == pytest.approx(9 / 11)


def test_describe_empty_and_single() -> None:
    empty = describe([None, None])
    assert empty.n == 0 and empty.mean is None and empty.coverage == 0.0
    single = describe([3.5])
    assert single.mean == 3.5 and single.std is None and single.outlier_count == 0


def test_coverage_is_bounded() -> None:
    assert coverage(24, 24) == 1.0
    assert coverage(18, 24) == 0.75
    assert coverage(30, 24) == 1.0
    assert coverage(5, 0) == 0.0
