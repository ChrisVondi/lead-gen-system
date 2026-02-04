"""
CRUD operations for database models.
"""

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from .models import (
    Company,
    DataVendorStats,
    EnrichmentLog,
    EnrichmentStatus,
    JobStatus,
    Lead,
    LeadSource,
    ScrapeJob,
)
from .schemas import (
    CompanyCreate,
    CompanyUpdate,
    LeadCreate,
    LeadUpdate,
    ScrapeJobCreate,
)


# ===========================================
# Company CRUD
# ===========================================


async def create_company(db: AsyncSession, company: CompanyCreate) -> Company:
    """Create a new company."""
    db_company = Company(**company.model_dump())
    db.add(db_company)
    await db.commit()
    await db.refresh(db_company)
    return db_company


async def get_company(db: AsyncSession, company_id: UUID) -> Optional[Company]:
    """Get a company by ID."""
    result = await db.execute(select(Company).where(Company.id == company_id))
    return result.scalar_one_or_none()


async def get_company_by_domain(db: AsyncSession, domain: str) -> Optional[Company]:
    """Get a company by domain."""
    result = await db.execute(select(Company).where(Company.domain == domain))
    return result.scalar_one_or_none()


async def get_company_by_google_place_id(
    db: AsyncSession, place_id: str
) -> Optional[Company]:
    """Get a company by Google Place ID."""
    result = await db.execute(
        select(Company).where(Company.google_place_id == place_id)
    )
    return result.scalar_one_or_none()


async def get_companies(
    db: AsyncSession,
    skip: int = 0,
    limit: int = 100,
    filters: Optional[Dict[str, Any]] = None,
) -> Tuple[List[Company], int]:
    """Get companies with pagination and filtering."""
    query = select(Company)

    if filters:
        if filters.get("industry"):
            query = query.where(Company.industry == filters["industry"])
        if filters.get("city"):
            query = query.where(Company.city == filters["city"])
        if filters.get("state"):
            query = query.where(Company.state == filters["state"])
        if filters.get("source"):
            query = query.where(Company.source == filters["source"])
        if filters.get("search"):
            search = f"%{filters['search']}%"
            query = query.where(
                or_(
                    Company.name.ilike(search),
                    Company.domain.ilike(search),
                )
            )

    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    # Get paginated results
    query = query.order_by(Company.created_at.desc()).offset(skip).limit(limit)
    result = await db.execute(query)
    companies = result.scalars().all()

    return list(companies), total


async def update_company(
    db: AsyncSession, company_id: UUID, company_update: CompanyUpdate
) -> Optional[Company]:
    """Update a company."""
    company = await get_company(db, company_id)
    if not company:
        return None

    update_data = company_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(company, field, value)

    await db.commit()
    await db.refresh(company)
    return company


async def delete_company(db: AsyncSession, company_id: UUID) -> bool:
    """Delete a company."""
    company = await get_company(db, company_id)
    if not company:
        return False

    await db.delete(company)
    await db.commit()
    return True


# ===========================================
# Lead CRUD
# ===========================================


async def create_lead(db: AsyncSession, lead: LeadCreate) -> Lead:
    """Create a new lead."""
    db_lead = Lead(**lead.model_dump())
    db.add(db_lead)
    await db.commit()
    await db.refresh(db_lead)
    return db_lead


async def create_leads_bulk(db: AsyncSession, leads: List[LeadCreate]) -> List[Lead]:
    """Create multiple leads in bulk."""
    db_leads = [Lead(**lead.model_dump()) for lead in leads]
    db.add_all(db_leads)
    await db.commit()
    for lead in db_leads:
        await db.refresh(lead)
    return db_leads


async def get_lead(db: AsyncSession, lead_id: UUID) -> Optional[Lead]:
    """Get a lead by ID."""
    result = await db.execute(
        select(Lead).where(Lead.id == lead_id).options(selectinload(Lead.company))
    )
    return result.scalar_one_or_none()


async def get_lead_by_email(db: AsyncSession, email: str) -> Optional[Lead]:
    """Get a lead by email."""
    result = await db.execute(select(Lead).where(Lead.email == email))
    return result.scalar_one_or_none()


