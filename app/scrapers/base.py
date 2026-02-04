"""
Base scraper class with common functionality.
"""

import asyncio
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Generic, List, Optional, TypeVar

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.config import settings

logger = logging.getLogger(__name__)

T = TypeVar("T")


@dataclass
class ScraperResult:
    """Result from a scraping operation."""

    success: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    source_url: Optional[str] = None
    raw_response: Optional[Dict[str, Any]] = None
    duration_ms: int = 0


@dataclass
class ScraperStats:
    """Statistics for a scraping session."""

    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    total_items_found: int = 0
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    errors: List[str] = field(default_factory=list)

    @property
    def success_rate(self) -> float:
        if self.total_requests == 0:
            return 0.0
        return self.successful_requests / self.total_requests

    @property
    def duration_seconds(self) -> float:
        if not self.start_time or not self.end_time:
            return 0.0
        return (self.end_time - self.start_time).total_seconds()


class RateLimiter:
    """Simple rate limiter for API calls."""

    def __init__(self, requests_per_minute: int):
        self.requests_per_minute = requests_per_minute
        self.interval = 60.0 / requests_per_minute
        self.last_request_time = 0.0
        self._lock = asyncio.Lock()

    async def acquire(self):
        """Wait if necessary to respect rate limit."""
        async with self._lock:
            now = time.time()
            time_since_last = now - self.last_request_time
            if time_since_last < self.interval:
                await asyncio.sleep(self.interval - time_since_last)
            self.last_request_time = time.time()


