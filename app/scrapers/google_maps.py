"""
Google Maps scraper for local business leads.
Scrapes by ZIP code for comprehensive coverage.
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional

import googlemaps

from app.config import settings

from .base import BaseScraper, CompanyData, ScraperResult

logger = logging.getLogger(__name__)


# US ZIP codes by state (sample - in production, load full list)
# You can get the full list from: https://simplemaps.com/data/us-zips
SAMPLE_ZIP_CODES = {
    "CA": ["90001", "90210", "94102", "92101", "95814"],
    "NY": ["10001", "10019", "11201", "14201", "12207"],
    "TX": ["75201", "77001", "78201", "79901", "73301"],
    "FL": ["33101", "32801", "33602", "34102", "32301"],
    "IL": ["60601", "60007", "61801", "62701", "60201"],
}


class GoogleMapsScraper(BaseScraper[CompanyData]):
    """
    Scraper for Google Maps/Places API.

    Strategy: Scrape by ZIP code to get comprehensive coverage
    (as mentioned in the video - 32,000+ US ZIP codes).
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        rate_limit: int = None,
    ):
        super().__init__(
            rate_limit=rate_limit or settings.google_maps_rate_limit,
            timeout=30,
            max_retries=3,
        )
        self.api_key = api_key or settings.google_maps_api_key
        self._gmaps: Optional[googlemaps.Client] = None

    @property
    def name(self) -> str:
        return "GoogleMaps"

    async def __aenter__(self):
        await super().__aenter__()
        if not self.api_key:
            raise ValueError("Google Maps API key is required")
        self._gmaps = googlemaps.Client(key=self.api_key)
        return self

    @property
    def gmaps(self) -> googlemaps.Client:
        if not self._gmaps:
            raise RuntimeError("Scraper must be used as async context manager")
        return self._gmaps

    async def scrape(
        self,
        query: str,
        zip_codes: Optional[List[str]] = None,
        states: Optional[List[str]] = None,
        max_results_per_zip: int = 20,
        include_details: bool = True,
    ) -> List[ScraperResult]:
        """
        Scrape Google Maps for businesses.

        Args:
            query: Business category to search (e.g., "dentist", "plumber")
            zip_codes: Specific ZIP codes to search. If None, uses states.
            states: States to search (uses sample ZIPs). If None, searches all.
            max_results_per_zip: Max results per ZIP code (1-60)
            include_details: Whether to fetch detailed info for each place

        Returns:
            List of ScraperResult objects containing CompanyData
        """
        results: List[ScraperResult] = []

        # Determine ZIP codes to search
        if zip_codes:
            zips_to_search = zip_codes
        elif states:
            zips_to_search = []
            for state in states:
                zips_to_search.extend(SAMPLE_ZIP_CODES.get(state.upper(), []))
        else:
            # Search all sample ZIP codes
            zips_to_search = [
                zip_code
                for state_zips in SAMPLE_ZIP_CODES.values()
                for zip_code in state_zips
            ]

        logger.info(
            f"Starting Google Maps scrape for '{query}' "
            f"across {len(zips_to_search)} ZIP codes"
        )

        for zip_code in zips_to_search:
            try:
                zip_results = await self._search_zip_code(
                    query=query,
                    zip_code=zip_code,
                    max_results=max_results_per_zip,
                    include_details=include_details,
                )
                results.extend(zip_results)
                logger.debug(
                    f"ZIP {zip_code}: Found {len(zip_results)} businesses"
                )
            except Exception as e:
                logger.error(f"Error searching ZIP {zip_code}: {e}")
                results.append(
                    ScraperResult(
                        success=False,
                        error=f"ZIP {zip_code}: {str(e)}",
                    )
                )

        self.stats.total_items_found = len([r for r in results if r.success])
        return results

    async def _search_zip_code(
        self,
        query: str,
        zip_code: str,
        max_results: int = 20,
        include_details: bool = True,
    ) -> List[ScraperResult]:
        """Search for businesses in a specific ZIP code."""
        results: List[ScraperResult] = []

        # Rate limit
        await self.rate_limiter.acquire()
        self.stats.total_requests += 1

        try:
            # Text search with ZIP code
            search_query = f"{query} {zip_code}"

            # Run in thread pool since googlemaps library is sync
            loop = asyncio.get_event_loop()
            places_result = await loop.run_in_executor(
                None,
                lambda: self.gmaps.places(
                    query=search_query,
                    type=None,  # Let Google determine the type
                )
            )

            self.stats.successful_requests += 1
            places = places_result.get("results", [])[:max_results]

            for place in places:
                try:
                    # Optionally get detailed info
                    if include_details and "place_id" in place:
                        await self.rate_limiter.acquire()
                        self.stats.total_requests += 1

                        details = await loop.run_in_executor(
                            None,
                            lambda pid=place["place_id"]: self.gmaps.place(
                                place_id=pid,
                                fields=[
                                    "name", "formatted_address", "formatted_phone_number",
                                    "website", "rating", "user_ratings_total",
                                    "business_status", "types", "opening_hours",
                                ]
                            )
                        )
                        self.stats.successful_requests += 1
                        place.update(details.get("result", {}))

                    company = self.parse_result(place)
                    company.zip_code = zip_code

                    results.append(
                        ScraperResult(
                            success=True,
                            data=company.to_dict(),
                            source_url=f"https://maps.google.com/?cid={place.get('place_id', '')}",
                            raw_response=place,
                        )
                    )
                except Exception as e:
                    logger.warning(f"Error parsing place: {e}")
                    self.stats.errors.append(str(e))

        except Exception as e:
            self.stats.failed_requests += 1
            self.stats.errors.append(str(e))
            raise

        return results

    def parse_result(self, raw_data: Dict[str, Any]) -> CompanyData:
        """Parse Google Maps place data into CompanyData."""
        # Parse address components
        address = raw_data.get("formatted_address", "")
        city, state, country = self._parse_address(address)

        # Extract website domain
        website = raw_data.get("website")
        domain = self._extract_domain(website)

        # Determine industry from types
        types = raw_data.get("types", [])
        industry = self._types_to_industry(types)

        return CompanyData(
            name=raw_data.get("name", ""),
            website=website,
            domain=domain,
            industry=industry,
            address=address,
            city=city,
            state=state,
            country=country or "USA",
            phone=self._clean_phone(raw_data.get("formatted_phone_number")),
            google_place_id=raw_data.get("place_id"),
            google_rating=raw_data.get("rating"),
            google_reviews_count=raw_data.get("user_ratings_total"),
            raw_data=raw_data,
        )

    def _parse_address(self, address: str) -> tuple:
        """Parse formatted address into city, state, country."""
        if not address:
            return None, None, None

        parts = [p.strip() for p in address.split(",")]

        city = None
        state = None
        country = None

        if len(parts) >= 3:
            city = parts[-3] if len(parts) > 3 else parts[0]
            # State and ZIP are usually together like "CA 90210"
            state_zip = parts[-2].strip()
            if state_zip:
                state_parts = state_zip.split()
                if state_parts:
                    state = state_parts[0]
            country = parts[-1]

        return city, state, country

    def _types_to_industry(self, types: List[str]) -> Optional[str]:
        """Convert Google Maps types to industry category."""
        type_to_industry = {
            "dentist": "Healthcare - Dental",
            "doctor": "Healthcare - Medical",
            "hospital": "Healthcare",
            "pharmacy": "Healthcare - Pharmacy",
            "lawyer": "Legal Services",
            "accounting": "Financial Services",
            "bank": "Financial Services - Banking",
            "insurance_agency": "Financial Services - Insurance",
            "real_estate_agency": "Real Estate",
            "restaurant": "Food & Beverage",
            "cafe": "Food & Beverage",
            "bar": "Food & Beverage",
            "gym": "Health & Fitness",
            "beauty_salon": "Beauty & Personal Care",
            "spa": "Beauty & Personal Care",
            "car_dealer": "Automotive",
            "car_repair": "Automotive",
            "plumber": "Home Services",
            "electrician": "Home Services",
            "roofing_contractor": "Home Services",
            "general_contractor": "Construction",
            "moving_company": "Moving & Storage",
            "storage": "Moving & Storage",
            "veterinary_care": "Pet Services",
            "pet_store": "Pet Services",
            "school": "Education",
            "university": "Education",
            "church": "Religious Organization",
        }

        for t in types:
            if t in type_to_industry:
                return type_to_industry[t]

        return None


async def scrape_google_maps(
    query: str,
    zip_codes: Optional[List[str]] = None,
    states: Optional[List[str]] = None,
    max_results_per_zip: int = 20,
    include_details: bool = True,
) -> List[ScraperResult]:
    """
    Convenience function to scrape Google Maps.

    Example:
        results = await scrape_google_maps(
            query="dentist",
            states=["CA", "NY"],
            max_results_per_zip=10,
        )
    """
    async with GoogleMapsScraper() as scraper:
        return await scraper.scrape(
            query=query,
            zip_codes=zip_codes,
            states=states,
            max_results_per_zip=max_results_per_zip,
            include_details=include_details,
        )
