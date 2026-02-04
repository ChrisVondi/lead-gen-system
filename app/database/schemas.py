"""
Pydantic schemas for request/response validation.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, HttpUrl


# ===========================================
# Enums (matching SQLAlchemy enums)
# ===========================================


class LeadSource(str):
    GOOGLE_MAPS = "google_maps"
    LINKEDIN = "linkedin"
    WEBSITE = "website"
    AI_ARK = "ai_ark"
    AI_ENRICHED = "ai_enriched"
    MANUAL = "manual"
    IMPORT = "import"


class EnrichmentStatus(str):
    RAW = "raw"
    PENDING = "pending"
    ENRICHED = "enriched"
    VALIDATED = "validated"
    FAILED = "failed"


class JobStatus(str):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


# ===========================================
# Company Schemas
# ===========================================


class CompanyBase(BaseModel):
    """Base company fields."""

    name: str = Field(..., min_length=1, max_length=500)
    website: Optional[str] = None
    domain: Optional[str] = None
    industry: Optional[str] = None
    employee_count: Optional[int] = None
    employee_range: Optional[str] = None
    revenue_range: Optional[str] = None
    founded_year: Optional[int] = None

    # Location
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country: str = "USA"
    zip_code: Optional[str] = None

    # External IDs
    google_place_id: Optional[str] = None
    linkedin_company_url: Optional[str] = None

    # Google Maps
    google_rating: Optional[float] = None
    google_reviews_count: Optional[int] = None
    google_phone: Optional[str] = None


class CompanyCreate(CompanyBase):
    """Schema for creating a company."""

    source: str = LeadSource.MANUAL
    raw_data: Optional[Dict[str, Any]] = None


class CompanyUpdate(BaseModel):
    """Schema for updating a company."""

    name: Optional[str] = None
    website: Optional[str] = None
    domain: Optional[str] = None
    industry: Optional[str] = None
    employee_count: Optional[int] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None


class CompanyResponse(CompanyBase):
    """Schema for company responses."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    source: str
    created_at: datetime
    updated_at: datetime
    leads_count: Optional[int] = None


# ===========================================
# Lead Schemas
# ===========================================


class LeadBase(BaseModel):
    """Base lead fields."""

    email: Optional[EmailStr] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    full_name: Optional[str] = None
    job_title: Optional[str] = None
    department: Optional[str] = None
    seniority_level: Optional[str] = None

    phone: Optional[str] = None
    linkedin_url: Optional[str] = None
    twitter_url: Optional[str] = None

    company_name: Optional[str] = None


class LeadCreate(LeadBase):
    """Schema for creating a lead."""

    company_id: Optional[UUID] = None
    source: str = LeadSource.MANUAL
    confidence_score: float = 0.0
    raw_data: Optional[Dict[str, Any]] = None
    tags: Optional[List[str]] = None


class LeadUpdate(BaseModel):
    """Schema for updating a lead."""

    email: Optional[EmailStr] = None
    email_verified: Optional[bool] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    job_title: Optional[str] = None
    phone: Optional[str] = None
    linkedin_url: Optional[str] = None
    confidence_score: Optional[float] = None
    enrichment_status: Optional[str] = None
    tags: Optional[List[str]] = None
    notes: Optional[str] = None


