"""
AI prompts for the Lead Finder system.
Uses Claude API for intelligent lead research and enrichment.
"""

# ===========================================
# Company Research Prompt
# ===========================================

COMPANY_RESEARCH_PROMPT = """You are a B2B research assistant helping to gather company information.

Given the following company details:
- Company Name: {company_name}
- Website/Domain: {domain}
- Industry: {industry}
- Location: {location}

Research and provide the following information in JSON format:
{{
    "company_name": "Official company name",
    "website": "Company website URL",
    "industry": "Primary industry/sector",
    "description": "Brief company description (1-2 sentences)",
    "employee_range": "Estimated employee count range (e.g., '10-50', '51-200')",
    "founded_year": "Year founded (if known)",
    "headquarters": {{
        "city": "City",
        "state": "State/Province",
        "country": "Country"
    }},
    "linkedin_url": "LinkedIn company page URL (if known)",
    "key_products_services": ["List", "of", "main", "offerings"],
    "confidence_score": 0.0-1.0
}}

Only include information you are confident about. Use null for unknown fields.
Focus on accuracy over completeness."""


# ===========================================
# Contact Finding Prompt
# ===========================================

CONTACT_FINDING_PROMPT = """You are a B2B contact research assistant. Your task is to find decision-makers at a company.

Company Information:
- Company Name: {company_name}
- Website/Domain: {domain}
- Industry: {industry}

Target Criteria:
- Job Titles: {job_titles}
- Departments: {departments}
- Seniority Levels: {seniority_levels}
- Number of contacts needed: {leads_count}

Based on your knowledge, provide potential contacts at this company in JSON format:
{{
    "contacts": [
        {{
            "first_name": "First name",
            "last_name": "Last name",
            "full_name": "Full name",
            "job_title": "Current job title",
            "department": "Department (e.g., Marketing, Engineering)",
            "seniority_level": "C-Level/VP/Director/Manager/Senior/Individual Contributor",
            "linkedin_url": "LinkedIn profile URL (if known)",
            "email_pattern": "Likely email pattern (e.g., 'first.last@domain.com')",
            "confidence_score": 0.0-1.0,
            "reasoning": "Why this person is a good fit"
        }}
    ],
    "email_patterns_found": ["first.last@domain.com", "flast@domain.com"],
    "company_email_domain": "Primary email domain"
}}

IMPORTANT:
- Only include contacts you have reasonable confidence exist
- Do NOT make up fake names or information
- If you're unsure, say so in the reasoning
- Prioritize accuracy over quantity
- Include reasoning for each contact suggestion"""


# ===========================================
# Email Validation Prompt
# ===========================================

EMAIL_VALIDATION_PROMPT = """You are an email validation assistant. Analyze the following email address and provide validation insights.

Email to validate: {email}
Company domain: {domain}
Person's name: {full_name}
Job title: {job_title}

Analyze and respond in JSON format:
{{
    "email": "{email}",
    "likely_valid": true/false,
    "validation_reasoning": "Explanation of validation logic",
    "matches_common_patterns": true/false,
    "pattern_used": "Pattern detected (e.g., 'first.last', 'flast', 'firstl')",
    "alternative_emails": [
        "alternative1@domain.com",
        "alternative2@domain.com"
    ],
    "confidence_score": 0.0-1.0
}}

Common email patterns to check:
1. first.last@domain.com
2. firstlast@domain.com
3. flast@domain.com
4. first.l@domain.com
5. first@domain.com
6. last@domain.com

Consider:
- Does the email match standard corporate patterns?
- Is the domain correct for this company?
- Are there obvious typos or issues?"""


# ===========================================
# ICP Matching Prompt
# ===========================================

ICP_MATCHING_PROMPT = """You are a sales intelligence assistant. Score how well a lead matches the Ideal Customer Profile (ICP).

Lead Information:
- Name: {full_name}
- Job Title: {job_title}
- Company: {company_name}
- Industry: {industry}
- Company Size: {employee_range}
- Location: {location}

ICP Criteria:
{icp_criteria}

Score this lead and respond in JSON format:
{{
    "icp_score": 0.0-1.0,
    "scoring_breakdown": {{
        "job_title_match": 0.0-1.0,
        "industry_match": 0.0-1.0,
        "company_size_match": 0.0-1.0,
        "location_match": 0.0-1.0,
        "seniority_match": 0.0-1.0
    }},
    "strengths": ["List", "of", "why", "good", "fit"],
    "weaknesses": ["List", "of", "potential", "concerns"],
    "recommendation": "PRIORITY_HIGH / PRIORITY_MEDIUM / PRIORITY_LOW / NOT_A_FIT",
    "personalization_angles": ["Suggested", "outreach", "angles"]
}}"""


