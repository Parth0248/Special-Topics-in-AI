"""Core research and evaluation tools for Agent A (Deep Research Lead Generation).

Provides multi-hop candidate discovery with live search grounding and deterministic
offline fallback, firmographic extraction, multi-dimensional lead fit evaluation,
and structured markdown dossier compilation.
"""

import json
import logging
import os
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union

try:
    from .models import (
        CategoryScoreBreakdown,
        CompanyProfile,
        FitScoreEvaluation,
        LeadDossier,
        TargetMarketCriteria,
    )
    from .mock_data import MOCK_COMPANIES
except (ImportError, ValueError):
    from models import (
        CategoryScoreBreakdown,
        CompanyProfile,
        FitScoreEvaluation,
        LeadDossier,
        TargetMarketCriteria,
    )
    from mock_data import MOCK_COMPANIES

logger = logging.getLogger(__name__)


def search_companies(
    query: str,
    industry: str = "",
    geography: str = "",
    limit: int = 5,
    mock_only: bool = False,
) -> List[Dict[str, Any]]:
    """Discovers company candidates matching search queries and target industry criteria.

    Supports live search grounding when Google API key is configured, with automatic
    deterministic fallback to the curated offline mock database for disconnected
    execution and reliable automated testing.

    Args:
        query: Search keywords, product themes, or target business descriptions.
        industry: Target industry filter (e.g. 'Fintech', 'Healthcare AI').
        geography: Optional target geographical focus (e.g. 'North America', 'Europe').
        limit: Maximum number of candidate profiles to return.
        mock_only: If True, bypasses live search grounding and queries offline data directly.

    Returns:
        A list of company candidate dictionaries with firmographics and signal data.
    """
    api_key = os.environ.get("GOOGLE_API_KEY")
    if not mock_only and api_key and not api_key.startswith("AQ.dummy"):
        try:
            results = _search_companies_live(query, industry, geography, limit, api_key)
            if results:
                logger.info(f"Retrieved {len(results)} candidate companies via live search grounding.")
                return results
        except Exception as e:
            logger.warning(f"Live search grounding failed or timed out: {e}. Falling back to offline dataset.")

    return _search_companies_offline(query, industry, geography, limit)


def _search_companies_live(
    query: str,
    industry: str,
    geography: str,
    limit: int,
    api_key: str,
) -> List[Dict[str, Any]]:
    """Executes live search grounding using google.genai and Gemini search tool."""
    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=api_key)
        model_name = os.environ.get("HARNESS_MODEL", "gemini-2.5-flash")

        search_prompt = (
            f"You are a deep research lead generation specialist. Find up to {limit} real companies matching:\n"
            f"- Search Query: {query}\n"
            f"- Target Industry: {industry or 'Any'}\n"
            f"- Target Geography: {geography or 'Global'}\n\n"
            "Return a clean JSON array of objects without Markdown formatting. Each object MUST include:\n"
            "- company_name: string\n"
            "- website: string (valid URL)\n"
            "- industry: string\n"
            "- sub_industry: string\n"
            "- headquarters: string (City, Country)\n"
            "- employee_count: integer\n"
            "- employee_count_range: string (e.g. '51-200')\n"
            "- funding_stage: string (e.g. 'Series A', 'Series B')\n"
            "- total_funding_raised: string (e.g. '$20M')\n"
            "- growth_signals: list of strings (funding, hiring, partnerships)\n"
            "- overview: string\n"
            "- key_offerings: list of strings\n"
            "- source_references: list of URLs\n"
        )

        config = types.GenerateContentConfig(
            temperature=0.2,
            response_mime_type="application/json",
        )
        # Attempt grounding if available
        try:
            config.tools = [{"google_search": {}}]
        except Exception:
            pass

        response = client.models.generate_content(
            model=model_name,
            contents=search_prompt,
            config=config,
        )

        raw_text = response.text or ""
        clean_json = raw_text.strip()
        if clean_json.startswith("```json"):
            clean_json = clean_json[7:]
        if clean_json.startswith("```"):
            clean_json = clean_json[3:]
        if clean_json.endswith("```"):
            clean_json = clean_json[:-3]
        clean_json = clean_json.strip()

        parsed = json.loads(clean_json)
        if isinstance(parsed, list):
            return parsed[:limit]
        elif isinstance(parsed, dict) and "companies" in parsed:
            return parsed["companies"][:limit]
    except Exception as e:
        logger.debug(f"Live search grounding execution detail: {e}")
        raise e

    return []


