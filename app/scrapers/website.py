"""
Generic website scraper for extracting contact information.
Scrapes contact pages, about pages, and team pages.
"""

import asyncio
import logging
import re
from typing import Any, Dict, List, Optional, Set
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from app.config import settings

from .base import BaseScraper, CompanyData, LeadData, ScraperResult

logger = logging.getLogger(__name__)


class WebsiteScraper(BaseScraper[Dict[str, Any]]):
    """
    Generic website scraper for extracting contact information.

    Extracts:
    - Email addresses
    - Phone numbers
    - Social media links
    - Team member information
    - Company information from structured data
    """

    # Common contact page paths
    CONTACT_PATHS = [
        "/contact",
        "/contact-us",
        "/contactus",
        "/get-in-touch",
        "/reach-us",
        "/support",
    ]

    ABOUT_PATHS = [
        "/about",
        "/about-us",
        "/aboutus",
        "/company",
        "/who-we-are",
    ]

    TEAM_PATHS = [
        "/team",
        "/our-team",
        "/leadership",
        "/management",
        "/about/team",
        "/about/leadership",
        "/people",
    ]

    # Email regex pattern
    EMAIL_PATTERN = re.compile(
        r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
        re.IGNORECASE
    )

    # Phone regex pattern (US format)
    PHONE_PATTERN = re.compile(
        r"(?:\+?1[-.\s]?)?\(?[2-9]\d{2}\)?[-.\s]?\d{3}[-.\s]?\d{4}"
    )

    def __init__(
        self,
        rate_limit: int = None,
        use_playwright: bool = False,
    ):
        super().__init__(
            rate_limit=rate_limit or settings.website_rate_limit,
            timeout=30,
            max_retries=3,
        )
        self.use_playwright = use_playwright
        self._browser = None

    @property
    def name(self) -> str:
        return "Website"

    async def __aenter__(self):
        await super().__aenter__()

        if self.use_playwright:
            try:
                from playwright.async_api import async_playwright
                self._playwright = await async_playwright().start()
                self._browser = await self._playwright.chromium.launch(headless=True)
            except ImportError:
                logger.warning("Playwright not installed, using httpx only")
                self.use_playwright = False

        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._browser:
            await self._browser.close()
            await self._playwright.stop()
        await super().__aexit__(exc_type, exc_val, exc_tb)

    async def scrape(
        self,
        urls: List[str],
        scrape_contact_page: bool = True,
        scrape_about_page: bool = True,
        scrape_team_page: bool = True,
        extract_emails: bool = True,
        extract_phones: bool = True,
        extract_social_links: bool = True,
        **kwargs,
    ) -> List[ScraperResult]:
        """
        Scrape websites for contact information.

        Args:
            urls: List of website URLs to scrape
            scrape_contact_page: Whether to scrape contact pages
            scrape_about_page: Whether to scrape about pages
            scrape_team_page: Whether to scrape team pages
            extract_emails: Whether to extract email addresses
            extract_phones: Whether to extract phone numbers
            extract_social_links: Whether to extract social media links

        Returns:
            List of ScraperResult with extracted data
        """
        results: List[ScraperResult] = []

        for url in urls:
            try:
                result = await self._scrape_website(
                    url=url,
                    scrape_contact=scrape_contact_page,
                    scrape_about=scrape_about_page,
                    scrape_team=scrape_team_page,
                    extract_emails=extract_emails,
                    extract_phones=extract_phones,
                    extract_social=extract_social_links,
                )
                results.append(result)
            except Exception as e:
                logger.error(f"Error scraping {url}: {e}")
                results.append(
                    ScraperResult(
                        success=False,
                        error=str(e),
                        source_url=url,
                    )
                )

        self.stats.total_items_found = len([r for r in results if r.success])
        return results

    async def _scrape_website(
        self,
        url: str,
        scrape_contact: bool,
        scrape_about: bool,
        scrape_team: bool,
        extract_emails: bool,
        extract_phones: bool,
        extract_social: bool,
    ) -> ScraperResult:
        """Scrape a single website."""
        # Normalize URL
        if not url.startswith(("http://", "https://")):
            url = f"https://{url}"

        base_url = f"{urlparse(url).scheme}://{urlparse(url).netloc}"
        domain = self._extract_domain(url)

        data = {
            "url": url,
            "domain": domain,
            "emails": set(),
            "phones": set(),
            "social_links": {},
            "team_members": [],
            "company_info": {},
        }

        pages_to_scrape = [(url, "homepage")]

        if scrape_contact:
            for path in self.CONTACT_PATHS:
                pages_to_scrape.append((urljoin(base_url, path), "contact"))

        if scrape_about:
            for path in self.ABOUT_PATHS:
                pages_to_scrape.append((urljoin(base_url, path), "about"))

        if scrape_team:
            for path in self.TEAM_PATHS:
                pages_to_scrape.append((urljoin(base_url, path), "team"))

        # Scrape pages concurrently (but with rate limiting)
        for page_url, page_type in pages_to_scrape:
            try:
                html = await self._fetch_page(page_url)
                if html:
                    await self._parse_page(
                        html=html,
                        page_url=page_url,
                        page_type=page_type,
                        data=data,
                        extract_emails=extract_emails,
                        extract_phones=extract_phones,
                        extract_social=extract_social,
                    )
            except Exception as e:
                logger.debug(f"Could not scrape {page_url}: {e}")

        # Convert sets to lists for JSON serialization
        data["emails"] = list(data["emails"])
        data["phones"] = list(data["phones"])

        # Filter out common non-personal emails
        data["emails"] = [
            e for e in data["emails"]
            if not self._is_generic_email(e)
        ]

        return ScraperResult(
            success=True,
            data=data,
            source_url=url,
        )

    async def _fetch_page(self, url: str) -> Optional[str]:
        """Fetch page HTML."""
        await self.rate_limiter.acquire()
        self.stats.total_requests += 1

        try:
            if self.use_playwright and self._browser:
                # Use Playwright for JS-heavy sites
                page = await self._browser.new_page()
                try:
                    await page.goto(url, wait_until="networkidle", timeout=30000)
                    html = await page.content()
                finally:
                    await page.close()
            else:
                # Use httpx for static sites
                response = await self.client.get(
                    url,
                    follow_redirects=True,
                    headers={
                        "User-Agent": (
                            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                            "AppleWebKit/537.36 (KHTML, like Gecko) "
                            "Chrome/120.0.0.0 Safari/537.36"
                        )
                    },
                )
                response.raise_for_status()
                html = response.text

            self.stats.successful_requests += 1
            return html

        except Exception as e:
            self.stats.failed_requests += 1
            raise

    async def _parse_page(
        self,
        html: str,
        page_url: str,
        page_type: str,
        data: Dict[str, Any],
        extract_emails: bool,
        extract_phones: bool,
        extract_social: bool,
    ):
        """Parse HTML and extract data."""
        soup = BeautifulSoup(html, "lxml")

        # Remove script and style elements
        for element in soup(["script", "style", "noscript"]):
            element.decompose()

        text = soup.get_text(separator=" ", strip=True)

        # Extract emails
        if extract_emails:
            emails = self.EMAIL_PATTERN.findall(text)
            # Also check mailto links
            for link in soup.find_all("a", href=True):
                href = link["href"]
                if href.startswith("mailto:"):
                    email = href.replace("mailto:", "").split("?")[0]
                    emails.append(email)
            data["emails"].update(self._clean_email(e) for e in emails if self._clean_email(e))

        # Extract phones
        if extract_phones:
            phones = self.PHONE_PATTERN.findall(text)
            # Also check tel links
            for link in soup.find_all("a", href=True):
                href = link["href"]
                if href.startswith("tel:"):
                    phone = href.replace("tel:", "")
                    phones.append(phone)
            data["phones"].update(self._clean_phone(p) for p in phones if self._clean_phone(p))

        # Extract social links
        if extract_social:
            social = self._extract_social_links(soup)
            data["social_links"].update(social)

        # Extract team members from team pages
        if page_type == "team":
            team = self._extract_team_members(soup)
            data["team_members"].extend(team)

        # Extract structured data (JSON-LD)
        structured = self._extract_structured_data(soup)
        if structured:
            data["company_info"].update(structured)

    def _extract_social_links(self, soup: BeautifulSoup) -> Dict[str, str]:
        """Extract social media links."""
        social = {}

        social_patterns = {
            "linkedin": r"linkedin\.com/(?:company|in)/[\w-]+",
            "twitter": r"(?:twitter|x)\.com/[\w]+",
            "facebook": r"facebook\.com/[\w.-]+",
            "instagram": r"instagram\.com/[\w.-]+",
            "youtube": r"youtube\.com/(?:channel|c|user)/[\w-]+",
            "github": r"github\.com/[\w-]+",
        }

        for link in soup.find_all("a", href=True):
            href = link["href"].lower()
            for platform, pattern in social_patterns.items():
                if platform not in social:
                    match = re.search(pattern, href)
                    if match:
                        social[platform] = href

        return social

    def _extract_team_members(self, soup: BeautifulSoup) -> List[Dict[str, Any]]:
        """Extract team member information from team pages."""
        team = []

        # Common patterns for team sections
        team_selectors = [
            ".team-member",
            ".person",
            ".staff",
            ".leadership",
            "[class*='team']",
            "[class*='member']",
        ]

        for selector in team_selectors:
            members = soup.select(selector)
            for member in members:
                person = {}

                # Try to find name
                name_elem = member.find(["h2", "h3", "h4", ".name", "[class*='name']"])
                if name_elem:
                    person["name"] = name_elem.get_text(strip=True)

                # Try to find title
                title_elem = member.find([".title", ".role", ".position", "[class*='title']", "[class*='role']"])
                if title_elem:
                    person["job_title"] = title_elem.get_text(strip=True)

                # Try to find LinkedIn
                linkedin = member.find("a", href=re.compile(r"linkedin\.com"))
                if linkedin:
                    person["linkedin_url"] = linkedin["href"]

                # Try to find email
                email_link = member.find("a", href=re.compile(r"mailto:"))
                if email_link:
                    email = email_link["href"].replace("mailto:", "").split("?")[0]
                    person["email"] = self._clean_email(email)

                if person.get("name"):
                    team.append(person)

            if team:
                break  # Found team members, stop looking

        return team

    def _extract_structured_data(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """Extract company info from JSON-LD structured data."""
        info = {}

        for script in soup.find_all("script", type="application/ld+json"):
            try:
                import json
                data = json.loads(script.string)

                # Handle array of objects
                if isinstance(data, list):
                    for item in data:
                        info.update(self._parse_jsonld(item))
                else:
                    info.update(self._parse_jsonld(data))

            except Exception:
                pass

        return info

    def _parse_jsonld(self, data: Dict) -> Dict[str, Any]:
        """Parse JSON-LD object for company information."""
        info = {}

        schema_type = data.get("@type", "")

        if schema_type in ["Organization", "Corporation", "LocalBusiness"]:
            if "name" in data:
                info["name"] = data["name"]
            if "description" in data:
                info["description"] = data["description"]
            if "telephone" in data:
                info["phone"] = data["telephone"]
            if "email" in data:
                info["email"] = data["email"]
            if "address" in data:
                addr = data["address"]
                if isinstance(addr, dict):
                    info["address"] = addr.get("streetAddress")
                    info["city"] = addr.get("addressLocality")
                    info["state"] = addr.get("addressRegion")
                    info["zip_code"] = addr.get("postalCode")
                    info["country"] = addr.get("addressCountry")
            if "numberOfEmployees" in data:
                emp = data["numberOfEmployees"]
                if isinstance(emp, dict):
                    info["employee_count"] = emp.get("value")
                else:
                    info["employee_count"] = emp
            if "foundingDate" in data:
                info["founded_year"] = data["foundingDate"][:4] if data["foundingDate"] else None

        return info

    def _is_generic_email(self, email: str) -> bool:
        """Check if email is a generic/non-personal address."""
        if not email:
            return True

        generic_prefixes = [
            "info@", "contact@", "hello@", "support@", "help@",
            "sales@", "marketing@", "admin@", "office@", "team@",
            "jobs@", "careers@", "hr@", "press@", "media@",
            "noreply@", "no-reply@", "donotreply@",
        ]

        email_lower = email.lower()
        return any(email_lower.startswith(prefix) for prefix in generic_prefixes)

    def parse_result(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """Parse scraper output (identity for website scraper)."""
        return raw_data


async def scrape_websites(
    urls: List[str],
    scrape_contact: bool = True,
    scrape_team: bool = True,
    use_playwright: bool = False,
) -> List[ScraperResult]:
    """
    Convenience function to scrape websites.

    Example:
        results = await scrape_websites(
            urls=["acme.com", "techcorp.io"],
            scrape_team=True,
        )
    """
    async with WebsiteScraper(use_playwright=use_playwright) as scraper:
        return await scraper.scrape(
            urls=urls,
            scrape_contact_page=scrape_contact,
            scrape_team_page=scrape_team,
        )
