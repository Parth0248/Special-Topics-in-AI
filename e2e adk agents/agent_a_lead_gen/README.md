# Agent A: Deep Research Lead Generation Agent (Google ADK)

A production-grade autonomous deep research multi-agent application built with the **Google Agent Development Kit (ADK)** and the Gemini model family. Modeled after Google's deep research multi-agent architecture and reference implementations (`leadGenerationAgentADK`).

---

## 1. Overview & Architecture

Agent A automates complex market discovery and high-probability B2B lead generation. Instead of basic scraping, it executes a 5-stage research workflow combining intent decomposition, candidate discovery, firmographic normalization, multi-dimensional weighted fit evaluation, and markdown dossier synthesis.

```
                              +---------------------------------------+
                              |      TargetMarketCriteria Input       |
                              |  (Industry, Geo, Headcount, Signals)  |
                              +---------------------------------------+
                                                  |
                                                  v
                                      [Stage 1: Planning]
                                      Keyword expansion &
                                      search query planning
                                                  |
                                                  v
                                 [Stage 2: Candidate Discovery]
                                       search_companies()
                                                  |
                      +---------------------------+---------------------------+
                      |                                                       |
                      v                                                       v
         [Live Search Grounding]                                     [Deterministic Fallback]
          Google Gemini Search                                        Curated Mock Dataset
            Tool Grounding                                             (20 Rich Profiles)
                      |                                                       |
                      +---------------------------+---------------------------+
                                                  |
                                                  v
                               [Stage 3: Firmographic Extraction]
                                   extract_company_profile()
                                                  |
                                                  v
                                 [Stage 4: Weighted Fit Scoring]
                                       evaluate_lead_fit()
                                 (30% Ind, 20% Geo, 25% Scale,
                                      25% Funding/Signals)
                                                  |
                                                  v
                                 [Stage 5: Dossier Synthesis]
                                   compile_dossier_report()
                                                  |
                                                  v
                             +-----------------------------------------+
                             |   Structured LeadDossier (MD / JSON)    |
                             |   Leaderboards, Citations, Playbooks    |
                             +-----------------------------------------+
```

---

## 2. Weighted Scoring Rubric

Agent A evaluates leads using a transparent 4-tier rubric totaling **100.0 points**:

| Category | Weight | Description | Scoring Logic |
| :--- | :---: | :--- | :--- |
| **Industry Alignment** | **30%** | Sector and sub-niche fit | Exact match: 30 pts; Sub-industry niche: 26 pts; Overlapping tech: 18 pts; Mismatch: 0 pts. |
| **Geography Alignment** | **20%** | Regional/country headquarters | "Global" or exact HQ match: 20 pts; Continental proximity: 17 pts; Divergence: 0 pts. |
| **Headcount & Scale Fit** | **25%** | Employee count vs target bounds | Within target range: 25 pts; Near threshold (±30%): 16 pts; Out of range: 5 pts. |
| **Funding Stage & Signals** | **25%** | Investment round & growth triggers | Target stage match: up to 15 pts; Verified expansion/hiring signals: up to 10 pts. |

### Qualification Tiers:
- **`HIGH_FIT`**: $\ge 80.0$ points (Immediate primary outreach candidate)
- **`MEDIUM_FIT`**: $60.0 - 79.9$ points (Secondary nurture pipeline)
- **`LOW_FIT`**: $40.0 - 59.9$ points (Monitor for growth trigger updates)
- **`DISQUALIFIED`**: $< 40.0$ points (Outside target mandate)

---

## 3. Directory Layout

```
agent_a_lead_gen/
├── README.md              # Architectural documentation & usage guide
├── .env.example           # Environment variables template
├── requirements.txt       # Project dependencies
├── pytest.ini             # Pytest configuration with Windows temp fix
├── __init__.py            # Package initialization & exports
├── main.py                # Command-line entry point
├── cli.py                 # Rich terminal interface & argument parsing
├── agent.py               # LeadGenAgent orchestrator & ADK integration
├── models.py              # Pydantic schemas (Criteria, Profile, Score, Dossier)
├── tools.py               # Discovery, extraction, scoring, and report tools
├── mock_data.py           # 20 curated offline company profiles across 7 sectors
└── tests/
    ├── __init__.py
    └── test_agent_a.py    # Automated test suite (20 tests, 100% pass)
```

---

## 4. Quickstart & Installation

### Prerequisites
- Python 3.11+
- Virtual environment (`.venv`)

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure Environment
```bash
cp .env.example .env
```
Edit `.env` to include your Google Gemini API key:
```env
GOOGLE_API_KEY=your_gemini_api_key
HARNESS_MODEL=gemini-2.5-flash
```

---

## 5. Running the Agent

### Automated Demo Mode
Run the built-in showcase evaluating high-growth Fintech companies:
```bash
python main.py --demo
```
This generates a formatted terminal leaderboard and exports `demo_lead_dossier.md`.

### Offline Deterministic Mode (`--mock`)
Execute without API keys or internet connection:
```bash
python main.py --mock --industry "Fintech" --geography "North America" --min-score 70 --output fintech_dossier.md
```

### Custom Market Criteria
```bash
python main.py \
  --industry "Healthcare AI" \
  --geography "North America" \
  --stages "Series A,Series B" \
  --signals "FDA,clinical,hiring" \
  --min-score 65 \
  --output healthcare_leads.md
```

### JSON Format Export
```bash
python main.py --mock --industry "CleanTech" --format json --output cleantech_leads.json
```

---

## 6. Programmatic Python API

You can import and orchestrate `LeadGenAgent` directly in your Python pipelines:

```python
from agent_a_lead_gen import LeadGenAgent, TargetMarketCriteria

# Define search scope
criteria = TargetMarketCriteria(
    industry="Enterprise SaaS",
    geography="North America",
    min_headcount=50,
    max_headcount=300,
    target_stages=["Series A", "Series B"],
    key_signals=["Kubernetes", "DevOps", "compliance"],
    min_fit_score=65.0,
)

# Initialize agent
agent = LeadGenAgent(mock_mode=True)

# Execute research workflow
dossier = agent.run(criteria=criteria, candidate_limit=6)

print(f"Discovered: {dossier.total_candidates_analyzed} candidates")
print(f"Qualified: {dossier.qualified_leads_count} leads")
for lead in dossier.leads:
    prof = lead["profile"]
    eval_data = lead["evaluation"]
    print(f"- {prof['company_name']}: {eval_data['overall_fit_score']}/100 ({eval_data['qualification_status']})")
```

---

## 7. Verification & Automated Tests

Run the comprehensive pytest suite:
```bash
pytest -o pythonpath=. --basetemp=.pytest_tmp tests/
```

### Test Coverage Highlights:
- **Pydantic Model Constraints**: Validates range checking, required fields, and score boundaries.
- **Offline Dataset Integrity**: Verifies 20 companies across Fintech, Healthcare AI, Enterprise SaaS, CleanTech, CyberSecurity, and Supply Chain.
- **Search Tooling**: Tests keyword expansion, geographic matching, and fallback mechanics.
- **Profile Extraction**: Tests both structured dictionary normalization and regex extraction from unstructured text.
- **Fit Scoring**: Tests HIGH_FIT, MEDIUM_FIT, and DISQUALIFIED scoring outcomes.
- **Dossier Generation**: Tests full markdown and JSON synthesis.
- **End-to-End Orchestrator**: Tests `LeadGenAgent.run()` and `LeadGenAgent.async_run()`.
- **CLI Invocations**: Tests `--demo` and custom parameter CLI runs.
