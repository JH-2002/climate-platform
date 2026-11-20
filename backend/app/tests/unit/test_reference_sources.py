"""T070/T072 — série do IAG/USP (AC-080) e parse da reanálise com resposta real gravada."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from app.analytics.climatology import annual_normal, monthly_normals
from app.integrations.iag.monthly_table import (
    parse_table_text,
    read_csv,
    read_normals_csv,
    validate,
)
from app.integrations.open_meteo.archive import build_params, parse_archive
from app.tests.fixtures import OPEN_METEO_ARCHIVE_SP, load

REFERENCE = Path(__file__).resolve().parents[3] / "data" / "reference"


def test_ac080_iag_series_is_complete_and_sums_match() -> None:
    years = read_csv(REFERENCE / "iag_usp_chuva_mensal_1933_2025.csv")
    assert len(years) == 93
    assert validate(years, 2025) == []
    by_year = {y.year: y for y in years}
    assert by_year[1933].annual == 849.8
    assert by_year[2025].months[3] == 186.9  # abril de 2025


def test_ac080_computed_normals_match_published() -> None:
    years = read_csv(REFERENCE / "iag_usp_chuva_mensal_1933_2025.csv")
    monthly = {(y.year, m): v for y in years for m, v in enumerate(y.months, start=1)}
    published = {
        n.period: n for n in read_normals_csv(REFERENCE / "iag_usp_normais_publicadas.csv")
    }
    for period in ("1961-1990", "1991-2020"):
        start, end = (int(p) for p in period.split("-"))
        normals = monthly_normals(monthly, start, end)
        for month in range(1, 13):
            assert normals[month].mean == pytest.approx(
                published[period].months[month - 1], abs=0.5
            )
        assert annual_normal(normals) == pytest.approx(published[period].annual, abs=0.5)


def test_pdf_text_with_split_numbers_is_read() -> None:
    lines = [
        "Normal¹ \\(1991-2020\\) 272,6 245,1 191,9 82,6 63,0 57,6 52,1 35,4 84,3 123,8 "
        "153,1 19 7,7 1.559,2",
        "1935 126,8 221,1 138,3 61,9 22,5 68,1 47,6 44,8 196,2 169,2 51,5 13 4,7 1.282,7",
        "1936 120,2 145,4 182,6 43,4 27,8 2,7 23,8 111,8 110,9 88,9 89,0 183 ,4 1.129,9",
        "Média Climatológica² \\(1933-2025\\) 235,5 217,9 170,0",
        "1937 179,4 101,4",
    ]
    table = parse_table_text(lines, 2025)
    assert [y.year for y in table.years] == [1935, 1936]
    assert table.years[0].months[11] == 134.7
    assert table.years[1].months[11] == 183.4
    assert table.years[1].annual == 1129.9
    assert table.normals[0].period == "1991-2020" and table.normals[0].annual == 1559.2
    assert table.rejected == [("1937", "2 valores")]
    assert validate(table.years, 1936) == ["anos ausentes: " + str(list(range(1933, 1935)))]


def test_archive_params_and_real_response() -> None:
    params = build_params(-23.57, -46.62, date(1991, 1, 1), date(2026, 11, 18))
    assert params["start_date"] == "1991-01-01"
    assert params["timezone"] == "America/Sao_Paulo"
    with pytest.raises(ValueError):
        build_params(-23.57, -46.62, date(2026, 1, 2), date(2026, 1, 1))
    parsed = parse_archive(load(OPEN_METEO_ARCHIVE_SP))
    assert parsed.cell_key == "-23.5852,-46.6596"
    assert parsed.missing_values == 0
    assert len(parsed.values) == 92 * 4
    rain = {v.day: v.value for v in parsed.values if v.variable == "precipitation_sum"}
    assert rain[date(2025, 11, 2)] == 21.8
    assert round(sum(v for d, v in rain.items() if d.month == 11), 1) == 131.7
    tmax = [v for v in parsed.values if v.variable == "air_temperature_max"]
    assert {v.unit for v in tmax} == {"°C"}


def test_archive_error_payload() -> None:
    with pytest.raises(ValueError, match="sem bloco diário: limite"):
        parse_archive({"error": True, "reason": "limite"})
