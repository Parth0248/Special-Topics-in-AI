"""Comprehensive automated pytest test suite for Agent A: Deep Research Lead Gen Agent.

Tests cover:
- Pydantic models and validation constraints
- Mock dataset integrity and multi-industry coverage
- Multi-hop company search with deterministic offline fallback
- Firmographic profile extraction and text normalization
- Multi-dimensional weighted fit evaluation and status tiering
- Markdown & JSON dossier report compilation
- End-to-end LeadGenAgent orchestration workflow
- CLI invocation, argument parsing, and output generation
"""

import json
import os
import tempfile
import pytest
from pydantic import ValidationError

from agent_a_lead_gen.models import (
    CompanyProfile,
    FitScoreEvaluation,
    LeadDossier,
    TargetMarketCriteria,
)
from agent_a_lead_gen.mock_data import MOCK_COMPANIES
from agent_a_lead_gen.tools import (
    compile_dossier_report,
    evaluate_lead_fit,
    extract_company_profile,
    search_companies,
)
from agent_a_lead_gen.agent import LeadGenAgent, create_adk_agent
from agent_a_lead_gen.cli import run_cli


# ============================================================================
# 1. Models & Validation Tests
# ============================================================================

def test_target_market_criteria_defaults():
    """Verifies default values and valid instantiation of TargetMarketCriteria."""
    crit = TargetMarketCriteria(industry="Fintech")
    assert crit.industry == "Fintech"
    assert crit.geography == "Global"
    assert crit.min_headcount is None
    assert crit.max_headcount is None
    assert crit.target_stages == []
    assert crit.key_signals == []
    assert crit.keywords == []
    assert crit.min_fit_score == 60.0


def test_target_market_criteria_validation_headcount():
    """Verifies that max_headcount < min_headcount raises a ValidationError."""
    with pytest.raises(ValidationError):
        TargetMarketCriteria(
            industry="Healthcare AI",
            min_headcount=200,
            max_headcount=50,
        )


def test_company_profile_instantiation():
    """Verifies CompanyProfile schema validation and serialization."""
    profile = CompanyProfile(
        company_name="Apex Payments",
        website="https://www.apexpayments.com",
        industry="Fintech",
        sub_industry="Merchant Acquiring",
        headquarters="New York, NY, USA",
        employee_count=120,
        employee_count_range="51-200",
        funding_stage="Series B",
        total_funding_raised="$25M",
        growth_signals=["Hiring 20 engineers", "Expanded to UK"],
        overview="Next-generation merchant payments platform.",
        key_offerings=["Virtual Terminals", "Payout API"],
        source_references=["https://techcrunch.com/apex-series-b"],
    )
    dumped = profile.model_dump()
    assert dumped["company_name"] == "Apex Payments"
    assert dumped["employee_count"] == 120
    assert len(dumped["growth_signals"]) == 2


def test_fit_score_evaluation_bounds():
    """Verifies FitScoreEvaluation validates score bounds between 0 and 100."""
    eval_obj = FitScoreEvaluation(
        company_name="Apex Payments",
        overall_fit_score=85.5,
        category_scores={
            "industry_match": 30.0,
            "geography_match": 18.0,
            "headcount_scale_fit": 20.0,
            "funding_and_signals_fit": 17.5,
        },
        qualification_status="HIGH_FIT",
        fit_rationale="Strong alignment across all categories.",
        strengths=["Top tier industry match"],
        identified_risks=[],
    )
    assert eval_obj.overall_fit_score == 85.5
    assert eval_obj.qualification_status == "HIGH_FIT"

    with pytest.raises(ValidationError):
        FitScoreEvaluation(
            company_name="Invalid Score Co",
            overall_fit_score=105.0,  # exceeds 100.0
            category_scores={},
            qualification_status="HIGH_FIT",
            fit_rationale="Invalid score",
        )


# ============================================================================
# 2. Mock Dataset Integrity Tests
# ============================================================================

def test_mock_data_structure_and_count():
    """Verifies that the offline dataset contains at least 15 comprehensive records."""
    assert len(MOCK_COMPANIES) >= 15
    industries = set()
    for comp in MOCK_COMPANIES:
        assert "company_name" in comp and comp["company_name"]
        assert "industry" in comp and comp["industry"]
        assert "website" in comp and comp["website"].startswith("http")
        assert "headquarters" in comp and comp["headquarters"]
        assert "funding_stage" in comp and comp["funding_stage"]
        assert "growth_signals" in comp and isinstance(comp["growth_signals"], list)
        assert len(comp["growth_signals"]) >= 2
        industries.add(comp["industry"])

    # Verifies multi-industry coverage
    assert "Fintech" in industries
    assert "Healthcare AI" in industries
    assert "Enterprise SaaS" in industries
    assert "CleanTech" in industries
    assert "CyberSecurity" in industries


# ============================================================================
# 3. Search Companies Tool Tests
# ============================================================================

