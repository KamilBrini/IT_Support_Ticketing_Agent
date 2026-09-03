# System Architecture

Governed by `.specify/memory/constitution.md` v2.0.0. Solid boxes/edges = implemented and verified (2026-09-02). Dashed boxes/edges = spec'd, not yet built (tasks.md Phase 17).

A rendered, presentation-ready version of both diagrams is also published as an Artifact for demo day — see the link shared in chat.

## Figure 1 — Layered Architecture and Data Flow

```mermaid
flowchart TD
    UI["Streamlit UI\nfrontend/app.py\nchat + tool cards"]
    API["FastAPI Gateway\nsrc/api/main.py\n/chat /health /tickets/{id}"]
    Redact["PII Redaction\nsrc/security/pii_redaction.py"]
    Guard["Injection Guard\nsrc/security/injection_guard.py"]
    Graph["LangGraph Orchestrator\nsrc/agent/graph.py"]
    RAG["RAG Retriever\nsrc/rag/retrieve.py"]
    KB[("ChromaDB\ndata/policies, local offline\nembeddings by default")]
    Tools["FastMCP Tools\nsrc/tools/mcp_server.py\nticket status/create, password reset"]
    LLM[["LLM Endpoint (planned)\nsrc/llm/client.py\nNVIDIA NIM / Gemini / OpenAI"]]
    Search[["search_external_knowledge (planned)\nGoogle / Wikipedia\nonly when RAG has no context"]]
    Trace["Arize Phoenix Tracing\nsrc/observability/tracing.py\nbatched export, fails safe"]
    Eval["Promptfoo Suite\neval/promptfooconfig.yaml\n10 tests: 4 golden + 3 adversarial + 3 edge"]

    UI -->|"REST POST /chat"| API
    API --> Redact --> Guard --> Graph
    Graph -->|"policy_question"| RAG --> KB
    Graph -->|"action_request"| Tools
    Graph -.->|"planned: generation calls"| LLM
    RAG -.->|"planned: no-context fallback"| Search
    Graph --> Trace
    Eval -.->|"drives"| API
    Graph -->|"JSON response"| API -->|"tool cards + text"| UI

    classDef planned stroke-dasharray: 5 5,fill:#fff4e0,stroke:#b8791e,color:#6b4a10;
    class LLM,Search planned;
```

## Figure 2 — Agent State Flow (LangGraph, `src/agent/graph.py`)

```mermaid
flowchart TD
    START([START]) --> A[redact_pii]
    A --> B[detect_injection]
    B -->|suspicious| BR[blocked_response]
    B -->|safe| C[classify_intent]

    C -->|policy_question| D[retrieve_from_rag]
    C -->|action_request| E[execute_tool]
    C -->|escalation| ESC[escalate]
    C -->|blocked| BR
    C -->|direct_response default| DR[direct_response]

    D -->|context found| F[generate_grounded_answer]
    D -->|no context| ESC
    D -.->|"planned: no-context, before escalate"| SEARCH[["search_external_knowledge"]]

    F --> UM[update_memory]
    E --> UM
    DR --> UM
    BR --> UM
    ESC --> UM
    UM --> END([END])

    LLMNOTE[["planned: LLMClient.generate()\ninside classify_intent +\ngenerate_grounded_answer"]]
    LLMNOTE -.-> C
    LLMNOTE -.-> F

    classDef planned stroke-dasharray: 5 5,fill:#fff4e0,stroke:#b8791e,color:#6b4a10;
    class SEARCH,LLMNOTE planned;
```

**Note vs. the original spec's LangGraph diagram** (`specs/001-it-support-ticketing-system/plan.md`): the shipped graph does not yet have a separate `load_session_memory` node or a `validate_structured_output` gate — routing decisions and generation are currently keyword/template-based, not model-based, so there is nothing to validate for schema drift yet. Both will matter once the real LLM call (Phase 17) lands.

## Exporting to PNG for the submission checklist

Section 23.2 of the project guide asks for `/docs/architecture.png` and `/docs/langgraph_state.png`. Easiest paths:
- VS Code: install the "Markdown Preview Mermaid Support" extension, open this file's preview, right-click each diagram → *Save image*.
- Or open the published Artifact (renders both diagrams) and take a browser screenshot of each figure.
