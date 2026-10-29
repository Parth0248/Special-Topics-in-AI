# Agent D: Production-Quality Code Review Assistant

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Google ADK](https://img.shields.io/badge/Google-ADK-green.svg)](https://cloud.google.com/blog/topics/developers-practitioners)
[![Pytest](https://img.shields.io/badge/tests-pytest-orange.svg)](https://docs.pytest.org/)

An automated, production-grade code review assistant built with the **Google Agent Development Kit (ADK)** pattern. Agent D performs static AST structural analysis, PEP 8 compliance scoring (0-100), OWASP Top 10 and CWE security vulnerability detection, unified git diff parsing, and iterative code remediation using Google ADK's **SequentialAgent** and **LoopAgent** architectures.

---

## 🏗️ Architecture & Pipeline Design

Agent D combines two cooperating agent orchestrators:

```
+-------------------------------------------------------------------------------------------------+
|                                    User / CLI / Git Hook Input                                  |
|                         (--file <path>, --diff <patch>, --pr-desc <text>)                       |
+-------------------------------------------------------------------------------------------------+
                                                 |
                                                 v
+-------------------------------------------------------------------------------------------------+
|                                 SequentialAgent: Review Pipeline                                |
+-------------------------------------------------------------------------------------------------+
|  1. AST Structure Analyzer  --> McCabe Cyclomatic Complexity, functions, classes, docstrings   |
|  2. PEP 8 Style Checker     --> Weighted 0-100 style scoring (E711, E712, E722, N802, etc.)     |
|  3. Security Scanner        --> OWASP Top 10 & CWE classification (SQLi, Command Injection)     |
|  4. Git Diff Parser         --> Unified diff hunk mapping and line correlation                  |
|  5. Feedback Synthesizer    --> Structured Markdown Review with severity breakdown & comments   |
+-------------------------------------------------------------------------------------------------+
                                                 |
                       [Review Report & Status: CHANGES REQUESTED / APPROVED]
                                                 |
                                                 v
+-------------------------------------------------------------------------------------------------+
|                                    LoopAgent: Fix Pipeline                                      |
+-------------------------------------------------------------------------------------------------+
|  1. Code Fixer              --> Surgical AST/regex remediation (parameterized SQL, env secrets) |
|  2. Fix Validator           --> Syntax compilation, security reduction, score gate check        |
|  3. Termination Check       --> Halts when validation passes or max iterations reached          |
+-------------------------------------------------------------------------------------------------+
                                                 |
                                                 v
+-------------------------------------------------------------------------------------------------+
|                                Remediated Code & Verified Output                                |
+-------------------------------------------------------------------------------------------------+
```

---

## 🛡️ Supported CWE & OWASP Security Rules

| CWE ID | Vulnerability Class | Default Severity | Detection Mechanism | Remediation |
|---|---|:---:|---|---|
| **CWE-89** | SQL Injection (SQLi) | `CRITICAL` | AST detection of f-strings, format, and concatenation in `cursor.execute()` | Use parameterized query placeholders `?` / `%s` |
| **CWE-78** | OS Command Injection | `CRITICAL` | `os.system()` with dynamic arguments; `subprocess` with `shell=True` | Set `shell=False` and pass arguments as list |
| **CWE-502** | Insecure Deserialization | `CRITICAL` | `pickle.loads()`, `yaml.load()` without `SafeLoader`, `marshal` | Use `json.loads` or `yaml.safe_load()` |
| **CWE-22** | Path Traversal | `HIGH` | Dynamic user paths in `open()` without boundary check | Validate path bounds or use `os.path.basename()` |
| **CWE-798** | Hardcoded Credentials | `HIGH` | Sensitive variable assignments (`API_KEY`, `password`) | Extract to `os.getenv("VARIABLE_NAME")` |
| **CWE-327** | Broken Cryptography | `HIGH` | `hashlib.md5()`, `hashlib.sha1()` for secure hashing | Upgrade to `hashlib.sha256()` or SHA-3 |
| **CWE-95** | Eval / Code Injection | `CRITICAL` | `eval()` or `exec()` on dynamic arguments | Use `ast.literal_eval()` or redesign |
| **CWE-703** | Silenced Exceptions | `LOW` | Bare `except:` or `except Exception: pass` | Catch specific exceptions and log |

---

## 📊 PEP 8 Compliance Scoring (0-100)

Agent D calculates an objective, weighted 0-100 PEP 8 score:
- **Baseline**: 100.0 points
- **Deductions**:
  - Bare `except:`: `-10.0` points
  - `== None` or `== True/False` comparisons: `-5.0` points each
  - Naming convention violations (`snake_case` functions, `PascalCase` classes): `-3.0` points
  - Missing docstring on public API: `-2.5` points
  - Indentation errors: `-3.0` points
  - Lines exceeding 88 characters: `-2.0` points
  - Trailing whitespace: `-1.0` point

---

## 🚀 Installation & Quick Start

### 1. Prerequisites
- Python 3.10 or higher
- Optional: Google Gemini API key (set in `.env` for generative AI insights)

### 2. Setup Virtual Environment
```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Environment Configuration
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```

---

## 💻 CLI Usage Guide

### 1. Interactive Demo Mode
Run the built-in end-to-end demonstration showcasing static analysis of flawed code followed by the `LoopAgent` iterative fix loop:
```bash
python main.py --demo
```

### 2. Review a Local Python File
```bash
python main.py --file path/to/source.py
```

### 3. Review a Git Diff
Review a diff directly from a patch file or stdin:
```bash
python main.py --diff my_feature.patch
# Or pipe git diff directly:
git diff main | python main.py
```

### 4. Contextual Pull Request Review
Include pull request description to enrich the review report:
```bash
python main.py --file auth.py --pr-desc "PR #104: Add user login and session authentication."
```

### 5. Automated Iterative Code Remediation (--auto-fix)
Trigger the `LoopAgent` to automatically remediate detected vulnerabilities and style violations:
```bash
python main.py --file auth.py --auto-fix
```
The repaired code will be written to `auth.py.fixed.py`.

### 6. Machine-Readable JSON Output
```bash
python main.py --file auth.py --output json --save review_report.json
```

---

## 🧪 Automated Testing

Agent D includes a complete automated test suite covering all AST metrics, PEP 8 scoring, security vulnerability detectors, git diff parser, and the fix loop:

```bash
pytest -o pythonpath=. --basetemp=.pytest_tmp tests/ -v
```

All 21+ automated tests pass with 100% reliability both offline and in continuous integration environments.
