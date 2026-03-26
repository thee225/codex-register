from pathlib import Path
import importlib

from fastapi.testclient import TestClient

web_app = importlib.import_module("src.web.app")


def test_static_asset_version_is_non_empty_string():
    version = web_app._build_static_asset_version(web_app.STATIC_DIR)

    assert isinstance(version, str)
    assert version
    assert version.isdigit()


def test_email_services_template_uses_versioned_static_assets():
    template = Path("templates/email_services.html").read_text(encoding="utf-8")

    assert '/static/css/style.css?v={{ static_version }}' in template
    assert '/static/js/utils.js?v={{ static_version }}' in template
    assert '/static/js/email_services.js?v={{ static_version }}' in template


def test_index_template_uses_versioned_static_assets():
    template = Path("templates/index.html").read_text(encoding="utf-8")

    assert '/static/css/style.css?v={{ static_version }}' in template
    assert '/static/js/utils.js?v={{ static_version }}' in template
    assert '/static/js/app.js?v={{ static_version }}' in template


def test_index_template_contains_account_monitor_controls():
    template = Path("templates/index.html").read_text(encoding="utf-8")

    assert 'account-monitor-status-badge' in template
    assert 'account-monitor-trigger-btn' in template
    assert '账号体检与补货' in template


def test_login_page_renders_successfully():
    client = TestClient(web_app.create_app())

    response = client.get("/login")

    assert response.status_code == 200
    assert "访问验证" in response.text
    assert 'form method="post" action="/login"' in response.text
