"""
Browser-based product page extraction using a persistent Playwright profile.
"""

import asyncio
from datetime import UTC, datetime
import logging
import time

from playwright.async_api import async_playwright

from src.config.settings import get_settings
from src.modules.product_ingestion.page_extractor import (
    ProductPageExtractor,
    ProductPageExtractionResult,
    ProductPageImageCandidate,
)

logger = logging.getLogger(__name__)


class ProductPageBrowserExtractor:
    """
    Extract product image candidates using a real browser session.
    """

    _SHOPEE_AUTH_SIGNALS = [
        "/buyer/login",
        "/verify",
        "/verification",
        "/auth",
        "/otp",
        "log in",
        "đăng nhập",
        "login",
        "sign in",
        "verify",
        "verification",
        "xác minh",
        "xác thực",
        "mã xác minh",
        "mã xác thực",
        "otp",
        "sms",
        "qr code",
        "mã qr",
        "quét mã",
        "ủy quyền",
        "authorization",
        "authorize",
        "security check",
        "captcha",
    ]

    def __init__(self):
        settings = get_settings()
        self.profile_dir = settings.playwright_profile_dir
        self._shopee_login_task: asyncio.Task | None = None
        self._shopee_login_session = {
            "status": "idle",
            "page_url": None,
            "final_url": None,
            "profile_dir": str(self.profile_dir),
            "message": "No Shopee login session has been started.",
            "started_at": None,
            "updated_at": None,
        }

    @staticmethod
    def _now_iso() -> str:
        return datetime.now(UTC).isoformat()

    def _set_shopee_login_session(
        self,
        *,
        status: str,
        message: str,
        page_url: str | None = None,
        final_url: str | None = None,
        started_at: str | None = None,
    ) -> None:
        current_started_at = started_at or self._shopee_login_session.get("started_at")
        if status in {"pending", "awaiting_login"} and current_started_at is None:
            current_started_at = self._now_iso()

        self._shopee_login_session = {
            "status": status,
            "page_url": (
                page_url
                if page_url is not None
                else self._shopee_login_session.get("page_url")
            ),
            "final_url": final_url,
            "profile_dir": str(self.profile_dir),
            "message": message,
            "started_at": current_started_at,
            "updated_at": self._now_iso(),
        }

    def get_shopee_login_session_status(self) -> dict[str, str | bool | None]:
        session = dict(self._shopee_login_session)
        session["is_ready"] = str(session.get("status") or "idle") == "ready"

        if self._shopee_login_task and self._shopee_login_task.done():
            try:
                self._shopee_login_task.result()
            except Exception as exc:
                if str(session.get("status") or "idle") not in {"failed", "ready"}:
                    self._set_shopee_login_session(
                        status="failed",
                        message=f"Shopee login session failed: {exc}",
                    )
                    session = dict(self._shopee_login_session)
                    session["is_ready"] = False

        return session

    def _consume_shopee_login_task_result(self, task: asyncio.Task) -> None:
        try:
            task.result()
        except Exception as exc:
            logger.warning("Shopee login session task finished with error: %s", exc)

    @staticmethod
    def is_shopee_page_url(page_url: str) -> bool:
        return "shopee." in (page_url or "").lower()

    @staticmethod
    def _is_shopee_captcha_challenge(
        page_url: str,
        page_title: str,
        body_text: str,
    ) -> bool:
        lowered_url = (page_url or "").lower()
        lowered_title = (page_title or "").lower()
        lowered_body = (body_text or "").lower()

        return any(
            signal in lowered_url or signal in lowered_title or signal in lowered_body
            for signal in [
                "/verify/captcha",
                "anti_bot",
                "anti-bot",
                "captcha",
                "crawler_item",
            ]
        )

    @classmethod
    def _is_shopee_blocked(
        cls,
        page_url: str,
        page_title: str,
        body_text: str,
    ) -> bool:
        lowered_url = (page_url or "").lower()
        lowered_title = (page_title or "").lower()
        lowered_body = (body_text or "").lower()

        if cls._is_shopee_captcha_challenge(page_url, page_title, body_text):
            return True

        return any(
            signal in lowered_url or signal in lowered_title or signal in lowered_body
            for signal in [
                "/verify/traffic/error",
                "page unavailable",
                "please log in and try again",
                "need help?",
            ]
        )

    @classmethod
    def _is_shopee_login_required(
        cls, page_url: str, page_title: str, body_text: str
    ) -> bool:
        lowered_url = (page_url or "").lower()
        lowered_title = (page_title or "").lower()
        lowered_body = (body_text or "").lower()

        if cls._is_shopee_blocked(page_url, page_title, body_text):
            return True

        return any(
            signal in lowered_url or signal in lowered_title or signal in lowered_body
            for signal in cls._SHOPEE_AUTH_SIGNALS
        )

    @classmethod
    def _build_shopee_blocked_message(
        cls,
        page_url: str,
        page_title: str,
        body_text: str,
    ) -> str:
        if cls._is_shopee_captcha_challenge(page_url, page_title, body_text):
            return (
                "Shopee returned an anti-bot CAPTCHA challenge for this page. "
                "Backend browser extraction cannot continue until the CAPTCHA is solved "
                "manually in the opened browser session. If Shopee keeps re-challenging, "
                "use /api/v1/products/fetch-image with a direct product image URL or "
                "upload/select the garment image manually."
            )

        return (
            "Shopee browser session is blocked or not ready. "
            "Complete login/verification in the opened browser window, then poll "
            "/api/v1/products/check-shopee-login-session until status=ready."
        )

    @staticmethod
    async def _collect_dom_image_urls(page) -> list[str]:
        return await page.evaluate(
            """
            () => {
              const urls = [];
              for (const img of Array.from(document.images)) {
                const candidates = [
                  img.currentSrc,
                  img.src,
                  img.getAttribute('src'),
                  img.getAttribute('data-src'),
                  img.getAttribute('data-original'),
                  img.getAttribute('data-lazy-src')
                ].filter(Boolean);

                const srcset = img.getAttribute('srcset');
                if (srcset) {
                  const first = srcset.split(',')[0]?.trim()?.split(' ')[0];
                  if (first) candidates.push(first);
                }

                for (const candidate of candidates) {
                  urls.push(candidate);
                }
              }
              return urls;
            }
            """
        )

    @staticmethod
    def _merge_browser_candidates(
        page_url: str,
        html_result: ProductPageExtractionResult,
        dom_urls: list[str],
        max_candidates: int,
    ) -> ProductPageExtractionResult:
        deduped: dict[str, ProductPageImageCandidate] = {
            candidate.image_url: candidate for candidate in html_result.candidates
        }

        for raw_url in dom_urls:
            candidate = ProductPageExtractor._score_candidate(
                page_url=page_url,
                raw_url=raw_url,
                source="browser-dom",
                attrs={},
            )
            if not candidate:
                continue

            candidate.score += 30
            candidate.reasons.append("browser DOM image")

            existing = deduped.get(candidate.image_url)
            if existing is None or candidate.score > existing.score:
                deduped[candidate.image_url] = candidate

        ranked_candidates = sorted(
            deduped.values(),
            key=lambda item: (-item.score, item.image_url),
        )[: max(1, max_candidates)]

        return ProductPageExtractionResult(
            page_url=page_url,
            best_candidate_url=(
                ranked_candidates[0].image_url if ranked_candidates else None
            ),
            candidates=ranked_candidates,
        )

    async def _wait_for_manual_login(
        self,
        page,
        timeout_seconds: int,
    ) -> None:
        deadline = time.time() + timeout_seconds
        while time.time() < deadline:
            title = await page.title()
            body_text = await page.locator("body").inner_text()
            if not self._is_shopee_login_required(page.url, title, body_text):
                return
            await page.wait_for_timeout(2000)

        raise ValueError(self._build_shopee_blocked_message(page.url, title, body_text))

    async def _launch_persistent_context(self, playwright, headless: bool):
        return await playwright.chromium.launch_persistent_context(
            user_data_dir=str(self.profile_dir),
            headless=headless,
            viewport={"width": 1440, "height": 900},
            locale="vi-VN",
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36"
            ),
        )

    async def _run_shopee_login_session(
        self,
        page_url: str,
        manual_login_timeout_seconds: int,
    ) -> None:
        async with async_playwright() as p:
            context = await self._launch_persistent_context(p, headless=False)
            try:
                page = context.pages[0] if context.pages else await context.new_page()
                await page.goto(page_url, wait_until="domcontentloaded", timeout=45000)
                await page.wait_for_timeout(3000)
                page_title = await page.title()
                body_text = await page.locator("body").inner_text()
                self._set_shopee_login_session(
                    status="awaiting_login",
                    page_url=page_url,
                    final_url=page.url,
                    message=self._build_shopee_blocked_message(
                        page.url,
                        page_title,
                        body_text,
                    ),
                )
                await self._wait_for_manual_login(
                    page,
                    timeout_seconds=manual_login_timeout_seconds,
                )
                await page.wait_for_timeout(2000)
                self._set_shopee_login_session(
                    status="ready",
                    page_url=page_url,
                    final_url=page.url,
                    message="Shopee login session is ready and saved to the persistent profile.",
                )
            except Exception as exc:
                current_url = page.url if "page" in locals() else page_url
                self._set_shopee_login_session(
                    status="failed",
                    page_url=page_url,
                    final_url=current_url,
                    message=f"Shopee login session failed: {exc}",
                )
                logger.error("Shopee login session background flow failed: %s", exc)
                raise
            finally:
                await context.close()
                self._shopee_login_task = None

    async def open_shopee_login_session(
        self,
        page_url: str | None = None,
        manual_login_timeout_seconds: int = 180,
    ) -> dict[str, str | bool | None]:
        """
        Start a persistent Shopee browser session in the background and return immediately.
        """
        target_url = page_url or "https://shopee.vn/buyer/login"
        target_url = ProductPageExtractor._validate_url(target_url)
        self.profile_dir.mkdir(parents=True, exist_ok=True)

        if not self.is_shopee_page_url(target_url):
            raise ValueError("open-shopee-login-session only supports Shopee URLs")

        current_status = self.get_shopee_login_session_status()
        if str(current_status.get("status") or "idle") in {"pending", "awaiting_login"}:
            return current_status

        logger.info(
            "Starting Shopee login session in persistent browser: %s",
            target_url,
        )
        self._set_shopee_login_session(
            status="pending",
            page_url=target_url,
            final_url=None,
            started_at=self._now_iso(),
            message=(
                "Shopee login browser is starting. Complete QR/SMS/CAPTCHA in the "
                "opened browser window, then poll /api/v1/products/check-shopee-login-session."
            ),
        )
        self._shopee_login_task = asyncio.create_task(
            self._run_shopee_login_session(
                page_url=target_url,
                manual_login_timeout_seconds=manual_login_timeout_seconds,
            )
        )
        self._shopee_login_task.add_done_callback(
            self._consume_shopee_login_task_result
        )
        return self.get_shopee_login_session_status()

    async def extract_from_page_url_browser(
        self,
        page_url: str,
        max_candidates: int = 5,
        headless: bool = True,
        interactive_login: bool = False,
        manual_login_timeout_seconds: int = 180,
    ) -> ProductPageExtractionResult:
        """
        Use a persistent browser session to load a product page and extract images.
        """
        page_url = ProductPageExtractor._validate_url(page_url)
        self.profile_dir.mkdir(parents=True, exist_ok=True)

        logger.info(
            "Extracting product image candidates via browser from page URL: %s",
            page_url,
        )

        async with async_playwright() as p:
            context = await self._launch_persistent_context(p, headless=headless)

            try:
                page = context.pages[0] if context.pages else await context.new_page()
                await page.goto(page_url, wait_until="domcontentloaded", timeout=45000)
                await page.wait_for_timeout(5000)

                page_title = await page.title()
                body_text = await page.locator("body").inner_text()
                if self._is_shopee_login_required(page.url, page_title, body_text):
                    login_status = self.get_shopee_login_session_status()
                    login_state = str(login_status.get("status") or "idle")
                    if interactive_login and not headless:
                        logger.info(
                            "Waiting for manual Shopee login in persistent browser..."
                        )
                        await self._wait_for_manual_login(
                            page,
                            timeout_seconds=manual_login_timeout_seconds,
                        )
                        await page.wait_for_timeout(3000)
                    elif login_state in {"pending", "awaiting_login"}:
                        raise ValueError(
                            self._build_shopee_blocked_message(
                                page.url,
                                page_title,
                                body_text,
                            )
                        )
                    else:
                        raise ValueError(
                            self._build_shopee_blocked_message(
                                page.url,
                                page_title,
                                body_text,
                            )
                        )

                html = await page.content()
                html_result = ProductPageExtractor.extract_candidates_from_html(
                    page_url=page.url,
                    html=html,
                    max_candidates=max_candidates,
                )
                dom_urls = await self._collect_dom_image_urls(page)

                merged_result = self._merge_browser_candidates(
                    page_url=page.url,
                    html_result=html_result,
                    dom_urls=dom_urls,
                    max_candidates=max_candidates,
                )

                if not merged_result.candidates:
                    raise ValueError(
                        "No product image candidates found in browser session. "
                        "The page may still be blocked or the product images may require additional interaction."
                    )

                return merged_result
            finally:
                await context.close()
