import importlib
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.config.settings import get_settings, update_settings
from src.database import crud
from src.database.init_db import initialize_database
from src.database.session import get_db


def _reset_test_state(monkeypatch, tmp_path: Path):
    database_url = f"sqlite:///{tmp_path / 'account-monitor.db'}"
    monkeypatch.setenv("APP_DATABASE_URL", database_url)

    settings_module = importlib.import_module("src.config.settings")
    session_module = importlib.import_module("src.database.session")

    settings_module._settings = None
    session_module._db_manager = None
    initialize_database(database_url)
    settings_module._settings = None

    return settings_module, session_module


def test_account_monitor_config_round_trip(monkeypatch, tmp_path):
    _reset_test_state(monkeypatch, tmp_path)

    router_module = importlib.import_module("src.web.routes.account_monitor")

    app = FastAPI()
    app.include_router(router_module.router, prefix="/api/account-monitor")
    client = TestClient(app)

    response = client.get("/api/account-monitor/config")
    assert response.status_code == 200
    assert response.json()["enabled"] is False

    payload = {
        "enabled": True,
        "interval_minutes": 45,
        "sleep_seconds": 2,
        "auto_register_enabled": True,
        "healthy_threshold": 6,
        "register_batch_count": 3,
        "email_service_selection": "tempmail:default",
        "auto_upload_cpa": True,
        "cpa_service_ids": [1, 2],
    }
    save_response = client.post("/api/account-monitor/config", json=payload)
    assert save_response.status_code == 200

    refreshed = client.get("/api/account-monitor/config")
    assert refreshed.status_code == 200
    assert refreshed.json() == payload


def test_account_monitor_trigger_returns_manual_logs(monkeypatch, tmp_path):
    _reset_test_state(monkeypatch, tmp_path)

    router_module = importlib.import_module("src.web.routes.account_monitor")

    captured = {}

    def fake_run_monitor_check(*, manual_logs=None):
        manual_logs.append("[INFO] 手动体检开始")
        manual_logs.append("[INFO] 手动体检完成")
        captured["called"] = True

    monkeypatch.setattr(router_module, "run_monitor_check", fake_run_monitor_check)

    app = FastAPI()
    app.include_router(router_module.router, prefix="/api/account-monitor")
    client = TestClient(app)

    response = client.post("/api/account-monitor/trigger")
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert captured["called"] is True
    assert body["logs"] == ["[INFO] 手动体检开始", "[INFO] 手动体检完成"]


def test_monitor_triggers_auto_registration_when_inventory_below_threshold(monkeypatch, tmp_path):
    _reset_test_state(monkeypatch, tmp_path)

    monitor_module = importlib.import_module("src.core.account_monitor")

    update_settings(
        account_monitor_enabled=True,
        account_monitor_interval_minutes=60,
        account_monitor_sleep_seconds=0,
        account_monitor_auto_register_enabled=True,
        account_monitor_healthy_threshold=1,
        account_monitor_register_batch_count=2,
        account_monitor_email_service_selection="tempmail:default",
        account_monitor_auto_upload_cpa=True,
        account_monitor_cpa_service_ids=[9],
    )

    queued = {}

    def fake_queue_auto_registration(*, count, email_service_selection, auto_upload_cpa, cpa_service_ids):
        queued["count"] = count
        queued["email_service_selection"] = email_service_selection
        queued["auto_upload_cpa"] = auto_upload_cpa
        queued["cpa_service_ids"] = cpa_service_ids

    monkeypatch.setattr(monitor_module, "queue_auto_registration", fake_queue_auto_registration)

    logs = []
    monitor_module.run_monitor_check(manual_logs=logs)

    assert queued == {
        "count": 2,
        "email_service_selection": "tempmail:default",
        "auto_upload_cpa": True,
        "cpa_service_ids": [9],
    }
    assert any("健康账号库存 0 低于阈值 1" in line for line in logs)


def test_monitor_skips_auto_registration_when_inventory_is_healthy(monkeypatch, tmp_path):
    _reset_test_state(monkeypatch, tmp_path)

    monitor_module = importlib.import_module("src.core.account_monitor")

    with get_db() as db:
        crud.create_account(
            db,
            email="healthy@example.com",
            email_service="tempmail",
            access_token="access-token",
            status="active",
        )

    update_settings(
        account_monitor_enabled=True,
        account_monitor_interval_minutes=60,
        account_monitor_sleep_seconds=0,
        account_monitor_auto_register_enabled=True,
        account_monitor_healthy_threshold=1,
        account_monitor_register_batch_count=2,
        account_monitor_email_service_selection="tempmail:default",
        account_monitor_auto_upload_cpa=False,
        account_monitor_cpa_service_ids=[],
    )

    monkeypatch.setattr(monitor_module, "refresh_account_token", lambda account_id, proxy_url=None: None)
    monkeypatch.setattr(monitor_module, "validate_account_token", lambda account_id, proxy_url=None: (True, None))

    queued = {"count": 0}

    def fake_queue_auto_registration(*, count, email_service_selection, auto_upload_cpa, cpa_service_ids):
        queued["count"] += count

    monkeypatch.setattr(monitor_module, "queue_auto_registration", fake_queue_auto_registration)

    logs = []
    monitor_module.run_monitor_check(manual_logs=logs)

    assert queued["count"] == 0
    assert any("健康账号库存 1" in line for line in logs)
