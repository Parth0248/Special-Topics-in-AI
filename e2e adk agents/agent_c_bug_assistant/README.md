# Agent C: MCP Tools-Based Bug Assistant Agent

A production-grade software bug triage assistant built with the **Google Agent Development Kit (ADK)** and the **Model Context Protocol (MCP)**. Agent C automates the software debugging lifecycle from crash logs to verified patches using pure Python tools with **zero Node.js dependencies**.

---

## Architecture Overview

```
                                      Crash Traceback / Error Log
                                                   │
                                                   ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                        Phase 1: Traceback Parsing & Frame Isolation                    │
│   • Extracts exception class, message, and caller hierarchy                           │
│   • Isolates application frames from stdlib / site-packages frames                     │
└──────────────────────────────────────────┬─────────────────────────────────────────────┘
                                           │ Primary Fault Frame
                                           ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                        Phase 2: Context Gathering via MCP Tools                        │
│   • Inspects source code surrounding fault site (±15 lines)                            │
│   • Locates function/class AST definitions via find_symbol                             │
│   • Inspects file metadata & workspace git status                                      │
└──────────────────────────────────────────┬─────────────────────────────────────────────┘
                                           │ Code Context
                                           ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                    Phase 3: Minimal Reproducible Test Case Synthesis                   │
│   • Generates standalone pytest test script asserting the bug presence                 │
│   • Validates Python AST syntax before execution                                       │
└──────────────────────────────────────────┬─────────────────────────────────────────────┘
                                           │ Verified Reproducer
                                           ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                        Phase 4: Surgical Patch Synthesis (diff -u)                     │
│   • Synthesizes targeted fix addressing the isolated root cause                        │
│   • Produces clean unified diff format without invasive refactoring                    │
└──────────────────────────────────────────┬─────────────────────────────────────────────┘
                                           │ Unified Diff
                                           ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                             Phase 5: Two-Stage Verification Loop                       │
│   1. Pre-Patch Execution:  Runs reproducer against original code  --> MUST FAIL        │
│   2. Patch Application:   Applies unified diff in pure Python                          │
│   3. Post-Patch Execution: Runs reproducer against patched code   --> MUST PASS        │
│   4. Rollback or Retain:   Rolls back if unverified; commits if --apply-patch is set   │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## Key Features

1. **Pure-Python FastMCP Server (`mcp_server.py`)**:
   - Zero Node.js / npm dependencies (eliminates `npx @modelcontextprotocol/server-filesystem`).
   - Standard JSON-RPC 2.0 communication over `stdio`.
   - Exposes filesystem, search, git, and execution tools.

2. **In-Process Embedded Tools Provider (`embedded_tools.py`)**:
   - Provides direct Python function execution mirroring the MCP tool interfaces.
   - Enables instant local execution, testing, and offline sandboxing.

3. **Autonomous 5-Phase Triage Engine (`triage.py`)**:
   - Traceback parsing with heuristic fallbacks for truncated/noisy crash logs.
   - Contextual code extraction with line numbers.
   - Standalone reproducer generation with syntax validation.
   - Deterministic surgical patching for common runtime bugs (ZeroDivisionError, IndexError, KeyError, NoneType AttributeError, etc.).
   - Full pre- and post-patch test execution verifying that the bug failed before the fix and passes after.

4. **Pure-Python Unified Diff Engine**:
   - Patches files directly using unified diff hunks without requiring external `patch.exe` or `git apply` binaries.
   - Automatic `.bak` backup creation and rollback protection.

5. **Google ADK Agent Integration (`agent.py`)**:
   - ADK Bug Assistant Agent with structured prompts and function calling.
   - Seamless offline fallback for deterministic triage without external API dependency.

---

## MCP Tools Reference

| Tool Name | Parameters | Description |
|---|---|---|
| `read_file` | `path: str, start_line?: int, end_line?: int` | Reads file content with optional 1-indexed line range slicing. |
| `write_file` | `path: str, content: str` | Writes content to file, creating parent directories as needed. |
| `list_directory` | `path: str, recursive?: bool` | Lists files and subdirectories, skipping cache/hidden files. |
| `directory_tree` | `path: str, max_depth?: int` | Generates formatted ASCII directory tree structure. |
| `get_file_info` | `path: str` | Returns size, line count, timestamps, and file/directory flags. |
| `search_files` | `pattern: str, path?: str, extension?: str` | Grep-style regex or literal pattern search across files. |
| `find_symbol` | `symbol_name: str, path?: str` | Searches Python files for function, class, or variable definitions using AST. |
| `git_status` | `repo_path?: str` | Returns `git status --porcelain` output. |
| `git_diff` | `repo_path?: str, target?: str` | Returns unified diff of repository changes. |
| `git_log` | `repo_path?: str, max_count?: int` | Returns recent oneline commit history. |
| `run_test_command` | `command: str, cwd?: str, timeout?: int` | Executes test command in subprocess with timeout protection. |

---

## Quickstart & CLI Usage

### Prerequisites
- Python 3.10+
- `mcp` >= 1.25.0
- `pytest` >= 8.0.0
- Optional: `google-genai` for online Gemini LLM reasoning

### 1. Run the Automated Demo
Experience the full 5-phase triage lifecycle on a realistic sample bug:
```bash
python main.py --demo
```

### 2. Triage an Error Traceback
Diagnose a crash log and generate a verified patch:
```bash
python main.py --stack-trace "crash.log" --repo "."
```

### 3. Triage and Apply Verified Patch Permanently
```bash
python main.py --stack-trace "crash.log" --repo "." --apply-patch
```

### 4. Run the FastMCP Server Directly
Run the FastMCP server over stdio for external MCP clients (e.g. Claude Desktop, VS Code MCP extensions, ADK):
```bash
python mcp_server.py
```

---

## Running the Automated Test Suite

To run the full unit and integration test suite:
```bash
pytest -o pythonpath=. --basetemp=.pytest_tmp tests/
```
