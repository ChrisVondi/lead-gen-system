"""
FastAPI routes for the Lead Generation System.
"""

import logging
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import crud, schemas
from app.database.models import EnrichmentStatus, JobStatus, JobType, LeadSource

logger = logging.getLogger(__name__)

# ===========================================
# Routers
# ===========================================

router = APIRouter()
leads_router = APIRouter(prefix="/leads", tags=["Leads"])
companies_router = APIRouter(prefix="/companies", tags=["Companies"])
scrapers_router = APIRouter(prefix="/scrapers", tags=["Scrapers"])
enrichment_router = APIRouter(prefix="/enrichment", tags=["Enrichment"])
jobs_router = APIRouter(prefix="/jobs", tags=["Jobs"])


# ===========================================
# Dependency to get database session
# ===========================================

async def get_db():
    """Dependency for getting async database session."""
    from app.main import get_async_session
    async for session in get_async_session():
        yield session


# ===========================================
# Health Check
# ===========================================

@router.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "lead-gen-system"}


@router.get("/stats", response_model=schemas.DashboardStats)
async def get_dashboard_stats(db: AsyncSession = Depends(get_db)):
    """Get dashboard statistics."""
    stats = await crud.get_dashboard_stats(db)
    return stats


# ===========================================
# Leads CRUD
# ===========================================