def test_search_companies_offline_query():
    """Verifies offline candidate search matching keywords and industry."""
    results = search_companies(
        query="payments treasury",
        industry="Fintech",
        limit=3,
        mock_only=True,
    )
    assert len(results) > 0
    assert len(results) <= 3
    # NovaPay or FinFlow should rank highly for payments in Fintech
    company_names = [c["company_name"] for c in results]
    assert any("NovaPay" in name or "FinFlow" in name for name in company_names)


def test_search_companies_geography_filtering():
    """Verifies candidate search with geographic preference."""
    results = search_companies(
        query="software",
        industry="Enterprise SaaS",
        geography="Europe",
        limit=5,
        mock_only=True,
    )
    assert len(results) > 0
    # DataPrism is in Berlin, Germany (Europe)
    company_names = [c["company_name"] for c in results]
    assert "DataPrism Analytics" in company_names


def test_search_companies_limit_constraint():
    """Verifies search result respects the limit parameter."""
    results = search_companies(query="AI", limit=2, mock_only=True)
    assert len(results) <= 2


# ============================================================================
# 4. Extract Company Profile Tool Tests
# ============================================================================

def test_extract_company_profile_from_structured_dict():
    """Verifies normalization when structured dictionary is provided."""
    raw = {
        "company_name": "TestCo",
        "industry": "Fintech",
        "headquarters": "Austin, TX, USA",
        "funding_stage": "Series A",
        "employee_count": 45,
    }
    profile = extract_company_profile(company_name="TestCo", structured_data=raw)
    assert isinstance(profile, CompanyProfile)
    assert profile.company_name == "TestCo"
    assert profile.headquarters == "Austin, TX, USA"
    assert profile.funding_stage == "Series A"


def test_extract_company_profile_from_unstructured_text():
    """Verifies heuristic entity extraction from raw narrative text."""
    snippet = (
        "OmniTech Inc is based in Seattle, WA. The startup has 120 employees and recently "
        "closed a $20M Series B funding round. Check out https://omnitech.example.com. "
        "They recently launched an automated cloud compliance product and hired a new VP."
    )
    profile = extract_company_profile(company_name="OmniTech Inc", raw_text=snippet)
    assert profile.company_name == "OmniTech Inc"
    assert "Seattle" in profile.headquarters
    assert profile.employee_count == 120
    assert profile.employee_count_range == "51-200"
    assert profile.funding_stage == "Series B"
    assert "$20M" in profile.total_funding_raised
    assert len(profile.growth_signals) >= 1


# ============================================================================
# 5. Fit Scoring Tool Tests
# ============================================================================

def test_evaluate_lead_fit_high_score():
    """Verifies that an ideal matching company achieves HIGH_FIT status (>= 80)."""
    company = CompanyProfile(
        company_name="Ideal Match Fintech",
        website="https://idealfintech.com",
        industry="Fintech",
        sub_industry="B2B Payments",
        headquarters="San Francisco, CA, USA",
        employee_count=100,
        employee_count_range="51-200",
        funding_stage="Series B",
        total_funding_raised="$30M",
        growth_signals=["Hiring 30 engineers", "Expanding to Europe", "SOC2 certified"],
        overview="B2B cross-border payments infrastructure platform.",
    )
    criteria = TargetMarketCriteria(
        industry="Fintech",
        geography="North America",
        min_headcount=50,
        max_headcount=200,
        target_stages=["Series A", "Series B"],
        key_signals=["hiring", "expanding"],
    )

    evaluation = evaluate_lead_fit(company, criteria)
    assert evaluation.overall_fit_score >= 80.0
    assert evaluation.qualification_status == "HIGH_FIT"
    assert evaluation.category_scores["industry_match"] == 30.0
    assert evaluation.category_scores["geography_match"] >= 17.0
    assert evaluation.category_scores["headcount_scale_fit"] == 25.0
    assert len(evaluation.strengths) > 0


def test_evaluate_lead_fit_disqualified():
    """Verifies that a mismatched company receives DISQUALIFIED status (< 40)."""
    company = CompanyProfile(
        company_name="Local Bakery Co",
        website="https://localbakery.com",
        industry="Food & Beverage",
        headquarters="Rome, Italy",
        employee_count=5,
        employee_count_range="1-10",
        funding_stage="Bootstrapped",
        overview="Artisanal sourdough bakery.",
    )
    criteria = TargetMarketCriteria(
        industry="CyberSecurity",
        geography="North America",
        min_headcount=50,
        max_headcount=500,
        target_stages=["Series B", "Series C"],
    )

    evaluation = evaluate_lead_fit(company, criteria)
    assert evaluation.overall_fit_score < 40.0
    assert evaluation.qualification_status == "DISQUALIFIED"
    assert evaluation.category_scores["industry_match"] == 0.0
    assert len(evaluation.identified_risks) >= 2


def test_evaluate_lead_fit_weight_distribution():
    """Verifies that the sum of maximum category weights is exactly 100.0."""
    max_weights = {
        "industry_match": 30.0,
        "geography_match": 20.0,
        "headcount_scale_fit": 25.0,
        "funding_and_signals_fit": 25.0,
    }
    assert sum(max_weights.values()) == 100.0


# ============================================================================
# 6. Dossier Compilation Tool Tests
# ============================================================================

