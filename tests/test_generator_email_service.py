import asyncio
import importlib.util
from contextlib import contextmanager
from pathlib import Path

from src.database.models import Base, EmailService
from src.database.session import DatabaseSessionManager
from src.web.routes import email as email_routes
from src.web.routes import registration as registration_routes


class DummySettings:
    custom_domain_base_url = ""
    custom_domain_api_key = None


def test_generator_email_module_exists():
    assert importlib.util.find_spec("src.services.generator_email") is not None


def test_email_service_types_include_generator_email():
    result = asyncio.run(email_routes.get_service_types())
    generator_type = next(item for item in result["types"] if item["value"] == "generator_email")

    assert generator_type["label"] == "Generator.email"
    field_names = [field["name"] for field in generator_type["config_fields"]]
    assert "base_url" in field_names
    assert "poll_interval" in field_names


def test_registration_available_services_include_generator_email(monkeypatch):
    runtime_dir = Path("tests_runtime")
    runtime_dir.mkdir(exist_ok=True)
    db_path = runtime_dir / "generator_email_routes.db"
    if db_path.exists():
        db_path.unlink()

    manager = DatabaseSessionManager(f"sqlite:///{db_path}")
    Base.metadata.create_all(bind=manager.engine)

    with manager.session_scope() as session:
        session.add(
            EmailService(
                service_type="generator_email",
                name="Generator 主服务",
                config={
                    "base_url": "https://generator.email",
                    "poll_interval": 6,
                },
                enabled=True,
                priority=0,
            )
        )

    @contextmanager
    def fake_get_db():
        session = manager.SessionLocal()
        try:
            yield session
        finally:
            session.close()

    monkeypatch.setattr(registration_routes, "get_db", fake_get_db)

    import src.config.settings as settings_module

    monkeypatch.setattr(settings_module, "get_settings", lambda: DummySettings())

    result = asyncio.run(registration_routes.get_available_email_services())

    assert result["generator_email"]["available"] is True
    assert result["generator_email"]["count"] == 1
    assert result["generator_email"]["services"][0]["name"] == "Generator 主服务"
    assert result["generator_email"]["services"][0]["type"] == "generator_email"
