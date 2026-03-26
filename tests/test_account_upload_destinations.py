import importlib
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.database import crud
from src.database.init_db import initialize_database
from src.database.session import get_db


def _reset_test_state(monkeypatch, tmp_path: Path):
    database_url = f"sqlite:///{tmp_path / 'account-upload-destinations.db'}"
    monkeypatch.setenv("APP_DATABASE_URL", database_url)

    settings_module = importlib.import_module("src.config.settings")
    session_module = importlib.import_module("src.database.session")

    settings_module._settings = None
    session_module._db_manager = None
    initialize_database(database_url)
    settings_module._settings = None

    return settings_module, session_module


def test_account_detail_includes_upload_destinations(monkeypatch, tmp_path):
    _reset_test_state(monkeypatch, tmp_path)

    accounts_module = importlib.import_module("src.web.routes.accounts")

    with get_db() as db:
        account = crud.create_account(
            db,
            email="uploaded@example.com",
            email_service="tempmail",
            access_token="access-token",
            extra_data={
                "upload_destinations": {
                    "sub2api": {
                        "uploaded_at": "2026-03-26T10:00:00Z",
                        "services": [
                            {
                                "id": 3,
                                "name": "主 Sub2API",
                                "uploaded_at": "2026-03-26T10:00:00Z",
                            }
                        ],
                    }
                }
            },
        )
        account.cpa_uploaded = True
        account.cpa_uploaded_at = datetime(2026, 3, 26, 2, 0, 0)
        db.commit()
        account_id = account.id

    app = FastAPI()
    app.include_router(accounts_module.router, prefix="/api/accounts")
    client = TestClient(app)

    response = client.get(f"/api/accounts/{account_id}")
    assert response.status_code == 200

    body = response.json()
    destinations = {item["key"]: item for item in body["upload_destinations"]}
    assert destinations["cpa"]["label"] == "CPA"
    assert destinations["sub2api"]["services"][0]["name"] == "主 Sub2API"


def test_upload_account_to_sub2api_records_destination_metadata(monkeypatch, tmp_path):
    _reset_test_state(monkeypatch, tmp_path)

    accounts_module = importlib.import_module("src.web.routes.accounts")

    monkeypatch.setattr(accounts_module, "upload_to_sub2api", lambda *args, **kwargs: (True, "上传成功"))

    with get_db() as db:
        account = crud.create_account(
            db,
            email="sub2api@example.com",
            email_service="tempmail",
            access_token="access-token",
        )
        service = crud.create_sub2api_service(
            db,
            name="主服务",
            api_url="https://sub2api.example.com",
            api_key="secret",
        )
        account_id = account.id
        service_id = service.id

    app = FastAPI()
    app.include_router(accounts_module.router, prefix="/api/accounts")
    client = TestClient(app)

    response = client.post(
        f"/api/accounts/{account_id}/upload-sub2api",
        json={"service_id": service_id},
    )
    assert response.status_code == 200
    assert response.json()["success"] is True

    with get_db() as db:
        refreshed = crud.get_account_by_id(db, account_id)
        upload_destinations = (refreshed.extra_data or {}).get("upload_destinations", {})
        sub2api_info = upload_destinations.get("sub2api")
        assert sub2api_info is not None
        assert sub2api_info["services"][0]["id"] == service_id
        assert sub2api_info["services"][0]["name"] == "主服务"
