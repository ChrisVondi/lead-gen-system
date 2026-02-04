"""
AI Ark integration for B2B lead data.
Primary data source that replaces Apollo (as mentioned in the video).
"""

import logging
from typing import Any, Dict, List, Optional

from app.config import settings

from .base import BaseScraper, LeadData, ScraperResult

logger = logging.getLogger(__name__)


class AIArkScraper(BaseScraper[LeadData]):
    """
    AI Ark API integration for B2B contact data.

    AI Ark is the primary lead data source in the waterfall:
    1. AI Ark (primary)
    2. LinkedIn/Bright Data (fallback)
    3. AI Lead Finder (last resort)

    Note: This implementation uses a generic structure.
    You'll need to update the endpoints and response parsing
    based on AI Ark's actual API documentation.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        rate_limit: int = None,
    ):
        super().__init__(
            rate_limit=rate_limit or settings.ai_ark_rate_limit,
            timeout=60,
            max_retries=3,
        )
        self.api_key = api_key or settings.ai_ark_api_key
        self.base_url = (base_url or settings.ai_ark_base_url).rstrip("/")

    @property
    def name(self) -> str:
        return "AIArk"

    @property
    def headers(self) -> Dict[str, str]:
        """Default headers for API requests."""
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    async def scrape(
        self,
        company_domains: Optional[List[str]] = None,
        company_names: Optional[List[str]] = None,
        job_titles: Optional[List[str]] = None,
        industries: Optional[List[str]] = None,
        employee_range: Optional[str] = None,
        locations: Optional[List[str]] = None,
        leads_per_company: int = 3,
        **kwargs,
    ) -> List[ScraperResult]:
        """
        Search AI Ark for B2B leads.

        Args:
            company_domains: List of company domains to search
            company_names: List of company names to search
            job_titles: Filter by job titles (e.g., ["CEO", "CTO", "VP Marketing"])
            industries: Filter by industries
            employee_range: Company size filter (e.g., "10-50", "51-200")
            locations: Geographic filters
            leads_per_company: Number of leads to return per company (default: 3)

        Returns:
            List of ScraperResult containing LeadData
        """
        if not self.api_key:
            raise ValueError("AI Ark API key is required")

        results: List[ScraperResult] = []

        # Build search payload
        search_params = {
            "leads_per_company": leads_per_company,
        }

        if company_domains:
            search_params["domains"] = company_domains
        if company_names:
            search_params["company_names"] = company_names
        if job_titles:
            search_params["job_titles"] = job_titles
        if industries:
            search_params["industries"] = industries
        if employee_range:
            search_params["employee_range"] = employee_range
        if locations:
            search_params["locations"] = locations

        logger.info(f"Starting AI Ark search with params: {search_params}")

        try:
            # Search endpoint - adjust based on actual AI Ark API
            response = await self.post(
                f"{self.base_url}/search/people",
                headers=self.headers,
                json=search_params,
            )

            data = response.json()
            leads = data.get("results", data.get("people", data.get("data", [])))

            for lead_data in leads:
                try:
                    lead = self.parse_result(lead_data)
                    results.append(
                        ScraperResult(
                            success=True,
                            data=lead.to_dict(),
                            source_url=lead_data.get("linkedin_url"),
                            raw_response=lead_data,
                        )
                    )
                except Exception as e:
                    logger.warning(f"Error parsing AI Ark lead: {e}")
                    self.stats.errors.append(str(e))

            self.stats.total_items_found = len(results)
            logger.info(f"AI Ark search returned {len(results)} leads")

        except Exception as e:
            logger.error(f"AI Ark search failed: {e}")
            results.append(
                ScraperResult(
                    success=False,
                    error=str(e),
                )
            )

        return results

    async def enrich_company(
        self,
        domain: Optional[str] = None,
        company_name: Optional[str] = None,
        leads_count: int = 3,
    ) -> List[ScraperResult]:
        """
        Get leads for a specific company.

        Args:
            domain: Company domain (e.g., "acme.com")
            company_name: Company name (used if domain not available)
            leads_count: Number of leads to return

        Returns:
            List of leads for the company
        """
        if not domain and not company_name:
            raise ValueError("Either domain or company_name is required")

        params = {"leads_per_company": leads_count}
        if domain:
            params["domains"] = [domain]
        else:
            params["company_names"] = [company_name]

        return await self.scrape(**params)

    async def lookup_person(
        self,
        linkedin_url: Optional[str] = None,
        email: Optional[str] = None,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        company_domain: Optional[str] = None,
    ) -> Optional[ScraperResult]:
        """
        Look up a specific person.

        Args:
            linkedin_url: Person's LinkedIn URL
            email: Person's email address
            first_name: First name (requires last_name and company)
            last_name: Last name (requires first_name and company)
            company_domain: Company domain (used with name lookup)

        Returns:
            ScraperResult with person data, or None if not found
        """
        if not self.api_key:
            raise ValueError("AI Ark API key is required")

        lookup_params = {}

        if linkedin_url:
            lookup_params["linkedin_url"] = linkedin_url
        elif email:
            lookup_params["email"] = email
        elif first_name and last_name and company_domain:
            lookup_params["first_name"] = first_name
            lookup_params["last_name"] = last_name
            lookup_params["company_domain"] = company_domain
        else:
            raise ValueError(
                "Must provide linkedin_url, email, or (first_name + last_name + company_domain)"
            )

        try:
            response = await self.post(
                f"{self.base_url}/lookup/person",
                headers=self.headers,
                json=lookup_params,
            )

            data = response.json()
            person = data.get("person", data.get("result", data))

            if person:
                lead = self.parse_result(person)
                return ScraperResult(
                    success=True,
                    data=lead.to_dict(),
                    source_url=person.get("linkedin_url"),
                    raw_response=person,
                )

        except Exception as e:
            logger.error(f"AI Ark person lookup failed: {e}")
            return ScraperResult(
                success=False,
                error=str(e),
            )

        return None

    async def verify_email(self, email: str) -> Dict[str, Any]:
        """
        Verify an email address.

        Returns:
            Dict with verification status and details
        """
        if not self.api_key:
            raise ValueError("AI Ark API key is required")

        try:
            response = await self.post(
                f"{self.base_url}/verify/email",
                headers=self.headers,
                json={"email": email},
            )

            return response.json()

        except Exception as e:
            logger.error(f"Email verification failed: {e}")
            return {"valid": False, "error": str(e)}

    def parse_result(self, raw_data: Dict[str, Any]) -> LeadData:
        """Parse AI Ark response into LeadData."""
        # Handle nested company data
        company = raw_data.get("company", {})
        if isinstance(company, str):
            company_name = company
            company_domain = None
        else:
            company_name = company.get("name", raw_data.get("company_name"))
            company_domain = company.get("domain", raw_data.get("company_domain"))

        # Determine seniority level from job title
        job_title = raw_data.get("job_title", raw_data.get("title", ""))
        seniority = self._infer_seniority(job_title)

        # Extract department from job title
        department = self._infer_department(job_title)

        return LeadData(
            email=self._clean_email(
                raw_data.get("email", raw_data.get("work_email"))
            ),
            first_name=raw_data.get("first_name"),
            last_name=raw_data.get("last_name"),
            full_name=raw_data.get("full_name", raw_data.get("name")),
            job_title=job_title,
            department=department,
            seniority_level=seniority,
            phone=self._clean_phone(
                raw_data.get("phone", raw_data.get("direct_phone"))
            ),
            linkedin_url=raw_data.get("linkedin_url", raw_data.get("linkedin")),
            company_name=company_name,
            company_domain=company_domain,
            confidence_score=raw_data.get("confidence", raw_data.get("score", 0.8)),
            raw_data=raw_data,
        )

    def _infer_seniority(self, job_title: str) -> Optional[str]:
        """Infer seniority level from job title."""
        if not job_title:
            return None

        title_lower = job_title.lower()

        # C-Level
        if any(x in title_lower for x in ["ceo", "cto", "cfo", "coo", "cmo", "chief"]):
            return "C-Level"

        # VP
        if any(x in title_lower for x in ["vp", "vice president", "evp", "svp"]):
            return "VP"

        # Director
        if "director" in title_lower:
            return "Director"

        # Manager
        if "manager" in title_lower or "head of" in title_lower:
            return "Manager"

        # Senior IC
        if any(x in title_lower for x in ["senior", "sr.", "lead", "principal"]):
            return "Senior"

        # Junior/Entry
        if any(x in title_lower for x in ["junior", "jr.", "associate", "intern"]):
            return "Entry"

        return "Individual Contributor"

    def _infer_department(self, job_title: str) -> Optional[str]:
        """Infer department from job title."""
        if not job_title:
            return None

        title_lower = job_title.lower()

        departments = {
            "Engineering": ["engineer", "developer", "software", "devops", "sre", "architect"],
            "Marketing": ["marketing", "brand", "content", "seo", "growth"],
            "Sales": ["sales", "account executive", "business development", "ae ", "sdr", "bdr"],
            "Product": ["product manager", "product owner", "pm"],
            "Design": ["design", "ux", "ui", "creative"],
            "Finance": ["finance", "accounting", "controller", "cfo"],
            "HR": ["hr", "human resources", "people", "talent", "recruiting"],
            "Operations": ["operations", "ops", "supply chain", "logistics"],
            "Legal": ["legal", "counsel", "attorney", "lawyer"],
            "IT": ["it ", "information technology", "system admin", "helpdesk"],
            "Customer Success": ["customer success", "cs ", "client success"],
            "Support": ["support", "customer service", "help desk"],
        }

        for dept, keywords in departments.items():
            if any(kw in title_lower for kw in keywords):
                return dept

        return None


async def search_ai_ark(
    company_domains: Optional[List[str]] = None,
    company_names: Optional[List[str]] = None,
    job_titles: Optional[List[str]] = None,
    industries: Optional[List[str]] = None,
    leads_per_company: int = 3,
) -> List[ScraperResult]:
    """
    Convenience function to search AI Ark.

    Example:
        results = await search_ai_ark(
            company_domains=["acme.com", "techcorp.io"],
            job_titles=["CEO", "CTO", "VP Engineering"],
            leads_per_company=3,
        )
    """
    async with AIArkScraper() as scraper:
        return await scraper.scrape(
            company_domains=company_domains,
            company_names=company_names,
            job_titles=job_titles,
            industries=industries,
            leads_per_company=leads_per_company,
        )


async def enrich_company_with_ai_ark(
    domain: Optional[str] = None,
    company_name: Optional[str] = None,
    leads_count: int = 3,
) -> List[ScraperResult]:
    """
    Convenience function to get leads for a company via AI Ark.

    Example:
        leads = await enrich_company_with_ai_ark(
            domain="acme.com",
            leads_count=5,
        )
    """
    async with AIArkScraper() as scraper:
        return await scraper.enrich_company(
            domain=domain,
            company_name=company_name,
            leads_count=leads_count,
        )
