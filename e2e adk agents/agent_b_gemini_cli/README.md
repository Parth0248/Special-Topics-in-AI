# Agent B: Gemini CLI in ADK Pipeline Tool Agent

Production-grade Google Agent Development Kit (ADK) pipeline tool agent that embeds the **Gemini CLI** as a headless, non-interactive subprocess tool inside an ADK execution workflow.

Based on Derrick Wong's reference architecture:
- [Combine ADK, Gemini CLI and Cloud Run](https://medium.com/@derrickchwong/combine-adk-gemini-cli-and-cloud-run-c5dea5118853)
- [Reference Repository: derrickchwong/gemini-cli-on-adk](https://github.com/derrickchwong/gemini-cli-on-adk)

---

## Architecture Overview

```
+-------------------------------------------------------------------------------+
|                     User / CLI Entrypoint (`main.py`)                        |
|             Flags: --demo, --task, --code-file, --dry-run, --format          |
+-------------------------------------------------------------------------------+
                                       |
                                       v
+-------------------------------------------------------------------------------+
|                      Google ADK Agent (`agent.py`)                           |
|                  Tools: `gemini_cli_tool`, `run_pipeline_tool`                |
+-------------------------------------------------------------------------------+
                                       |
                                       v
+-------------------------------------------------------------------------------+
|                     4-Stage ADK Pipeline (`pipeline.py`)                      |
|                                                                               |
|  [Stage 1: Decompose]                                                        |
|    └─ Formulates task decomposition prompt -> extracts atomic subtasks        |
|                                                                               |
|  [Stage 2: Tool Invocation via CLI Subprocess]                               |
|    └─ Executes subtasks via GeminiCliWrapper -> captures stdout/stderr        |
|                                                                               |
|  [Stage 3: Code/Text Transformation]                                         |
|    └─ Extracts code blocks -> AST parsing (ast.parse) & syntax validation    |
|                                                                               |
|  [Stage 4: Synthesis & Telemetry]                                            |
|    └─ Aggregates per-stage outputs -> compiles final dossier and telemetry   |
+-------------------------------------------------------------------------------+
                                       |
                                       v
+-------------------------------------------------------------------------------+
|                 Gemini CLI Subprocess Wrapper (`cli_wrapper.py`)              |
|                                                                               |
|  - Headless Execution: `gemini -p <prompt> -o json`                          |
|  - Timeout Guardrails: Synchronous & Async (subprocess.TimeoutExpired)       |
|  - Robust JSON Parser: Direct json.loads + Multi-pattern Regex Fallbacks     |
|  - Resilient Fallback Layer:                                                 |
|      * Auto-detects binary presence via shutil.which('gemini')                |
|      * Routes to `google.genai` SDK when GOOGLE_API_KEY is present           |
|      * Routes to deterministic Mock Emulator for offline zero-credential use |
+-------------------------------------------------------------------------------+
```

---

## Key Features

1. **Headless Subprocess Execution**:
   - Executes `gemini -p <prompt> -o json` with non-interactive flags.
   - Enforces configurable timeout limits (default: 120s) preventing hung processes.
   - Captures both stdout and stderr, recording non-zero exit codes into telemetry.

2. **Multi-Pattern Regex & Envelope Extraction**:
   - Standard JSON parser handles native CLI envelopes (`{"response": ..., "stats": ...}`).
   - Markdown code fence extractor parses ````json ... ```` blocks embedded in logs.
   - Outer brace (`{...}`) and bracket (`[...]`) regex recovery for malformed stdout.
   - Raw text fallback ensures unparseable text is preserved without throwing exceptions.

3. **Dual-Mode Resilient Fallback**:
   - When the `gemini` executable is absent from system PATH or `GEMINI_CLI_FALLBACK=1` is configured, execution automatically falls back:
     - **SDK Mode**: Uses official `google.genai.Client()` with `HARNESS_MODEL` (e.g. `gemini-2.5-flash`).
     - **Mock Emulator Mode**: Deterministic offline generator producing realistic task decompositions, refactored code, and pytest unit tests with zero network dependencies.

4. **AST Code Validation**:
   - Stage 3 performs syntax tree verification via Python's standard `ast.parse()` to catch malformed code before output synthesis.

5. **Google ADK Integration**:
   - Exposes tools adhering to Google ADK conventions (`gemini_cli_tool`, `run_pipeline_tool`).
   - Compatible with native `google.adk.agents.Agent` as well as standalone environments.

---

## Project Structure

```
agent_b_gemini_cli/
├── README.md              # Comprehensive documentation and architecture guide
├── .env.example           # Environment configuration template
├── requirements.txt       # Project dependencies
├── pytest.ini             # Pytest configuration with Windows temp fix
├── schemas.py             # Pydantic data models (TaskRequest, CliResult, StageOutput, PipelineSummary)
├── cli_wrapper.py         # Subprocess executor, JSON parser, and fallback handler
├── pipeline.py            # 4-stage ADK pipeline orchestrator
├── agent.py               # Google ADK agent and tool definitions
├── main.py                # Command Line Interface (CLI) entrypoint
└── tests/
    ├── __init__.py
    └── test_agent_b.py    # Automated pytest verification suite (15 test cases)
```

---

## Installation & Setup

### 1. Prerequisites
- Python 3.10+ (tested on Python 3.13)
- Virtual environment (`.venv`)

### 2. Virtual Environment Setup
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 3. Environment Configuration
Copy `.env.example` to `.env`:
```powershell
cp .env.example .env
```
Configure your settings:
```ini
GOOGLE_API_KEY=your_gemini_api_key_here
HARNESS_MODEL=gemini-2.5-flash
GEMINI_CLI_FALLBACK=0
```

---

## Usage Instructions

### 1. Run the Multi-Stage Pipeline Demo
Executes the full 4-stage pipeline demonstrating code analysis, refactoring, AST validation, and test generation:
```powershell
python main.py --demo
```

### 2. Run in Offline Dry-Run Mode
Forces the deterministic mock emulator with zero network or binary dependencies:
```powershell
python main.py --demo --dry-run
```

### 3. Execute a Custom Task
```powershell
python main.py --task "Implement a rate limiter class with unit tests"
```

### 4. Analyze an Existing Code File
```powershell
python main.py --task "Refactor and add type hints" --code-file ./my_script.py --output refactored_report.md
```

### 5. Structured JSON Output
```powershell
python main.py --demo --dry-run --format json
```

---

## Automated Test Verification

Run the automated pytest test suite using the project's Windows-compatible configuration:
```powershell
pytest -o pythonpath=. --basetemp=.pytest_tmp tests/
```

### Test Coverage Highlights:
- Subprocess execution with exit code 0 and stdout JSON parsing.
- Subprocess non-zero exit codes with stderr capture.
- Subprocess timeout expiration (`subprocess.TimeoutExpired` and `asyncio.TimeoutError`).
- Multi-pattern regex extraction for markdown-wrapped and brace-bounded JSON.
- Raw text fallback resilience.
- `google.genai` SDK fallback path.
- Deterministic mock emulator fallback path.
- End-to-end 4-stage pipeline execution with stage duration telemetry.
- AST Python syntax validation.
- Google ADK Agent tool integration and dispatch.
- CLI entry point verification (`--demo`, `--task`, `--dry-run`).
