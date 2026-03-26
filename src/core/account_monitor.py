"""
账号体检与自动补注册
"""

import asyncio
import logging
import threading
import time
import uuid
from typing import List, Optional, Tuple

from ..config.settings import get_settings
from ..core.openai.token_refresh import refresh_account_token, validate_account_token
from ..database import crud
from ..database.models import Account
from ..database.session import get_db
from ..web.task_manager import task_manager

logger = logging.getLogger(__name__)

system_logs: List[dict] = []
global_log_counter = 0

_log_lock = threading.Lock()
_job_lock = threading.Lock()
_scheduler_started = False
_is_running = False


def append_system_log(level: str, message: str) -> None:
    global global_log_counter

    with _log_lock:
        global_log_counter += 1
        system_logs.append(
            {
                "id": global_log_counter,
                "level": level,
                "message": message,
            }
        )
        if len(system_logs) > 1000:
            del system_logs[:500]

    getattr(logger, level if level in {"debug", "info", "warning", "error"} else "info")(message)


def get_system_logs(since_id: int = 0) -> Tuple[List[dict], int]:
    with _log_lock:
        if since_id > global_log_counter:
            since_id = 0
        logs = [item for item in system_logs if item["id"] > since_id]
        last_id = logs[-1]["id"] if logs else since_id
    return logs, last_id


def _log(level: str, message: str, manual_logs: Optional[List[str]] = None) -> None:
    append_system_log(level, message)
    if manual_logs is not None:
        manual_logs.append(f"[{level.upper()}] {message}")


def _parse_email_service_selection(selection: str) -> Tuple[str, Optional[int]]:
    raw = (selection or "").strip() or "tempmail:default"
    if ":" not in raw:
        return raw, None

    service_type, service_id = raw.split(":", 1)
    service_type = service_type.strip() or "tempmail"
    service_id = service_id.strip()

    if not service_id or service_id == "default":
        return service_type, None

    return service_type, int(service_id)


def _resolve_proxy() -> Optional[str]:
    return get_settings().proxy_url


def _candidate_accounts() -> List[Account]:
    with get_db() as db:
        return db.query(Account).order_by(Account.created_at.desc()).all()


def queue_auto_registration(
    *,
    count: int,
    email_service_selection: str,
    auto_upload_cpa: bool,
    cpa_service_ids: List[int],
) -> None:
    from ..web.routes.registration import run_batch_registration

    loop = task_manager.get_loop()
    if loop is None:
        raise RuntimeError("任务事件循环未初始化，无法自动补注册")

    email_service_type, email_service_id = _parse_email_service_selection(email_service_selection)
    batch_id = str(uuid.uuid4())
    task_uuids: List[str] = []

    with get_db() as db:
        for _ in range(count):
            task_uuid = str(uuid.uuid4())
            crud.create_registration_task(db, task_uuid=task_uuid, proxy=None)
            task_uuids.append(task_uuid)

    future = asyncio.run_coroutine_threadsafe(
        run_batch_registration(
            batch_id=batch_id,
            task_uuids=task_uuids,
            email_service_type=email_service_type,
            proxy=None,
            email_service_config=None,
            email_service_id=email_service_id,
            interval_min=get_settings().registration_sleep_min,
            interval_max=get_settings().registration_sleep_max,
            concurrency=2,
            mode="pipeline",
            auto_upload_cpa=auto_upload_cpa,
            cpa_service_ids=cpa_service_ids,
        ),
        loop,
    )
    future.add_done_callback(lambda fut: fut.exception())


def run_monitor_check(*, manual_logs: Optional[List[str]] = None) -> None:
    global _is_running

    with _job_lock:
        if _is_running:
            _log("warning", "账号体检任务已在运行，跳过本次请求", manual_logs)
            return
        _is_running = True

    settings = get_settings()
    proxy_url = _resolve_proxy()

    try:
        accounts = _candidate_accounts()
        _log("info", f"开始账号体检，本次共检查 {len(accounts)} 个账号", manual_logs)

        healthy_count = 0

        for index, account in enumerate(accounts, start=1):
            if settings.account_monitor_sleep_seconds > 0 and index > 1:
                time.sleep(settings.account_monitor_sleep_seconds)

            try:
                if account.session_token or account.refresh_token:
                    refresh_result = refresh_account_token(account.id, proxy_url=proxy_url)
                    if getattr(refresh_result, "success", False):
                        _log("info", f"账号 {account.email} Token 刷新成功", manual_logs)
                    elif refresh_result is not None:
                        _log("warning", f"账号 {account.email} Token 刷新失败: {refresh_result.error_message}", manual_logs)

                is_valid, error = validate_account_token(account.id, proxy_url=proxy_url)

                with get_db() as db:
                    new_status = "active" if is_valid else "expired"
                    if error and "封禁" in error:
                        new_status = "banned"
                    crud.update_account(db, account.id, status=new_status)

                if is_valid:
                    healthy_count += 1
                    _log("info", f"账号 {account.email} 体检通过", manual_logs)
                else:
                    _log("warning", f"账号 {account.email} 体检失败: {error or '未知错误'}", manual_logs)
            except Exception as exc:
                _log("error", f"账号 {account.email} 体检异常: {exc}", manual_logs)

        threshold = max(0, int(settings.account_monitor_healthy_threshold or 0))
        if settings.account_monitor_auto_register_enabled and threshold > 0 and healthy_count < threshold:
            _log("warning", f"健康账号库存 {healthy_count} 低于阈值 {threshold}，准备自动补注册", manual_logs)
            batch_count = max(0, int(settings.account_monitor_register_batch_count or 0))
            if batch_count > 0:
                queue_auto_registration(
                    count=batch_count,
                    email_service_selection=settings.account_monitor_email_service_selection,
                    auto_upload_cpa=settings.account_monitor_auto_upload_cpa,
                    cpa_service_ids=list(settings.account_monitor_cpa_service_ids or []),
                )
                _log("info", f"已自动排队 {batch_count} 个注册任务", manual_logs)
        else:
            _log("info", f"健康账号库存 {healthy_count}，达到阈值 {threshold}，无需补货", manual_logs)

        _log("info", "账号体检完成", manual_logs)
    finally:
        _is_running = False


async def _scheduler_loop() -> None:
    await asyncio.sleep(5)
    loop = asyncio.get_running_loop()

    while True:
        settings = get_settings()
        try:
            if settings.account_monitor_enabled:
                await loop.run_in_executor(None, run_monitor_check)
        except Exception as exc:
            append_system_log("error", f"账号体检调度异常: {exc}")

        interval_minutes = max(1, int(settings.account_monitor_interval_minutes or 1))
        await asyncio.sleep(interval_minutes * 60)


def start_account_monitor_scheduler(loop: Optional[asyncio.AbstractEventLoop] = None) -> None:
    global _scheduler_started
    if _scheduler_started:
        return

    event_loop = loop or task_manager.get_loop() or asyncio.get_event_loop()
    event_loop.create_task(_scheduler_loop())
    _scheduler_started = True
