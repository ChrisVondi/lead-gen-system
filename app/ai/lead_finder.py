"""
AI Lead Finder using Claude API.
The final step in the waterfall when primary sources don't have data.
"""

import json
import logging
import time
from typing import Any, Dict, List, Optional

import anthropic

from app.config import settings

from .prompts import (
    ALTERNATE_CONTACT_PROMPT,
    COMPANY_RESEARCH_PROMPT,
    CONTACT_FINDING_PROMPT,
    EMAIL_VALIDATION_PROMPT,
    FULL_ENRICHMENT_PROMPT,
    ICP_MATCHING_PROMPT,
)

logger = logging.getLogger(__name__)


class AILeadFinder:
    """
    AI-powered lead finder using Claude API.

    This is the last resort in the waterfall strategy:
    1. AI Ark (primary)
    2. LinkedIn/Bright Data (fallback)
    3. AI Lead Finder (this) <-- when all else fails

    Uses Claude to:
    - Research companies
    - Find contacts when databases don't have them
    - Validate and enrich existing lead data
    - Find alternate contact methods
    - Score ICP fit
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
    ):
        self.api_key = api_key or settings.anthropic_api_key
        self.model = model or settings.claude_model
        self._client: Optional[anthropic.Anthropic] = None

        # Cost tracking (approximate)
        self.total_input_tokens = 0
        self.total_output_tokens = 0

    @property
    def client(self) -> anthropic.Anthropic:
        """Get or create Anthropic client."""
        if not self._client:
            if not self.api_key:
                raise ValueError("Anthropic API key is required")
            self._client = anthropic.Anthropic(api_key=self.api_key)
        return self._client

    async def _call_claude(
        self,
        prompt: str,
        system: str = "You are a helpful B2B research assistant. Always respond with valid JSON.",
        max_tokens: int = 2000,
    ) -> Dict[str, Any]:
        """
        Call Claude API and parse JSON response.

        Returns:
            Parsed JSON response, tokens used, and duration
        """
        start_time = time.time()

        try:
            # Note: Using sync client for simplicity
            # For production, consider using async httpx calls
            message = self.client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                system=system,
                messages=[{"role": "user", "content": prompt}],
            )

            # Track tokens
            input_tokens = message.usage.input_tokens
            output_tokens = message.usage.output_tokens
            self.total_input_tokens += input_tokens
            self.total_output_tokens += output_tokens

            # Parse response
            content = message.content[0].text
            duration_ms = int((time.time() - start_time) * 1000)

            # Try to extract JSON from response
            try:
                # Handle potential markdown code blocks
                if "```json" in content:
                    content = content.split("```json")[1].split("```")[0]
                elif "```" in content:
                    content = content.split("```")[1].split("```")[0]

                result = json.loads(content.strip())
            except json.JSONDecodeError:
                logger.warning(f"Failed to parse JSON response: {content[:200]}")
                result = {"raw_response": content, "parse_error": True}

            return {
                "data": result,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "duration_ms": duration_ms,
                "model": self.model,
            }

        except Exception as e:
            logger.error(f"Claude API error: {e}")
            raise

    async def research_company(
        self,
        company_name: str,
        domain: Optional[str] = None,
        industry: Optional[str] = None,
        location: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Research a company using AI.

        Args:
            company_name: Company name to research
            domain: Company website/domain (optional)
            industry: Known industry (optional)
            location: Known location (optional)

        Returns:
            Company information and enrichment metadata
        """
        prompt = COMPANY_RESEARCH_PROMPT.format(
            company_name=company_name,
            domain=domain or "Unknown",
            industry=industry or "Unknown",
            location=location or "Unknown",
        )

        result = await self._call_claude(prompt)

        return {
            "company_data": result["data"],
            "tokens_used": result["input_tokens"] + result["output_tokens"],
            "cost_usd": self._estimate_cost(result["input_tokens"], result["output_tokens"]),
            "duration_ms": result["duration_ms"],
        }

    async def find_contacts(
        self,
        company_name: str,
        domain: Optional[str] = None,
        industry: Optional[str] = None,
        job_titles: Optional[List[str]] = None,
        departments: Optional[List[str]] = None,
        seniority_levels: Optional[List[str]] = None,
        leads_count: int = 3,
    ) -> Dict[str, Any]:
        """
        Find contacts at a company using AI.

        This is the last resort when AI Ark and LinkedIn don't have data.

        Args:
            company_name: Target company
            domain: Company domain
            industry: Company industry
            job_titles: Target job titles
            departments: Target departments
            seniority_levels: Target seniority levels
            leads_count: Number of contacts to find

        Returns:
            Found contacts and metadata
        """
        prompt = CONTACT_FINDING_PROMPT.format(
            company_name=company_name,
            domain=domain or "Unknown",
            industry=industry or "Unknown",
            job_titles=", ".join(job_titles) if job_titles else "Decision makers",
            departments=", ".join(departments) if departments else "Any",
            seniority_levels=", ".join(seniority_levels) if seniority_levels else "Manager and above",
            leads_count=leads_count,
        )

        result = await self._call_claude(prompt, max_tokens=3000)

        return {
            "contacts": result["data"].get("contacts", []),
            "email_patterns": result["data"].get("email_patterns_found", []),
            "company_email_domain": result["data"].get("company_email_domain"),
            "tokens_used": result["input_tokens"] + result["output_tokens"],
            "cost_usd": self._estimate_cost(result["input_tokens"], result["output_tokens"]),
            "duration_ms": result["duration_ms"],
        }

    async def validate_email(
        self,
        email: str,
        domain: str,
        full_name: Optional[str] = None,
        job_title: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Validate an email address using AI analysis.

        Args:
            email: Email to validate
            domain: Company domain
            full_name: Person's full name
            job_title: Person's job title

        Returns:
            Validation results and alternative emails
        """
        prompt = EMAIL_VALIDATION_PROMPT.format(
            email=email,
            domain=domain,
            full_name=full_name or "Unknown",
            job_title=job_title or "Unknown",
        )

        result = await self._call_claude(prompt)

        return {
            "validation": result["data"],
            "tokens_used": result["input_tokens"] + result["output_tokens"],
            "cost_usd": self._estimate_cost(result["input_tokens"], result["output_tokens"]),
            "duration_ms": result["duration_ms"],
        }

    async def find_alternate_contacts(
        self,
        full_name: str,
        company_name: str,
        job_title: Optional[str] = None,
        known_email: Optional[str] = None,
        linkedin_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Find alternate ways to contact a person.

        As mentioned in the video: "if it can't find a valid email for Joe,
        it'll go, okay, does Joe have any other valid emails?"

        Args:
            full_name: Person's name
            company_name: Current company
            job_title: Job title
            known_email: Email we already have
            linkedin_url: LinkedIn profile

        Returns:
            Alternate contact methods
        """
        prompt = ALTERNATE_CONTACT_PROMPT.format(
            full_name=full_name,
            company_name=company_name,
            job_title=job_title or "Unknown",
            known_email=known_email or "None",
            linkedin_url=linkedin_url or "None",
        )

        result = await self._call_claude(prompt)

        return {
            "alternate_emails": result["data"].get("alternate_emails", []),
            "alternate_companies": result["data"].get("alternate_companies", []),
            "social_profiles": result["data"].get("social_profiles", []),
            "recommendation": result["data"].get("outreach_recommendation"),
            "tokens_used": result["input_tokens"] + result["output_tokens"],
            "cost_usd": self._estimate_cost(result["input_tokens"], result["output_tokens"]),
            "duration_ms": result["duration_ms"],
        }

    async def score_icp_match(
        self,
        lead_data: Dict[str, Any],
        icp_criteria: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Score how well a lead matches the Ideal Customer Profile.

        Args:
            lead_data: Lead information
            icp_criteria: ICP criteria to match against

        Returns:
            ICP score and breakdown
        """
        # Format ICP criteria as readable text
        icp_text = "\n".join(f"- {k}: {v}" for k, v in icp_criteria.items())

        prompt = ICP_MATCHING_PROMPT.format(
            full_name=lead_data.get("full_name", "Unknown"),
            job_title=lead_data.get("job_title", "Unknown"),
            company_name=lead_data.get("company_name", "Unknown"),
            industry=lead_data.get("industry", "Unknown"),
            employee_range=lead_data.get("employee_range", "Unknown"),
            location=lead_data.get("location", "Unknown"),
            icp_criteria=icp_text,
        )

        result = await self._call_claude(prompt)

        return {
            "icp_score": result["data"].get("icp_score", 0),
            "breakdown": result["data"].get("scoring_breakdown", {}),
            "recommendation": result["data"].get("recommendation"),
            "strengths": result["data"].get("strengths", []),
            "weaknesses": result["data"].get("weaknesses", []),
            "personalization_angles": result["data"].get("personalization_angles", []),
            "tokens_used": result["input_tokens"] + result["output_tokens"],
            "cost_usd": self._estimate_cost(result["input_tokens"], result["output_tokens"]),
            "duration_ms": result["duration_ms"],
        }

    async def enrich_lead(
        self,
        current_data: Dict[str, Any],
        company_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Fully enrich a lead with AI.

        Args:
            current_data: Current lead data
            company_context: Additional company context

        Returns:
            Enriched lead data
        """
        prompt = FULL_ENRICHMENT_PROMPT.format(
            current_data=json.dumps(current_data, indent=2),
            company_context=json.dumps(company_context or {}, indent=2),
        )

        result = await self._call_claude(prompt, max_tokens=3000)

        return {
            "enriched_data": result["data"].get("enriched_data", {}),
            "alternate_emails": result["data"].get("alternate_emails", []),
            "alternate_companies": result["data"].get("alternate_companies", []),
            "validation_notes": result["data"].get("validation_notes", {}),
            "confidence_score": result["data"].get("confidence_score", 0),
            "summary": result["data"].get("enrichment_summary", ""),
            "tokens_used": result["input_tokens"] + result["output_tokens"],
            "cost_usd": self._estimate_cost(result["input_tokens"], result["output_tokens"]),
            "duration_ms": result["duration_ms"],
        }

    def _estimate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """
        Estimate API cost based on token usage.

        Pricing (as of 2024):
        - Claude 3 Sonnet: $3/1M input, $15/1M output
        - Claude 3 Haiku: $0.25/1M input, $1.25/1M output
        """
        if "haiku" in self.model.lower():
            input_cost = (input_tokens / 1_000_000) * 0.25
            output_cost = (output_tokens / 1_000_000) * 1.25
        else:  # Sonnet or other
            input_cost = (input_tokens / 1_000_000) * 3
            output_cost = (output_tokens / 1_000_000) * 15

        return round(input_cost + output_cost, 6)

    def get_total_cost(self) -> float:
        """Get total estimated cost for this session."""
        return self._estimate_cost(self.total_input_tokens, self.total_output_tokens)


# ===========================================
# Waterfall Enrichment Pipeline
# ===========================================


class EnrichmentPipeline:
    """
    Complete enrichment pipeline implementing the waterfall strategy:
    1. AI Ark (primary)
    2. LinkedIn/Bright Data (fallback)
    3. AI Lead Finder (last resort)
    """

    def __init__(self):
        self.ai_finder = AILeadFinder()
        self.stats = {
            "total_enriched": 0,
            "ai_ark_hits": 0,
            "linkedin_hits": 0,
            "ai_finder_hits": 0,
            "failed": 0,
            "total_cost": 0.0,
        }

    async def enrich_lead(
        self,
        lead_data: Dict[str, Any],
        use_ai_ark: bool = True,
        use_linkedin: bool = True,
        use_ai_finder: bool = True,
    ) -> Dict[str, Any]:
        """
        Enrich a lead using the waterfall strategy.

        Args:
            lead_data: Initial lead data
            use_ai_ark: Whether to try AI Ark first
            use_linkedin: Whether to try LinkedIn second
            use_ai_finder: Whether to use AI as last resort

        Returns:
            Enriched lead data with source information
        """
        enriched = lead_data.copy()
        source = None
        cost = 0.0

        company_name = lead_data.get("company_name")
        company_domain = lead_data.get("company_domain")

        # Step 1: Try AI Ark
        if use_ai_ark and (company_name or company_domain):
            try:
                from app.scrapers.ai_ark import AIArkScraper

                async with AIArkScraper() as scraper:
                    results = await scraper.enrich_company(
                        domain=company_domain,
                        company_name=company_name,
                        leads_count=1,
                    )

                    if results and results[0].success:
                        enriched.update(results[0].data)
                        source = "ai_ark"
                        self.stats["ai_ark_hits"] += 1
                        logger.info(f"AI Ark found data for {company_name}")

            except Exception as e:
                logger.warning(f"AI Ark enrichment failed: {e}")

        # Step 2: Try LinkedIn/Bright Data
        if not source and use_linkedin:
            try:
                from app.scrapers.linkedin import LinkedInScraper

                linkedin_url = lead_data.get("linkedin_url")
                if linkedin_url:
                    async with LinkedInScraper() as scraper:
                        result = await scraper.scrape_profile(linkedin_url)
                        if result and result.success:
                            enriched.update(result.data)
                            source = "linkedin"
                            self.stats["linkedin_hits"] += 1
                            logger.info(f"LinkedIn found data for {linkedin_url}")

            except Exception as e:
                logger.warning(f"LinkedIn enrichment failed: {e}")

        # Step 3: Use AI Lead Finder as last resort
        if not source and use_ai_finder:
            try:
                result = await self.ai_finder.enrich_lead(
                    current_data=lead_data,
                    company_context={"company_name": company_name, "domain": company_domain},
                )

                if result.get("enriched_data"):
                    enriched.update(result["enriched_data"])
                    enriched["alternate_emails"] = result.get("alternate_emails", [])
                    enriched["alternate_companies"] = result.get("alternate_companies", [])
                    enriched["ai_reasoning"] = result.get("summary")
                    source = "ai_enriched"
                    cost = result.get("cost_usd", 0)
                    self.stats["ai_finder_hits"] += 1
                    self.stats["total_cost"] += cost
                    logger.info(f"AI Finder enriched lead (cost: ${cost:.4f})")

            except Exception as e:
                logger.error(f"AI Finder enrichment failed: {e}")

        # Track results
        if source:
            self.stats["total_enriched"] += 1
            enriched["enrichment_source"] = source
            enriched["enrichment_cost"] = cost
        else:
            self.stats["failed"] += 1
            enriched["enrichment_source"] = None

        return enriched

    async def enrich_leads_batch(
        self,
        leads: List[Dict[str, Any]],
        concurrency: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Enrich multiple leads concurrently.

        Args:
            leads: List of leads to enrich
            concurrency: Max concurrent enrichments

        Returns:
            List of enriched leads
        """
        import asyncio

        semaphore = asyncio.Semaphore(concurrency)

        async def enrich_with_semaphore(lead: Dict[str, Any]) -> Dict[str, Any]:
            async with semaphore:
                return await self.enrich_lead(lead)

        tasks = [enrich_with_semaphore(lead) for lead in leads]
        return await asyncio.gather(*tasks)


# ===========================================
# Convenience Functions
# ===========================================


async def find_contacts_with_ai(
    company_name: str,
    domain: Optional[str] = None,
    job_titles: Optional[List[str]] = None,
    leads_count: int = 3,
) -> Dict[str, Any]:
    """
    Convenience function to find contacts using AI.

    Example:
        contacts = await find_contacts_with_ai(
            company_name="Acme Corp",
            domain="acme.com",
            job_titles=["CEO", "CTO"],
            leads_count=3,
        )
    """
    finder = AILeadFinder()
    return await finder.find_contacts(
        company_name=company_name,
        domain=domain,
        job_titles=job_titles,
        leads_count=leads_count,
    )


async def enrich_lead_with_ai(lead_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convenience function to enrich a lead with AI.

    Example:
        enriched = await enrich_lead_with_ai({
            "first_name": "John",
            "company_name": "Acme Corp",
        })
    """
    finder = AILeadFinder()
    return await finder.enrich_lead(lead_data)