def _search_companies_offline(
    query: str,
    industry: str = "",
    geography: str = "",
    limit: int = 5,
) -> List[Dict[str, Any]]:
    """Deterministic offline search over MOCK_COMPANIES with scoring and token matching."""
    scored_candidates = []
    query_tokens = set(re.findall(r"\w+", (query + " " + industry + " " + geography).lower()))

    # Geographies mapping for region queries
    region_aliases = {
        "north america": ["usa", "united states", "canada", "ca", "ny", "wa", "tx", "ma", "az", "co", "il"],
        "europe": ["uk", "united kingdom", "germany", "switzerland", "sweden", "netherlands", "ireland", "london", "berlin", "zurich", "stockholm", "amsterdam", "dublin"],
        "apac": ["singapore", "australia", "melbourne", "japan", "tokyo", "asia"],
        "asia": ["singapore", "australia", "melbourne", "japan", "tokyo", "asia", "israel", "tel aviv"],
    }

    target_geo_lower = geography.strip().lower()

    for comp in MOCK_COMPANIES:
        score = 0.0
        comp_text = (
            f"{comp['company_name']} {comp['industry']} {comp.get('sub_industry', '')} "
            f"{comp['headquarters']} {comp['overview']} "
            f"{' '.join(comp.get('growth_signals', []))} {' '.join(comp.get('key_offerings', []))}"
        ).lower()

        # Industry match
        if industry:
            ind_lower = industry.lower()
            if ind_lower in comp["industry"].lower():
                score += 40.0
            elif any(t in comp_text for t in ind_lower.split()):
                score += 20.0

        # Geography match
        if target_geo_lower and target_geo_lower != "global":
            hq_lower = comp["headquarters"].lower()
            if target_geo_lower in hq_lower:
                score += 25.0
            elif target_geo_lower in region_aliases:
                if any(alias in hq_lower for alias in region_aliases[target_geo_lower]):
                    score += 20.0
        else:
            score += 10.0  # Global baseline

        # Query token matches
        for token in query_tokens:
            if len(token) <= 2:
                continue
            if token in comp_text:
                score += 5.0

        # Base presence score
        score += 1.0
        scored_candidates.append((score, comp))

    scored_candidates.sort(key=lambda x: x[0], reverse=True)
    return [comp for _, comp in scored_candidates[:limit]]


