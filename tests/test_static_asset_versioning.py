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


def test_accounts_template_uses_versioned_static_assets():
    template = Path("templates/accounts.html").read_text(encoding="utf-8")

    assert '/static/css/style.css?v={{ static_version }}' in template
    assert '/static/js/utils.js?v={{ static_version }}' in template
    assert '/static/js/accounts.js?v={{ static_version }}' in template


def test_accounts_template_contains_account_monitor_controls():
    template = Path("templates/accounts.html").read_text(encoding="utf-8")

    assert 'account-monitor-status-badge' in template
    assert 'account-monitor-trigger-btn' in template
    assert '定时巡检与补货' in template
    assert '账号体检与补货' not in template
    assert '立即执行一次' in template
    assert '强制体检' not in template
    assert template.index('体检日志') < template.index('account-monitor-trigger-btn')
    assert 'account-monitor-email-service' in template
    assert 'account-monitor-auto-upload-cpa' in template
    assert 'account-monitor-cpa-services' in template


def test_accounts_template_uses_banned_stat_card_and_clear_failed_label():
    template = Path("templates/accounts.html").read_text(encoding="utf-8")

    assert 'id="banned-accounts"' in template
    assert '封禁账号' in template
    assert '失败账号' not in template
    assert '注册失败记录' in template
    assert '去向' in template


def test_utils_js_formats_dates_in_utc_plus_8():
    script = Path("static/js/utils.js").read_text(encoding="utf-8")

    assert "Asia/Shanghai" in script
    assert "dateStr.endsWith('Z')" in script
    assert "dateStr.includes('+')" in script


def test_index_template_does_not_contain_account_monitor_controls():
    template = Path("templates/index.html").read_text(encoding="utf-8")

    assert 'account-monitor-status-badge' not in template
    assert 'account-monitor-trigger-btn' not in template


def test_login_page_renders_successfully():
    client = TestClient(web_app.create_app())

    response = client.get("/login")

    assert response.status_code == 200
    assert "访问验证" in response.text
    assert 'form method="post" action="/login"' in response.text
