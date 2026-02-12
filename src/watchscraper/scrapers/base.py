import logging
import random
import time
from abc import ABC, abstractmethod

import requests
from fake_useragent import UserAgent
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from watchscraper.config import settings
from watchscraper.schemas import ScrapedListing

logger = logging.getLogger(__name__)

_ua = UserAgent(fallback="Mozilla/5.0")


class BaseScraper(ABC):
    """Abstract base for all watch scrapers."""

    source_name: str = ""

    def __init__(self) -> None:
        self.session = requests.Session()
        self._rotate_ua()

    def _rotate_ua(self) -> None:
        self.session.headers["User-Agent"] = _ua.random

    def _delay(self) -> None:
        delay = random.uniform(settings.scrape_delay_min, settings.scrape_delay_max)
        logger.debug("Sleeping %.1fs", delay)
        time.sleep(delay)

    @retry(
        retry=retry_if_exception_type(requests.RequestException),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, min=4, max=30),
        reraise=True,
    )
    def _get(self, url: str, **kwargs) -> requests.Response:
        self._rotate_ua()
        self._delay()
        resp = self.session.get(url, timeout=30, **kwargs)
        resp.raise_for_status()
        return resp

    @abstractmethod
    def scrape(self, query: str, **kwargs) -> list[ScrapedListing]:
        """Scrape listings for a given query (e.g. 'Rolex Submariner 126610LN').

        Returns validated ScrapedListing objects.
        """
        ...