async def get_leads(
    db: AsyncSession,
    skip: int = 0,
    limit: int = 100,
    filters: Optional[Dict[str, Any]] = None,
) -> Tuple[List[Lead], int]:
    """Get leads with pagination and filtering."""
    query = select(Lead)

    if filters:
        conditions = []

        if filters.get("source"):
            conditions.append(Lead.source == filters["source"])
        if filters.get("enrichment_status"):
            conditions.append(Lead.enrichment_status == filters["enrichment_status"])
        if filters.get("company_id"):
            conditions.append(Lead.company_id == filters["company_id"])
        if filters.get("min_confidence"):
            conditions.append(Lead.confidence_score >= filters["min_confidence"])
        if filters.get("email_verified") is not None:
            conditions.append(Lead.email_verified == filters["email_verified"])
        if filters.get("search"):
            search = f"%{filters['search']}%"
            conditions.append(
                or_(
                    Lead.email.ilike(search),
                    Lead.full_name.ilike(search),
                    Lead.company_name.ilike(search),
                    Lead.job_title.ilike(search),
                )
            )
        if filters.get("created_after"):
            conditions.append(Lead.created_at >= filters["created_after"])
        if filters.get("created_before"):
            conditions.append(Lead.created_at <= filters["created_before"])
        if filters.get("tags"):
            # Filter by tags (JSONB contains)
            for tag in filters["tags"]:
                conditions.append(Lead.tags.contains([tag]))

        if conditions:
            query = query.where(and_(*conditions))

    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    # Get paginated results
    query = query.order_by(Lead.created_at.desc()).offset(skip).limit(limit)
    result = await db.execute(query)
    leads = result.scalars().all()

    return list(leads), total


async def get_leads_for_enrichment(
    db: AsyncSession, limit: int = 100
) -> List[Lead]:
    """Get leads that need enrichment."""
    result = await db.execute(
        select(Lead)
        .where(
            Lead.enrichment_status.in_(
                [EnrichmentStatus.RAW, EnrichmentStatus.PENDING]
            )
        )
        .order_by(Lead.created_at.asc())
        .limit(limit)
    )
    return list(result.scalars().all())


async def update_lead(
    db: AsyncSession, lead_id: UUID, lead_update: LeadUpdate
) -> Optional[Lead]:
    """Update a lead."""
    lead = await get_lead(db, lead_id)
    if not lead:
        return None

    update_data = lead_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(lead, field, value)

    lead.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(lead)
    return lead


async def update_lead_enrichment(
    db: AsyncSession,
    lead_id: UUID,
    enrichment_data: Dict[str, Any],
    status: EnrichmentStatus,
) -> Optional[Lead]:
    """Update lead with enrichment data."""
    lead = await get_lead(db, lead_id)
    if not lead:
        return None

    for field, value in enrichment_data.items():
        if hasattr(lead, field) and value is not None:
            setattr(lead, field, value)

    lead.enrichment_status = status
    lead.last_enriched_at = datetime.utcnow()
    lead.updated_at = datetime.utcnow()

    await db.commit()
    await db.refresh(lead)
    return lead


async def delete_lead(db: AsyncSession, lead_id: UUID) -> bool:
    """Delete a lead."""
    lead = await get_lead(db, lead_id)
    if not lead:
        return False

    await db.delete(lead)
    await db.commit()
    return True


# ===========================================
# Scrape Job CRUD
# ===========================================


async def create_scrape_job(db: AsyncSession, job: ScrapeJobCreate) -> ScrapeJob:
    """Create a new scrape job."""
    db_job = ScrapeJob(**job.model_dump())
    db.add(db_job)
    await db.commit()
    await db.refresh(db_job)
    return db_job


async def get_scrape_job(db: AsyncSession, job_id: UUID) -> Optional[ScrapeJob]:
    """Get a scrape job by ID."""
    result = await db.execute(select(ScrapeJob).where(ScrapeJob.id == job_id))
    return result.scalar_one_or_none()


async def get_scrape_jobs(
    db: AsyncSession,
    skip: int = 0,
    limit: int = 50,
    status: Optional[JobStatus] = None,
) -> Tuple[List[ScrapeJob], int]:
    """Get scrape jobs with pagination."""
    query = select(ScrapeJob)

    if status:
        query = query.where(ScrapeJob.status == status)

    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    query = query.order_by(ScrapeJob.created_at.desc()).offset(skip).limit(limit)
    result = await db.execute(query)
    jobs = result.scalars().all()

    return list(jobs), total