class LeadResponse(LeadBase):
    """Schema for lead responses."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email_verified: bool
    phone_verified: bool
    company_id: Optional[UUID] = None
    confidence_score: float
    icp_score: Optional[float] = None
    enrichment_status: str
    source: str
    source_url: Optional[str] = None
    ai_reasoning: Optional[str] = None
    alternate_emails: Optional[List[str]] = None
    tags: Optional[List[str]] = None
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    last_enriched_at: Optional[datetime] = None


class LeadBulkCreate(BaseModel):
    """Schema for bulk lead creation."""

    leads: List[LeadCreate] = Field(..., min_length=1, max_length=10000)


# ===========================================
# Scrape Job Schemas
# ===========================================


class GoogleMapsScrapeParams(BaseModel):
    """Parameters for Google Maps scraping."""

    query: str = Field(..., description="Business category to search, e.g., 'dentist'")
    zip_codes: Optional[List[str]] = Field(
        None, description="List of ZIP codes to search. If empty, uses all US ZIP codes."
    )
    states: Optional[List[str]] = Field(
        None, description="Filter by states, e.g., ['CA', 'NY']"
    )
    max_results_per_zip: int = Field(default=20, ge=1, le=60)
    include_details: bool = Field(
        default=True, description="Fetch detailed info for each place"
    )


class LinkedInScrapeParams(BaseModel):
    """Parameters for LinkedIn scraping."""

    job_titles: List[str] = Field(..., min_length=1)
    company_names: Optional[List[str]] = None
    industries: Optional[List[str]] = None
    locations: Optional[List[str]] = None
    seniority_levels: Optional[List[str]] = None
    max_results: int = Field(default=100, ge=1, le=1000)


class AIArkLookupParams(BaseModel):
    """Parameters for AI Ark B2B lookup."""

    company_domains: Optional[List[str]] = None
    company_names: Optional[List[str]] = None
    job_titles: Optional[List[str]] = None
    industries: Optional[List[str]] = None
    employee_range: Optional[str] = None
    locations: Optional[List[str]] = None
    leads_per_company: int = Field(default=3, ge=1, le=10)


class WebsiteScrapeParams(BaseModel):
    """Parameters for website scraping."""

    urls: List[str] = Field(..., min_length=1)
    scrape_contact_page: bool = True
    scrape_about_page: bool = True
    scrape_team_page: bool = True
    extract_emails: bool = True
    extract_phones: bool = True
    extract_social_links: bool = True


class AIEnrichmentParams(BaseModel):
    """Parameters for AI-powered enrichment."""

    lead_ids: Optional[List[UUID]] = Field(
        None, description="Specific leads to enrich. If empty, enriches all pending."
    )
    max_leads: int = Field(default=100, ge=1, le=1000)
    find_alternate_emails: bool = True
    find_alternate_companies: bool = True
    validate_existing_data: bool = True
    score_icp_match: bool = False
    icp_criteria: Optional[Dict[str, Any]] = None


class ScrapeJobCreate(BaseModel):
    """Schema for creating a scrape job."""

    job_type: str
    parameters: Dict[str, Any]


class ScrapeJobResponse(BaseModel):
    """Schema for scrape job responses."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    job_type: str
    status: str
    parameters: Optional[Dict[str, Any]] = None
    total_items: int
    processed_items: int
    successful_items: int
    failed_items: int
    results_count: int
    error_message: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime

    @property
    def progress_percentage(self) -> float:
        if self.total_items == 0:
            return 0.0
        return (self.processed_items / self.total_items) * 100


# ===========================================
# Enrichment Log Schemas
# ===========================================


class EnrichmentLogResponse(BaseModel):
    """Schema for enrichment log responses."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    lead_id: UUID
    enrichment_type: str
    source: Optional[str] = None
    success: bool
    error_message: Optional[str] = None
    tokens_used: Optional[int] = None
    cost_usd: Optional[float] = None
    duration_ms: Optional[int] = None
    created_at: datetime


# ===========================================
# Statistics Schemas
# ===========================================


class DashboardStats(BaseModel):
    """Dashboard statistics."""

    total_leads: int
    total_companies: int
    leads_by_source: Dict[str, int]
    leads_by_status: Dict[str, int]
    avg_confidence_score: float
    leads_created_today: int
    leads_created_this_week: int
    active_jobs: int
    total_cost_usd: float


class VendorPerformance(BaseModel):
    """Vendor performance statistics."""

    vendor: str
    total_lookups: int
    success_rate: float
    valid_email_rate: float
    avg_confidence_score: float
    total_cost_usd: float
    cost_per_valid_lead: float


# ===========================================
# Export Schemas
# ===========================================


class LeadExportRequest(BaseModel):
    """Request for exporting leads."""

    format: str = Field(default="csv", pattern="^(csv|xlsx|json)$")
    filters: Optional[Dict[str, Any]] = None
    columns: Optional[List[str]] = None
    include_companies: bool = True
    max_rows: int = Field(default=10000, ge=1, le=100000)


# ===========================================
# Pagination
# ===========================================


class PaginatedResponse(BaseModel):
    """Generic paginated response."""

    items: List[Any]
    total: int
    page: int
    page_size: int
    total_pages: int

    @property
    def has_next(self) -> bool:
        return self.page < self.total_pages

    @property
    def has_previous(self) -> bool:
        return self.page > 1
