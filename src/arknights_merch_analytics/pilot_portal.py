from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from datetime import datetime, timezone
from http import HTTPStatus
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

import pandas as pd

from arknights_merch_analytics.pilot import (
    PILOT_TABLE_COLUMNS,
    PRIMARY_KEYS,
    load_pilot_tables,
    validate_pilot_tables,
)


PILOT_CANDIDATES = {
    "CAND-002": {
        "campaign_id": "CAM-20260905-ACRYLIC",
        "operator": "新约能天使",
        "category": "亚克力制品",
        "positioning": "主力展示款",
        "price_options": [48, 68, 88],
        "qualification_price": 48,
        "preorder_gate_days": 30,
        "description": "突出角色立绘表现与桌面陈列场景，验证中等价格带的视觉吸引力。",
    },
    "CAND-006": {
        "campaign_id": "CAM-20260905-BADGE",
        "operator": "新约能天使",
        "category": "吧唧（徽章）",
        "positioning": "低客单验证款",
        "price_options": [18, 28, 38],
        "qualification_price": 18,
        "preorder_gate_days": 21,
        "description": "验证低客单收藏需求、价格敏感度与组合购买意愿。",
    },
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _connect(database_path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(database_path, timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def init_portal_database(database_path: Path) -> None:
    database_path.parent.mkdir(parents=True, exist_ok=True)
    with _connect(database_path) as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS portal_sessions (
                session_hash TEXT PRIMARY KEY,
                first_seen_at TEXT NOT NULL,
                source_channel TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS portal_events (
                event_id TEXT PRIMARY KEY,
                session_hash TEXT NOT NULL,
                candidate_id TEXT NOT NULL,
                campaign_id TEXT NOT NULL,
                event_type TEXT NOT NULL CHECK(event_type IN ('impression', 'click')),
                occurred_at TEXT NOT NULL,
                UNIQUE(session_hash, candidate_id, event_type),
                FOREIGN KEY(session_hash) REFERENCES portal_sessions(session_hash)
            );

            CREATE TABLE IF NOT EXISTS portal_responses (
                response_id TEXT PRIMARY KEY,
                session_hash TEXT NOT NULL UNIQUE,
                submitted_at TEXT NOT NULL,
                consent INTEGER NOT NULL CHECK(consent = 1),
                experience_months INTEGER NOT NULL,
                role_affinity INTEGER NOT NULL,
                prior_buyer INTEGER NOT NULL,
                preferred_candidate TEXT NOT NULL,
                completed_seconds INTEGER NOT NULL,
                source_channel TEXT NOT NULL,
                FOREIGN KEY(session_hash) REFERENCES portal_sessions(session_hash)
            );

            CREATE TABLE IF NOT EXISTS portal_intents (
                lead_id TEXT PRIMARY KEY,
                response_id TEXT NOT NULL,
                candidate_id TEXT NOT NULL,
                purchase_intent INTEGER NOT NULL,
                accepted_price REAL NOT NULL,
                preorder_tolerance_days INTEGER NOT NULL,
                qualified_intent INTEGER NOT NULL,
                qualified_reason TEXT NOT NULL,
                UNIQUE(response_id, candidate_id),
                FOREIGN KEY(response_id) REFERENCES portal_responses(response_id)
            );

            CREATE TABLE IF NOT EXISTS portal_supplier_quotes (
                quote_id TEXT PRIMARY KEY,
                candidate_id TEXT NOT NULL,
                supplier_code TEXT NOT NULL,
                quoted_at TEXT NOT NULL,
                rights_verified INTEGER NOT NULL,
                rights_evidence_ref TEXT NOT NULL,
                moq INTEGER NOT NULL,
                unit_cost REAL NOT NULL,
                sample_cost REAL NOT NULL,
                lead_time_days INTEGER NOT NULL,
                defect_allowance_pct REAL NOT NULL,
                payment_terms TEXT NOT NULL,
                quote_status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                UNIQUE(candidate_id, supplier_code)
            );

            CREATE INDEX IF NOT EXISTS idx_portal_event_candidate
                ON portal_events(candidate_id, event_type, occurred_at);
            CREATE INDEX IF NOT EXISTS idx_portal_intent_candidate
                ON portal_intents(candidate_id, qualified_intent);
            CREATE INDEX IF NOT EXISTS idx_portal_quote_candidate
                ON portal_supplier_quotes(candidate_id, rights_verified, quote_status);
            """
        )


def hash_session_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def register_session(database_path: Path, session_hash: str, source_channel: str) -> None:
    source = source_channel.strip()[:40] or "direct"
    with _connect(database_path) as connection:
        connection.execute(
            """
            INSERT OR IGNORE INTO portal_sessions(session_hash, first_seen_at, source_channel)
            VALUES (?, ?, ?)
            """,
            (session_hash, _now_iso(), source),
        )


def record_campaign_event(
    database_path: Path,
    session_hash: str,
    candidate_id: str,
    event_type: str,
) -> bool:
    if candidate_id not in PILOT_CANDIDATES:
        raise ValueError("unknown candidate_id")
    if event_type not in {"impression", "click"}:
        raise ValueError("event_type must be impression or click")
    campaign_id = PILOT_CANDIDATES[candidate_id]["campaign_id"]
    with _connect(database_path) as connection:
        if event_type == "click":
            impression = connection.execute(
                """
                SELECT 1 FROM portal_events
                WHERE session_hash = ? AND candidate_id = ? AND event_type = 'impression'
                """,
                (session_hash, candidate_id),
            ).fetchone()
            if impression is None:
                raise ValueError("click requires a prior impression")
        cursor = connection.execute(
            """
            INSERT OR IGNORE INTO portal_events(
                event_id, session_hash, candidate_id, campaign_id, event_type, occurred_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                f"EVT-{uuid.uuid4().hex}",
                session_hash,
                candidate_id,
                campaign_id,
                event_type,
                _now_iso(),
            ),
        )
        return cursor.rowcount == 1


def _as_int(payload: dict[str, Any], key: str, minimum: int, maximum: int) -> int:
    try:
        value = int(payload[key])
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError(f"{key} must be an integer") from error
    if not minimum <= value <= maximum:
        raise ValueError(f"{key} must be between {minimum} and {maximum}")
    return value


def _as_float(payload: dict[str, Any], key: str, minimum: float, maximum: float) -> float:
    try:
        value = float(payload[key])
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError(f"{key} must be numeric") from error
    if not minimum <= value <= maximum:
        raise ValueError(f"{key} must be between {minimum} and {maximum}")
    return round(value, 2)


def submit_intent_response(
    database_path: Path,
    session_hash: str,
    payload: dict[str, Any],
) -> str:
    if payload.get("consent") is not True:
        raise ValueError("consent is required")
    experience_months = _as_int(payload, "experience_months", 0, 120)
    role_affinity = _as_int(payload, "role_affinity", 1, 5)
    completed_seconds = _as_int(payload, "completed_seconds", 10, 3600)
    preferred_candidate = str(payload.get("preferred_candidate", ""))
    if preferred_candidate not in PILOT_CANDIDATES:
        raise ValueError("preferred_candidate is invalid")
    answers = payload.get("answers")
    if not isinstance(answers, dict) or set(answers) != set(PILOT_CANDIDATES):
        raise ValueError("answers must cover every approved candidate")
    source_channel = str(payload.get("source_channel", "direct")).strip()[:40] or "direct"
    prior_buyer = bool(payload.get("prior_buyer", False))
    response_id = f"RESP-{uuid.uuid4().hex}"
    submitted_at = _now_iso()
    intent_rows = []
    for candidate_id, candidate in PILOT_CANDIDATES.items():
        answer = answers[candidate_id]
        if not isinstance(answer, dict):
            raise ValueError(f"answer for {candidate_id} must be an object")
        purchase_intent = _as_int(answer, "purchase_intent", 1, 5)
        accepted_price = _as_float(answer, "accepted_price", 0, 10000)
        preorder_days = _as_int(answer, "preorder_tolerance_days", 0, 365)
        reasons = []
        if experience_months < 3:
            reasons.append("experience_below_3_months")
        if role_affinity < 3:
            reasons.append("role_affinity_below_3")
        if purchase_intent < 4:
            reasons.append("purchase_intent_below_4")
        if accepted_price < candidate["qualification_price"]:
            reasons.append("accepted_price_below_floor")
        qualified = not reasons
        intent_rows.append(
            (
                f"LEAD-{hashlib.sha256(f'{response_id}:{candidate_id}'.encode()).hexdigest()[:20]}",
                response_id,
                candidate_id,
                purchase_intent,
                accepted_price,
                preorder_days,
                int(qualified),
                "qualified" if qualified else "|".join(reasons),
            )
        )
    with _connect(database_path) as connection:
        try:
            connection.execute(
                """
                INSERT INTO portal_responses(
                    response_id, session_hash, submitted_at, consent, experience_months,
                    role_affinity, prior_buyer, preferred_candidate, completed_seconds,
                    source_channel
                ) VALUES (?, ?, ?, 1, ?, ?, ?, ?, ?, ?)
                """,
                (
                    response_id,
                    session_hash,
                    submitted_at,
                    experience_months,
                    role_affinity,
                    int(prior_buyer),
                    preferred_candidate,
                    completed_seconds,
                    source_channel,
                ),
            )
            connection.executemany(
                """
                INSERT INTO portal_intents(
                    lead_id, response_id, candidate_id, purchase_intent, accepted_price,
                    preorder_tolerance_days, qualified_intent, qualified_reason
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                intent_rows,
            )
        except sqlite3.IntegrityError as error:
            raise ValueError("this anonymous session has already submitted") from error
    return response_id


def add_supplier_quote(database_path: Path, payload: dict[str, Any]) -> str:
    candidate_id = str(payload.get("candidate_id", ""))
    if candidate_id not in PILOT_CANDIDATES:
        raise ValueError("unknown candidate_id")
    supplier_code = str(payload.get("supplier_code", "")).strip().upper()
    if not supplier_code or len(supplier_code) > 40:
        raise ValueError("supplier_code is required")
    rights_verified = payload.get("rights_verified") is True
    rights_ref = str(payload.get("rights_evidence_ref", "")).strip()
    quote_status = str(payload.get("quote_status", "qualified")).strip()
    if quote_status not in {"draft", "qualified", "accepted", "rejected"}:
        raise ValueError("invalid quote_status")
    if quote_status in {"qualified", "accepted"} and (not rights_verified or not rights_ref):
        raise ValueError("qualified quote requires verified rights evidence")
    quote_id = str(payload.get("quote_id", "")).strip() or f"QUOTE-{uuid.uuid4().hex[:16]}"
    row = (
        quote_id,
        candidate_id,
        supplier_code,
        str(payload.get("quoted_at", "")).strip() or _now_iso(),
        int(rights_verified),
        rights_ref,
        _as_int(payload, "moq", 1, 100000),
        _as_float(payload, "unit_cost", 0.01, 1000000),
        _as_float(payload, "sample_cost", 0, 1000000),
        _as_int(payload, "lead_time_days", 1, 365),
        _as_float(payload, "defect_allowance_pct", 0, 100),
        str(payload.get("payment_terms", "")).strip()[:200],
        quote_status,
        _now_iso(),
    )
    with _connect(database_path) as connection:
        try:
            connection.execute(
                """
                INSERT INTO portal_supplier_quotes(
                    quote_id, candidate_id, supplier_code, quoted_at, rights_verified,
                    rights_evidence_ref, moq, unit_cost, sample_cost, lead_time_days,
                    defect_allowance_pct, payment_terms, quote_status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                row,
            )
        except sqlite3.IntegrityError as error:
            raise ValueError("supplier quote already exists for this candidate") from error
    return quote_id


def portal_summary(database_path: Path) -> dict[str, Any]:
    with _connect(database_path) as connection:
        candidate_rows = []
        for candidate_id, candidate in PILOT_CANDIDATES.items():
            metrics = connection.execute(
                """
                SELECT
                    COUNT(DISTINCT CASE WHEN events.event_type = 'impression' THEN events.session_hash END) AS impressions,
                    COUNT(DISTINCT CASE WHEN events.event_type = 'click' THEN events.session_hash END) AS clicks
                FROM portal_events AS events
                JOIN portal_sessions AS sessions USING (session_hash)
                WHERE events.candidate_id = ?
                  AND sessions.source_channel NOT LIKE 'internal_%'
                """,
                (candidate_id,),
            ).fetchone()
            intents = connection.execute(
                """
                SELECT COUNT(*) AS intent_count,
                       COALESCE(SUM(intents.qualified_intent), 0) AS qualified_count,
                       ROUND(AVG(intents.purchase_intent), 2) AS average_intent,
                       ROUND(AVG(intents.accepted_price), 2) AS average_price
                FROM portal_intents AS intents
                JOIN portal_responses AS responses USING (response_id)
                WHERE intents.candidate_id = ?
                  AND responses.source_channel NOT LIKE 'internal_%'
                """,
                (candidate_id,),
            ).fetchone()
            suppliers = connection.execute(
                """
                SELECT COUNT(DISTINCT CASE WHEN rights_verified = 1 THEN supplier_code END)
                FROM portal_supplier_quotes WHERE candidate_id = ?
                """,
                (candidate_id,),
            ).fetchone()[0]
            impressions = int(metrics["impressions"] or 0)
            clicks = int(metrics["clicks"] or 0)
            candidate_rows.append(
                {
                    "candidate_id": candidate_id,
                    **candidate,
                    "impressions": impressions,
                    "clicks": clicks,
                    "ctr_pct": round(100 * clicks / impressions, 2) if impressions else 0,
                    "intent_count": int(intents["intent_count"] or 0),
                    "qualified_count": int(intents["qualified_count"] or 0),
                    "average_intent": intents["average_intent"] or 0,
                    "average_price": intents["average_price"] or 0,
                    "verified_supplier_count": int(suppliers or 0),
                }
            )
        response_count = connection.execute(
            """
            SELECT COUNT(*) FROM portal_responses
            WHERE source_channel NOT LIKE 'internal_%'
            """
        ).fetchone()[0]
    return {
        "project": "Arknights Analytics",
        "operator": "新约能天使",
        "response_count": response_count,
        "candidates": candidate_rows,
        "gates": {
            "responses_target": 30,
            "qualified_per_candidate": 30,
            "suppliers_per_candidate": 3,
        },
    }


def _merge_table(existing: pd.DataFrame, incoming: pd.DataFrame, key: str) -> pd.DataFrame:
    if incoming.empty:
        return existing
    combined = pd.concat([existing, incoming], ignore_index=True)
    return combined.drop_duplicates(subset=[key], keep="last")


def export_portal_capture(database_path: Path, manual_dir: Path) -> dict[str, int]:
    init_portal_database(database_path)
    tables = load_pilot_tables(manual_dir)
    with _connect(database_path) as connection:
        events = pd.read_sql_query(
            """
            SELECT events.*
            FROM portal_events AS events
            JOIN portal_sessions AS sessions USING (session_hash)
            WHERE sessions.source_channel NOT LIKE 'internal_%'
            """,
            connection,
        )
        responses = pd.read_sql_query(
            """
            SELECT * FROM portal_responses
            WHERE source_channel NOT LIKE 'internal_%'
            """,
            connection,
        )
        intents = pd.read_sql_query(
            """
            SELECT intents.*
            FROM portal_intents AS intents
            JOIN portal_responses AS responses USING (response_id)
            WHERE responses.source_channel NOT LIKE 'internal_%'
            """,
            connection,
        )
        quotes = pd.read_sql_query("SELECT * FROM portal_supplier_quotes", connection)

    campaign_rows = []
    if not events.empty:
        for candidate_id, candidate in PILOT_CANDIDATES.items():
            subset = events.loc[events["candidate_id"].eq(candidate_id)]
            if subset.empty:
                continue
            impressions = subset.loc[subset["event_type"].eq("impression"), "session_hash"].nunique()
            clicks = subset.loc[subset["event_type"].eq("click"), "session_hash"].nunique()
            campaign_rows.append(
                {
                    "campaign_id": candidate["campaign_id"],
                    "candidate_id": candidate_id,
                    "channel": "local_pilot_portal",
                    "creative_variant": candidate["category"],
                    "published_at": subset["occurred_at"].min(),
                    "impressions": impressions,
                    "clicks": clicks,
                    "landing_uv": impressions,
                    "evidence_ref": f"pilot_capture.db#{candidate['campaign_id']}",
                    "is_simulated": False,
                }
            )
    campaign_frame = pd.DataFrame(campaign_rows, columns=PILOT_TABLE_COLUMNS["pilot_campaigns"])

    lead_rows = []
    if not intents.empty:
        response_lookup = responses.set_index("response_id").to_dict("index")
        for row in intents.to_dict("records"):
            response = response_lookup[row["response_id"]]
            candidate = PILOT_CANDIDATES[row["candidate_id"]]
            lead_rows.append(
                {
                    "lead_id": row["lead_id"],
                    "campaign_id": candidate["campaign_id"],
                    "candidate_id": row["candidate_id"],
                    "submitted_at": response["submitted_at"],
                    "accepted_price": row["accepted_price"],
                    "preorder_tolerance_days": row["preorder_tolerance_days"],
                    "purchase_intent": row["purchase_intent"],
                    "qualified_intent": bool(row["qualified_intent"]),
                    "consent": bool(response["consent"]),
                    "source_channel": response["source_channel"],
                    "is_simulated": False,
                }
            )
    lead_frame = pd.DataFrame(lead_rows, columns=PILOT_TABLE_COLUMNS["pilot_intent_leads"])

    quote_rows = []
    if not quotes.empty:
        for row in quotes.to_dict("records"):
            quote_rows.append(
                {
                    column: (
                        bool(row[column])
                        if column in {"rights_verified"}
                        else row[column]
                    )
                    for column in PILOT_TABLE_COLUMNS["pilot_supplier_quotes"]
                    if column != "is_simulated"
                }
                | {"is_simulated": False}
            )
    quote_frame = pd.DataFrame(quote_rows, columns=PILOT_TABLE_COLUMNS["pilot_supplier_quotes"])

    updates = {
        "pilot_campaigns": campaign_frame,
        "pilot_intent_leads": lead_frame,
        "pilot_supplier_quotes": quote_frame,
    }
    updated_tables = dict(tables)
    for table_name, incoming in updates.items():
        updated_tables[table_name] = _merge_table(
            tables[table_name], incoming, PRIMARY_KEYS[table_name]
        )
    validate_pilot_tables(updated_tables)
    for table_name in updates:
        updated_tables[table_name].to_csv(
            manual_dir / f"{table_name}.csv", index=False, encoding="utf-8-sig"
        )
    return {
        "campaigns": len(updated_tables["pilot_campaigns"]),
        "intent_leads": len(updated_tables["pilot_intent_leads"]),
        "supplier_quotes": len(updated_tables["pilot_supplier_quotes"]),
    }


class PilotPortalHandler(BaseHTTPRequestHandler):
    database_path: Path
    web_root: Path

    def _is_local(self) -> bool:
        return self.client_address[0] in {"127.0.0.1", "::1"}

    def _session(self, source_channel: str = "direct") -> tuple[str, str | None]:
        cookie = SimpleCookie(self.headers.get("Cookie"))
        morsel = cookie.get("pilot_session")
        token = morsel.value if morsel else uuid.uuid4().hex
        session_hash = hash_session_token(token)
        register_session(self.database_path, session_hash, source_channel)
        return session_hash, None if morsel else token

    def _send_json(
        self,
        payload: dict[str, Any],
        status: HTTPStatus = HTTPStatus.OK,
        session_token: str | None = None,
    ) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        if session_token:
            self.send_header(
                "Set-Cookie",
                f"pilot_session={session_token}; Path=/; HttpOnly; SameSite=Lax",
            )
        self.end_headers()
        self.wfile.write(body)

    def _send_static(self, filename: str, content_type: str) -> None:
        path = self.web_root / filename
        if not path.exists():
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        body = path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self) -> dict[str, Any]:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError as error:
            raise ValueError("invalid content length") from error
        if length <= 0 or length > 100_000:
            raise ValueError("request body is empty or too large")
        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ValueError("invalid JSON body") from error
        if not isinstance(payload, dict):
            raise ValueError("JSON body must be an object")
        return payload

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        if path == "/":
            self._send_static("index.html", "text/html; charset=utf-8")
        elif path == "/admin":
            if not self._is_local():
                self.send_error(HTTPStatus.FORBIDDEN)
                return
            self._send_static("admin.html", "text/html; charset=utf-8")
        elif path == "/styles.css":
            self._send_static("styles.css", "text/css; charset=utf-8")
        elif path == "/app.js":
            self._send_static("app.js", "text/javascript; charset=utf-8")
        elif path == "/admin.js":
            self._send_static("admin.js", "text/javascript; charset=utf-8")
        elif path == "/api/config":
            source_channel = parse_qs(parsed.query).get("source", ["direct"])[0]
            session_hash, token = self._session(source_channel)
            self._send_json(
                {
                    "project": "Arknights Analytics",
                    "operator": "新约能天使",
                    "session": session_hash[:12],
                    "candidates": [
                        {"candidate_id": candidate_id, **candidate}
                        for candidate_id, candidate in PILOT_CANDIDATES.items()
                    ],
                },
                session_token=token,
            )
        elif path == "/api/summary":
            if not self._is_local():
                self.send_error(HTTPStatus.FORBIDDEN)
                return
            self._send_json(portal_summary(self.database_path))
        else:
            self.send_error(HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        try:
            payload = self._read_json()
            source_channel = str(payload.get("source_channel", "direct"))
            session_hash, token = self._session(source_channel)
            if path == "/api/events":
                inserted = record_campaign_event(
                    self.database_path,
                    session_hash,
                    str(payload.get("candidate_id", "")),
                    str(payload.get("event_type", "")),
                )
                self._send_json({"ok": True, "inserted": inserted}, session_token=token)
            elif path == "/api/intents":
                response_id = submit_intent_response(
                    self.database_path, session_hash, payload
                )
                self._send_json(
                    {"ok": True, "response_id": response_id},
                    HTTPStatus.CREATED,
                    token,
                )
            elif path == "/api/admin/supplier-quotes":
                if not self._is_local():
                    self.send_error(HTTPStatus.FORBIDDEN)
                    return
                quote_id = add_supplier_quote(self.database_path, payload)
                self._send_json(
                    {"ok": True, "quote_id": quote_id}, HTTPStatus.CREATED, token
                )
            elif path == "/api/admin/export":
                if not self._is_local():
                    self.send_error(HTTPStatus.FORBIDDEN)
                    return
                manual_dir = self.database_path.parent
                counts = export_portal_capture(self.database_path, manual_dir)
                self._send_json({"ok": True, "counts": counts}, session_token=token)
            else:
                self.send_error(HTTPStatus.NOT_FOUND)
        except ValueError as error:
            self._send_json(
                {"ok": False, "error": str(error)}, HTTPStatus.BAD_REQUEST
            )


def create_server(
    host: str,
    port: int,
    database_path: Path,
    web_root: Path,
) -> ThreadingHTTPServer:
    init_portal_database(database_path)

    class ConfiguredHandler(PilotPortalHandler):
        pass

    ConfiguredHandler.database_path = database_path
    ConfiguredHandler.web_root = web_root
    return ThreadingHTTPServer((host, port), ConfiguredHandler)
