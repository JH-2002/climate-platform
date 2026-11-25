"""Spec 009, Parte A — alertas oficiais (IDAP e INMET), subprefeituras, regras e API.

Respostas reais gravadas (recortadas). Onde o teste precisa de um caso que o recorte não tem,
a mensagem real é copiada com o identificador ou a lista de municípios trocados, e isso está
dito no teste.
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, update

from app.api.v1.deps import get_clock
from app.core.config import get_settings
from app.core.geo import BoundingBox
from app.ingestion.alert_jobs import make_idap_job, make_inmet_job, make_subprefecture_sync_job
from app.ingestion.pipeline import RunOutcome, run_ingestion
from app.main import create_app
from app.models.tables import data_sources, official_alerts, system_alerts
from app.services.alerts import evaluate_system_alerts
from app.tests.fixtures import (
    GEOSAMPA_SUBPREFECTURES,
    IDAP_FEED,
    INMET_CAP_ALERT,
    INMET_CAP_CANCEL,
    INMET_CAP_STORM,
    INMET_RSS,
    load,
    load_bytes,
)
from app.tests.integration.test_flood_sync import run, sessions
from app.tests.integration.test_risk_api import FIXED_NOW as RISK_NOW
from app.tests.integration.test_risk_api import query, seed_and_compute
from app.tests.integration.test_simulation_api import simulate

pytestmark = [pytest.mark.integration, pytest.mark.usefixtures("clean_db")]

REGION = BoundingBox(-46.83, -24.01, -46.36, -23.35)
IBGE = "3550308"
NOW = datetime(2026, 11, 24, 20, 0, tzinfo=UTC)  # 17h em Brasília: alertas da IDAP vigentes
WFS = "http://wfs.test/geoserver/geoportal/wfs"
FEED = "https://idap.test/cap"
RSS = "https://inmet.test/avisos/rss"
ITEM = "https://apiprevmet3.inmet.gov.br/avisos/rss/"

STORM_ID = "urn:oid:2.49.0.0.76.0.2026.28761.1"
CANCELLED_ID = "urn:oid:2.49.0.0.76.0.2026.28758.1"


def other_region_cap() -> bytes:
    """Aviso 56504 (ventos costeiros no RS): a resposta gravada é a do 56501 com a lista de
    municípios trocada por Porto Alegre e o identificador trocado. Fica fora da região."""
    body = load_bytes(INMET_CAP_STORM).decode()
    start = body.index("<valueName>Municipios</valueName><value>") + len(
        "<valueName>Municipios</valueName><value>"
    )
    end = body.index("</value>", start)
    body = body[:start] + "Porto Alegre - RS (4314902)" + body[end:]
    return body.replace(STORM_ID, "urn:oid:2.49.0.0.76.0.2026.28764.1").encode()


def cancelled_target_cap() -> bytes:
    """O aviso que o 56500 cancela (28758.1) não está no recorte: cópia do 56501 com esse id."""
    return load_bytes(INMET_CAP_STORM).decode().replace(STORM_ID, CANCELLED_ID).encode()


INMET_BODIES: dict[str, bytes] = {
    RSS: load_bytes(INMET_RSS),
    ITEM + "56504": other_region_cap(),
    ITEM + "56503": load_bytes(INMET_CAP_ALERT),
    ITEM + "56501": load_bytes(INMET_CAP_STORM),
    ITEM + "56500": load_bytes(INMET_CAP_CANCEL),
}


def bytes_fetcher(bodies: dict[str, bytes], calls: list[str] | None = None) -> Any:
    async def fetch(url: str) -> bytes | None:
        if calls is not None:
            calls.append(url)
        return bodies[url]

    return fetch


async def subprefecture_fetcher(_url: str, _params: dict[str, str] | None) -> Any:
    return load(GEOSAMPA_SUBPREFECTURES)


def ingest(code: str, job: Any) -> RunOutcome:
    outcome: RunOutcome = run(lambda s: run_ingestion(s, code, job))
    return outcome


def sync_subprefectures() -> None:
    outcome = ingest(
        "geosampa-subprefectures", make_subprefecture_sync_job(subprefecture_fetcher, WFS)
    )
    assert outcome.status == "SUCCESS", outcome.error
    assert outcome.result.inserted == 3


def fetch_idap() -> RunOutcome:
    job = make_idap_job(bytes_fetcher({FEED: load_bytes(IDAP_FEED)}), FEED, REGION, IBGE)
    return ingest("idap-alerts", job)


def fetch_inmet(
    bodies: dict[str, bytes] = INMET_BODIES, calls: list[str] | None = None
) -> RunOutcome:
    return ingest("inmet-warnings", make_inmet_job(bytes_fetcher(bodies, calls), RSS, REGION, IBGE))


def stored() -> dict[str, Any]:
    return {r.external_id: r for r in query(select(official_alerts))}


def evaluate(now: datetime) -> Any:
    async def go() -> Any:
        async with sessions() as factory, factory() as session:
            return await evaluate_system_alerts(session, now)

    return asyncio.run(go())


def open_system_alerts() -> list[Any]:
    return query(select(system_alerts).where(system_alerts.c.closed_at.is_(None)))


@pytest.fixture
def client() -> Iterator[TestClient]:
    app = create_app(get_settings())
    app.dependency_overrides[get_clock] = lambda: lambda: NOW
    with TestClient(app) as test_client:
        yield test_client


# --- coleta ---------------------------------------------------------------------------------


def test_ac140_idap_keeps_city_alerts_with_subprefectures() -> None:
    sync_subprefectures()
    outcome = fetch_idap()
    assert outcome.status == "SUCCESS", outcome.error
    assert outcome.result.inserted == 3
    alerts = stored()
    assert set(alerts) == {"200371/2026", "200433/2026", "200436/2026"}  # Sorocaba fora
    west = alerts["200433/2026"]
    assert west.category == "CIVIL_DEFENSE"
    assert "PINHEIROS" in west.subprefectures
    assert west.area_approximate is False
    assert 0 < west.city_fraction <= 1
    assert west.headline.startswith("Defesa Civil:16:15")  # texto oficial intocado (BR-141)
    # a mensagem CAP original fica guardada
    raw = query(
        select(official_alerts.c.raw_payload_id).where(
            official_alerts.c.external_id == "200433/2026"
        )
    )
    assert raw[0][0] is not None


def test_without_subprefectures_area_is_approximate() -> None:
    assert fetch_idap().status == "SUCCESS"
    alerts = stored()
    assert alerts and all(a.area_approximate for a in alerts.values())
    assert all(a.subprefectures == [] for a in alerts.values())


def test_ac142_repeated_collection_does_not_duplicate() -> None:
    sync_subprefectures()
    fetch_idap()
    again = fetch_idap()
    assert (again.result.inserted, again.result.updated) == (0, 3)
    calls: list[str] = []
    fetch_inmet()
    second = fetch_inmet(calls=calls)
    assert second.status == "SUCCESS"
    assert calls == [RSS]  # avisos já guardados ou ignorados não são baixados de novo
    assert len(stored()) == 3 + 3  # IDAP + 56503, 56501 e o Cancel 56500 (oculto nas listas)


def test_ac141_cancel_ends_the_referenced_warning() -> None:
    sync_subprefectures()
    outcome = fetch_inmet()
    assert outcome.status == "SUCCESS", outcome.error
    assert outcome.result.received == 4 and outcome.result.inserted == 3
    alerts = stored()
    assert alerts[STORM_ID].category == "WEATHER_WARNING"
    assert alerts[STORM_ID].color == "#F96602"
    assert CANCELLED_ID not in alerts
    cancel = alerts["urn:oid:2.49.0.0.76.0.2026.28758.2"]
    assert cancel.msg_type == "Cancel" and cancel.refs == [CANCELLED_ID]
    # o aviso cancelado chega depois do Cancel: o encerramento vale em qualquer ordem
    bodies = dict(INMET_BODIES)
    bodies[RSS] = (
        load_bytes(INMET_RSS)
        .decode()
        .replace("</channel>", f"<item><link>{ITEM}56499</link></item></channel>")
        .encode()
    )
    bodies[ITEM + "56499"] = cancelled_target_cap()
    assert fetch_inmet(bodies).status == "SUCCESS"
    cancelled = stored()[CANCELLED_ID]
    assert cancelled.ended_reason == "CANCELLED"
    assert cancelled.ended_at is not None


def test_failed_cap_download_is_partial_and_keeps_others() -> None:
    bodies = dict(INMET_BODIES)

    async def flaky(url: str) -> bytes | None:
        if url.endswith("56503"):
            raise ValueError("HTTP 503")
        return bodies[url]

    outcome = ingest("inmet-warnings", make_inmet_job(flaky, RSS, REGION, IBGE))
    assert outcome.status == "PARTIAL"
    assert outcome.result.rejected == 1
    assert STORM_ID in stored()


# --- API --------------------------------------------------------------------------------------


def collect_all() -> None:
    sync_subprefectures()
    assert fetch_idap().status == "SUCCESS"
    assert fetch_inmet().status == "SUCCESS"


def test_active_alerts_separate_categories(client: TestClient) -> None:
    collect_all()
    body = client.get("/api/v1/alerts/active").json()
    categories = [a["category"] for a in body["official"]]
    assert categories == ["CIVIL_DEFENSE"] * 3 + ["WEATHER_WARNING"] * 2
    assert body["counts"]["official_active"] == 3
    assert body["counts"]["official_upcoming"] == 2  # avisos do INMET para 25 e 26/11
    first = body["official"][0]
    assert first["category_label"] == "Alerta oficial — Defesa Civil"
    assert first["status"] == "ACTIVE" and first["severity_label"] == "Moderada"
    inmet = [a for a in body["official"] if a["category"] == "WEATHER_WARNING"]
    assert {a["level_name"] for a in inmet} == {"Laranja — Perigo"}
    assert all(a["msg_type"] != "Cancel" for a in body["official"])
    assert "40199" in body["official_channel"]


def test_ac144_stale_source_is_not_reported_as_no_alert(client: TestClient) -> None:
    collect_all()
    assert client.get("/api/v1/alerts/active").json()["sources_ok"] is True
    stale_since = NOW - timedelta(hours=2)
    query_update = (
        update(data_sources)
        .where(data_sources.c.code == "idap-alerts")
        .values(last_success_at=stale_since, last_status="SUCCESS")
    )

    async def go() -> None:
        async with sessions() as factory, factory() as session:
            await session.execute(query_update)
            await session.commit()

    asyncio.run(go())
    evaluate(NOW)
    body = client.get("/api/v1/alerts/active").json()
    assert body["sources_ok"] is False
    idap = next(s for s in body["sources"] if s["code"] == "idap-alerts")
    assert idap["freshness"] == "STALE"
    quality = [s for s in body["system"] if s["rule_code"] == "source-unavailable"]
    assert [s["scope_label"] for s in quality] == ["alertas da Defesa Civil (IDAP)"]
    assert quality[0]["category_label"] == "Qualidade dos dados"


def test_point_detail_history_and_layer(client: TestClient) -> None:
    collect_all()
    by_external = {external: row.id for external, row in stored().items()}
    at = client.get("/api/v1/alerts/at?lat=-23.56&lon=-46.70").json()  # Pinheiros
    ids = {a["id"] for a in at}
    assert {by_external["200371/2026"], by_external["200433/2026"]} <= ids
    detail = client.get(f"/api/v1/alerts/official/{min(ids)}").json()
    assert detail["geometry"]["type"] == "MultiPolygon"
    assert client.get("/api/v1/alerts/official/999999").status_code == 404
    assert client.get("/api/v1/alerts/at?lat=99&lon=0").status_code == 422

    history = client.get("/api/v1/alerts").json()
    assert history["total"] == 5  # 3 da IDAP + 2 do INMET (o Cancel não entra)
    assert {e["kind"] for e in history["items"]} == {"official"}
    only_inmet = client.get("/api/v1/alerts?categoria=WEATHER_WARNING").json()
    assert {e["category"] for e in only_inmet["items"]} == {"WEATHER_WARNING"}
    too_long = client.get("/api/v1/alerts?desde=2026-01-01T00:00:00Z&ate=2026-11-24T00:00:00Z")
    assert too_long.status_code == 422

    layer = client.get("/api/v1/map/layers/alerts").json()
    assert layer["attribution"].startswith("Alertas: Defesa Civil")
    assert len(layer["features"]) == 5
    assert {f["properties"]["kind"] for f in layer["features"]} == {"OFFICIAL"}


def test_rules_endpoint(client: TestClient) -> None:
    body = client.get("/api/v1/alerts/rules").json()
    assert body["version"] == "1" and body["clear_after"] == 2
    assert [r["code"] for r in body["rules"]] == [
        "risk-subprefecture",
        "source-unavailable",
        "risk-stale",
    ]


# --- regras do sistema --------------------------------------------------------------------------


def test_ac143_one_alert_per_subprefecture_and_hysteresis() -> None:
    seed_and_compute(heavy_rain_mm=30.0)  # 2 setores em alto em São Miguel Paulista
    evaluate(RISK_NOW)
    evaluate(RISK_NOW)
    risk = [a for a in open_system_alerts() if a.rule_code == "risk-subprefecture"]
    assert [(a.scope_key, a.level) for a in risk] == [("SAO MIGUEL PAULISTA", "HIGH")]
    assert risk[0].details == {"high": 2, "critical": 0}

    seed_and_compute()  # sem chuva forte: nenhum setor em alto
    evaluate(RISK_NOW)
    still = [a for a in open_system_alerts() if a.rule_code == "risk-subprefecture"]
    assert len(still) == 1 and still[0].clear_count == 1  # primeira ausência: continua aberto
    evaluate(RISK_NOW)
    assert not [a for a in open_system_alerts() if a.rule_code == "risk-subprefecture"]
    closed = query(select(system_alerts).where(system_alerts.c.closed_at.is_not(None)))
    assert len(closed) == 1


def test_ac147_simulation_never_opens_system_alerts() -> None:
    seed_and_compute()
    app = create_app(get_settings())
    app.dependency_overrides[get_clock] = lambda: lambda: RISK_NOW
    with TestClient(app) as sim_client:
        run_body = simulate(sim_client)
    assert run_body["counts"]["CRITICAL"] == 3
    evaluate(RISK_NOW)
    assert not [a for a in open_system_alerts() if a.category == "RISK_ESTIMATE"]


def test_risk_stale_rule_opens_when_no_recent_computation() -> None:
    seed_and_compute()
    evaluate(RISK_NOW + timedelta(hours=4))
    stale = [a for a in open_system_alerts() if a.rule_code == "risk-stale"]
    assert len(stale) == 1 and stale[0].category == "DATA_QUALITY"
