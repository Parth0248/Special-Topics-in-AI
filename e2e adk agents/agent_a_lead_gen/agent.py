"""Agent A: Deep Research Lead Generation Agent.

Modeled on Google's Deep Research multi-agent architecture and Google ADK patterns
(e.g., leadGenerationAgentADK). Coordinates multi-hop company search, firmographic
normalization, multi-dimensional lead fit evaluation, and markdown dossier synthesis.
"""

import asyncio
import logging
import os
import time
from typing import Any, Callable, Dict, List, Optional

try:
    from .models import (
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
except (ImportError, ValueError):
    from models import (
        CompanyProfile,
        FitScoreEvaluation,
        LeadDossier,
        TargetMarketCriteria,
    )
    from tools import (
        compile_dossier_report,
        evaluate_lead_fit,
        extract_company_profile,
        search_companies,
    )

logger = logging.getLogger(__name__)


class LeadGenAgent:
    """Deep Research Lead Generation Agent orchestrator using Google ADK paradigms."""

    def __init__(
        self,
        model_name: Optional[str] = None,
        mock_mode: bool = False,
        progress_callback: Optional[Callable[[str, int, int], None]] = None,
    ):
        """Initializes the LeadGenAgent.

        Args:
            model_name: Gemini model identifier (defaults to HARNESS_MODEL or 'gemini-2.5-flash').
            mock_mode: If True, forces deterministic local execution over curated mock data.
            progress_callback: Optional callback(stage_name, step, total_steps) for UI progress updates.
        """
        self.model_name = model_name or os.environ.get("HARNESS_MODEL", "gemini-2.5-flash")
        self.mock_mode = mock_mode
        self.progress_callback = progress_callback
        self.session_state: Dict[str, Any] = {
            "execution_history": [],
            "current_status": "IDLE",
            "telemetry": {},
        }

    def _notify_progress(self, stage: str, step: int, total_steps: int = 5) -> None:
        """Emits progress telemetry to the callback if registered."""
        self.session_state["current_status"] = stage
        self.session_state["execution_history"].append({
            "stage": stage,
            "step": step,
            "timestamp": time.time(),
        })
        if self.progress_callback:
            try:
                self.progress_callback(stage, step, total_steps)
            except Exception as e:
                logger.debug(f"Progress callback notification error: {e}")

    def run(
        self,
        criteria: TargetMarketCriteria,
        candidate_limit: int = 10,
        mock_mode: Optional[bool] = None,
    ) -> LeadDossier:
        """Executes the complete synchronous 5-stage deep research lead generation pipeline.

        Pipeline Stages:
        1. Planning & Query Expansion
        2. Multi-Hop Candidate Discovery
        3. Firmographic Extraction & Normalization
        4. Fit Scoring, Weight Calculation & Risk Identification
        5. Dossier Synthesis & Report Generation

        Args:
            criteria: TargetMarketCriteria defining the search scope and parameters.
            candidate_limit: Maximum candidates to discover and evaluate.
            mock_mode: Override instance mock_mode setting.

        Returns:
            A populated LeadDossier with ranked qualified leads and insights.
        """
        start_time = time.time()
        effective_mock = self.mock_mode if mock_mode is None else mock_mode

        logger.info(f"Starting Deep Research for industry='{criteria.industry}', geo='{criteria.geography}'")

        # Stage 1: Planning & Query Expansion
        self._notify_progress("Planning & Keyword Expansion", 1, 5)
        search_terms = self._generate_search_terms(criteria)

        # Stage 2: Multi-Hop Candidate Discovery
        self._notify_progress(f"Multi-Hop Candidate Discovery (Target: {candidate_limit})", 2, 5)
        raw_candidates = self._discover_candidates(criteria, search_terms, candidate_limit, effective_mock)

        # Stage 3: Firmographic Extraction & Normalization
        self._notify_progress(f"Firmographic Extraction ({len(raw_candidates)} profiles)", 3, 5)
        normalized_profiles = self._extract_profiles(raw_candidates)

        # Stage 4: Weighted Fit Scoring & Risk Analysis
        self._notify_progress(f"Evaluating Lead Fit & Qualification Rubric", 4, 5)
        evaluated_leads = self._evaluate_leads(normalized_profiles, criteria)

        # Filter qualified leads meeting min_fit_score
        qualified_leads = [
            lead for lead in evaluated_leads
            if lead["evaluation"]["overall_fit_score"] >= criteria.min_fit_score
        ]

        # Stage 5: Synthesis & Dossier Compilation
        self._notify_progress(f"Synthesizing Dossier ({len(qualified_leads)} qualified)", 5, 5)
        markdown_report = compile_dossier_report(
            leads=qualified_leads,
            criteria=criteria,
            output_format="markdown",
        )

        elapsed = time.time() - start_time
        self.session_state["telemetry"] = {
            "elapsed_seconds": round(elapsed, 2),
            "candidates_discovered": len(raw_candidates),
            "qualified_count": len(qualified_leads),
            "mock_mode": effective_mock,
        }
        self.session_state["current_status"] = "COMPLETED"

        dossier = LeadDossier(
            title=f"Deep Research Lead Dossier: {criteria.industry} ({criteria.geography})",
            target_criteria=criteria,
            total_candidates_analyzed=len(raw_candidates),
            qualified_leads_count=len(qualified_leads),
            leads=qualified_leads,
            market_insights_summary=(
                f"Evaluated {len(raw_candidates)} potential candidates in {criteria.industry}. "
                f"{len(qualified_leads)} targets satisfied the minimum qualification threshold "
                f"of {criteria.min_fit_score}/100."
            ),
            next_steps=[
                "Schedule qualification calls with identified HIGH_FIT accounts.",
                "Verify recent expansion announcements through executive LinkedIn networks.",
                "Review enterprise compliance requirements and alignment.",
            ],
            markdown_report=markdown_report,
        )

        return dossier

    async def async_run(
        self,
        criteria: TargetMarketCriteria,
        candidate_limit: int = 10,
        mock_mode: Optional[bool] = None,
    ) -> LeadDossier:
        """Asynchronous execution wrapper for LeadGenAgent."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            self.run,
            criteria,
            candidate_limit,
            mock_mode,
        )

    def _generate_search_terms(self, criteria: TargetMarketCriteria) -> List[str]:
        """Expands input criteria into comprehensive search keyword queries."""
        terms = [criteria.industry]
        if criteria.keywords:
            terms.extend(criteria.keywords)
        if criteria.key_signals:
            terms.extend(criteria.key_signals[:2])
        return terms

    def _discover_candidates(
        self,
        criteria: TargetMarketCriteria,
        search_terms: List[str],
        limit: int,
        mock_mode: bool,
    ) -> List[Dict[str, Any]]:
        """Executes candidate searches across queries, deduplicating by company name."""
        candidates_by_name: Dict[str, Dict[str, Any]] = {}

        # Primary query combining industry and keywords
        primary_query = f"{criteria.industry} {' '.join(criteria.keywords)}".strip()
        results = search_companies(
            query=primary_query,
            industry=criteria.industry,
            geography=criteria.geography,
            limit=limit,
            mock_only=mock_mode,
        )

        for comp in results:
            name = comp.get("company_name", "").strip().lower()
            if name and name not in candidates_by_name:
                candidates_by_name[name] = comp

        # If secondary queries needed to reach limit
        if len(candidates_by_name) < limit and criteria.keywords:
            for kw in criteria.keywords:
                secondary_results = search_companies(
                    query=kw,
                    industry=criteria.industry,
                    geography=criteria.geography,
                    limit=limit - len(candidates_by_name),
                    mock_only=mock_mode,
                )
                for comp in secondary_results:
                    name = comp.get("company_name", "").strip().lower()
                    if name and name not in candidates_by_name:
                        candidates_by_name[name] = comp
                if len(candidates_by_name) >= limit:
                    break

        return list(candidates_by_name.values())[:limit]

    def _extract_profiles(self, raw_candidates: List[Dict[str, Any]]) -> List[CompanyProfile]:
        """Normalizes each candidate record into a verified CompanyProfile."""
        profiles = []
        for cand in raw_candidates:
            try:
                prof = extract_company_profile(
                    company_name=cand.get("company_name", "Unknown Company"),
                    structured_data=cand,
                )
                profiles.append(prof)
            except Exception as e:
                logger.warning(f"Error normalizing company candidate {cand}: {e}")
        return profiles

    def _evaluate_leads(
        self,
        profiles: List[CompanyProfile],
        criteria: TargetMarketCriteria,
    ) -> List[Dict[str, Any]]:
        """Calculates multi-dimensional fit scores and structures output records."""
        evaluated = []
        for prof in profiles:
            evaluation = evaluate_lead_fit(prof, criteria)
            evaluated.append({
                "profile": prof.model_dump(),
                "evaluation": evaluation.model_dump(),
            })

        # Sort descending by score
        evaluated.sort(
            key=lambda x: x["evaluation"]["overall_fit_score"],
            reverse=True,
        )
        return evaluated


def create_adk_agent(mock_mode: bool = False) -> Any:
    """Builds a Google ADK-compatible Agent wrapper or returns LeadGenAgent.

    Attempts to use google.adk if available in the environment; otherwise returns
    the native LeadGenAgent implementing Google ADK tool and runner contracts.
    """
    try:
        from google.adk.agents import Agent
        from google.adk.tools import FunctionTool

        tools = [
            FunctionTool(search_companies),
            FunctionTool(extract_company_profile),
            FunctionTool(evaluate_lead_fit),
            FunctionTool(compile_dossier_report),
        ]

        adk_agent = Agent(
            name="lead_generation_agent",
            description="Autonomous deep research agent for B2B target market research and lead fit scoring.",
            tools=tools,
        )
        return adk_agent
    except ImportError:
        # Graceful compatibility return
        return LeadGenAgent(mock_mode=mock_mode)
