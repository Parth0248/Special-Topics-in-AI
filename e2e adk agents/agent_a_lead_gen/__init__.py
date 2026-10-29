"""Agent A: Deep Research Lead Generation Agent (Google ADK).

Exports key models, tools, and the orchestrator agent.
"""

from .agent import LeadGenAgent, create_adk_agent
from .models import (
    CategoryScoreBreakdown,
    CompanyProfile,
    FitScoreEvaluation,
    LeadDossier,
    TargetMarketCriteria,
)
from .tools import (
    compile_dossier_report,
    evaluate_lead_fit,
    extract_company_profile,
    search_companies,
)

__all__ = [
    "LeadGenAgent",
    "create_adk_agent",
    "TargetMarketCriteria",
    "CompanyProfile",
    "FitScoreEvaluation",
    "CategoryScoreBreakdown",
    "LeadDossier",
    "search_companies",
    "extract_company_profile",
    "evaluate_lead_fit",
    "compile_dossier_report",
]