async def update_scrape_job_status(
    db: AsyncSession,
    job_id: UUID,
    status: JobStatus,
    error_message: Optional[str] = None,
    results_count: Optional[int] = None,
) -> Optional[ScrapeJob]:
    """Update scrape job status."""
    job = await get_scrape_job(db, job_id)
    if not job:
        return None

    job.status = status

    if status == JobStatus.RUNNING and not job.started_at:
        job.started_at = datetime.utcnow()

    if status in [JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED]:
        job.completed_at = datetime.utcnow()

    if error_message:
        job.error_message = error_message

    if results_count is not None:
        job.results_count = results_count

    await db.commit()
    await db.refresh(job)
    return job


async def update_scrape_job_progress(
    db: AsyncSession,
    job_id: UUID,
    processed: int,
    successful: int,
    failed: int,
) -> Optional[ScrapeJob]:
    """Update scrape job progress."""
    job = await get_scrape_job(db, job_id)
    if not job:
        return None

    job.processed_items = processed
    job.successful_items = successful
    job.failed_items = failed

    await db.commit()
    await db.refresh(job)
    return job


# ===========================================
# Enrichment Log CRUD
# ===========================================


async def create_enrichment_log(
    db: AsyncSession,
    lead_id: UUID,
    enrichment_type: str,
    source: LeadSource,
    success: bool,
    request_data: Optional[Dict] = None,
    response_data: Optional[Dict] = None,
    error_message: Optional[str] = None,
    tokens_used: Optional[int] = None,
    cost_usd: Optional[float] = None,
    duration_ms: Optional[int] = None,
) -> EnrichmentLog:
    """Create an enrichment log entry."""
    log = EnrichmentLog(
        lead_id=lead_id,
        enrichment_type=enrichment_type,
        source=source,
        success=success,
        request_data=request_data,
        response_data=response_data,
        error_message=error_message,
        tokens_used=tokens_used,
        cost_usd=cost_usd,
        duration_ms=duration_ms,
    )
    db.add(log)
    await db.commit()
    await db.refresh(log)
    return log


async def get_enrichment_logs_for_lead(
    db: AsyncSession, lead_id: UUID
) -> List[EnrichmentLog]:
    """Get all enrichment logs for a lead."""
    result = await db.execute(
        select(EnrichmentLog)
        .where(EnrichmentLog.lead_id == lead_id)
        .order_by(EnrichmentLog.created_at.desc())
    )
    return list(result.scalars().all())


# ===========================================
# Statistics
# ===========================================


async def get_dashboard_stats(db: AsyncSession) -> Dict[str, Any]:
    """Get dashboard statistics."""
    now = datetime.utcnow()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = today_start - timedelta(days=7)

    # Total counts
    total_leads = (await db.execute(select(func.count(Lead.id)))).scalar() or 0
    total_companies = (await db.execute(select(func.count(Company.id)))).scalar() or 0

    # Leads by source
    source_counts = await db.execute(
        select(Lead.source, func.count(Lead.id)).group_by(Lead.source)
    )
    leads_by_source = {str(row[0].value): row[1] for row in source_counts}

    # Leads by status
    status_counts = await db.execute(
        select(Lead.enrichment_status, func.count(Lead.id)).group_by(
            Lead.enrichment_status
        )
    )
    leads_by_status = {str(row[0].value): row[1] for row in status_counts}

    # Average confidence score
    avg_score = (
        await db.execute(select(func.avg(Lead.confidence_score)))
    ).scalar() or 0.0

    # Leads created today/this week
    leads_today = (
        await db.execute(
            select(func.count(Lead.id)).where(Lead.created_at >= today_start)
        )
    ).scalar() or 0

    leads_this_week = (
        await db.execute(
            select(func.count(Lead.id)).where(Lead.created_at >= week_start)
        )
    ).scalar() or 0

    # Active jobs
    active_jobs = (
        await db.execute(
            select(func.count(ScrapeJob.id)).where(
                ScrapeJob.status.in_([JobStatus.PENDING, JobStatus.RUNNING])
            )
        )
    ).scalar() or 0

    # Total cost
    total_cost = (
        await db.execute(select(func.sum(EnrichmentLog.cost_usd)))
    ).scalar() or 0.0

    return {
        "total_leads": total_leads,
        "total_companies": total_companies,
        "leads_by_source": leads_by_source,
        "leads_by_status": leads_by_status,
        "avg_confidence_score": round(avg_score, 3),
        "leads_created_today": leads_today,
        "leads_created_this_week": leads_this_week,
        "active_jobs": active_jobs,
        "total_cost_usd": round(total_cost, 2),
    }
