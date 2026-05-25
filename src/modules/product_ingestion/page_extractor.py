"""
Minimal product page image candidate extraction.
"""

from dataclasses import dataclass
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse
import logging
import re

import httpx

from src.config.settings import get_settings

logger = logging.getLogger(__name__)

GARMENT_HINTS = {
    "shirt",
    "tshirt",
    "t-shirt",
    "tee",
    "jersey",
    "dress",
    "gown",
    "top",
    "blouse",
    "hoodie",
    "sweater",
    "cardigan",
    "jacket",
    "coat",
    "pants",
    "trousers",
    "jeans",
    "shorts",
    "skirt",
    "garment",
    "product",
}

PREFERRED_HINTS = {
    "product",
    "gallery",
    "main",
    "hero",
    "detail",
    "primary",
}

REJECT_HINTS = {
    "icon",
    "logo",
    "avatar",
    "sprite",
    "thumb",
    "thumbnail",
    "placeholder",
    "loading",
    "banner",
    "ads",
    "splash",
    "ios_splash_screen",
    "android_splash",
    "shopee-mobilemall-live",
    "deo.shopeemobile.com",
    "/assets/",
}

IMAGE_HOST_HINTS = {
    "img.susercontent.com",
    "down-vn.img.susercontent.com",
    "cf.shopee.vn",
}

NON_IMAGE_EXTENSIONS = {
    ".js",
    ".css",
    ".svg",
    ".ico",
    ".woff",
    ".woff2",
    ".ttf",
    ".map",
}


@dataclass
class ProductPageImageCandidate:
    image_url: str
    score: int
    source: str
    reasons: list[str]


@dataclass
class ProductPageExtractionResult:
    page_url: str
    best_candidate_url: str | None
    candidates: list[ProductPageImageCandidate]


class _ProductPageHTMLParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.meta_images: list[dict] = []
        self.img_candidates: list[dict] = []

    @staticmethod
    def _attrs_to_dict(attrs: list[tuple[str, str | None]]) -> dict[str, str]:
        return {key.lower(): (value or "").strip() for key, value in attrs}

    @staticmethod
    def _pick_image_attr(attrs: dict[str, str]) -> str:
        if attrs.get("src"):
            return attrs["src"]
        if attrs.get("data-src"):
            return attrs["data-src"]
        if attrs.get("data-original"):
            return attrs["data-original"]
        if attrs.get("data-lazy-src"):
            return attrs["data-lazy-src"]
        if attrs.get("srcset"):
            first_entry = attrs["srcset"].split(",")[0].strip()
            return first_entry.split(" ")[0]
        return ""

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]):
        attrs_dict = self._attrs_to_dict(attrs)

        if tag == "meta":
            meta_key = (
                attrs_dict.get("property") or attrs_dict.get("name") or ""
            ).lower()
            if meta_key in {"og:image", "og:image:secure_url", "twitter:image"}:
                content = attrs_dict.get("content", "")
                if content:
                    self.meta_images.append(
                        {"url": content, "source": meta_key, "attrs": attrs_dict}
                    )

        if tag == "img":
            image_url = self._pick_image_attr(attrs_dict)
            if image_url:
                self.img_candidates.append(
                    {
                        "url": image_url,
                        "source": "img",
                        "attrs": attrs_dict,
                    }
                )