@leads_router.get("", response_model=schemas.PaginatedResponse)
async def list_leads(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    source: Optional[str] = None,
    status: Optional[str] = None,
    min_confidence: Optional[float] = Query(None, ge=0, le=1),
    search: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """List leads with filtering and pagination."""
    filters = {}
    if source:
        filters["source"] = source
    if status:
        filters["enrichment_status"] = status
    if min_confidence is not None:
        filters["min_confidence"] = min_confidence
    if search:
        filters["search"] = search

    skip = (page - 1) * page_size
    leads, total = await crud.get_leads(db, skip=skip, limit=page_size, filters=filters)

    return {
        "items": [schemas.LeadResponse.model_validate(lead) for lead in leads],
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size,
    }


@leads_router.get("/{lead_id}", response_model=schemas.LeadResponse)
async def get_lead(lead_id: UUID, db: AsyncSession = Depends(get_db)):
    """Get a specific lead by ID."""
    lead = await crud.get_lead(db, lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    return schemas.LeadResponse.model_validate(lead)


@leads_router.post("", response_model=schemas.LeadResponse)
async def create_lead(
    lead: schemas.LeadCreate,
    db: AsyncSession = Depends(get_db),
):
    """Create a new lead."""
    db_lead = await crud.create_lead(db, lead)
    return schemas.LeadResponse.model_validate(db_lead)


@leads_router.post("/bulk", response_model=Dict[str, Any])
async def create_leads_bulk(
    data: schemas.LeadBulkCreate,
    db: AsyncSession = Depends(get_db),
):
    """Create multiple leads in bulk."""
    leads = await crud.create_leads_bulk(db, data.leads)
    return {
        "created": len(leads),
        "lead_ids": [str(lead.id) for lead in leads],
    }


@leads_router.patch("/{lead_id}", response_model=schemas.LeadResponse)
async def update_lead(
    lead_id: UUID,
    lead_update: schemas.LeadUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update a lead."""
    lead = await crud.update_lead(db, lead_id, lead_update)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    return schemas.LeadResponse.model_validate(lead)


@leads_router.delete("/{lead_id}")
async def delete_lead(lead_id: UUID, db: AsyncSession = Depends(get_db)):
    """Delete a lead."""
    deleted = await crud.delete_lead(db, lead_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Lead not found")
    return {"deleted": True, "lead_id": str(lead_id)}


@leads_router.get("/{lead_id}/enrichment-logs")
async def get_lead_enrichment_logs(
    lead_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get enrichment history for a lead."""
    logs = await crud.get_enrichment_logs_for_lead(db, lead_id)
    return [schemas.EnrichmentLogResponse.model_validate(log) for log in logs]


# ===========================================
# Companies CRUD
# ===========================================

@companies_router.get("", response_model=schemas.PaginatedResponse)
async def list_companies(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    industry: Optional[str] = None,
    city: Optional[str] = None,
    state: Optional[str] = None,
    search: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """List companies with filtering and pagination."""
    filters = {}
    if industry:
        filters["industry"] = industry
    if city:
        filters["city"] = city
    if state:
        filters["state"] = state
    if search:
        filters["search"] = search

    skip = (page - 1) * page_size
    companies, total = await crud.get_companies(db, skip=skip, limit=page_size, filters=filters)

    return {
        "items": [schemas.CompanyResponse.model_validate(c) for c in companies],
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size,
    }


@companies_router.get("/{company_id}", response_model=schemas.CompanyResponse)
async def get_company(company_id: UUID, db: AsyncSession = Depends(get_db)):
    """Get a specific company by ID."""
    company = await crud.get_company(db, company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    return schemas.CompanyResponse.model_validate(company)


@companies_router.post("", response_model=schemas.CompanyResponse)
async def create_company(
    company: schemas.CompanyCreate,
    db: AsyncSession = Depends(get_db),
):
    """Create a new company."""
    db_company = await crud.create_company(db, company)
    return schemas.CompanyResponse.model_validate(db_company)


@companies_router.patch("/{company_id}", response_model=schemas.CompanyResponse)
async def update_company(
    company_id: UUID,
    company_update: schemas.CompanyUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update a company."""
    company = await crud.update_company(db, company_id, company_update)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    return schemas.CompanyResponse.model_validate(company)


@companies_router.delete("/{company_id}")
async def delete_company(company_id: UUID, db: AsyncSession = Depends(get_db)):
    """Delete a company."""
    deleted = await crud.delete_company(db, company_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Company not found")
    return {"deleted": True, "company_id": str(company_id)}


# ===========================================
# Scraper Endpoints
# ===========================================

@scrapers_router.post("/google-maps")
async def start_google_maps_scrape(
    params: schemas.GoogleMapsScrapeParams,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """Start a Google Maps scraping job."""
    # Create job record
    job = await crud.create_scrape_job(
        db,
        schemas.ScrapeJobCreate(
            job_type=JobType.GOOGLE_MAPS_SCRAPE.value,
            parameters=params.model_dump(),
        ),
    )

    # Run in background
    background_tasks.add_task(
        run_google_maps_scrape,
        job_id=job.id,
        params=params,
    )

    return {
        "job_id": str(job.id),
        "status": "started",
        "message": f"Google Maps scrape started for '{params.query}'",
    }


@scrapers_router.post("/linkedin")
async def start_linkedin_scrape(
    params: schemas.LinkedInScrapeParams,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """Start a LinkedIn scraping job."""
    job = await crud.create_scrape_job(
        db,
        schemas.ScrapeJobCreate(
            job_type=JobType.LINKEDIN_SCRAPE.value,
            parameters=params.model_dump(),
        ),
    )

    background_tasks.add_task(
        run_linkedin_scrape,
        job_id=job.id,
        params=params,
    )

    return {
        "job_id": str(job.id),
        "status": "started",
        "message": "LinkedIn scrape started",
    }


@scrapers_router.post("/ai-ark")
async def start_ai_ark_lookup(
    params: schemas.AIArkLookupParams,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """Start an AI Ark lookup job."""
    job = await crud.create_scrape_job(
        db,
        schemas.ScrapeJobCreate(
            job_type=JobType.AI_ARK_LOOKUP.value,
            parameters=params.model_dump(),
        ),
    )

    background_tasks.add_task(
        run_ai_ark_lookup,
        job_id=job.id,
        params=params,
    )

    return {
        "job_id": str(job.id),
        "status": "started",
        "message": "AI Ark lookup started",
    }


@scrapers_router.post("/website")
async def start_website_scrape(
    params: schemas.WebsiteScrapeParams,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """Start a website scraping job."""
    job = await crud.create_scrape_job(
        db,
        schemas.ScrapeJobCreate(
            job_type=JobType.WEBSITE_SCRAPE.value,
            parameters=params.model_dump(),
        ),
    )

    background_tasks.add_task(
        run_website_scrape,
        job_id=job.id,
        params=params,
    )

    return {
        "job_id": str(job.id),
        "status": "started",
        "message": f"Website scrape started for {len(params.urls)} URLs",
    }


# ===========================================
# Enrichment Endpoints
# ===========================================

@enrichment_router.post("/start")
async def start_enrichment(
    params: schemas.AIEnrichmentParams,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """Start AI enrichment job."""
    job = await crud.create_scrape_job(
        db,
        schemas.ScrapeJobCreate(
            job_type=JobType.AI_ENRICHMENT.value,
            parameters=params.model_dump(),
        ),
    )

    background_tasks.add_task(
        run_enrichment,
        job_id=job.id,
        params=params,
    )

    return {
        "job_id": str(job.id),
        "status": "started",
        "message": "AI enrichment started",
    }


@enrichment_router.post("/lead/{lead_id}")
async def enrich_single_lead(
    lead_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Enrich a single lead immediately."""
    lead = await crud.get_lead(db, lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    # Run enrichment
    from app.ai.lead_finder import EnrichmentPipeline

    pipeline = EnrichmentPipeline()
    lead_data = {
        "first_name": lead.first_name,
        "last_name": lead.last_name,
        "full_name": lead.full_name,
        "email": lead.email,
        "job_title": lead.job_title,
        "company_name": lead.company_name,
        "linkedin_url": lead.linkedin_url,
    }

    enriched = await pipeline.enrich_lead(lead_data)

    # Update lead in database
    await crud.update_lead_enrichment(
        db,
        lead_id,
        enriched,
        EnrichmentStatus.ENRICHED if enriched.get("enrichment_source") else EnrichmentStatus.FAILED,
    )

    return {
        "lead_id": str(lead_id),
        "enriched": bool(enriched.get("enrichment_source")),
        "source": enriched.get("enrichment_source"),
        "cost": enriched.get("enrichment_cost", 0),
    }


# ===========================================
# Jobs Endpoints
# ===========================================

@jobs_router.get("", response_model=schemas.PaginatedResponse)
async def list_jobs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """List scrape/enrichment jobs."""
    skip = (page - 1) * page_size
    job_status = JobStatus(status) if status else None
    jobs, total = await crud.get_scrape_jobs(db, skip=skip, limit=page_size, status=job_status)

    return {
        "items": [schemas.ScrapeJobResponse.model_validate(job) for job in jobs],
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size,
    }


@jobs_router.get("/{job_id}", response_model=schemas.ScrapeJobResponse)
async def get_job(job_id: UUID, db: AsyncSession = Depends(get_db)):
    """Get a specific job by ID."""
    job = await crud.get_scrape_job(db, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return schemas.ScrapeJobResponse.model_validate(job)


@jobs_router.post("/{job_id}/cancel")
async def cancel_job(job_id: UUID, db: AsyncSession = Depends(get_db)):
    """Cancel a running job."""
    job = await crud.update_scrape_job_status(db, job_id, JobStatus.CANCELLED)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return {"job_id": str(job_id), "status": "cancelled"}


# ===========================================
# Background Task Functions
# ===========================================

async def run_google_maps_scrape(job_id: UUID, params: schemas.GoogleMapsScrapeParams):
    """Background task for Google Maps scraping."""
    from app.main import async_session_maker
    from app.scrapers.google_maps import GoogleMapsScraper

    async with async_session_maker() as db:
        try:
            await crud.update_scrape_job_status(db, job_id, JobStatus.RUNNING)

            async with GoogleMapsScraper() as scraper:
                results = await scraper.scrape(
                    query=params.query,
                    zip_codes=params.zip_codes,
                    states=params.states,
                    max_results_per_zip=params.max_results_per_zip,
                    include_details=params.include_details,
                )

            # Save results
            successful = [r for r in results if r.success]
            for result in successful:
                company_data = schemas.CompanyCreate(
                    source=LeadSource.GOOGLE_MAPS.value,
                    **result.data,
                )
                await crud.create_company(db, company_data)

            await crud.update_scrape_job_status(
                db, job_id, JobStatus.COMPLETED, results_count=len(successful)
            )

        except Exception as e:
            logger.error(f"Google Maps scrape failed: {e}")
            await crud.update_scrape_job_status(
                db, job_id, JobStatus.FAILED, error_message=str(e)
            )


async def run_linkedin_scrape(job_id: UUID, params: schemas.LinkedInScrapeParams):
    """Background task for LinkedIn scraping."""
    from app.main import async_session_maker
    from app.scrapers.linkedin import LinkedInScraper

    async with async_session_maker() as db:
        try:
            await crud.update_scrape_job_status(db, job_id, JobStatus.RUNNING)

            async with LinkedInScraper() as scraper:
                results = await scraper.scrape(
                    job_titles=params.job_titles,
                    company_names=params.company_names,
                    industries=params.industries,
                    locations=params.locations,
                    seniority_levels=params.seniority_levels,
                    max_results=params.max_results,
                )

            successful = [r for r in results if r.success]
            for result in successful:
                lead_data = schemas.LeadCreate(
                    source=LeadSource.LINKEDIN.value,
                    **result.data,
                )
                await crud.create_lead(db, lead_data)

            await crud.update_scrape_job_status(
                db, job_id, JobStatus.COMPLETED, results_count=len(successful)
            )

        except Exception as e:
            logger.error(f"LinkedIn scrape failed: {e}")
            await crud.update_scrape_job_status(
                db, job_id, JobStatus.FAILED, error_message=str(e)
            )


async def run_ai_ark_lookup(job_id: UUID, params: schemas.AIArkLookupParams):
    """Background task for AI Ark lookup."""
    from app.main import async_session_maker
    from app.scrapers.ai_ark import AIArkScraper

    async with async_session_maker() as db:
        try:
            await crud.update_scrape_job_status(db, job_id, JobStatus.RUNNING)

            async with AIArkScraper() as scraper:
                results = await scraper.scrape(
                    company_domains=params.company_domains,
                    company_names=params.company_names,
                    job_titles=params.job_titles,
                    industries=params.industries,
                    employee_range=params.employee_range,
                    locations=params.locations,
                    leads_per_company=params.leads_per_company,
                )

            successful = [r for r in results if r.success]
            for result in successful:
                lead_data = schemas.LeadCreate(
                    source=LeadSource.AI_ARK.value,
                    **result.data,
                )
                await crud.create_lead(db, lead_data)

            await crud.update_scrape_job_status(
                db, job_id, JobStatus.COMPLETED, results_count=len(successful)
            )

        except Exception as e:
            logger.error(f"AI Ark lookup failed: {e}")
            await crud.update_scrape_job_status(
                db, job_id, JobStatus.FAILED, error_message=str(e)
            )


async def run_website_scrape(job_id: UUID, params: schemas.WebsiteScrapeParams):
    """Background task for website scraping."""
    from app.main import async_session_maker
    from app.scrapers.website import WebsiteScraper

    async with async_session_maker() as db:
        try:
            await crud.update_scrape_job_status(db, job_id, JobStatus.RUNNING)

            async with WebsiteScraper() as scraper:
                results = await scraper.scrape(
                    urls=params.urls,
                    scrape_contact_page=params.scrape_contact_page,
                    scrape_about_page=params.scrape_about_page,
                    scrape_team_page=params.scrape_team_page,
                    extract_emails=params.extract_emails,
                    extract_phones=params.extract_phones,
                    extract_social_links=params.extract_social_links,
                )

            # Process results - extract leads from team members
            successful = [r for r in results if r.success]
            leads_created = 0

            for result in successful:
                data = result.data
                team_members = data.get("team_members", [])

                for member in team_members:
                    if member.get("name") or member.get("email"):
                        lead_data = schemas.LeadCreate(
                            source=LeadSource.WEBSITE.value,
                            full_name=member.get("name"),
                            email=member.get("email"),
                            job_title=member.get("job_title"),
                            linkedin_url=member.get("linkedin_url"),
                            source_url=result.source_url,
                        )
                        await crud.create_lead(db, lead_data)
                        leads_created += 1

            await crud.update_scrape_job_status(
                db, job_id, JobStatus.COMPLETED, results_count=leads_created
            )

        except Exception as e:
            logger.error(f"Website scrape failed: {e}")
            await crud.update_scrape_job_status(
                db, job_id, JobStatus.FAILED, error_message=str(e)
            )


async def run_enrichment(job_id: UUID, params: schemas.AIEnrichmentParams):
    """Background task for AI enrichment."""
    from app.main import async_session_maker
    from app.ai.lead_finder import EnrichmentPipeline

    async with async_session_maker() as db:
        try:
            await crud.update_scrape_job_status(db, job_id, JobStatus.RUNNING)

            # Get leads to enrich
            if params.lead_ids:
                leads = [await crud.get_lead(db, lid) for lid in params.lead_ids]
                leads = [l for l in leads if l]
            else:
                leads = await crud.get_leads_for_enrichment(db, limit=params.max_leads)

            pipeline = EnrichmentPipeline()
            enriched_count = 0

            for lead in leads:
                lead_data = {
                    "first_name": lead.first_name,
                    "last_name": lead.last_name,
                    "full_name": lead.full_name,
                    "email": lead.email,
                    "job_title": lead.job_title,
                    "company_name": lead.company_name,
                    "linkedin_url": lead.linkedin_url,
                }

                enriched = await pipeline.enrich_lead(lead_data)

                if enriched.get("enrichment_source"):
                    await crud.update_lead_enrichment(
                        db, lead.id, enriched, EnrichmentStatus.ENRICHED
                    )
                    enriched_count += 1
                else:
                    await crud.update_lead_enrichment(
                        db, lead.id, {}, EnrichmentStatus.FAILED
                    )

            await crud.update_scrape_job_status(
                db, job_id, JobStatus.COMPLETED, results_count=enriched_count
            )

        except Exception as e:
            logger.error(f"Enrichment failed: {e}")
            await crud.update_scrape_job_status(
                db, job_id, JobStatus.FAILED, error_message=str(e)
            )


# ===========================================
# Include all routers
# ===========================================

router.include_router(leads_router)
router.include_router(companies_router)
router.include_router(scrapers_router)
router.include_router(enrichment_router)
router.include_router(jobs_router)
