# Build Roadmap

Status snapshot: 2026-09-04 (demo day). Each checkpoint lists a **prompt to give Claude**, what it should produce, and **how to verify it yourself** before moving on. Checkpoints map to `tasks.md` Phase 17 and the still-open user stories (US-014, US-015) in `specs/001-it-support-ticketing-system/spec.md`.

## Where things stand right now

**Real and verified (2026-09-04):**
- FastAPI backend (`/chat`, `/health`, `/tickets/{id}`), Streamlit frontend, both run and talk to each other over REST.
- LangGraph 11-node workflow: PII redaction → injection guard → session + long-term memory → intent classification → RAG / tool / remember-fact / direct / blocked / escalate → response. **Routing/classification/guardrails are deterministic keyword rules by design** (Principle IV); **`generate_grounded_answer` calls NVIDIA NIM (Nemotron)** for real, with an automatic fallback to the deterministic template on any API failure or degenerate output.
- RAG: ChromaDB retrieval over `data/policies/*.md`, local offline embedding model (no API key needed), plus a relevance-distance cutoff so off-topic questions correctly escalate instead of grounding in the nearest-but-wrong chunk.
- FastMCP tools: `get_ticket_status` (real ticket-ID extraction from the message), `request_password_reset`, `create_ticket` — in-memory seeded data, real Pydantic validation, results flow through as structured data (not stringified) with a clean human-readable summary.
- PII redaction + prompt injection guard: regex/keyword-based, real and tested.
- Session memory (US-008): `src/agent/memory.py`, 6-turn sliding window per session, feeds the last 3 turns into the LLM prompt. Non-durable (in-process dict).
- Long-term memory (US-009): `src/agent/long_term_memory.py`, per-user ChromaDB collection, persisted on disk, explicit "remember that ..." trigger. Verified live across a fresh session and cross-user isolation — see Checkpoint 4b.
- Promptfoo suite: 10/10 passing, real live run against the running backend, committed to `eval/results.json` (two false-negative assertions found and fixed along the way — see `docs/demo_script.md` bug log #10).
- Phoenix tracing: wired into every node including a `llm_call` span (provider, model, status), fails safe when no collector is running, batched (non-blocking) export.
- Git: repo initialized, work committed (was previously **zero** git history — a real gap now closed).
- `docs/SDD.md`, `docs/architecture.png`, `docs/langgraph_state.png`: written/generated and committed.
- Test coverage: 97 pytest tests across PII redaction, injection guard, all three FastMCP tools, Pydantic schemas, and full LangGraph node/routing logic including both memory systems (`NFR-008`).

**Spec'd but not built:**
- Gemini/OpenAI adapters behind the same `LLMClient` interface (Checkpoint 2 below) — NVIDIA NIM only for now.
- `search_external_knowledge` FastMCP tool (US-015).
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

## ✅ Checkpoint 4b — DONE (2026-09-04): Long-term memory (US-009)

`src/agent/long_term_memory.py`: a per-user ChromaDB collection (`user_memory_{user_id}`), persisted on disk (survives a backend restart, unlike Checkpoint 4a's in-process session window). Storage is deterministic and explicit only — triggered by the user saying "remember that ..." / "remember my ..." / "please remember ..." (new `remember_fact` intent and graph node) — never an automatic LLM inference, consistent with Principle IV. `load_session_memory` now also recalls relevant facts for the current question and threads them into `generate_grounded_answer`'s prompt as a clearly-labeled "known facts about this user, never a source of policy" block.

**Verified live** (2026-09-04, real backend, real NVIDIA NIM):
- Stored "I work from the London office on a MacBook Pro." in one session.
- A **different, brand-new session** (same `user_id`) asking a VPN policy question got an answer that correctly referenced "your London office network" and "Since you are on a MacBook Pro" — proving genuine cross-session recall, not session-scoped memory bleeding through.
- The same question asked as a **different `user_id`** got the same policy answer with zero personalization — confirming per-user isolation (each user gets their own Chroma collection).
- An unrelated policy question (software licensing) correctly did **not** pull in the stored fact — the distance-based relevance filter (`MAX_RELEVANT_DISTANCE = 1.6` in `long_term_memory.py`, recalibrated from the RAG module's 1.2 since short single-sentence facts score higher distances even when genuinely relevant) keeps recall targeted.

**Known limitation**: like session memory, recall only reaches the model on the `policy_question` path (inside `generate_grounded_answer`) — a pure `direct_response` question doesn't consult stored facts, since routing is still keyword-based (Principle IV).

---

## ✅ Checkpoint 5 — DONE (2026-09-04): Close the test-coverage gap

Added `tests/test_injection_guard.py`, `tests/test_mcp_tools.py`, `tests/test_schemas.py`, `tests/test_graph_routing.py`, `tests/test_rag_retrieve.py`, `tests/test_long_term_memory.py`. 97 passing (up from 4). LLM calls are monkeypatched in the graph-routing tests so the suite stays fast, deterministic, and free — no real NVIDIA NIM traffic, no test ever depends on network access except the ChromaDB-backed RAG/long-term-memory tests, which run against the real local (offline) index.

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

Checkpoints 1, 4a, 4b, 5, 6, and 7 are all done and demo-ready — see `docs/demo_script.md` Scenes 2, 2a, and 2b. What's left, in rough order of value: 6's one remaining item (trace screenshot — five minutes, do it once Phoenix is running anyway) → 2 (Gemini/OpenAI adapters) → 3 (external search tool). Neither remaining checkpoint blocks presenting what's already built.