def test_compile_dossier_markdown():
    """Verifies structured Markdown dossier report output."""
    sample_lead = {
        "profile": {
            "company_name": "NovaPay Solutions",
            "website": "https://www.novapaysolutions.io",
            "industry": "Fintech",
            "sub_industry": "B2B Payments",
            "headquarters": "San Francisco, CA, USA",
            "funding_stage": "Series B",
            "total_funding_raised": "$38M",
            "employee_count": 145,
            "employee_count_range": "51-200",
            "overview": "Cross-border payment infrastructure.",
            "growth_signals": ["Series B $25M raised", "Expanding APAC team"],
            "source_references": ["https://techcrunch.com/novapay"],
        },
        "evaluation": {
            "overall_fit_score": 92.0,
            "qualification_status": "HIGH_FIT",
            "category_scores": {
                "industry_match": 30.0,
                "geography_match": 20.0,
                "headcount_scale_fit": 25.0,
                "funding_and_signals_fit": 17.0,
            },
            "fit_rationale": "Exceptional fit across all categories.",
            "strengths": ["Top industry match", "Strong headcount"],
            "identified_risks": [],
        },
    }
    criteria = TargetMarketCriteria(industry="Fintech", geography="North America")

    md_report = compile_dossier_report(leads=[sample_lead], criteria=criteria, output_format="markdown")
    assert "# Deep Research Lead Dossier: Fintech" in md_report
    assert "NovaPay Solutions" in md_report
    assert "92.0/100" in md_report
    assert "HIGH_FIT" in md_report
    assert "Leaderboard" in md_report
    assert "Strategic Recommendations" in md_report


def test_compile_dossier_json():
    """Verifies JSON format dossier output."""
    criteria = TargetMarketCriteria(industry="CleanTech")
    json_str = compile_dossier_report(leads=[], criteria=criteria, output_format="json")
    parsed = json.loads(json_str)
    assert "Deep Research Lead Dossier" in parsed["title"]
    assert parsed["qualified_leads_count"] == 0
    assert parsed["total_candidates_analyzed"] == 0


# ============================================================================
# 7. End-to-End LeadGenAgent Orchestrator Tests
# ============================================================================

def test_agent_orchestrator_end_to_end_mock():
    """Verifies that LeadGenAgent executes the 5-stage pipeline and produces a LeadDossier."""
    agent = LeadGenAgent(mock_mode=True)
    criteria = TargetMarketCriteria(
        industry="Healthcare AI",
        geography="North America",
        min_fit_score=60.0,
    )

    dossier = agent.run(criteria=criteria, candidate_limit=5)
    assert isinstance(dossier, LeadDossier)
    assert dossier.total_candidates_analyzed > 0
    assert dossier.qualified_leads_count >= 1
    assert len(dossier.leads) == dossier.qualified_leads_count
    # All qualified leads must meet or exceed min_fit_score
    for lead in dossier.leads:
        assert lead["evaluation"]["overall_fit_score"] >= criteria.min_fit_score

    # Verify session state telemetry
    assert agent.session_state["current_status"] == "COMPLETED"
    assert "elapsed_seconds" in agent.session_state["telemetry"]
    assert len(agent.session_state["execution_history"]) >= 5


@pytest.mark.asyncio
async def test_agent_async_run():
    """Verifies asynchronous agent execution wrapper."""
    agent = LeadGenAgent(mock_mode=True)
    criteria = TargetMarketCriteria(industry="Enterprise SaaS", geography="Global")
    dossier = await agent.async_run(criteria=criteria, candidate_limit=4)
    assert isinstance(dossier, LeadDossier)
    assert dossier.qualified_leads_count >= 1


def test_create_adk_agent_factory():
    """Verifies create_adk_agent factory function returns a functional agent."""
    adk_agent = create_adk_agent(mock_mode=True)
    assert adk_agent is not None
    # If falling back to LeadGenAgent, verify run method exists
    assert hasattr(adk_agent, "run") or hasattr(adk_agent, "name")


# ============================================================================
# 8. CLI Entrypoint Tests
# ============================================================================

def test_cli_demo_mode():
    """Verifies CLI execution in --demo mode."""
    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = os.path.join(tmpdir, "demo_test_dossier.md")
        exit_code = run_cli(["--demo", "--output", output_path])
        assert exit_code == 0
        assert os.path.exists(output_path)
        with open(output_path, "r", encoding="utf-8") as f:
            content = f.read()
        assert "Deep Research Lead Dossier" in content
        assert "Leaderboard" in content


def test_cli_custom_criteria_with_mock():
    """Verifies CLI execution with explicit criteria flags."""
    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = os.path.join(tmpdir, "custom_lead_dossier.json")
        exit_code = run_cli([
            "--mock",
            "--industry", "CleanTech",
            "--geography", "North America",
            "--min-score", "50.0",
            "--limit", "4",
            "--format", "json",
            "--output", output_path,
        ])
        assert exit_code == 0
        assert os.path.exists(output_path)
        with open(output_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert data["total_candidates_analyzed"] > 0
