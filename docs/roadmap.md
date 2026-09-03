# Build Roadmap

Status snapshot: 2026-09-04 (demo day). Each checkpoint lists a **prompt to give Claude**, what it should produce, and **how to verify it yourself** before moving on. Checkpoints map to `tasks.md` Phase 17 and the still-open user stories (US-009, US-014, US-015) in `specs/001-it-support-ticketing-system/spec.md`.

## Where things stand right now

**Real and verified (2026-09-04):**
- FastAPI backend (`/chat`, `/health`, `/tickets/{id}`), Streamlit frontend, both run and talk to each other over REST.
- LangGraph 10-node workflow: PII redaction → injection guard → session memory → intent classification → RAG / tool / direct / blocked / escalate → response. **Routing/classification/guardrails are deterministic keyword rules by design** (Principle IV); **`generate_grounded_answer` calls NVIDIA NIM (Nemotron)** for real, with an automatic fallback to the deterministic template on any API failure or degenerate output.
- RAG: ChromaDB retrieval over `data/policies/*.md`, local offline embedding model (no API key needed), plus a relevance-distance cutoff so off-topic questions correctly escalate instead of grounding in the nearest-but-wrong chunk.
- FastMCP tools: `get_ticket_status` (real ticket-ID extraction from the message), `request_password_reset`, `create_ticket` — in-memory seeded data, real Pydantic validation, results flow through as structured data (not stringified) with a clean human-readable summary.
- PII redaction + prompt injection guard: regex/keyword-based, real and tested (`tests/test_pii_redaction.py`).
- Session memory (US-008): `src/agent/memory.py`, 6-turn sliding window per session, feeds the last 3 turns into the LLM prompt. Non-durable (in-process dict).
- Promptfoo suite: 10/10 passing, real live run against the running backend, committed to `eval/results.json` (two false-negative assertions found and fixed along the way — see `docs/demo_script.md` bug log #10).
- Phoenix tracing: wired into every node including a `llm_call` span (provider, model, status), fails safe when no collector is running, batched (non-blocking) export.
- Git: repo initialized, work committed (was previously **zero** git history — a real gap now closed).
- `docs/SDD.md`, `docs/architecture.png`, `docs/langgraph_state.png`: written/generated and committed.

**Spec'd but not built:**
- Gemini/OpenAI adapters behind the same `LLMClient` interface (Checkpoint 2 below) — NVIDIA NIM only for now.
- `search_external_knowledge` FastMCP tool (US-015).
- Long-term per-user memory across sessions (US-009) — not built. (Short-term session memory, US-008, is done — see Checkpoint 4a.)
- Test coverage beyond PII redaction: injection guard, tools, graph routing, RAG retrieval, schemas, LLM client (`NFR-008`).
- `docs/trace_screenshot.png` — not captured yet (needs a live Phoenix run to screenshot).

---

## ✅ Checkpoint 1 — DONE (2026-09-03): Provider-agnostic LLM client (NVIDIA NIM)

`src/llm/client.py` implements `LLMClient`/`get_llm_client()`, wired into `generate_grounded_answer` in `src/agent/graph.py`. Verified live against NVIDIA NIM (`nvidia/nemotron-3.5-lightning-30b-a3b`) across all 4 golden questions plus escalation/injection/tool regression checks.

Two real issues found and fixed during integration:
- This Nemotron deployment dumps full chain-of-thought into `content` unless told not to — fixed via `extra_body={"chat_template_kwargs": {"thinking": False}}` (NIM-specific; the older "detailed thinking off" system-prompt convention did **not** work for this model).
- Roughly 1 in 4 real calls produced degenerate output (a corrupted opening line). Added `_looks_like_valid_answer()` in `graph.py`: rejects output with repeated-word patterns or under 40 chars, silently falling back to the deterministic template (which is always coherent, since it's built from the same retrieved text). This is on top of the existing try/except fallback for outright API failures — the grounded-answer path is not allowed to ever emit something worse than what already worked.

`classify_intent`, `execute_tool` routing, PII redaction, and injection detection remain deterministic — intentionally, not as a stopgap (Constitution Principle IV: guardrails run before any model call).

Gemini/OpenAI adapters are not yet added — that's Checkpoint 2 below.

---

## Checkpoint 2 — Gemini / OpenAI adapters behind the same interface

**Prompt**: *"Add Gemini and OpenAI adapters to `src/llm/client.py` behind the same `LLMClient` protocol. Add a startup check that fails fast if `LLM_PROVIDER` is unset or not in {nvidia_nim, gemini, openai}."*

**Verify**: Swap `LLM_PROVIDER` in `.env` across all three values, re-run the same curl above each time — response shape (`intent`, `response`, `tool_result`) must stay identical; only response text/latency should change. No other file outside `src/llm/` and `.env` should need edits (NFR-011).

---

## Checkpoint 3 — External search tool (Google/Wikipedia)

**Prompt**: *"Implement `search_external_knowledge` in `src/tools/mcp_server.py` per the schema in plan.md, and route to it from `retrieve_from_rag`'s no-context branch instead of going straight to `escalate` (tasks.md T112–T115). Render it as a labeled 'external source' card in `frontend/app.py`."*

**Verify**:
- Ask something with no policy match (`"What is the capital of France?"`) → tool card appears, labeled external.
- Re-ask a policy question (e.g. the VPN one) → confirm the external tool is **not** invoked (check the trace or a debug log) — internal RAG must take precedence (Principle I / II).
- Unplug network or point at a bad URL → confirm `ERR-TOOL-002` and a graceful fallback, not a crash.

---

## ✅ Checkpoint 4a — DONE (2026-09-03): Session memory (US-008)

`src/agent/memory.py` (process-local dict, 6-pair sliding window per `session_id`) + a new `load_session_memory` graph node (runs after guardrails clear, before `classify_intent`, matching plan.md's node order) + `generate_grounded_answer` now includes the last 3 turns as "context only, not a policy source" in the LLM prompt. `update_memory` persists each turn (skipping blocked ones, so injection attempts never pollute future context).

Verified: trim logic unit-tested (9 turns in → exactly the last 6 kept, oldest 3 correctly dropped); live 2-turn conversation confirmed the model used prior context — asked a contractor follow-up after a VPN question, and it correctly recognized the follow-up was still about access policy while honestly saying this turn's retrieved chunk didn't cover contractors specifically (grounding held even across turns, no fabrication).

**Known limitation**: `classify_intent` is still keyword-based, so a follow-up with zero policy keywords (e.g. "and for contractors?" with no "policy"/"vpn"/etc.) won't route to RAG at all — memory helps *within* the policy_question path, it doesn't change routing. Worth knowing before a demo follow-up question.

**Not durable**: memory is an in-process dict — restarting the backend clears all sessions. Fine for a demo; would need a real store (Redis, SQLite) to survive restarts or scale to multiple workers.

---

## Checkpoint 4b (open) — Long-term memory (US-009)

**Prompt**: *"Add a per-user ChromaDB collection (`user_memory_{user_id}`) for long-term safe-fact recall (office region, preferred device type, etc.), per plan.md §11.2. Never store passwords, secrets, or raw PII."*

**Verify**: confirm two different `user_id`s never see each other's long-term facts (tenant isolation test); confirm a stored fact is retrieved and influences a later response in a **new** session (proving it's cross-session, unlike Checkpoint 4a's per-session memory).

---

## Checkpoint 5 — Close the test-coverage gap

**Prompt**: *"Add unit tests for the injection guard, all three FastMCP tools, LangGraph routing (all 5 intents + blocked path), RAG retrieval, and Pydantic schema validation, matching NFR-008 and the Definition of Done's 'Testing Complete' checklist."*

**Verify**: `pytest -q` — all green, and manually confirm each file in `tests/` maps to a real DoD bullet, not just line coverage.

---

## ✅ Checkpoint 6 — Mostly DONE (2026-09-04): Evaluation and observability evidence

Promptfoo suite ran live against the real backend: 10/10 passing, saved to `eval/results.json` (committed — the file is no longer in `.gitignore`). Two test-config false negatives were found and fixed in the process (see `docs/demo_script.md` bug log #10) — not product bugs, just assertions that were checking the wrong field or an exact wrong phrase.

**Still open**: `docs/trace_screenshot.png` — needs a live Phoenix run (`python -m phoenix.server.main serve`) plus a manual screenshot of one full trace. Do this once during T-30 setup or right after the demo.

---

## ✅ Checkpoint 7 — Mostly DONE (2026-09-04): Submission packaging

`docs/SDD.md` written (real system as built, includes an explicit "Known Deviations" table against the original spec/contracts docs — notably that `specs/.../data-model.md` and `contracts/rag-and-tools.md` describe an aspirational multi-tenant design that was never implemented; the shipped system is single-tenant). `docs/architecture.png` and `docs/langgraph_state.png` generated via `mermaid-cli` from `docs/_figure1_architecture.mmd` / `docs/_figure2_langgraph.mmd` and committed.

**Still open**: `docs/trace_screenshot.png` (see Checkpoint 6); README's Copilot Reflection section hasn't been refreshed to mention today's LLM/memory/git/eval work; `/frontend/src` in the original checklist literally doesn't exist as a path (the app is a single `frontend/app.py` file — a documented deviation, see `docs/SDD.md` §8, not a missing file).

---

## Suggested order given the Friday deadline

Checkpoints 1 (LLM) and 4a (session memory) are done and demo-ready — see `docs/demo_script.md` Scenes 2 and 2a. Git, Promptfoo, and the doc/PNG exports (Checkpoints 6-7) are also done. What's left, in order of value if there's time before or after the demo: 5 (test coverage — protects against silent regressions) → 6's remaining item (trace screenshot — five minutes, do it once Phoenix is running anyway) → 2 (Gemini/OpenAI adapters) → 3 (external search tool) → 4b (long-term memory). None of the remaining items block presenting what's already built.
