"""Fetch one representative image per watch family from Chrono24 search results.

Downloads dealer listing photos into src/watchscraper/web/static/img/families/
as {slug}.jpg. Picks the first search-result card whose title matches the
family pattern so a "Royal Oak" query can't hand us an Offshore image.
"""

import logging
import random
import re
import sys
import time
from pathlib import Path
from urllib.parse import quote_plus

from bs4 import BeautifulSoup
from curl_cffi import requests as cffi

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from watchscraper.analysis import FAMILY_PATTERNS  # noqa: E402
from watchscraper.web.services import slugify  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

OUT_DIR = (
    Path(__file__).resolve().parent.parent
    / "src" / "watchscraper" / "web" / "static" / "img" / "families"
)
SEARCH_URL = "https://www.chrono24.com/search/index.htm?query={query}&dosearch=true"
IMG_WIDTH = "440"


def find_image_url(html: str, family_pattern: str) -> str | None:
    soup = BeautifulSoup(html, "lxml")
    for card in soup.select("div.js-listing-item-container"):
        title_div = card.select_one("div.p-t-3")
        title = title_div.get_text(" ", strip=True) if title_div else ""
        if not re.search(family_pattern, title, re.IGNORECASE):
            continue
        img = card.select_one("img[data-lazy-sweet-spot-master-src]")
        if img:
            src = img["data-lazy-sweet-spot-master-src"]
            return src.replace("_SIZE_", IMG_WIDTH)
    return None


def fetch_family_image(brand: str, family: str, pattern: str) -> bool:
    slug = slugify(family)
    out_path = OUT_DIR / f"{slug}.jpg"
    if out_path.exists():
        logger.info("%s: already have image, skipping", family)
        return True

    query = f"{brand} {family}"
    url = SEARCH_URL.format(query=quote_plus(query))
    try:
        resp = cffi.get(url, impersonate="chrome", timeout=30)
    except Exception:
        logger.exception("%s: search request failed", family)
        return False
    if resp.status_code != 200:
        logger.warning("%s: search returned %d", family, resp.status_code)
        return False

    img_url = find_image_url(resp.text, pattern)
    if not img_url:
        logger.warning("%s: no matching card with image", family)
        return False

    try:
        img_resp = cffi.get(img_url, impersonate="chrome", timeout=30)
    except Exception:
        logger.exception("%s: image download failed", family)
        return False
    if img_resp.status_code != 200 or len(img_resp.content) < 2000:
        logger.warning("%s: bad image response (%d, %db)",
                       family, img_resp.status_code, len(img_resp.content))
        return False

    out_path.write_bytes(img_resp.content)
    logger.info("%s: saved %s (%.0f KB)", family, out_path.name, len(img_resp.content) / 1024)
    return True


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    got, missed = 0, []
    for brand, family, pattern in FAMILY_PATTERNS:
        if fetch_family_image(brand, family, pattern):
            got += 1
        else:
            missed.append(family)
        time.sleep(1.5 + random.random() * 1.5)
    logger.info("Done: %d images, %d missing%s",
                got, len(missed), f" ({', '.join(missed)})" if missed else "")


if __name__ == "__main__":
    main()