# ===========================================
# Alternate Contact Finder Prompt
# ===========================================

ALTERNATE_CONTACT_PROMPT = """You are a contact research assistant. Find alternate ways to reach this person.

Person Information:
- Name: {full_name}
- Current Company: {company_name}
- Job Title: {job_title}
- Known Email: {known_email}
- LinkedIn: {linkedin_url}

Task: Find potential alternate contact methods for this person.

Consider:
1. Personal email addresses (common providers: gmail, outlook, yahoo)
2. Other companies they may work at (consultants, advisors, board members often have multiple roles)
3. Previous companies they worked at
4. Alternative social profiles

Respond in JSON format:
{{
    "alternate_emails": [
        {{
            "email": "email@example.com",
            "type": "personal/work/other",
            "confidence": 0.0-1.0,
            "reasoning": "Why this might be valid"
        }}
    ],
    "alternate_companies": [
        {{
            "company_name": "Company name",
            "role": "Their role there",
            "relationship": "advisor/board/consultant/previous_employer",
            "potential_email": "email@company.com"
        }}
    ],
    "social_profiles": [
        {{
            "platform": "Twitter/GitHub/etc",
            "url": "Profile URL",
            "username": "username"
        }}
    ],
    "outreach_recommendation": "Best channel to reach this person"
}}

IMPORTANT:
- Only suggest alternate contacts you have reasonable confidence in
- Clearly explain your reasoning
- Do NOT fabricate information"""


# ===========================================
# Full Enrichment Pipeline Prompt
# ===========================================

FULL_ENRICHMENT_PROMPT = """You are a comprehensive B2B lead enrichment assistant.

Given a lead with partial information, enrich it with as much additional data as possible.

Current Lead Data:
{current_data}

Company Context:
{company_context}

Your task:
1. Fill in any missing standard fields
2. Validate existing information
3. Find additional contact methods
4. Score the lead quality

Respond in JSON format:
{{
    "enriched_data": {{
        "first_name": "value or null",
        "last_name": "value or null",
        "full_name": "value or null",
        "job_title": "value or null",
        "department": "value or null",
        "seniority_level": "value or null",
        "email": "value or null",
        "email_verified": false,
        "phone": "value or null",
        "linkedin_url": "value or null",
        "twitter_url": "value or null",
        "company_name": "value or null",
        "company_domain": "value or null"
    }},
    "alternate_emails": ["email1@example.com"],
    "alternate_companies": [
        {{
            "company": "Company Name",
            "role": "Role there"
        }}
    ],
    "validation_notes": {{
        "email_validation": "Analysis of email validity",
        "data_freshness": "How recent this data likely is",
        "overall_quality": "Assessment of data quality"
    }},
    "confidence_score": 0.0-1.0,
    "enrichment_summary": "Brief summary of what was enriched and confidence level"
}}

Guidelines:
- Only include information you're reasonably confident about
- Use null for truly unknown fields
- Explain your reasoning in the enrichment_summary
- Be conservative with confidence scores"""


# ===========================================
# Batch Research Prompt
# ===========================================

BATCH_COMPANY_RESEARCH_PROMPT = """You are a B2B research assistant. Research multiple companies efficiently.

Companies to research:
{companies_list}

For each company, provide:
{{
    "companies": [
        {{
            "input_identifier": "The identifier provided",
            "company_name": "Official name",
            "website": "Website URL",
            "industry": "Industry",
            "employee_range": "Size range",
            "headquarters_location": "City, State, Country",
            "linkedin_url": "LinkedIn company URL",
            "key_decision_maker_titles": ["CEO", "CTO", etc.],
            "confidence_score": 0.0-1.0
        }}
    ]
}}

Focus on accuracy. Use null for fields you cannot determine with confidence."""