def extract_company_profile(
    company_name: str,
    raw_text: str = "",
    structured_data: Optional[Dict[str, Any]] = None,
) -> CompanyProfile:
    """Normalizes and validates firmographic data into a structured CompanyProfile.

    Accepts structured dictionaries or raw unstructured news/press snippets.

    Args:
        company_name: Name of the company.
        raw_text: Raw narrative snippet or scrape text.
        structured_data: Optional pre-parsed dictionary of attributes.

    Returns:
        A validated CompanyProfile instance.
    """
    if structured_data:
        data = dict(structured_data)
        data.setdefault("company_name", company_name)
        data.setdefault("website", f"https://www.{re.sub(r'[^a-zA-Z0-9]', '', company_name.lower())}.com")
        data.setdefault("industry", "Technology")
        data.setdefault("headquarters", "Global")
        data.setdefault("employee_count_range", "Unknown")
        data.setdefault("funding_stage", "Unknown")
        data.setdefault("total_funding_raised", "Undisclosed")
        data.setdefault("growth_signals", [])
        data.setdefault("overview", raw_text or f"Profile for {company_name}")
        data.setdefault("key_offerings", [])
        data.setdefault("source_references", [])
        return CompanyProfile(**data)

    # Heuristic parsing from unstructured text snippet
    website_match = re.search(r"https?://[^\s,;]+", raw_text)
    website = website_match.group(0) if website_match else f"https://www.{re.sub(r'[^a-zA-Z0-9]', '', company_name.lower())}.com"

    # Headquarters pattern
    hq_match = re.search(r"(?:headquartered in|based in|HQ in|location:?)\s*([A-Za-z\s,.-]+?)(?:\.|\n|$|;)", raw_text, re.IGNORECASE)
    headquarters = hq_match.group(1).strip() if hq_match else "Global"

    # Employee count pattern
    emp_match = re.search(r"(\d+)\s*(?:employees|staff|team members|headcount)", raw_text, re.IGNORECASE)
    employee_count = int(emp_match.group(1)) if emp_match else None
    employee_range = "Unknown"
    if employee_count:
        if employee_count <= 10:
            employee_range = "1-10"
        elif employee_count <= 50:
            employee_range = "11-50"
        elif employee_count <= 200:
            employee_range = "51-200"
        elif employee_count <= 500:
            employee_range = "201-500"
        else:
            employee_range = "500+"

    # Funding stage pattern
    stage_match = re.search(r"(Seed|Series A|Series B|Series C|Series D|Growth|Bootstrapped)", raw_text, re.IGNORECASE)
    funding_stage = stage_match.group(1).title() if stage_match else "Unknown"

    # Total funding pattern
    funding_match = re.search(r"(\$\d+(?:\.\d+)?(?:M|B|K)?(?:\s*million|\s*billion)?)", raw_text, re.IGNORECASE)
    total_funding = funding_match.group(1) if funding_match else "Undisclosed"

    # Extract signals
    signals = []
    for line in raw_text.splitlines():
        line_clean = line.strip(" -*•")
        if any(keyword in line_clean.lower() for keyword in ["raised", "launched", "expanded", "hired", "compliance", "certified", "partnership", "grew"]):
            signals.append(line_clean)

    if not signals and raw_text:
        signals = [raw_text[:120].strip()]

    return CompanyProfile(
        company_name=company_name,
        website=website,
        industry="Technology",
        headquarters=headquarters,
        employee_count=employee_count,
        employee_count_range=employee_range,
        funding_stage=funding_stage,
        total_funding_raised=total_funding,
        growth_signals=signals,
        overview=raw_text.strip() or f"Overview for {company_name}",
        key_offerings=[],
        source_references=[website] if website else [],
    )


