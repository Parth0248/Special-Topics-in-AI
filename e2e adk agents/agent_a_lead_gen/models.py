"""Data models for Agent A: Deep Research Lead Generation Agent.

Defines Pydantic schemas for target market criteria, company profiles,
fit evaluations, and structured lead dossiers.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field, field_validator


class TargetMarketCriteria(BaseModel):
    """Specification of target customer or investment criteria for research."""

    industry: str = Field(
        ...,
        description="Target industry sector (e.g., 'Fintech', 'Healthcare AI', 'Enterprise SaaS').",
    )
    geography: str = Field(
        default="Global",
        description="Target geographic region or country (e.g., 'North America', 'Europe', 'Global').",
    )
    min_headcount: Optional[int] = Field(
        default=None,
        description="Minimum number of employees.",
        ge=1,
    )
    max_headcount: Optional[int] = Field(
        default=None,
        description="Maximum number of employees.",
        ge=1,
    )
    target_stages: List[str] = Field(
        default_factory=list,
        description="Target funding stages (e.g., ['Seed', 'Series A', 'Series B']).",
    )
    key_signals: List[str] = Field(
        default_factory=list,
        description="Specific growth signals sought (e.g., ['hiring', 'expansion', 'SOC2']).",
    )
    keywords: List[str] = Field(
        default_factory=list,
        description="Search keywords and product themes.",
    )
    min_fit_score: float = Field(
        default=60.0,
        ge=0.0,
        le=100.0,
        description="Minimum overall fit score (0-100) to qualify as a lead.",
    )

    @field_validator("max_headcount")
    @classmethod
    def validate_headcount_range(cls, v: Optional[int], info) -> Optional[int]:
        """Ensures max_headcount is greater than or equal to min_headcount if both are given."""
        min_val = info.data.get("min_headcount")
        if v is not None and min_val is not None and v < min_val:
            raise ValueError(f"max_headcount ({v}) cannot be less than min_headcount ({min_val})")
        return v


class CompanyProfile(BaseModel):
    """Structured firmographic profile of a candidate company."""

    company_name: str = Field(..., description="Legal or common name of the company.")
    website: str = Field(..., description="Company official website URL.")
    industry: str = Field(..., description="Primary industry sector.")
    sub_industry: Optional[str] = Field(default=None, description="Sub-sector or niche specialty.")
    headquarters: str = Field(..., description="Location of company headquarters (City, Country/State).")
    employee_count: Optional[int] = Field(default=None, description="Estimated total employee count.")
    employee_count_range: str = Field(
        default="Unknown",
        description="Employee band (e.g., '11-50', '51-200', '201-500').",
    )
    funding_stage: str = Field(default="Unknown", description="Current funding stage.")
    total_funding_raised: str = Field(
        default="Undisclosed",
        description="Estimated total funding raised (e.g., '$15M').",
    )
    growth_signals: List[str] = Field(
        default_factory=list,
        description="Identified growth triggers and expansion signals.",
    )
    overview: str = Field(default="", description="Executive summary of business and offering.")
    key_offerings: List[str] = Field(
        default_factory=list,
        description="Key products, services, or technical capabilities.",
    )
    source_references: List[str] = Field(
        default_factory=list,
        description="Citation URLs or source references used to construct the profile.",
    )


class CategoryScoreBreakdown(BaseModel):
    """Detailed category breakdown of the weighted fit score."""

    industry_match: float = Field(
        ...,
        ge=0.0,
        le=30.0,
        description="Industry alignment score (weight: 30%).",
    )
    geography_match: float = Field(
        ...,
        ge=0.0,
        le=20.0,
        description="Geographic alignment score (weight: 20%).",
    )
    headcount_scale_fit: float = Field(
        ...,
        ge=0.0,
        le=25.0,
        description="Headcount & organizational scale fit score (weight: 25%).",
    )
    funding_and_signals_fit: float = Field(
        ...,
        ge=0.0,
        le=25.0,
        description="Funding stage & growth trigger signals fit score (weight: 25%).",
    )


class FitScoreEvaluation(BaseModel):
    """Evaluation output detailing lead qualification and scoring."""

    company_name: str = Field(..., description="Name of evaluated company.")
    overall_fit_score: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description="Aggregate weighted fit score from 0.0 to 100.0.",
    )
    category_scores: Dict[str, float] = Field(
        ...,
        description="Mapping of category name to numerical score.",
    )
    qualification_status: Literal["HIGH_FIT", "MEDIUM_FIT", "LOW_FIT", "DISQUALIFIED"] = Field(
        ...,
        description="Qualification tier based on overall score.",
    )
    fit_rationale: str = Field(..., description="Detailed explanation of scoring determination.")
    strengths: List[str] = Field(
        default_factory=list,
        description="Key reasons for positive alignment with target criteria.",
    )
    identified_risks: List[str] = Field(
        default_factory=list,
        description="Risks, gaps, or mismatch areas identified during research.",
    )


class LeadDossier(BaseModel):
    """Comprehensive synthesized dossier report summarizing research findings."""

    title: str = Field(..., description="Report title.")
    target_criteria: TargetMarketCriteria = Field(..., description="Input search criteria applied.")
    generated_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="ISO 8601 UTC timestamp of report generation.",
    )
    total_candidates_analyzed: int = Field(
        ...,
        ge=0,
        description="Total number of candidates discovered and evaluated.",
    )
    qualified_leads_count: int = Field(
        ...,
        ge=0,
        description="Count of candidates meeting or exceeding min_fit_score.",
    )
    leads: List[Dict[str, Any]] = Field(
        ...,
        description="List of qualified lead entries with profile and evaluation data.",
    )
    market_insights_summary: str = Field(
        ...,
        description="Macro market trends, competitive observations, and synthesis.",
    )
    next_steps: List[str] = Field(
        default_factory=list,
        description="Actionable sales or outreach recommendations.",
    )
    markdown_report: Optional[str] = Field(
        default=None,
        description="Full rendered Markdown report string.",
    )
