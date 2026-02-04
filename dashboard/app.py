"""
Streamlit Dashboard for Lead Generation System.
"""

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
import streamlit as st
from datetime import datetime

# ===========================================
# Configuration
# ===========================================

API_BASE_URL = "http://localhost:8000/api/v1"

st.set_page_config(
    page_title="Lead Generation System",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ===========================================
# API Helper Functions
# ===========================================

def api_get(endpoint: str, params: dict = None):
    """Make GET request to API."""
    try:
        response = requests.get(f"{API_BASE_URL}{endpoint}", params=params)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        st.error(f"API Error: {e}")
        return None


def api_post(endpoint: str, data: dict = None):
    """Make POST request to API."""
    try:
        response = requests.post(f"{API_BASE_URL}{endpoint}", json=data)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        st.error(f"API Error: {e}")
        return None


# ===========================================
# Sidebar Navigation
# ===========================================

st.sidebar.title("🎯 Lead Gen System")
st.sidebar.markdown("---")

page = st.sidebar.radio(
    "Navigation",
    ["Dashboard", "Leads", "Companies", "Scrapers", "Enrichment", "Jobs"],
    index=0,
)

st.sidebar.markdown("---")
st.sidebar.markdown("### Quick Actions")

if st.sidebar.button("🔄 Refresh Data"):
    st.rerun()


# ===========================================
# Dashboard Page
# ===========================================

if page == "Dashboard":
    st.title("📊 Dashboard")
    st.markdown("Overview of your lead generation system")

    # Fetch stats
    stats = api_get("/stats")

    if stats:
        # Top metrics row
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric(
                label="Total Leads",
                value=f"{stats['total_leads']:,}",
                delta=f"+{stats['leads_created_today']} today",
            )

        with col2:
            st.metric(
                label="Total Companies",
                value=f"{stats['total_companies']:,}",
            )

        with col3:
            st.metric(
                label="Avg Confidence",
                value=f"{stats['avg_confidence_score']:.1%}",
            )

        with col4:
            st.metric(
                label="Total Cost",
                value=f"${stats['total_cost_usd']:.2f}",
            )

        st.markdown("---")

        # Charts row
        col1, col2 = st.columns(2)

        with col1:
            st.subheader("Leads by Source")
            if stats['leads_by_source']:
                fig = px.pie(
                    values=list(stats['leads_by_source'].values()),
                    names=list(stats['leads_by_source'].keys()),
                    color_discrete_sequence=px.colors.qualitative.Set3,
                )
                fig.update_layout(margin=dict(t=0, b=0, l=0, r=0))
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No leads yet")

        with col2:
            st.subheader("Leads by Status")
            if stats['leads_by_status']:
                fig = px.bar(
                    x=list(stats['leads_by_status'].keys()),
                    y=list(stats['leads_by_status'].values()),
                    color=list(stats['leads_by_status'].keys()),
                    color_discrete_sequence=px.colors.qualitative.Pastel,
                )
                fig.update_layout(
                    xaxis_title="Status",
                    yaxis_title="Count",
                    showlegend=False,
                    margin=dict(t=0, b=0, l=0, r=0),
                )
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No leads yet")

        # Active jobs
        st.markdown("---")
        st.subheader("Active Jobs")

        if stats['active_jobs'] > 0:
            st.info(f"🔄 {stats['active_jobs']} job(s) currently running")
        else:
            st.success("✅ No active jobs")

    else:
        st.warning("Could not fetch dashboard stats. Is the API running?")
        st.code("docker-compose up -d\npython -m app.main", language="bash")


# ===========================================
# Leads Page
# ===========================================

elif page == "Leads":
    st.title("👥 Leads")

    # Filters
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        search = st.text_input("🔍 Search", placeholder="Name, email, company...")

    with col2:
        source_filter = st.selectbox(
            "Source",
            ["All", "google_maps", "linkedin", "website", "ai_ark", "ai_enriched", "manual"],
        )

    with col3:
        status_filter = st.selectbox(
            "Status",
            ["All", "raw", "pending", "enriched", "validated", "failed"],
        )

    with col4:
        min_confidence = st.slider("Min Confidence", 0.0, 1.0, 0.0, 0.1)

    # Build params
    params = {"page": 1, "page_size": 100}
    if search:
        params["search"] = search
    if source_filter != "All":
        params["source"] = source_filter
    if status_filter != "All":
        params["status"] = status_filter
    if min_confidence > 0:
        params["min_confidence"] = min_confidence

    # Fetch leads
    data = api_get("/leads", params)

    if data and data.get("items"):
        st.markdown(f"**{data['total']} leads found**")

        # Convert to DataFrame
        df = pd.DataFrame(data["items"])

        # Select columns to display
        display_cols = [
            "full_name", "email", "job_title", "company_name",
            "source", "confidence_score", "enrichment_status", "created_at"
        ]
        display_cols = [c for c in display_cols if c in df.columns]

        # Format confidence score
        if "confidence_score" in df.columns:
            df["confidence_score"] = df["confidence_score"].apply(lambda x: f"{x:.0%}")

        st.dataframe(
            df[display_cols],
            use_container_width=True,
            hide_index=True,
        )

        # Export button
        col1, col2, col3 = st.columns([1, 1, 4])
        with col1:
            csv = df.to_csv(index=False)
            st.download_button(
                "📥 Export CSV",
                csv,
                "leads_export.csv",
                "text/csv",
            )

    else:
        st.info("No leads found. Start a scraping job to collect leads!")


# ===========================================
# Companies Page
# ===========================================

elif page == "Companies":
    st.title("🏢 Companies")

    # Filters
    col1, col2, col3 = st.columns(3)

    with col1:
        search = st.text_input("🔍 Search", placeholder="Company name or domain...")

    with col2:
        industry = st.text_input("Industry", placeholder="e.g., Healthcare")

    with col3:
        state = st.text_input("State", placeholder="e.g., CA")

    # Build params
    params = {"page": 1, "page_size": 100}
    if search:
        params["search"] = search
    if industry:
        params["industry"] = industry
    if state:
        params["state"] = state

    # Fetch companies
    data = api_get("/companies", params)

    if data and data.get("items"):
        st.markdown(f"**{data['total']} companies found**")

        df = pd.DataFrame(data["items"])

        display_cols = [
            "name", "domain", "industry", "city", "state",
            "google_rating", "google_reviews_count", "source", "created_at"
        ]
        display_cols = [c for c in display_cols if c in df.columns]

        st.dataframe(
            df[display_cols],
            use_container_width=True,
            hide_index=True,
        )

    else:
        st.info("No companies found. Run a Google Maps scrape to collect companies!")


# ===========================================
# Scrapers Page
# ===========================================

elif page == "Scrapers":
    st.title("🔧 Scrapers")
    st.markdown("Start scraping jobs to collect leads and companies")

    tab1, tab2, tab3, tab4 = st.tabs([
        "🗺️ Google Maps",
        "🔗 LinkedIn",
        "🌐 Website",
        "🚀 AI Ark",
    ])

    # Google Maps Tab
    with tab1:
        st.subheader("Google Maps Scraper")
        st.markdown("Scrape local businesses by category and location")

        with st.form("google_maps_form"):
            query = st.text_input(
                "Business Category",
                placeholder="e.g., dentist, plumber, restaurant",
            )

            col1, col2 = st.columns(2)
            with col1:
                states = st.multiselect(
                    "States",
                    ["CA", "NY", "TX", "FL", "IL", "PA", "OH", "GA", "NC", "MI"],
                    default=["CA"],
                )
            with col2:
                max_per_zip = st.slider("Max results per ZIP", 5, 60, 20)

            include_details = st.checkbox("Include detailed info", value=True)

            submitted = st.form_submit_button("🚀 Start Scrape")

            if submitted:
                if not query:
                    st.error("Please enter a business category")
                else:
                    result = api_post("/scrapers/google-maps", {
                        "query": query,
                        "states": states,
                        "max_results_per_zip": max_per_zip,
                        "include_details": include_details,
                    })
                    if result:
                        st.success(f"✅ Job started! ID: {result['job_id']}")

    # LinkedIn Tab
    with tab2:
        st.subheader("LinkedIn Scraper")
        st.markdown("Find professionals on LinkedIn (via Bright Data)")

        with st.form("linkedin_form"):
            job_titles = st.text_area(
                "Job Titles (one per line)",
                placeholder="CEO\nCTO\nVP Marketing",
            )

            col1, col2 = st.columns(2)
            with col1:
                companies = st.text_area(
                    "Companies (optional)",
                    placeholder="Google\nMeta\nAmazon",
                )
            with col2:
                locations = st.text_area(
                    "Locations (optional)",
                    placeholder="San Francisco, CA\nNew York, NY",
                )

            max_results = st.slider("Max results", 10, 500, 100)

            submitted = st.form_submit_button("🚀 Start Scrape")

            if submitted:
                titles = [t.strip() for t in job_titles.split("\n") if t.strip()]
                if not titles:
                    st.error("Please enter at least one job title")
                else:
                    result = api_post("/scrapers/linkedin", {
                        "job_titles": titles,
                        "company_names": [c.strip() for c in companies.split("\n") if c.strip()] or None,
                        "locations": [l.strip() for l in locations.split("\n") if l.strip()] or None,
                        "max_results": max_results,
                    })
                    if result:
                        st.success(f"✅ Job started! ID: {result['job_id']}")

    # Website Tab
    with tab3:
        st.subheader("Website Scraper")
        st.markdown("Extract contacts from company websites")

        with st.form("website_form"):
            urls = st.text_area(
                "Website URLs (one per line)",
                placeholder="acme.com\ntechcorp.io\nstartup.co",
            )

            col1, col2, col3 = st.columns(3)
            with col1:
                scrape_contact = st.checkbox("Scrape contact pages", value=True)
            with col2:
                scrape_about = st.checkbox("Scrape about pages", value=True)
            with col3:
                scrape_team = st.checkbox("Scrape team pages", value=True)

            submitted = st.form_submit_button("🚀 Start Scrape")

            if submitted:
                url_list = [u.strip() for u in urls.split("\n") if u.strip()]
                if not url_list:
                    st.error("Please enter at least one URL")
                else:
                    result = api_post("/scrapers/website", {
                        "urls": url_list,
                        "scrape_contact_page": scrape_contact,
                        "scrape_about_page": scrape_about,
                        "scrape_team_page": scrape_team,
                    })
                    if result:
                        st.success(f"✅ Job started! ID: {result['job_id']}")

    # AI Ark Tab
    with tab4:
        st.subheader("AI Ark Lookup")
        st.markdown("Get B2B contacts from AI Ark (primary data source)")

        with st.form("ai_ark_form"):
            col1, col2 = st.columns(2)

            with col1:
                domains = st.text_area(
                    "Company Domains",
                    placeholder="acme.com\ntechcorp.io",
                )
            with col2:
                job_titles = st.text_area(
                    "Job Titles (optional)",
                    placeholder="CEO\nCTO\nVP Sales",
                )

            leads_per_company = st.slider("Leads per company", 1, 10, 3)

            submitted = st.form_submit_button("🚀 Start Lookup")

            if submitted:
                domain_list = [d.strip() for d in domains.split("\n") if d.strip()]
                if not domain_list:
                    st.error("Please enter at least one domain")
                else:
                    result = api_post("/scrapers/ai-ark", {
                        "company_domains": domain_list,
                        "job_titles": [t.strip() for t in job_titles.split("\n") if t.strip()] or None,
                        "leads_per_company": leads_per_company,
                    })
                    if result:
                        st.success(f"✅ Job started! ID: {result['job_id']}")


# ===========================================
# Enrichment Page
# ===========================================

elif page == "Enrichment":
    st.title("✨ AI Enrichment")
    st.markdown("Enrich leads using AI (Claude API)")

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Batch Enrichment")
        st.markdown("Enrich multiple leads automatically")

        with st.form("enrichment_form"):
            max_leads = st.slider("Max leads to enrich", 10, 1000, 100)

            col_a, col_b = st.columns(2)
            with col_a:
                find_alt_emails = st.checkbox("Find alternate emails", value=True)
            with col_b:
                find_alt_companies = st.checkbox("Find alternate companies", value=True)

            submitted = st.form_submit_button("🚀 Start Enrichment")

            if submitted:
                result = api_post("/enrichment/start", {
                    "max_leads": max_leads,
                    "find_alternate_emails": find_alt_emails,
                    "find_alternate_companies": find_alt_companies,
                })
                if result:
                    st.success(f"✅ Enrichment started! Job ID: {result['job_id']}")

    with col2:
        st.subheader("Single Lead Enrichment")
        st.markdown("Enrich a specific lead by ID")

        lead_id = st.text_input("Lead ID (UUID)")

        if st.button("🔍 Enrich Lead"):
            if not lead_id:
                st.error("Please enter a lead ID")
            else:
                result = api_post(f"/enrichment/lead/{lead_id}")
                if result:
                    if result.get("enriched"):
                        st.success(f"✅ Lead enriched via {result['source']}")
                        st.metric("Cost", f"${result.get('cost', 0):.4f}")
                    else:
                        st.warning("Could not enrich lead")

    st.markdown("---")
    st.subheader("Enrichment Pipeline")
    st.markdown("""
    The waterfall enrichment strategy:
    1. **AI Ark** (primary) - Try to get data from AI Ark first
    2. **LinkedIn/Bright Data** (fallback) - If AI Ark doesn't have data
    3. **AI Lead Finder** (last resort) - Use Claude AI to research the lead

    This approach minimizes costs while maximizing data coverage.
    """)


# ===========================================
# Jobs Page
# ===========================================

elif page == "Jobs":
    st.title("📋 Jobs")
    st.markdown("Monitor scraping and enrichment jobs")

    # Status filter
    status_filter = st.selectbox(
        "Filter by status",
        ["All", "pending", "running", "completed", "failed", "cancelled"],
    )

    params = {"page": 1, "page_size": 50}
    if status_filter != "All":
        params["status"] = status_filter

    # Fetch jobs
    data = api_get("/jobs", params)

    if data and data.get("items"):
        for job in data["items"]:
            with st.expander(
                f"**{job['job_type']}** - {job['status'].upper()} - {job['created_at'][:19]}",
                expanded=job["status"] == "running",
            ):
                col1, col2, col3 = st.columns(3)

                with col1:
                    st.markdown(f"**Job ID:** `{job['id']}`")
                    st.markdown(f"**Type:** {job['job_type']}")

                with col2:
                    st.markdown(f"**Status:** {job['status']}")
                    st.markdown(f"**Results:** {job['results_count']}")

                with col3:
                    if job.get("started_at"):
                        st.markdown(f"**Started:** {job['started_at'][:19]}")
                    if job.get("completed_at"):
                        st.markdown(f"**Completed:** {job['completed_at'][:19]}")

                # Progress bar for running jobs
                if job["status"] == "running" and job["total_items"] > 0:
                    progress = job["processed_items"] / job["total_items"]
                    st.progress(progress, text=f"{progress:.0%} complete")

                # Error message
                if job.get("error_message"):
                    st.error(f"Error: {job['error_message']}")

                # Cancel button for running jobs
                if job["status"] in ["pending", "running"]:
                    if st.button(f"Cancel Job", key=f"cancel_{job['id']}"):
                        api_post(f"/jobs/{job['id']}/cancel")
                        st.rerun()

    else:
        st.info("No jobs found. Start a scraping job from the Scrapers page!")


# ===========================================
# Footer
# ===========================================

st.sidebar.markdown("---")
st.sidebar.markdown(
    """
    <div style='text-align: center; color: #888;'>
    <small>Lead Generation System v1.0</small><br>
    <small>Built with Claude Code</small>
    </div>
    """,
    unsafe_allow_html=True,
)