class BaseScraper(ABC, Generic[T]):
    """
    Abstract base class for all scrapers.
    Provides common functionality like rate limiting, retries, and error handling.
    """

    def __init__(
        self,
        rate_limit: int = 60,
        timeout: int = 30,
        max_retries: int = 3,
    ):
        self.rate_limiter = RateLimiter(rate_limit)
        self.timeout = timeout
        self.max_retries = max_retries
        self.stats = ScraperStats()
        self._client: Optional[httpx.AsyncClient] = None

    @property
    @abstractmethod
    def name(self) -> str:
        """Name of the scraper."""
        pass

    async def __aenter__(self):
        """Async context manager entry."""
        self._client = httpx.AsyncClient(timeout=self.timeout)
        self.stats = ScraperStats(start_time=datetime.utcnow())
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self._client:
            await self._client.aclose()
        self.stats.end_time = datetime.utcnow()
        logger.info(
            f"{self.name} scraper finished. "
            f"Success rate: {self.stats.success_rate:.2%}, "
            f"Items found: {self.stats.total_items_found}, "
            f"Duration: {self.stats.duration_seconds:.1f}s"
        )

    @property
    def client(self) -> httpx.AsyncClient:
        """Get HTTP client, raising if not initialized."""
        if not self._client:
            raise RuntimeError("Scraper must be used as async context manager")
        return self._client

    @retry(
        retry=retry_if_exception_type((httpx.HTTPError, asyncio.TimeoutError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
    )
    async def _make_request(
        self,
        method: str,
        url: str,
        **kwargs,
    ) -> httpx.Response:
        """Make an HTTP request with rate limiting and retries."""
        await self.rate_limiter.acquire()
        self.stats.total_requests += 1

        try:
            response = await self.client.request(method, url, **kwargs)
            response.raise_for_status()
            self.stats.successful_requests += 1
            return response
        except Exception as e:
            self.stats.failed_requests += 1
            self.stats.errors.append(str(e))
            raise

    async def get(self, url: str, **kwargs) -> httpx.Response:
        """Make a GET request."""
        return await self._make_request("GET", url, **kwargs)

    async def post(self, url: str, **kwargs) -> httpx.Response:
        """Make a POST request."""
        return await self._make_request("POST", url, **kwargs)

    @abstractmethod
    async def scrape(self, **kwargs) -> List[ScraperResult]:
        """
        Main scraping method to be implemented by subclasses.
        Should return a list of ScraperResult objects.
        """
        pass

    @abstractmethod
    def parse_result(self, raw_data: Dict[str, Any]) -> T:
        """
        Parse raw API/scrape response into the target data structure.
        To be implemented by subclasses.
        """
        pass

    def _extract_domain(self, url: Optional[str]) -> Optional[str]:
        """Extract domain from URL."""
        if not url:
            return None
        try:
            from urllib.parse import urlparse

            parsed = urlparse(url)
            domain = parsed.netloc or parsed.path
            # Remove www. prefix
            if domain.startswith("www."):
                domain = domain[4:]
            return domain.lower()
        except Exception:
            return None

    def _clean_phone(self, phone: Optional[str]) -> Optional[str]:
        """Clean and standardize phone number."""
        if not phone:
            return None
        # Remove common non-numeric characters except + for international
        import re

        cleaned = re.sub(r"[^\d+]", "", phone)
        if len(cleaned) >= 10:
            return cleaned
        return None

    def _clean_email(self, email: Optional[str]) -> Optional[str]:
        """Clean and validate email."""
        if not email:
            return None
        email = email.strip().lower()
        # Basic validation
        if "@" in email and "." in email.split("@")[-1]:
            return email
        return None


class CompanyData:
    """Standard company data structure."""

    def __init__(
        self,
        name: str,
        website: Optional[str] = None,
        domain: Optional[str] = None,
        industry: Optional[str] = None,
        employee_count: Optional[int] = None,
        address: Optional[str] = None,
        city: Optional[str] = None,
        state: Optional[str] = None,
        country: str = "USA",
        zip_code: Optional[str] = None,
        phone: Optional[str] = None,
        google_place_id: Optional[str] = None,
        google_rating: Optional[float] = None,
        google_reviews_count: Optional[int] = None,
        linkedin_company_url: Optional[str] = None,
        raw_data: Optional[Dict[str, Any]] = None,
    ):
        self.name = name
        self.website = website
        self.domain = domain
        self.industry = industry
        self.employee_count = employee_count
        self.address = address
        self.city = city
        self.state = state
        self.country = country
        self.zip_code = zip_code
        self.phone = phone
        self.google_place_id = google_place_id
        self.google_rating = google_rating
        self.google_reviews_count = google_reviews_count
        self.linkedin_company_url = linkedin_company_url
        self.raw_data = raw_data or {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "website": self.website,
            "domain": self.domain,
            "industry": self.industry,
            "employee_count": self.employee_count,
            "address": self.address,
            "city": self.city,
            "state": self.state,
            "country": self.country,
            "zip_code": self.zip_code,
            "phone": self.phone,
            "google_place_id": self.google_place_id,
            "google_rating": self.google_rating,
            "google_reviews_count": self.google_reviews_count,
            "linkedin_company_url": self.linkedin_company_url,
            "raw_data": self.raw_data,
        }


class LeadData:
    """Standard lead data structure."""

    def __init__(
        self,
        email: Optional[str] = None,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        full_name: Optional[str] = None,
        job_title: Optional[str] = None,
        department: Optional[str] = None,
        seniority_level: Optional[str] = None,
        phone: Optional[str] = None,
        linkedin_url: Optional[str] = None,
        company_name: Optional[str] = None,
        company_domain: Optional[str] = None,
        confidence_score: float = 0.0,
        source_url: Optional[str] = None,
        raw_data: Optional[Dict[str, Any]] = None,
    ):
        self.email = email
        self.first_name = first_name
        self.last_name = last_name
        self.full_name = full_name or f"{first_name or ''} {last_name or ''}".strip()
        self.job_title = job_title
        self.department = department
        self.seniority_level = seniority_level
        self.phone = phone
        self.linkedin_url = linkedin_url
        self.company_name = company_name
        self.company_domain = company_domain
        self.confidence_score = confidence_score
        self.source_url = source_url
        self.raw_data = raw_data or {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "email": self.email,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "full_name": self.full_name,
            "job_title": self.job_title,
            "department": self.department,
            "seniority_level": self.seniority_level,
            "phone": self.phone,
            "linkedin_url": self.linkedin_url,
            "company_name": self.company_name,
            "company_domain": self.company_domain,
            "confidence_score": self.confidence_score,
            "source_url": self.source_url,
            "raw_data": self.raw_data,
        }