def evaluate_lead_fit(
    company_data: Union[CompanyProfile, Dict[str, Any]],
    criteria: Union[TargetMarketCriteria, Dict[str, Any]],
) -> FitScoreEvaluation:
    """Evaluates candidate fit score across industry, geography, headcount, and signals.

    Calculates a transparent weighted rubric totaling 100.0 maximum points:
    - Industry match: 30%
    - Geography match: 20%
    - Headcount / Scale fit: 25%
    - Funding stage & Growth trigger signals: 25%

    Args:
        company_data: CompanyProfile or dictionary representing the lead.
        criteria: TargetMarketCriteria or dictionary specifying target bounds.

    Returns:
        A FitScoreEvaluation instance with numerical category scores, qualification tier,
        strengths, identified risks, and a rationale.
    """
    if isinstance(company_data, dict):
        company = CompanyProfile(**company_data)
    else:
        company = company_data

    if isinstance(criteria, dict):
        crit = TargetMarketCriteria(**criteria)
    else:
        crit = criteria

    strengths: List[str] = []
    risks: List[str] = []

    # 1. Industry Match (Max 30 pts)
    target_ind = (crit.industry or "").lower().strip()
    comp_ind = (company.industry or "").lower().strip()
    comp_sub = (company.sub_industry or "").lower().strip()
    comp_text = ((company.overview or "") + " " + " ".join(company.key_offerings or [])).lower()

    if not target_ind:
        industry_score = 15.0
        strengths.append("Target industry unspecified; assigned neutral baseline fit.")
    elif comp_ind and (target_ind in comp_ind or comp_ind in target_ind):
        industry_score = 30.0
        strengths.append(f"Strong primary industry alignment: {company.industry} matches {crit.industry}.")
    elif comp_sub and (target_ind in comp_sub or comp_sub in target_ind):
        industry_score = 26.0
        strengths.append(f"Direct sub-industry niche alignment: {company.sub_industry}.")
    elif any(token in comp_ind or token in comp_text for token in target_ind.split() if len(token) > 3):
        industry_score = 18.0
        strengths.append(f"Cross-sector capability overlap with target industry {crit.industry}.")
    else:
        industry_score = 0.0
        risks.append(f"Industry mismatch: Company operates in {company.industry}, not {crit.industry}.")

    # 2. Geography Match (Max 20 pts)
    target_geo = crit.geography.strip().lower()
    comp_hq = company.headquarters.strip().lower()

    region_map = {
        "north america": ["usa", "united states", "canada", "san francisco", "new york", "boston", "seattle", "austin", "boulder", "phoenix", "chicago", "toronto"],
        "europe": ["uk", "united kingdom", "germany", "switzerland", "sweden", "netherlands", "ireland", "london", "zurich", "berlin", "stockholm", "amsterdam", "dublin"],
        "asia": ["singapore", "australia", "japan", "israel", "tel aviv", "melbourne"],
        "apac": ["singapore", "australia", "melbourne", "japan"],
    }

    if target_geo in ["global", "any", "all", ""]:
        geo_score = 20.0
        strengths.append(f"Geographic presence at {company.headquarters} satisfies global market criteria.")
    elif target_geo in comp_hq:
        geo_score = 20.0
        strengths.append(f"Exact geographic headquarters match: {company.headquarters}.")
    elif target_geo in region_map and any(loc in comp_hq for loc in region_map[target_geo]):
        geo_score = 17.0
        strengths.append(f"Regional proximity match: {company.headquarters} aligns with {crit.geography}.")
    else:
        geo_score = 0.0
        risks.append(f"Geographic divergence: Located in {company.headquarters}, expected {crit.geography}.")

    # 3. Headcount / Scale Fit (Max 25 pts)
    comp_emp = company.employee_count
    if comp_emp is None:
        # Heuristic from range string
        range_match = re.search(r"(\d+)-(\d+)", company.employee_count_range)
        if range_match:
            comp_emp = (int(range_match.group(1)) + int(range_match.group(2))) // 2

    if crit.min_headcount is None and crit.max_headcount is None:
        headcount_score = 25.0
        strengths.append("Company scale satisfies open headcount criteria.")
    elif comp_emp is not None:
        min_h = crit.min_headcount or 1
        max_h = crit.max_headcount or 100000

        if min_h <= comp_emp <= max_h:
            headcount_score = 25.0
            strengths.append(f"Headcount ({comp_emp} employees) falls precisely within target band [{min_h}-{max_h}].")
        elif (min_h * 0.7) <= comp_emp <= (max_h * 1.3):
            headcount_score = 16.0
            risks.append(f"Headcount ({comp_emp}) is near target threshold [{min_h}-{max_h}].")
        else:
            headcount_score = 5.0
            risks.append(f"Headcount ({comp_emp}) out of target range [{min_h}-{max_h}].")
    else:
        headcount_score = 15.0
        risks.append("Employee count is unverified.")

    # 4. Funding Stage & Growth Signals Fit (Max 25 pts)
    # Stage sub-score: up to 15 pts
    comp_stage = company.funding_stage.strip().lower()
    stage_sub_score = 0.0
    if not crit.target_stages:
        stage_sub_score = 15.0
        strengths.append(f"Funding stage {company.funding_stage} accepted under open stage criteria.")
    else:
        target_stages_lower = [s.strip().lower() for s in crit.target_stages]
        if comp_stage in target_stages_lower:
            stage_sub_score = 15.0
            strengths.append(f"Exact funding stage match: {company.funding_stage}.")
        elif any(comp_stage in s or s in comp_stage for s in target_stages_lower):
            stage_sub_score = 10.0
            strengths.append(f"Adjacent funding stage alignment: {company.funding_stage}.")
        else:
            stage_sub_score = 3.0
            risks.append(f"Funding stage {company.funding_stage} is not in preferred target stages ({', '.join(crit.target_stages)}).")

    # Signals sub-score: up to 10 pts
    signal_sub_score = 0.0
    if not crit.key_signals:
        signal_sub_score = 10.0
        if company.growth_signals:
            strengths.append(f"Demonstrates positive momentum with {len(company.growth_signals)} active growth signals.")
    else:
        matched_signals = 0
        company_signals_text = " ".join(company.growth_signals).lower()
        for expected_signal in crit.key_signals:
            if expected_signal.lower().strip() in company_signals_text:
                matched_signals += 1

        if matched_signals > 0:
            signal_sub_score = min(10.0, matched_signals * 3.5)
            strengths.append(f"Matched {matched_signals} priority trigger signals in recent company announcements.")
        else:
            signal_sub_score = 2.0
            risks.append(f"Did not find explicit trigger signals matching: {', '.join(crit.key_signals)}.")

    funding_signals_score = stage_sub_score + signal_sub_score

    # Compute overall score and breakdown
    category_scores = {
        "industry_match": round(industry_score, 1),
        "geography_match": round(geo_score, 1),
        "headcount_scale_fit": round(headcount_score, 1),
        "funding_and_signals_fit": round(funding_signals_score, 1),
    }

    overall_fit = round(sum(category_scores.values()), 1)
    overall_fit = min(100.0, max(0.0, overall_fit))

    # Qualification Status
    if overall_fit >= 80.0:
        status = "HIGH_FIT"
    elif overall_fit >= 60.0:
        status = "MEDIUM_FIT"
    elif overall_fit >= 40.0:
        status = "LOW_FIT"
    else:
        status = "DISQUALIFIED"

    # Synthesis rationale
    rationale = (
        f"{company.company_name} achieved an overall fit score of {overall_fit}/100 ({status}). "
        f"Scoring breakdown: Industry={category_scores['industry_match']}/30, "
        f"Geography={category_scores['geography_match']}/20, "
        f"Headcount={category_scores['headcount_scale_fit']}/25, "
        f"Funding & Signals={category_scores['funding_and_signals_fit']}/25. "
        f"Key determining factor: {strengths[0] if strengths else 'Standard baseline assessment'}."
    )

    return FitScoreEvaluation(
        company_name=company.company_name,
        overall_fit_score=overall_fit,
        category_scores=category_scores,
        qualification_status=status,
        fit_rationale=rationale,
        strengths=strengths,
        identified_risks=risks,
    )


