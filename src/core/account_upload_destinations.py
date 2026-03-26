"""
账号上传去向记录辅助函数
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from ..database.models import Account

UPLOAD_DESTINATION_LABELS = {
    "cpa": "CPA",
    "sub2api": "Sub2API",
    "tm": "Team Manager",
}

UPLOAD_DESTINATION_ORDER = ["cpa", "sub2api", "tm"]


def _isoformat(value: Optional[datetime]) -> Optional[str]:
    if not value:
        return None
    return value.isoformat()


def _normalize_services(services: Any) -> List[Dict[str, Any]]:
    normalized: List[Dict[str, Any]] = []
    if not isinstance(services, list):
        return normalized

    for item in services:
        if not isinstance(item, dict):
            continue
        normalized.append(
            {
                "id": item.get("id"),
                "name": item.get("name") or "",
                "uploaded_at": item.get("uploaded_at"),
            }
        )
    return normalized


def record_upload_destination(
    account: Account,
    destination_key: str,
    *,
    service_id: Optional[int] = None,
    service_name: Optional[str] = None,
    uploaded_at: Optional[datetime] = None,
) -> None:
    """在账号 extra_data 中记录上传去向。"""
    if destination_key not in UPLOAD_DESTINATION_LABELS:
        raise ValueError(f"unsupported upload destination: {destination_key}")

    timestamp = _isoformat(uploaded_at or datetime.utcnow())
    extra_data = dict(account.extra_data or {})
    upload_destinations = dict(extra_data.get("upload_destinations") or {})

    destination = upload_destinations.get(destination_key)
    if not isinstance(destination, dict):
        destination = {}

    services = _normalize_services(destination.get("services"))
    if service_id is not None or service_name:
        matched = None
        for item in services:
            if service_id is not None and item.get("id") == service_id:
                matched = item
                break
            if service_id is None and service_name and item.get("name") == service_name:
                matched = item
                break

        if matched is None:
            services.append(
                {
                    "id": service_id,
                    "name": service_name or "",
                    "uploaded_at": timestamp,
                }
            )
        else:
            matched["id"] = service_id if service_id is not None else matched.get("id")
            matched["name"] = service_name or matched.get("name") or ""
            matched["uploaded_at"] = timestamp

    destination["uploaded_at"] = timestamp
    destination["services"] = services
    upload_destinations[destination_key] = destination
    extra_data["upload_destinations"] = upload_destinations
    account.extra_data = extra_data

    if destination_key == "cpa":
        account.cpa_uploaded = True
        account.cpa_uploaded_at = uploaded_at or datetime.utcnow()


def build_upload_destinations(account: Account) -> List[Dict[str, Any]]:
    """构建返回给前端的上传去向信息。"""
    extra_data = account.extra_data or {}
    stored_destinations = extra_data.get("upload_destinations") or {}
    result: List[Dict[str, Any]] = []

    for key in UPLOAD_DESTINATION_ORDER:
        destination = stored_destinations.get(key)
        uploaded_at = None
        services: List[Dict[str, Any]] = []

        if isinstance(destination, dict):
            uploaded_at = destination.get("uploaded_at")
            services = _normalize_services(destination.get("services"))

        if key == "cpa" and account.cpa_uploaded:
            uploaded_at = uploaded_at or _isoformat(account.cpa_uploaded_at)

        if not uploaded_at and not services:
            continue

        result.append(
            {
                "key": key,
                "label": UPLOAD_DESTINATION_LABELS[key],
                "uploaded_at": uploaded_at,
                "services": services,
            }
        )

    return result