class ProductPageExtractor:
    """
    Extract ranked product image candidates from a product page URL.
    """

    def __init__(self):
        settings = get_settings()
        self.timeout = min(float(settings.replicate_timeout), 30.0)

    @staticmethod
    def _extract_shopee_ids_from_page_url(page_url: str) -> tuple[str, str] | None:
        patterns = [
            r"-i\.(\d+)\.(\d+)(?:[/?#]|$)",
            r"/product/(\d+)/(\d+)(?:[/?#]|$)",
        ]
        for pattern in patterns:
            match = re.search(pattern, page_url)
            if match:
                return match.group(1), match.group(2)
        return None

    @staticmethod
    def _validate_url(page_url: str) -> str:
        parsed = urlparse(page_url)
        if parsed.scheme not in {"http", "https"}:
            raise ValueError("Only http and https page URLs are supported")
        if not parsed.netloc:
            raise ValueError("Page URL must include a valid host")
        return page_url

    @staticmethod
    def _looks_like_http_image(candidate_url: str) -> bool:
        parsed = urlparse(candidate_url)
        if parsed.scheme not in {"http", "https"}:
            return False
        if not parsed.netloc:
            return False
        lowered_path = parsed.path.lower()
        if lowered_path in {"", "/"}:
            return False
        if any(lowered_path.endswith(ext) for ext in NON_IMAGE_EXTENSIONS):
            return False
        return True

    @staticmethod
    def _normalize_candidate_url(page_url: str, raw_url: str) -> str:
        candidate_url = (raw_url or "").strip()
        if not candidate_url:
            return ""

        candidate_url = candidate_url.replace("\\/", "/")
        candidate_url = candidate_url.replace("&amp;", "&")

        if candidate_url.startswith("//"):
            candidate_url = f"https:{candidate_url}"

        if candidate_url.startswith("/"):
            candidate_url = urljoin(page_url, candidate_url)

        return candidate_url

    @staticmethod
    def _looks_like_shopee_image_id(value: str) -> bool:
        candidate = (value or "").strip()
        if not candidate or "/" in candidate or candidate.lower().startswith("http"):
            return False

        patterns = [
            r"^[a-z]{2}-\d{8,}-[A-Za-z0-9._-]{8,}$",
            r"^\d{8,}-[A-Za-z0-9._-]{8,}$",
            r"^vn-\d{8,}-[A-Za-z0-9._-]{8,}$",
        ]
        return any(
            re.match(pattern, candidate, flags=re.IGNORECASE) for pattern in patterns
        )

    @staticmethod
    def _parse_dimension(value: str) -> int:
        match = re.search(r"\d+", value or "")
        return int(match.group(0)) if match else 0

    @classmethod
    def _score_candidate(
        cls, page_url: str, raw_url: str, source: str, attrs: dict[str, str]
    ) -> ProductPageImageCandidate | None:
        absolute_url = cls._normalize_candidate_url(page_url, raw_url)
        if not cls._looks_like_http_image(absolute_url):
            return None

        parsed_url = urlparse(absolute_url)
        host_lower = parsed_url.netloc.lower()
        path_lower = parsed_url.path.lower()
        combined_text = " ".join(
            [
                absolute_url.lower(),
                attrs.get("alt", "").lower(),
                attrs.get("class", "").lower(),
                attrs.get("id", "").lower(),
            ]
        )

        score = 0
        reasons: list[str] = []

        if source.startswith("og:image"):
            score += 120
            reasons.append("Open Graph image")
        elif source == "twitter:image":
            score += 110
            reasons.append("Twitter card image")
        elif source == "shopee-image-id":
            score += 160
            reasons.append("Shopee product image id")
        elif source == "raw-html":
            score += 20
            reasons.append("Raw HTML/script image candidate")
        else:
            score += 50
            reasons.append("HTML image tag")

        if any(hint in combined_text for hint in PREFERRED_HINTS):
            score += 20
            reasons.append("product/gallery hint")

        if any(hint in combined_text for hint in GARMENT_HINTS):
            score += 25
            reasons.append("garment-related hint")

        if any(host_hint in host_lower for host_hint in IMAGE_HOST_HINTS):
            score += 35
            reasons.append("known commerce image host")

        if "/file/" in path_lower:
            score += 20
            reasons.append("image file path hint")

        if "susercontent.com" in host_lower and "/file/" not in path_lower:
            score -= 40
            reasons.append("susercontent URL without product file path")

        if "deo.shopeemobile.com" in host_lower:
            score -= 80
            reasons.append("Shopee app asset host")

        if any(hint in combined_text for hint in REJECT_HINTS):
            score -= 50
            reasons.append("likely non-product asset")

        width = cls._parse_dimension(attrs.get("width", ""))
        height = cls._parse_dimension(attrs.get("height", ""))
        largest_dimension = max(width, height)

        if largest_dimension >= 1000:
            score += 30
            reasons.append("large declared image")
        elif largest_dimension >= 500:
            score += 15
            reasons.append("medium declared image")

        if absolute_url.endswith((".jpg", ".jpeg", ".png", ".webp")):
            score += 5
            reasons.append("direct image extension")

        if score <= 0:
            return None

        return ProductPageImageCandidate(
            image_url=absolute_url,
            score=score,
            source=source,
            reasons=reasons,
        )

    @classmethod
    def extract_candidates_from_html(
        cls, page_url: str, html: str, max_candidates: int = 5
    ) -> ProductPageExtractionResult:
        parser = _ProductPageHTMLParser()
        parser.feed(html)

        deduped: dict[str, ProductPageImageCandidate] = {}

        for raw_url in cls._extract_shopee_image_urls_from_raw_html(page_url, html):
            candidate = cls._score_candidate(
                page_url=page_url,
                raw_url=raw_url,
                source="shopee-image-id",
                attrs={},
            )
            if not candidate:
                continue

            deduped[candidate.image_url] = candidate

        for raw_candidate in [*parser.meta_images, *parser.img_candidates]:
            candidate = cls._score_candidate(
                page_url=page_url,
                raw_url=raw_candidate["url"],
                source=raw_candidate["source"],
                attrs=raw_candidate["attrs"],
            )
            if not candidate:
                continue

            existing = deduped.get(candidate.image_url)
            if existing is None or candidate.score > existing.score:
                deduped[candidate.image_url] = candidate

        if not deduped:
            for raw_url in cls._extract_image_urls_from_raw_html(html):
                candidate = cls._score_candidate(
                    page_url=page_url,
                    raw_url=raw_url,
                    source="raw-html",
                    attrs={},
                )
                if not candidate:
                    continue

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

    @staticmethod
    def _extract_shopee_image_urls_from_raw_html(page_url: str, html: str) -> list[str]:
        """
        Extract Shopee product image IDs from raw JSON and build CDN URLs.
        """
        page_host = urlparse(page_url).netloc.lower()
        if "shopee." not in page_host:
            return []

        image_urls: list[str] = []
        seen: set[str] = set()

        def add_image_id(image_id: str):
            if not ProductPageExtractor._looks_like_shopee_image_id(image_id):
                return
            candidate_url = f"https://down-vn.img.susercontent.com/file/{image_id}"
            if candidate_url not in seen:
                seen.add(candidate_url)
                image_urls.append(candidate_url)

        array_blocks = re.findall(
            r'"images"\s*:\s*\[(.*?)\]',
            html,
            flags=re.IGNORECASE | re.DOTALL,
        )
        for block in array_blocks:
            for image_id in re.findall(r'"([^"]+)"', block):
                add_image_id(image_id)

        single_value_patterns = [
            r'"image"\s*:\s*"([^"]+)"',
            r'"thumbnail"\s*:\s*"([^"]+)"',
            r'"image_url"\s*:\s*"([^"]+)"',
            r'"cover"\s*:\s*"([^"]+)"',
        ]
        for pattern in single_value_patterns:
            for value in re.findall(pattern, html, flags=re.IGNORECASE):
                normalized = value.replace("\\/", "/")
                if normalized.lower().startswith("http"):
                    if normalized not in seen:
                        seen.add(normalized)
                        image_urls.append(normalized)
                else:
                    add_image_id(normalized)

        generic_image_ids = re.findall(
            r'"([a-z]{2}-\d{8,}-[A-Za-z0-9._-]{8,})"',
            html,
            flags=re.IGNORECASE,
        )
        for image_id in generic_image_ids:
            add_image_id(image_id)

        return image_urls

    @classmethod
    def _map_shopee_api_images_to_candidates(
        cls, page_url: str, images: list[str], max_candidates: int
    ) -> ProductPageExtractionResult:
        deduped: dict[str, ProductPageImageCandidate] = {}

        for image_id in images:
            candidate = cls._score_candidate(
                page_url=page_url,
                raw_url=f"https://down-vn.img.susercontent.com/file/{image_id}",
                source="shopee-api",
                attrs={},
            )
            if not candidate:
                continue

            candidate.score += 40
            candidate.reasons.append("Shopee item API image")
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

    async def _extract_from_shopee_item_api(
        self, page_url: str, max_candidates: int
    ) -> ProductPageExtractionResult | None:
        ids = self._extract_shopee_ids_from_page_url(page_url)
        if not ids:
            return None

        shop_id, item_id = ids
        parsed_page_url = urlparse(page_url)
        api_url = (
            f"{parsed_page_url.scheme}://{parsed_page_url.netloc}"
            f"/api/v4/item/get?itemid={item_id}&shopid={shop_id}"
        )

        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36"
            ),
            "Accept": "application/json, text/plain, */*",
            "Referer": page_url,
            "x-api-source": "pc",
            "af-ac-enc-dat": "1",
        }

        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=self.timeout,
            headers=headers,
        ) as client:
            response = await client.get(api_url)
            response.raise_for_status()

        try:
            payload = response.json()
        except ValueError:
            logger.warning("Shopee item API fallback did not return valid JSON")
            return None

        data = payload.get("data") or {}
        image_ids = data.get("images") or []
        if not image_ids:
            single_image = data.get("image")
            if single_image:
                image_ids = [single_image]

        image_ids = [
            image_id
            for image_id in image_ids
            if self._looks_like_shopee_image_id(image_id)
        ]
        if not image_ids:
            logger.warning("Shopee item API fallback returned no usable image ids")
            return None

        return self._map_shopee_api_images_to_candidates(
            page_url=page_url,
            images=image_ids,
            max_candidates=max_candidates,
        )

    @staticmethod
    def _extract_image_urls_from_raw_html(html: str) -> list[str]:
        """
        Extract likely image URLs from raw HTML/JSON/script blobs.
        """
        patterns = [
            r"https?:\\?/\\?/[^\"'\s<>]+",
            r"https?://[^\"'\s<>]+",
            r"//[^\"'\s<>]*img\.susercontent\.com[^\"'\s<>]+",
            r"//[^\"'\s<>]*susercontent\.com[^\"'\s<>]+",
        ]

        raw_matches: list[str] = []
        for pattern in patterns:
            raw_matches.extend(re.findall(pattern, html, flags=re.IGNORECASE))

        candidates: list[str] = []
        seen: set[str] = set()
        for raw_match in raw_matches:
            normalized = raw_match.strip().rstrip(",);")
            normalized = normalized.replace("\\u002F", "/")
            normalized = normalized.replace("\\u0026", "&")
            normalized = normalized.replace("\\/", "/")

            lowered = normalized.lower()
            if not any(
                hint in lowered
                for hint in (
                    "img.susercontent.com",
                    "susercontent.com",
                    "/file/",
                    "og:image",
                    "twitter:image",
                )
            ) and not re.search(r"\.(jpe?g|png|webp)(?:[?#]|$)", lowered):
                continue

            if normalized not in seen:
                seen.add(normalized)
                candidates.append(normalized)

        return candidates

    async def extract_from_page_url(
        self, page_url: str, max_candidates: int = 5
    ) -> ProductPageExtractionResult:
        page_url = self._validate_url(page_url)
        logger.info(f"Extracting product image candidates from page URL: {page_url}")

        headers = {
            "User-Agent": "tryon-visual-project/0.1",
            "Accept": "text/html,application/xhtml+xml",
        }

        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=self.timeout,
            headers=headers,
        ) as client:
            response = await client.get(page_url)
            response.raise_for_status()

        content_type = response.headers.get("content-type", "").split(";")[0].strip()
        if content_type and "html" not in content_type:
            raise ValueError(
                f"URL did not return an HTML page. Content-Type was '{content_type}'"
            )

        result = self.extract_candidates_from_html(
            page_url=page_url,
            html=response.text,
            max_candidates=max_candidates,
        )

        if not result.candidates:
            page_host = urlparse(page_url).netloc.lower()
            if "shopee." in page_host:
                try:
                    api_result = await self._extract_from_shopee_item_api(
                        page_url=page_url,
                        max_candidates=max_candidates,
                    )
                except httpx.HTTPStatusError as e:
                    if e.response.status_code == 403:
                        raise ValueError(
                            "Shopee blocked the item API fallback with 403 Forbidden. "
                            "This product page likely requires a real browser session or anti-bot token."
                        ) from e
                    raise
                if api_result and api_result.candidates:
                    return api_result

                raise ValueError(
                    "No product image candidates found in Shopee HTML response or item API fallback. "
                    "The page may require a browser session, anti-bot token, or JS-rendered data."
                )
            raise ValueError("No image candidates found on the product page")

        return result
