"""
账号体检与自动补注册 API
"""

import asyncio
from typing import List

from fastapi import APIRouter
from pydantic import BaseModel

from ...config.settings import get_settings, update_settings
from ...core.account_monitor import get_system_logs, run_monitor_check

router = APIRouter()


class AccountMonitorConfig(BaseModel):
    enabled: bool = False
    interval_minutes: int = 60
    sleep_seconds: int = 1
    auto_register_enabled: bool = False
    healthy_threshold: int = 10
    register_batch_count: int = 5
    email_service_selection: str = "tempmail:default"
    auto_upload_cpa: bool = False
    cpa_service_ids: List[int] = []


@router.get("/config")
async def get_account_monitor_config():
    settings = get_settings()
    return {
        "enabled": settings.account_monitor_enabled,
        "interval_minutes": settings.account_monitor_interval_minutes,
        "sleep_seconds": settings.account_monitor_sleep_seconds,
        "auto_register_enabled": settings.account_monitor_auto_register_enabled,
        "healthy_threshold": settings.account_monitor_healthy_threshold,
        "register_batch_count": settings.account_monitor_register_batch_count,
        "email_service_selection": settings.account_monitor_email_service_selection,
        "auto_upload_cpa": settings.account_monitor_auto_upload_cpa,
        "cpa_service_ids": settings.account_monitor_cpa_service_ids,
    }


@router.post("/config")
async def update_account_monitor_config(request: AccountMonitorConfig):
    update_settings(
        account_monitor_enabled=request.enabled,
        account_monitor_interval_minutes=request.interval_minutes,
        account_monitor_sleep_seconds=request.sleep_seconds,
        account_monitor_auto_register_enabled=request.auto_register_enabled,
        account_monitor_healthy_threshold=request.healthy_threshold,
        account_monitor_register_batch_count=request.register_batch_count,
        account_monitor_email_service_selection=request.email_service_selection,
        account_monitor_auto_upload_cpa=request.auto_upload_cpa,
        account_monitor_cpa_service_ids=request.cpa_service_ids,
    )
    return {"success": True, "message": "账号体检配置已保存"}


@router.get("/logs")
async def get_account_monitor_logs(since_id: int = 0):
    logs, last_id = get_system_logs(since_id)
    return {"success": True, "logs": logs, "last_id": last_id}


@router.post("/trigger")
async def trigger_account_monitor():
    manual_logs: List[str] = []
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, lambda: run_monitor_check(manual_logs=manual_logs))
    return {"success": True, "logs": manual_logs, "message": "账号体检执行完毕"}
