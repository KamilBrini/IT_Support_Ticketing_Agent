# System Architecture

Governed by `.specify/memory/constitution.md` v2.0.0. Solid boxes/edges = implemented and verified (2026-09-04). Dashed boxes/edges = spec'd, not yet built (tasks.md Phase 17).

A rendered, presentation-ready version of both diagrams is also published as an Artifact for demo day — see the link shared in chat.

## Figure 1 — Layered Architecture and Data Flow

```mermaid
flowchart TD
    UI["Streamlit UI\nfrontend/app.py\nchat + tool cards"]
    API["FastAPI Gateway\nsrc/api/main.py\n/chat /health /tickets/{id}"]
    Redact["PII Redaction\nsrc/security/pii_redaction.py"]
    Guard["Injection Guard\nsrc/security/injection_guard.py"]
    Mem["Session Memory\nsrc/agent/memory.py\n6-turn sliding window per session_id"]
    Graph["LangGraph Orchestrator\nsrc/agent/graph.py"]
    RAG["RAG Retriever\nsrc/rag/retrieve.py\nrelevance-distance cutoff"]
    KB[("ChromaDB\ndata/policies, local offline\nembeddings by default")]
    Tools["FastMCP Tools\nsrc/tools/mcp_server.py\nticket status/create, password reset"]
    LLM["LLM Client\nsrc/llm/client.py\nNVIDIA NIM (Nemotron) live;\nGemini/OpenAI adapters planned"]
    Search[["search_external_knowledge (planned)\nGoogle / Wikipedia\nonly when RAG has no context"]]
    Trace["Arize Phoenix Tracing\nsrc/observability/tracing.py\nbatched export, fails safe"]
    Eval["Promptfoo Suite\neval/promptfooconfig.yaml\n10 tests: 4 golden + 3 adversarial + 3 edge"]

    UI -->|"REST POST /chat"| API
    API --> Redact --> Guard --> Mem --> Graph
    Graph -->|"policy_question"| RAG --> KB
    Graph -->|"action_request"| Tools
    Graph -->|"grounded-answer generation"| LLM
    RAG -.->|"planned: no-context fallback"| Search
    Graph --> Trace
    Eval -.->|"drives"| API
    Graph -->|"JSON response"| API -->|"tool cards + text"| UI

    classDef planned stroke-dasharray: 5 5,fill:#fff4e0,stroke:#b8791e,color:#6b4a10;
    class Search planned;
```

## Figure 2 — Agent State Flow (LangGraph, `src/agent/graph.py`)

```mermaid
flowchart TD
    START([START]) --> A[redact_pii]
    A --> B[detect_injection]
    B -->|suspicious| BR[blocked_response]
    B -->|safe| LSM[load_session_memory]
    LSM --> C[classify_intent]

    C -->|policy_question| D[retrieve_from_rag]
    C -->|action_request| E[execute_tool]
    C -->|escalation| ESC[escalate]
    C -->|blocked| BR
    C -->|direct_response default| DR[direct_response]

    D -->|context found| F[generate_grounded_answer]
    D -->|no context| ESC
    D -.->|"planned: no-context, before escalate"| SEARCH[["search_external_knowledge"]]

    LLMNOTE["LLMClient.generate() (Nemotron)\nfalls back to template on\nfailure/degenerate output"] --> F
    F --> UM[update_memory]
    E --> UM
    DR --> UM
    BR --> UM
    ESC --> UM
    UM --> END([END])

    classDef planned stroke-dasharray: 5 5,fill:#fff4e0,stroke:#b8791e,color:#6b4a10;
    class SEARCH planned;
```

**Note vs. the original spec's LangGraph diagram** (`specs/001-it-support-ticketing-system/plan.md`): `load_session_memory` (US-008) and the real `LLMClient.generate()` call inside `generate_grounded_answer` are both now shipped and live. `classify_intent` and `execute_tool` routing remain deterministic keyword rules by design (Constitution Principle IV — guardrails/routing run before any model call), not a gap. There is still no separate `validate_structured_output` gate — Pydantic validation happens inline in the tool schemas (`src/schemas/models.py`) instead of as its own graph node.

## PNG exports for the submission checklist

Section 23.2 of the project guide asks for `/docs/architecture.png` and `/docs/langgraph_state.png` — both are committed and generated from `docs/_figure1_architecture.mmd` / `docs/_figure2_langgraph.mmd` (kept in sync with the Mermaid source above). Regenerate after editing either diagram:

```powershell
npx -y @mermaid-js/mermaid-cli -i docs/_figure1_architecture.mmd -o docs/architecture.png -b white -s 2
npx -y @mermaid-js/mermaid-cli -i docs/_figure2_langgraph.mmd -o docs/langgraph_state.png -b white -s 2
```
