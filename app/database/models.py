"""
SQLAlchemy database models for the Lead Generation System.
"""

import enum
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()


# ===========================================
# Enums
# ===========================================


class LeadSource(str, enum.Enum):
    """Source of the lead data."""

    GOOGLE_MAPS = "google_maps"
    LINKEDIN = "linkedin"
    WEBSITE = "website"
    AI_ARK = "ai_ark"
    AI_ENRICHED = "ai_enriched"
    MANUAL = "manual"
    IMPORT = "import"


class EnrichmentStatus(str, enum.Enum):
    """Status of lead enrichment."""

    RAW = "raw"
    PENDING = "pending"
    ENRICHED = "enriched"
    VALIDATED = "validated"
    FAILED = "failed"


class JobStatus(str, enum.Enum):
    """Status of scrape/enrichment jobs."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class JobType(str, enum.Enum):
    """Type of job."""

    GOOGLE_MAPS_SCRAPE = "google_maps_scrape"
    LINKEDIN_SCRAPE = "linkedin_scrape"
    WEBSITE_SCRAPE = "website_scrape"
    AI_ARK_LOOKUP = "ai_ark_lookup"
    AI_ENRICHMENT = "ai_enrichment"
    BULK_IMPORT = "bulk_import"
    BULK_EXPORT = "bulk_export"


# ===========================================
# Models
# ===========================================


class Company(Base):
    """Company information."""

    __tablename__ = "companies"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(500), nullable=False, index=True)
    website = Column(String(500), index=True)
    domain = Column(String(255), index=True)  # Extracted from website
    industry = Column(String(255))
    employee_count = Column(Integer)
    employee_range = Column(String(50))  # e.g., "10-50", "51-200"
    revenue_range = Column(String(50))
    founded_year = Column(Integer)

    # Location
    address = Column(Text)
    city = Column(String(255))
    state = Column(String(100))
    country = Column(String(100), default="USA")
    zip_code = Column(String(20))

    # External IDs
    google_place_id = Column(String(255), unique=True)
    linkedin_company_url = Column(String(500))
    linkedin_company_id = Column(String(100))

    # Google Maps specific
    google_rating = Column(Float)
    google_reviews_count = Column(Integer)
    google_phone = Column(String(50))

    # Metadata
    raw_data = Column(JSONB)  # Store original scraped data
    source = Column(Enum(LeadSource), default=LeadSource.MANUAL)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    leads = relationship("Lead", back_populates="company", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_company_domain", "domain"),
        Index("idx_company_location", "city", "state", "country"),
    )


class Lead(Base):
    """Individual lead/contact information."""

    __tablename__ = "leads"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Basic Info
    email = Column(String(255), index=True)
    email_verified = Column(Boolean, default=False)
    first_name = Column(String(255))
    last_name = Column(String(255))
    full_name = Column(String(500))
    job_title = Column(String(500))
    department = Column(String(255))
    seniority_level = Column(String(100))  # e.g., "C-Level", "VP", "Director", "Manager"

    # Contact Info
    phone = Column(String(50))
    phone_verified = Column(Boolean, default=False)
    linkedin_url = Column(String(500))
    twitter_url = Column(String(500))

    # Company relation
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id"), index=True)
    company_name = Column(String(500))  # Denormalized for quick access

    # Scoring & Validation
    confidence_score = Column(Float, default=0.0)  # 0.0 to 1.0
    icp_score = Column(Float)  # Ideal Customer Profile match score
    enrichment_status = Column(
        Enum(EnrichmentStatus), default=EnrichmentStatus.RAW, index=True
    )

    # Source tracking
    source = Column(Enum(LeadSource), default=LeadSource.MANUAL, index=True)
    source_url = Column(String(1000))  # Where the lead was found
    ai_reasoning = Column(Text)  # AI's explanation for finding this lead

    # Alternate contacts (for waterfall)
    alternate_emails = Column(JSONB)  # List of other email addresses found
    alternate_companies = Column(JSONB)  # Other companies this person works at

    # Metadata
    raw_data = Column(JSONB)  # Store original data from source
    tags = Column(JSONB)  # Custom tags for categorization
    notes = Column(Text)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_enriched_at = Column(DateTime)

    # Relationships
    company = relationship("Company", back_populates="leads")
    enrichment_logs = relationship(
        "EnrichmentLog", back_populates="lead", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("idx_lead_email", "email"),
        Index("idx_lead_company_name", "company_name"),
        Index("idx_lead_source_status", "source", "enrichment_status"),
        Index("idx_lead_score", "confidence_score"),
    )


class ScrapeJob(Base):
    """Track scraping and enrichment jobs."""

    __tablename__ = "scrape_jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_type = Column(Enum(JobType), nullable=False, index=True)
    status = Column(Enum(JobStatus), default=JobStatus.PENDING, index=True)

    # Job parameters
    parameters = Column(JSONB)  # Search criteria, filters, etc.

    # Progress tracking
    total_items = Column(Integer, default=0)
    processed_items = Column(Integer, default=0)
    successful_items = Column(Integer, default=0)
    failed_items = Column(Integer, default=0)

    # Results
    results_count = Column(Integer, default=0)
    error_message = Column(Text)
    error_details = Column(JSONB)

    # Timing
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Who triggered it
    triggered_by = Column(String(255))  # user ID or "system"

    __table_args__ = (Index("idx_job_status_type", "status", "job_type"),)


class EnrichmentLog(Base):
    """Log of all enrichment attempts for a lead."""

    __tablename__ = "enrichment_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lead_id = Column(UUID(as_uuid=True), ForeignKey("leads.id"), index=True)

    # Enrichment details
    enrichment_type = Column(String(100))  # e.g., "ai_ark_lookup", "claude_research"
    source = Column(Enum(LeadSource))
    success = Column(Boolean, default=False)

    # Request/Response
    request_data = Column(JSONB)
    response_data = Column(JSONB)
    error_message = Column(Text)

    # Cost tracking
    tokens_used = Column(Integer)
    api_calls = Column(Integer, default=1)
    cost_usd = Column(Float)  # Estimated cost in USD

    # Timing
    duration_ms = Column(Integer)  # How long the enrichment took
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    lead = relationship("Lead", back_populates="enrichment_logs")


class DataVendorStats(Base):
    """Track performance of different data vendors/sources."""

    __tablename__ = "data_vendor_stats"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    vendor = Column(String(100), nullable=False, index=True)  # e.g., "ai_ark", "bright_data"
    industry = Column(String(255), index=True)
    job_title_category = Column(String(255))  # e.g., "Marketing", "Engineering"

    # Stats
    total_lookups = Column(Integer, default=0)
    successful_lookups = Column(Integer, default=0)
    valid_emails_found = Column(Integer, default=0)
    avg_confidence_score = Column(Float)

    # Cost efficiency
    total_cost_usd = Column(Float, default=0.0)
    cost_per_valid_lead = Column(Float)

    # Time period
    period_start = Column(DateTime)
    period_end = Column(DateTime)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("idx_vendor_industry", "vendor", "industry"),
    )
