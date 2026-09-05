from __future__ import annotations

import sqlite3
import json
import threading
from http.cookiejar import CookieJar
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import HTTPCookieProcessor, Request, build_opener

import pandas as pd
import pytest

from arknights_merch_analytics.pilot import create_pilot_templates
from arknights_merch_analytics.pilot_portal import (
    PILOT_CANDIDATES,
    add_supplier_quote,
    create_server,
    export_portal_capture,
    hash_session_token,
    init_portal_database,
    portal_summary,
    record_campaign_event,
    register_session,
    submit_intent_response,
)


ROOT = Path(__file__).resolve().parents[1]


def _session(database_path, token: str = "anonymous-session") -> str:
    session_hash = hash_session_token(token)
    register_session(database_path, session_hash, "pytest")
    return session_hash


def _valid_payload() -> dict:
    return {
        "consent": True,
        "experience_months": 24,
        "role_affinity": 5,
        "prior_buyer": True,
        "preferred_candidate": "CAND-002",
        "completed_seconds": 90,
        "source_channel": "pytest",
        "answers": {
            "CAND-002": {
                "purchase_intent": 5,
                "accepted_price": 68,
                "preorder_tolerance_days": 45,
            },
            "CAND-006": {
                "purchase_intent": 4,
                "accepted_price": 28,
                "preorder_tolerance_days": 30,
            },
        },
    }


def test_initializes_capture_database(tmp_path) -> None:
    database_path = tmp_path / "pilot_capture.db"
    init_portal_database(database_path)
    with sqlite3.connect(database_path) as connection:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
    assert {
        "portal_sessions",
        "portal_events",
        "portal_responses",
        "portal_intents",
        "portal_supplier_quotes",
    }.issubset(tables)


def test_records_unique_impressions_and_clicks(tmp_path) -> None:
    database_path = tmp_path / "pilot_capture.db"
    init_portal_database(database_path)
    session_hash = _session(database_path)
    assert record_campaign_event(database_path, session_hash, "CAND-002", "impression")
    assert not record_campaign_event(database_path, session_hash, "CAND-002", "impression")
    assert record_campaign_event(database_path, session_hash, "CAND-002", "click")


def test_rejects_click_without_impression(tmp_path) -> None:
    database_path = tmp_path / "pilot_capture.db"
    init_portal_database(database_path)
    with pytest.raises(ValueError, match="prior impression"):
        record_campaign_event(database_path, _session(database_path), "CAND-002", "click")


def test_submits_two_qualified_candidate_intents(tmp_path) -> None:
    database_path = tmp_path / "pilot_capture.db"
    init_portal_database(database_path)
    session_hash = _session(database_path)
    response_id = submit_intent_response(database_path, session_hash, _valid_payload())
    assert response_id.startswith("RESP-")
    with sqlite3.connect(database_path) as connection:
        count, qualified = connection.execute(
            "SELECT COUNT(*), SUM(qualified_intent) FROM portal_intents"
        ).fetchone()
    assert count == 2
    assert qualified == 2


def test_rejects_duplicate_session_submission(tmp_path) -> None:
    database_path = tmp_path / "pilot_capture.db"
    init_portal_database(database_path)
    session_hash = _session(database_path)
    submit_intent_response(database_path, session_hash, _valid_payload())
    with pytest.raises(ValueError, match="already submitted"):
        submit_intent_response(database_path, session_hash, _valid_payload())


def test_rejects_response_without_consent(tmp_path) -> None:
    database_path = tmp_path / "pilot_capture.db"
    init_portal_database(database_path)
    payload = _valid_payload()
    payload["consent"] = False
    with pytest.raises(ValueError, match="consent"):
        submit_intent_response(database_path, _session(database_path), payload)


def test_marks_low_price_intent_unqualified(tmp_path) -> None:
    database_path = tmp_path / "pilot_capture.db"
    init_portal_database(database_path)
    payload = _valid_payload()
    payload["answers"]["CAND-002"]["accepted_price"] = 20
    submit_intent_response(database_path, _session(database_path), payload)
    with sqlite3.connect(database_path) as connection:
        row = connection.execute(
            """
            SELECT qualified_intent, qualified_reason
            FROM portal_intents WHERE candidate_id = 'CAND-002'
            """
        ).fetchone()
    assert row[0] == 0
    assert "accepted_price_below_floor" in row[1]


def test_rejects_qualified_supplier_without_rights(tmp_path) -> None:
    database_path = tmp_path / "pilot_capture.db"
    init_portal_database(database_path)
    payload = {
        "candidate_id": "CAND-002",
        "supplier_code": "SUP-001",
        "rights_verified": False,
        "rights_evidence_ref": "",
        "moq": 20,
        "unit_cost": 32,
        "sample_cost": 80,
        "lead_time_days": 20,
        "defect_allowance_pct": 1,
        "payment_terms": "30% deposit",
        "quote_status": "qualified",
    }
    with pytest.raises(ValueError, match="verified rights"):
        add_supplier_quote(database_path, payload)