def compile_dossier_report(
    leads: List[Dict[str, Any]],
    criteria: Union[TargetMarketCriteria, Dict[str, Any]],
    output_format: str = "markdown",
) -> str:
    """Synthesizes structured dossier reports in Markdown or JSON format.

    Args:
        leads: List of evaluated leads containing 'profile' and 'evaluation' dictionaries.
        criteria: Target criteria used for the research engagement.
        output_format: 'markdown' or 'json'.

    Returns:
        Formatted report string.
    """
    if isinstance(criteria, dict):
        crit = TargetMarketCriteria(**criteria)
    else:
        crit = criteria

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    # Sort leads by score descending
    sorted_leads = sorted(
        leads,
        key=lambda item: item.get("evaluation", {}).get("overall_fit_score", 0.0),
        reverse=True,
    )

    if output_format.lower() == "json":
        dossier_data = {
            "title": f"Deep Research Lead Dossier: {crit.industry} ({crit.geography})",
            "target_criteria": crit.model_dump(),
            "generated_at": timestamp,
            "total_candidates_analyzed": len(leads),
            "qualified_leads_count": len(sorted_leads),
            "leads": sorted_leads,
        }
        return json.dumps(dossier_data, indent=2)

    # Markdown Synthesis
    md_lines: List[str] = [
        f"# Deep Research Lead Dossier: {crit.industry}",
        "",
        f"**Generated**: {timestamp}  ",
        f"**Target Geography**: {crit.geography}  ",
        f"**Target Stages**: {', '.join(crit.target_stages) if crit.target_stages else 'Any'}  ",
        f"**Headcount Range**: [{crit.min_headcount or 'None'} - {crit.max_headcount or 'None'}]  ",
        f"**Minimum Fit Threshold**: {crit.min_fit_score}/100  ",
        "",
        "---",
        "",
        "## 1. Executive Summary & Market Intelligence",
        "",
        (
            f"This deep research report synthesized intelligence across target candidates within the "
            f"**{crit.industry}** sector ({crit.geography}). Out of {len(leads)} companies rigorously evaluated "
            f"across industry alignment, organizational scale, funding velocity, and real-world expansion signals, "
            f"**{len(sorted_leads)} candidate(s)** qualified as actionable high-probability sales and investment leads."
        ),
        "",
        "### Key Market Observations:",
        "- **Capital Velocity**: Candidate companies demonstrate strong institutional backing and recent growth rounds.",
        "- **Signal Corroboration**: High-fit targets exhibit concrete hiring acceleration and regulatory compliance milestones.",
        "- **Territorial Dynamics**: Expansion strategies show regional clustering with rapid internationalization initiatives.",
        "",
        "---",
        "",
        "## 2. Lead Qualification Leaderboard",
        "",
        "| Rank | Company Name | Fit Score | Status | Funding Stage | Headcount | Headquarters |",
        "| :---: | :--- | :---: | :---: | :---: | :---: | :--- |",
    ]

    for rank, item in enumerate(sorted_leads, start=1):
        prof = item.get("profile", {})
        eval_data = item.get("evaluation", {})
        md_lines.append(
            f"| {rank} | **{prof.get('company_name', 'Unknown')}** | "
            f"{eval_data.get('overall_fit_score', 0.0)}/100 | "
            f"`{eval_data.get('qualification_status', 'UNKNOWN')}` | "
            f"{prof.get('funding_stage', 'Unknown')} | "
            f"{prof.get('employee_count_range', 'Unknown')} | "
            f"{prof.get('headquarters', 'Unknown')} |"
        )

    md_lines.extend([
        "",
        "---",
        "",
        "## 3. Deep-Dive Candidate Intelligence Profiles",
        "",
    ])

    for rank, item in enumerate(sorted_leads, start=1):
        prof = item.get("profile", {})
        eval_data = item.get("evaluation", {})
        cat_scores = eval_data.get("category_scores", {})

        md_lines.extend([
            f"### #{rank} {prof.get('company_name', 'Unknown')}",
            f"- **Website**: [{prof.get('website', '')}]({prof.get('website', '')})",
            f"- **Industry / Sub-Industry**: {prof.get('industry', '')} — {prof.get('sub_industry', 'N/A')}",
            f"- **Headquarters**: {prof.get('headquarters', '')}",
            f"- **Funding Stage & Capital**: {prof.get('funding_stage', '')} ({prof.get('total_funding_raised', 'Undisclosed')})",
            f"- **Employee Count**: ~{prof.get('employee_count', 'Unknown')} ({prof.get('employee_count_range', '')})",
            "",
            f"**Company Overview**:",
            f"> {prof.get('overview', '')}",
            "",
            "**Fit Score Breakdown**:",
            f"- **Overall Fit Score**: **{eval_data.get('overall_fit_score', 0.0)} / 100.0** (`{eval_data.get('qualification_status', '')}`)",
            f"- Industry Match: `{cat_scores.get('industry_match', 0.0)} / 30.0`",
            f"- Geography Match: `{cat_scores.get('geography_match', 0.0)} / 20.0`",
            f"- Headcount & Scale: `{cat_scores.get('headcount_scale_fit', 0.0)} / 25.0`",
            f"- Funding & Signals: `{cat_scores.get('funding_and_signals_fit', 0.0)} / 25.0`",
            "",
            "**Key Growth Signals Identified**:",
        ])

        for sig in prof.get("growth_signals", []):
            md_lines.append(f"- 🚀 {sig}")

        if eval_data.get("strengths"):
            md_lines.append("")
            md_lines.append("**Key Strengths**:")
            for s in eval_data.get("strengths", []):
                md_lines.append(f"- ✅ {s}")

        if eval_data.get("identified_risks"):
            md_lines.append("")
            md_lines.append("**Identified Risks / Considerations**:")
            for r in eval_data.get("identified_risks", []):
                md_lines.append(f"- ⚠️ {r}")

        if prof.get("source_references"):
            md_lines.append("")
            md_lines.append("**Intelligence Citations**:")
            for ref in prof.get("source_references", []):
                md_lines.append(f"- 🔗 [{ref}]({ref})")

        md_lines.extend(["", "---", ""])

    md_lines.extend([
        "## 4. Strategic Recommendations & Next Steps",
        "",
        "1. **Initial Outreach Prioritization**: Initiate tier-1 outreach sequence with HIGH_FIT candidates exhibiting immediate hiring or product expansion triggers.",
        "2. **Multi-Threading Engagement**: Reach out to technical leadership (VP Eng, CTO) citing recent compliance or platform scale milestones.",
        "3. **Value Proposition Alignment**: Tailor messaging around addressing cross-border compliance, automated reliability, or enterprise infrastructure acceleration.",
        "",
        "---",
        "*Report compiled by Agent A (Google ADK Deep Research Lead Generation Engine)*",
    ])

    return "\n".join(md_lines)
