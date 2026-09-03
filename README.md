# IT Support Ticketing System

## Project Overview

This project is an AI-assisted IT support system with:

- FastAPI backend for chat and ticket endpoints
- LangGraph orchestration for intent-based routing
- Security controls for PII redaction and prompt-injection blocking
- ChromaDB-based policy retrieval (RAG)
- FastMCP tools for ticket and account actions
- Streamlit frontend for a simple chat experience
- Promptfoo evaluation suite for quality and safety checks
- Arize Phoenix tracing for local observability

Main implemented flow:

1. Redact PII from incoming message
2. Detect injection/jailbreak patterns
3. Classify intent (currently deterministic keyword rules)
4. Route to RAG, tool action, direct response, escalation, or block
5. Return structured JSON response

### Target architecture (see `specs/001-it-support-ticketing-system/plan.md`)

Per Constitution v2.0.0 (`.specify/memory/constitution.md`), two pieces are
specified but **not yet implemented** in `src/`:

- **Provider-agnostic LLM client** (`src/llm/`, planned) — `classify_intent`
  and `generate_grounded_answer` currently use keyword rules and template
  strings, not a real model call. The target is a single client interface
  selectable via `LLM_PROVIDER` among NVIDIA NIM, Gemini, and OpenAI.
- **External knowledge search tool** (`search_external_knowledge`, planned) —
  a FastMCP tool for Google/Wikipedia lookups, used only when internal RAG
  has no matching policy context, and labeled as an external source.

Do not assume either is live until this note is removed and the README
"Copilot Usage Log" / traceability matrix reference their tests and traces.

## Repository Structure

- `src/api/main.py` - FastAPI app (`/chat`, `/health`, `/tickets/{ticket_id}`)
- `src/agent/graph.py` - LangGraph workflow nodes and routing
- `src/security/` - PII redaction and injection guard
- `src/rag/` - policy ingestion/retrieval with ChromaDB
- `src/tools/mcp_server.py` - FastMCP tool implementations
- `src/observability/tracing.py` - Phoenix/OpenTelemetry setup and span helpers
- `frontend/app.py` - Streamlit frontend
- `eval/promptfooconfig.yaml` - Promptfoo test suite
- `data/policies/` - mock IT policy docs for RAG

## Setup Instructions

### 1. Create and activate a virtual environment

PowerShell (Windows):

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 2. Install dependencies

Install package dependencies from `pyproject.toml`:

```powershell
python -m pip install --upgrade pip
pip install -e ".[dev]"
```

Install runtime dependencies used by API/UI/eval:

```powershell
pip install fastapi uvicorn streamlit langgraph requests opentelemetry-api arize-phoenix
```

### 3. Configure environment variables

Create `.env` from `.env.example` and fill values:

```powershell
Copy-Item .env.example .env
```

Required variables:

- `CHROMA_DB_PATH` (example: `./data/chroma`)
- `PHOENIX_COLLECTOR_ENDPOINT` (example: `http://localhost:6006`)

`OPENAI_API_KEY` is **optional**. When unset, RAG ingestion/retrieval fall back to a local offline embedding model (`all-MiniLM-L6-v2`, no external API calls); set it only if you want OpenAI's `text-embedding-3-small` embeddings instead.

Then ingest the policy docs (downloads the local model, ~79MB, once):

```powershell
python -m src.rag.ingest
```

Optional frontend/runtime variables:

- `API_BASE_URL` (default: `http://localhost:8000`)
- `TRACE_VIEWER_URL` (default: `http://localhost:6006`)

## Run the FastAPI Backend

From repository root:

```powershell
uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000
```

Health check:

```powershell
curl http://localhost:8000/health
```

Expected response:

```json
{"status":"ok","version":"0.1.0"}
```

## Run the Streamlit Frontend

In a second terminal (same venv):

```powershell
streamlit run frontend/app.py
```

Then open the Streamlit URL shown in terminal (usually `http://localhost:8501`).

## Run Promptfoo Eval

If you do not have Promptfoo installed:

```powershell
npm install -g promptfoo
```

Run evaluation:

```powershell
promptfoo eval -c eval/promptfooconfig.yaml
```

## View Phoenix Traces Locally

Phoenix tracing is initialized through `phoenix.otel.register()` in `src/observability/tracing.py` and used in LangGraph node spans.

Typical local trace viewer URL:

- `http://localhost:6006`

How to see traces:

1. Start backend
2. Send chat requests from Streamlit or `/chat`
3. Open Phoenix UI and inspect spans such as:
   - `pii_redaction`
   - `injection_check`
   - `intent_classification`
   - `rag_retrieval`
   - `tool_call`
   - `final_response_generation`

## Copilot Usage Log

Documented examples (replace or extend with your own notes as needed):

### Example 1 - Tooling and ticket flow scaffolding

- Goal: Add FastMCP tools for ticket status, password reset, and ticket creation.
- Copilot output used: MCP server module and Pydantic request/response models.
- Result: Added structured, non-throwing tool responses and in-memory seeded ticket behavior.

### Example 2 - Security hardening implementation

- Goal: Add deterministic safeguards before model execution.
- Copilot output used: `pii_redaction.py` and `injection_guard.py` with regex/keyword detection.
- Result: PII is redacted pre-agent and suspicious prompts route to refusal/escalation paths.

### Example 3 - End-to-end UX and eval setup

- Goal: Add frontend and evaluation coverage for normal and adversarial use cases.
- Copilot output used: Streamlit chat app and Promptfoo config with golden/adversarial/edge tests.
- Result: Interactive local UI plus repeatable eval cases against `/chat` endpoint.