def test_summary_reports_per_candidate_progress(tmp_path) -> None:
    database_path = tmp_path / "pilot_capture.db"
    init_portal_database(database_path)
    session_hash = _session(database_path)
    for candidate_id in PILOT_CANDIDATES:
        record_campaign_event(database_path, session_hash, candidate_id, "impression")
    submit_intent_response(database_path, session_hash, _valid_payload())
    summary = portal_summary(database_path)
    assert summary["response_count"] == 1
    assert {row["qualified_count"] for row in summary["candidates"]} == {1}


def test_internal_qa_sessions_are_excluded_from_metrics(tmp_path) -> None:
    database_path = tmp_path / "pilot_capture.db"
    init_portal_database(database_path)
    session_hash = hash_session_token("internal-session")
    register_session(database_path, session_hash, "internal_qa")
    for candidate_id in PILOT_CANDIDATES:
        record_campaign_event(database_path, session_hash, candidate_id, "impression")
    payload = _valid_payload()
    payload["source_channel"] = "internal_qa"
    submit_intent_response(database_path, session_hash, payload)
    summary = portal_summary(database_path)
    assert summary["response_count"] == 0
    assert {row["impressions"] for row in summary["candidates"]} == {0}


def test_exports_capture_to_valid_pilot_csv(tmp_path) -> None:
    manual_dir = tmp_path / "commercial_pilot"
    create_pilot_templates(manual_dir)
    database_path = manual_dir / "pilot_capture.db"
    init_portal_database(database_path)
    session_hash = _session(database_path)
    for candidate_id in PILOT_CANDIDATES:
        record_campaign_event(database_path, session_hash, candidate_id, "impression")
        record_campaign_event(database_path, session_hash, candidate_id, "click")
    submit_intent_response(database_path, session_hash, _valid_payload())
    counts = export_portal_capture(database_path, manual_dir)
    assert counts == {"campaigns": 2, "intent_leads": 2, "supplier_quotes": 0}
    campaigns = pd.read_csv(manual_dir / "pilot_campaigns.csv")
    leads = pd.read_csv(manual_dir / "pilot_intent_leads.csv")
    assert len(campaigns) == 2
    assert len(leads) == 2
    assert not campaigns["is_simulated"].astype(bool).any()


def test_http_portal_end_to_end(tmp_path) -> None:
    manual_dir = tmp_path / "commercial_pilot"
    create_pilot_templates(manual_dir)
    database_path = manual_dir / "pilot_capture.db"
    server = create_server("127.0.0.1", 0, database_path, ROOT / "web" / "pilot")
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base_url = f"http://127.0.0.1:{server.server_port}"
    opener = build_opener(HTTPCookieProcessor(CookieJar()))

    def get(path: str) -> tuple[int, bytes]:
        with opener.open(f"{base_url}{path}") as response:
            return response.status, response.read()

    def post(path: str, payload: dict) -> tuple[int, dict]:
        request = Request(
            f"{base_url}{path}",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with opener.open(request) as response:
            return response.status, json.loads(response.read().decode("utf-8"))

    try:
        status, home = get("/")
        assert status == 200
        assert "新约能天使周边专项调研" in home.decode("utf-8")
        assert get("/admin")[0] == 200
        assert get("/styles.css")[0] == 200
        assert get("/app.js")[0] == 200
        assert get("/admin.js")[0] == 200

        status, config_body = get("/api/config?source=pytest_http")
        assert status == 200
        config = json.loads(config_body.decode("utf-8"))
        assert len(config["candidates"]) == 2

        for candidate_id in PILOT_CANDIDATES:
            assert post(
                "/api/events",
                {
                    "candidate_id": candidate_id,
                    "event_type": "impression",
                    "source_channel": "pytest_http",
                },
            )[0] == 200
        assert post(
            "/api/events",
            {
                "candidate_id": "CAND-002",
                "event_type": "click",
                "source_channel": "pytest_http",
            },
        )[0] == 200

        status, submitted = post("/api/intents", _valid_payload())
        assert status == 201
        assert submitted["response_id"].startswith("RESP-")

        quote_payload = {
            "candidate_id": "CAND-002",
            "supplier_code": "SUP-HTTP",
            "rights_verified": True,
            "rights_evidence_ref": "evidence/http-rights.md",
            "moq": 20,
            "unit_cost": 32,
            "sample_cost": 80,
            "lead_time_days": 20,
            "defect_allowance_pct": 1,
            "payment_terms": "30% deposit",
            "quote_status": "qualified",
            "source_channel": "local_admin",
        }
        assert post("/api/admin/supplier-quotes", quote_payload)[0] == 201

        _, summary_body = get("/api/summary")
        summary = json.loads(summary_body.decode("utf-8"))
        assert summary["response_count"] == 1
        assert summary["candidates"][0]["verified_supplier_count"] == 1

        status, exported = post(
            "/api/admin/export", {"source_channel": "local_admin"}
        )
        assert status == 200
        assert exported["counts"] == {
            "campaigns": 2,
            "intent_leads": 2,
            "supplier_quotes": 1,
        }

        with pytest.raises(HTTPError) as missing:
            get("/missing")
        assert missing.value.code == 404

        with pytest.raises(HTTPError) as duplicate:
            post("/api/intents", _valid_payload())
        assert duplicate.value.code == 400
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
