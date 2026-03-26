"""
Generator.email 邮箱服务实现
"""

import re
import time
import logging
from typing import Optional, Dict, Any, List, Tuple

from .base import BaseEmailService, EmailServiceError, EmailServiceType
from ..core.http_client import HTTPClient, RequestConfig
from ..config.constants import OTP_CODE_PATTERN


logger = logging.getLogger(__name__)


class GeneratorEmailService(BaseEmailService):
    """
    Generator.email 临时邮箱服务
    基于网页解析方式获取邮箱与验证码
    """

    def __init__(self, config: Dict[str, Any] = None, name: str = None):
        super().__init__(EmailServiceType.GENERATOR_EMAIL, name)

        default_config = {
            "base_url": "https://generator.email",
            "timeout": 30,
            "max_retries": 3,
            "poll_interval": 6,
            "impersonate": "chrome110",
            "user_agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/110.0.0.0 Safari/537.36"
            ),
            "proxy_url": None,
        }

        self.config = {**default_config, **(config or {})}
        self.base_url = self.config["base_url"].rstrip("/")

        http_config = RequestConfig(
            timeout=self.config["timeout"],
            max_retries=self.config["max_retries"],
            impersonate=self.config["impersonate"],
        )
        self.http_client = HTTPClient(
            proxy_url=self.config.get("proxy_url"),
            config=http_config,
        )

        self.headers = {
            "User-Agent": self.config["user_agent"],
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }

        self._email_cache: Dict[str, Dict[str, Any]] = {}
        self._last_code_cache: Dict[str, str] = {}

    def _parse_user_domain(self, html: str) -> Optional[Tuple[str, str]]:
        if not html:
            return None
        user_match = re.search(r'id="userName"[^>]*value="([^"]+)"', html, re.I)
        domain_match = re.search(r'id="domainName2"[^>]*value="([^"]+)"', html, re.I)
        if not user_match or not domain_match:
            return None
        return user_match.group(1).strip(), domain_match.group(1).strip()

    def _parse_email(self, html: str) -> Optional[str]:
        if not html:
            return None
        match = re.search(r'id="email_ch_text"[^>]*>([^<]+)</span>', html, re.I)
        if not match:
            match = re.search(r'id="email_ch_text"[^>]*>([^<]+)<', html, re.I)
        if match:
            return match.group(1).strip()

        parsed = self._parse_user_domain(html)
        if not parsed:
            return None
        username, domain = parsed
        if not username or not domain:
            return None
        return f"{username}@{domain}"

    def _sanitize_username(self, username: str) -> str:
        return re.sub(r"[^a-zA-Z_0-9.-]", "", username or "").lower()

    def _build_surl(self, email: str) -> Optional[str]:
        if not email or "@" not in email:
            return None
        username, domain = email.split("@", 1)
        safe_user = self._sanitize_username(username)
        if not safe_user or not domain:
            return None
        return f"{domain.lower()}/{safe_user}"

    def _normalize_surl(self, surl: str) -> Optional[str]:
        if not surl:
            return None
        normalized = surl.strip().strip("/")
        return f"{normalized}/" if normalized else None

    def _build_mailbox_url(self, surl: str) -> str:
        return f"{self.base_url}/{(surl or '').strip().strip('/')}"

    def _resolve_surl(self, email: str, email_id: Optional[str]) -> Optional[str]:
        if email_id:
            if "/" in email_id and "@" not in email_id:
                return self._normalize_surl(email_id)
            if "@" in email_id:
                return self._normalize_surl(self._build_surl(email_id))
        return self._normalize_surl(self._build_surl(email))

    def _extract_code(self, html: str, pattern: str) -> Optional[str]:
        if not html:
            return None

        direct = re.findall(r"Your ChatGPT code is (\d{6})", html, re.I)
        if direct:
            return direct[-1]

        contextual = re.findall(r"(?:openai|chatgpt)[\\s\\S]{0,200}?(\\d{6})", html, re.I)
        if contextual:
            return contextual[-1]

        lower_html = html.lower()
        if "openai" in lower_html or "chatgpt" in lower_html:
            generic = re.findall(pattern, html, re.I)
            if generic:
                return generic[-1]

        return None

    def create_email(self, config: Dict[str, Any] = None) -> Dict[str, Any]:
        try:
            response = self.http_client.get(self.base_url, headers=self.headers)

            if response.status_code != 200:
                self.update_status(False, EmailServiceError(f"请求失败，状态码: {response.status_code}"))
                raise EmailServiceError(f"Generator.email 请求失败，状态码: {response.status_code}")

            email = self._parse_email(response.text)
            if not email:
                self.update_status(False, EmailServiceError("未解析到邮箱地址"))
                raise EmailServiceError("Generator.email 未解析到邮箱地址")

            service_id = self._normalize_surl(self._build_surl(email))
            email_info = {
                "email": email,
                "service_id": service_id,
                "created_at": time.time(),
            }
            self._email_cache[email] = email_info

            logger.info(f"成功创建 Generator.email 邮箱: {email}")
            self.update_status(True)
            return email_info

        except Exception as e:
            self.update_status(False, e)
            if isinstance(e, EmailServiceError):
                raise
            raise EmailServiceError(f"创建 Generator.email 邮箱失败: {e}")

    def get_verification_code(
        self,
        email: str,
        email_id: str = None,
        timeout: int = 120,
        pattern: str = OTP_CODE_PATTERN,
        otp_sent_at: Optional[float] = None,
    ) -> Optional[str]:
        surl_value = self._resolve_surl(email, email_id)
        if not surl_value:
            logger.warning(f"邮箱 {email} 无法构造 surl，跳过验证码获取")
            return None

        cookies = {"surl": surl_value}
        mailbox_url = self._build_mailbox_url(surl_value)
        start_time = time.time()

        while time.time() - start_time < timeout:
            try:
                response = self.http_client.get(
                    mailbox_url,
                    headers=self.headers,
                    cookies=cookies,
                )

                if response.status_code != 200:
                    time.sleep(self.config["poll_interval"])
                    continue

                html = response.text or ""
                code = self._extract_code(html, pattern)
                if code:
                    last_code = self._last_code_cache.get(email)
                    if last_code == code:
                        time.sleep(self.config["poll_interval"])
                        continue
                    self._last_code_cache[email] = code
                    logger.info(f"获取验证码成功: {code}")
                    self.update_status(True)
                    return code

            except Exception as e:
                logger.debug(f"轮询 Generator.email 失败: {e}")

            time.sleep(self.config["poll_interval"])

        self.update_status(False, EmailServiceError("获取验证码超时"))
        return None

    def list_emails(self, **kwargs) -> List[Dict[str, Any]]:
        return list(self._email_cache.values())

    def delete_email(self, email_id: str) -> bool:
        removed = False
        for address, info in list(self._email_cache.items()):
            if info.get("service_id") == email_id or address == email_id:
                self._email_cache.pop(address, None)
                self._last_code_cache.pop(address, None)
                removed = True
        return removed

    def check_health(self) -> bool:
        try:
            response = self.http_client.get(self.base_url, headers=self.headers)
            healthy = response.status_code == 200
            self.update_status(healthy, None if healthy else EmailServiceError(f"HTTP {response.status_code}"))
            return healthy
        except Exception as e:
            self.update_status(False, e)
            return False
