"""
LinkedIn scraper using Bright Data's Web Scraper API.
Used as fallback when AI Ark doesn't have data.
"""

import logging
from typing import Any, Dict, List, Optional

from app.config import settings

from .base import BaseScraper, LeadData, ScraperResult

logger = logging.getLogger(__name__)


class LinkedInScraper(BaseScraper[LeadData]):
    """
    LinkedIn scraper using Bright Data's infrastructure.

    Bright Data handles:
    - Proxy rotation
    - Anti-bot detection bypass
    - Rate limiting

    This is the fallback in the waterfall strategy:
    1. AI Ark (primary)
    2. LinkedIn/Bright Data (this) <-- fallback
    3. AI Lead Finder (last resort)
    """

    # Bright Data Web Scraper API endpoints
    BRIGHT_DATA_API = "https://api.brightdata.com"

    def __init__(
        self,
        username: Optional[str] = None,
        password: Optional[str] = None,
        rate_limit: int = None,
    ):
        super().__init__(
            rate_limit=rate_limit or settings.linkedin_rate_limit,
            timeout=120,  # LinkedIn scraping can be slow
            max_retries=3,
        )
        self.username = username or settings.bright_data_username
        self.password = password or settings.bright_data_password

    @property
    def name(self) -> str:
        return "LinkedIn"

    @property
    def proxy_url(self) -> Optional[str]:
        """Get Bright Data proxy URL."""
        if self.username and self.password:
            return (
                f"http://{self.username}:{self.password}"
                f"@{settings.bright_data_host}:{settings.bright_data_port}"
            )
        return None

    @property
    def auth(self) -> tuple:
        """Basic auth for Bright Data API."""
        return (self.username, self.password)

    async def scrape(
        self,
        job_titles: Optional[List[str]] = None,
        company_names: Optional[List[str]] = None,
        industries: Optional[List[str]] = None,
        locations: Optional[List[str]] = None,
        seniority_levels: Optional[List[str]] = None,
        keywords: Optional[str] = None,
        max_results: int = 100,
        **kwargs,
    ) -> List[ScraperResult]:
        """
        Search LinkedIn for people using Bright Data.

        Args:
            job_titles: Filter by job titles
            company_names: Filter by company names
            industries: Filter by industries
            locations: Filter by locations (e.g., ["San Francisco, CA", "New York, NY"])
            seniority_levels: Filter by seniority (e.g., ["Director", "VP", "C-Level"])
            keywords: General keyword search
            max_results: Maximum number of results

        Returns:
            List of ScraperResult containing LeadData
        """
        if not self.username or not self.password:
            raise ValueError("Bright Data credentials are required")

        results: List[ScraperResult] = []

        # Build search criteria
        search_criteria = {
            "max_results": max_results,
        }

        if job_titles:
            search_criteria["job_titles"] = job_titles
        if company_names:
            search_criteria["companies"] = company_names
        if industries:
            search_criteria["industries"] = industries
        if locations:
            search_criteria["locations"] = locations
        if seniority_levels:
            search_criteria["seniority"] = seniority_levels
        if keywords:
            search_criteria["keywords"] = keywords

        logger.info(f"Starting LinkedIn search via Bright Data: {search_criteria}")

        try:
            # Use Bright Data's LinkedIn Scraper dataset
            # Docs: https://docs.brightdata.com/scraping-automation/web-scraper/linkedin
            response = await self.post(
                f"{self.BRIGHT_DATA_API}/datasets/v3/trigger",
                auth=self.auth,
                json={
                    "dataset_id": "gd_linkedin_people_search",  # Bright Data dataset ID
                    "input": search_criteria,
                    "format": "json",
                },
            )

            data = response.json()

            # Handle async job (Bright Data may return job ID for large requests)
            if "snapshot_id" in data:
                # Poll for results
                results = await self._poll_for_results(data["snapshot_id"])
            else:
                # Synchronous results
                profiles = data.get("results", data.get("data", []))
                for profile in profiles:
                    try:
                        lead = self.parse_result(profile)
                        results.append(
                            ScraperResult(
                                success=True,
                                data=lead.to_dict(),
                                source_url=profile.get("linkedin_url", profile.get("url")),
                                raw_response=profile,
                            )
                        )
                    except Exception as e:
                        logger.warning(f"Error parsing LinkedIn profile: {e}")
                        self.stats.errors.append(str(e))

            self.stats.total_items_found = len([r for r in results if r.success])
            logger.info(f"LinkedIn search returned {self.stats.total_items_found} profiles")

        except Exception as e:
            logger.error(f"LinkedIn search failed: {e}")
            results.append(
                ScraperResult(
                    success=False,
                    error=str(e),
                )
            )

        return results

    async def _poll_for_results(
        self,
        snapshot_id: str,
        max_attempts: int = 30,
        poll_interval: int = 10,
    ) -> List[ScraperResult]:
        """Poll Bright Data for async job results."""
        import asyncio

        results: List[ScraperResult] = []

        for attempt in range(max_attempts):
            try:
                response = await self.get(
                    f"{self.BRIGHT_DATA_API}/datasets/v3/snapshot/{snapshot_id}",
                    auth=self.auth,
                    params={"format": "json"},
                )

                data = response.json()
                status = data.get("status", "")

                if status == "ready":
                    profiles = data.get("results", data.get("data", []))
                    for profile in profiles:
                        try:
                            lead = self.parse_result(profile)
                            results.append(
                                ScraperResult(
                                    success=True,
                                    data=lead.to_dict(),
                                    source_url=profile.get("linkedin_url"),
                                    raw_response=profile,
                                )
                            )
                        except Exception as e:
                            logger.warning(f"Error parsing profile: {e}")
                    return results

                elif status == "failed":
                    error = data.get("error", "Unknown error")
                    logger.error(f"Bright Data job failed: {error}")
                    return [ScraperResult(success=False, error=error)]

                # Still processing
                logger.debug(f"Bright Data job still processing (attempt {attempt + 1})")
                await asyncio.sleep(poll_interval)

            except Exception as e:
                logger.error(f"Error polling Bright Data: {e}")
                await asyncio.sleep(poll_interval)

        return [ScraperResult(success=False, error="Polling timeout")]

    async def scrape_profile(self, linkedin_url: str) -> Optional[ScraperResult]:
        """
        Scrape a specific LinkedIn profile.

        Args:
            linkedin_url: Full LinkedIn profile URL

        Returns:
            ScraperResult with profile data
        """
        if not self.username or not self.password:
            raise ValueError("Bright Data credentials are required")

        try:
            response = await self.post(
                f"{self.BRIGHT_DATA_API}/datasets/v3/trigger",
                auth=self.auth,
                json={
                    "dataset_id": "gd_linkedin_profile",
                    "input": [{"url": linkedin_url}],
                    "format": "json",
                },
            )

            data = response.json()

            if "snapshot_id" in data:
                results = await self._poll_for_results(data["snapshot_id"])
                return results[0] if results else None

            profiles = data.get("results", data.get("data", []))
            if profiles:
                lead = self.parse_result(profiles[0])
                return ScraperResult(
                    success=True,
                    data=lead.to_dict(),
                    source_url=linkedin_url,
                    raw_response=profiles[0],
                )

        except Exception as e:
            logger.error(f"Profile scrape failed: {e}")
            return ScraperResult(
                success=False,
                error=str(e),
            )

        return None

    async def scrape_company_employees(
        self,
        company_url: Optional[str] = None,
        company_name: Optional[str] = None,
        job_titles: Optional[List[str]] = None,
        max_results: int = 50,
    ) -> List[ScraperResult]:
        """
        Get employees from a specific company.

        Args:
            company_url: LinkedIn company page URL
            company_name: Company name (used if URL not provided)
            job_titles: Filter by job titles
            max_results: Maximum employees to return

        Returns:
            List of employee profiles
        """
        if not company_url and not company_name:
            raise ValueError("Either company_url or company_name is required")

        search_params = {
            "max_results": max_results,
        }

        if company_url:
            search_params["company_url"] = company_url
        else:
            search_params["companies"] = [company_name]

        if job_titles:
            search_params["job_titles"] = job_titles

        return await self.scrape(**search_params)

    def parse_result(self, raw_data: Dict[str, Any]) -> LeadData:
        """Parse LinkedIn profile data into LeadData."""
        # Handle various field name formats from Bright Data
        first_name = raw_data.get("first_name", raw_data.get("firstName", ""))
        last_name = raw_data.get("last_name", raw_data.get("lastName", ""))
        full_name = raw_data.get("full_name", raw_data.get("name", ""))

        if not full_name and (first_name or last_name):
            full_name = f"{first_name} {last_name}".strip()

        # Job info
        job_title = raw_data.get(
            "job_title",
            raw_data.get("title", raw_data.get("headline", ""))
        )

        # Current company
        company_name = raw_data.get(
            "company_name",
            raw_data.get("company", raw_data.get("current_company", ""))
        )

        # Handle nested company object
        if isinstance(company_name, dict):
            company_name = company_name.get("name", "")

        # Experience data might have more details
        experiences = raw_data.get("experiences", raw_data.get("experience", []))
        if experiences and isinstance(experiences, list) and len(experiences) > 0:
            current_exp = experiences[0]
            if not job_title:
                job_title = current_exp.get("title", "")
            if not company_name:
                company_name = current_exp.get("company", current_exp.get("company_name", ""))

        # LinkedIn URL
        linkedin_url = raw_data.get(
            "linkedin_url",
            raw_data.get("url", raw_data.get("profile_url", ""))
        )

        # Email (if available - often not from LinkedIn scraping)
        email = raw_data.get("email", raw_data.get("work_email"))

        # Determine seniority
        seniority = self._infer_seniority(job_title)

        return LeadData(
            email=self._clean_email(email),
            first_name=first_name,
            last_name=last_name,
            full_name=full_name,
            job_title=job_title,
            seniority_level=seniority,
            linkedin_url=linkedin_url,
            company_name=company_name,
            confidence_score=0.7 if email else 0.5,  # Lower confidence without email
            source_url=linkedin_url,
            raw_data=raw_data,
        )

    def _infer_seniority(self, job_title: str) -> Optional[str]:
        """Infer seniority level from job title."""
        if not job_title:
            return None

        title_lower = job_title.lower()

        if any(x in title_lower for x in ["ceo", "cto", "cfo", "coo", "cmo", "chief", "founder", "owner"]):
            return "C-Level"
        if any(x in title_lower for x in ["vp", "vice president", "evp", "svp"]):
            return "VP"
        if "director" in title_lower:
            return "Director"
        if "manager" in title_lower or "head of" in title_lower:
            return "Manager"
        if any(x in title_lower for x in ["senior", "sr.", "lead", "principal", "staff"]):
            return "Senior"
        if any(x in title_lower for x in ["junior", "jr.", "associate", "intern", "entry"]):
            return "Entry"

        return "Individual Contributor"


async def scrape_linkedin(
    job_titles: Optional[List[str]] = None,
    company_names: Optional[List[str]] = None,
    locations: Optional[List[str]] = None,
    max_results: int = 100,
) -> List[ScraperResult]:
    """
    Convenience function to search LinkedIn.

    Example:
        results = await scrape_linkedin(
            job_titles=["VP Marketing", "CMO"],
            company_names=["Google", "Meta"],
            max_results=50,
        )
    """
    async with LinkedInScraper() as scraper:
        return await scraper.scrape(
            job_titles=job_titles,
            company_names=company_names,
            locations=locations,
            max_results=max_results,
        )


async def scrape_linkedin_profile(linkedin_url: str) -> Optional[ScraperResult]:
    """
    Convenience function to scrape a specific LinkedIn profile.

    Example:
        result = await scrape_linkedin_profile(
            "https://www.linkedin.com/in/johndoe"
        )
    """
    async with LinkedInScraper() as scraper:
        return await scraper.scrape_profile(linkedin_url)
