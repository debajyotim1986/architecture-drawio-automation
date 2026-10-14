# Point 3: Context-Grounding — Detailed Interpretation & Implementation Guide

## 1. The Clause (as written in the tender)

- Output is grounded **at inference time** in the **client's own corpus, documents or structured data**
- Grounding may be achieved by:
  - Retrieval-augmented generation (RAG)
  - Tool-mediated data access
  - Fine-tuning on client data
  - An equivalent mechanism, **to be named by the Bidder**
- **Exclusion:** A general-purpose assistant with no access to client-specific content does not qualify

## 2. What It Actually Means (Plain Interpretation)

- The answer must be based on **the client's data**, not only on what the LLM learned during pre-training
- The system must **know things about the client** that a public model (ChatGPT, Gemini app) cannot know
- The client data must be **used while answering** (at the moment of the request), not merely somewhere in the project
- The Bidder must **explicitly name the mechanism** used; a vague "AI uses client data" claim will not pass

## 3. Key Phrases Decoded

### "Grounded"
- The model's answer is **anchored to supplied facts**, not invented from its training memory
- Purpose: reduce hallucination, make answers client-specific and verifiable

### "At inference time"
- Grounding happens **when the user asks**, not only during training
- The model receives client data as part of its working context for that specific request
- Implication: RAG and tool access fit naturally; fine-tuning alone is weaker on this phrase (see Section 7)

### "Client's own corpus, documents or structured data"
- **Corpus / documents (unstructured):** policies, SOPs, circulars, manuals, contracts, PDFs, emails, tickets, case files
- **Structured data:** databases, data warehouses, ERP/CRM records, spreadsheets, transaction tables
- Must belong to **the client** — public internet data or generic datasets do not count

### "Equivalent mechanism, to be named by the Bidder"
- The list is not exhaustive; other valid methods may be proposed
- The Bidder carries the burden of **naming and describing** the mechanism precisely
- Examples of acceptable "equivalent" mechanisms:
  - Knowledge-graph retrieval (GraphRAG)
  - Long-context injection of client documents
  - MCP servers exposing client systems
  - Text-to-SQL over client databases
  - Enterprise search grounding (e.g., Vertex AI Search grounding)

### "General-purpose assistant ... does not qualify"
- Pre-empts bidders citing a plain chatbot deployment (e.g., Copilot/ChatGPT/Gemini licences rolled out to staff)
- If removing the client data would not change the answers, the system fails

## 4. Qualifies vs. Does Not Qualify

### Qualifies
- Chatbot answering employee questions from the client's HR policy documents via RAG
- Agent that queries the client's claims database to explain a specific claim status
- Assistant that reads a citizen's application record via API and drafts a response
- Model fine-tuned on client's historical case notes **and** retrieving current records at runtime

### Does Not Qualify
- LLM answering from its own general knowledge only
- Model connected only to public web search
- System grounded on generic/public datasets, not client data
- Client documents used only once to write prompts or test cases, not consulted at runtime
- A "RAG" demo built on sample/dummy documents instead of the client's real corpus

## 5. Foolproof Self-Test (Apply to Your Project)

- **Removal test:** Disconnect the client data source — do the answers become generic or wrong? If yes, grounding is real
- **Uniqueness test:** Could a public LLM answer this question correctly? If no, the system is client-grounded
- **Traceability test:** Can each answer be traced to a specific client document, record or query result?
- **Freshness test:** If a client document/record is updated today, does the next answer reflect it? (proves inference-time grounding)
- **Ownership test:** Is the data source owned by or licensed to the client?
- **Naming test:** Can you name the mechanism, the components and the data sources in one line each?

## 6. How It Is Achieved Through RAG

### 6.1 Ingestion Pipeline (offline / scheduled)
- **Source connectors:** SharePoint, Google Drive, Cloud Storage, DMS, email archives, file shares
- **Parsing:** extract text from PDF, DOCX, scanned images (OCR), tables
  - GCP examples: Document AI, Vertex AI RAG Engine layout parser
- **Cleaning & enrichment:** remove boilerplate, attach metadata (department, date, document type, access level, language)
- **Chunking:** split into retrievable units
  - Fixed-size with overlap, semantic chunking, or structure-aware (by heading/section)
- **Embedding:** convert chunks to vectors with a named embedding model
  - Examples: `text-embedding-005`, `text-multilingual-embedding-002` (for Indic languages)
- **Indexing:** store in a vector store
  - Examples: Vertex AI Vector Search, AlloyDB / Cloud SQL with pgvector, Vertex AI Search, Elasticsearch

### 6.2 Retrieval at Inference Time (online, per request)
- **Query understanding:** rewrite or expand the user query (optional)
- **Retrieval:** semantic (vector) search, often combined with keyword search (**hybrid search**)
- **Filtering:** metadata filters + **user-level access control** (user sees only documents they are entitled to)
- **Re-ranking:** re-order top results for relevance (e.g., Vertex AI Ranking API, cross-encoder)
- **Context assembly:** insert top-k chunks into the prompt with source identifiers

### 6.3 Grounded Generation
- **Instruction:** model is told to answer **only from supplied context**
- **Refusal behaviour:** if context lacks the answer, the model says so instead of guessing
- **Citations:** each answer references source document, section/page
- **Grounding check:** post-generation verification that claims are supported (e.g., Vertex AI check-grounding API, LLM-as-judge)

### 6.4 Evidence of RAG Grounding
- Named corpus with size (e.g., "12,400 client documents, 3.1M chunks")
- Named embedding model, vector store, retrieval method, re-ranker
- Sample answers with citations pointing to client documents
- Retrieval evaluation metrics (recall@k, faithfulness, answer relevance)

## 7. How It Is Achieved Through Agentic Systems

### 7.1 Tool-Mediated Data Access
- The agent **decides at runtime** which client data source to consult
- Data is fetched live through tools, not pre-indexed
- Typical tools:
  - `query_database` — Text-to-SQL or parameterised queries on Cloud SQL / BigQuery
  - `get_record` — REST API calls to ERP / CRM / case-management systems
  - `search_documents` — RAG retrieval exposed as a tool
  - `read_file` — fetch a specific document by ID
- Strongest fit for **structured data** and **real-time records**

### 7.2 Agentic RAG
- Retrieval itself becomes a **tool the agent chooses** to call
- Agent can:
  - Decide whether retrieval is needed at all
  - Reformulate the query if first results are weak
  - Retrieve from multiple corpora and combine
  - Perform **multi-hop retrieval** (answer from document A leads to a lookup in document B)
- Supports Points 5, 6 and 7 simultaneously

### 7.3 Hybrid Grounding (Recommended Pattern)
- **Unstructured knowledge** via RAG (policies, manuals)
- **Live structured facts** via tools (account status, balances, case records)
- **Example flow:**
  - User: "Is my pending refund eligible under the new policy?"
  - Agent calls `get_refund_record(user_id)` → structured data
  - Agent calls `search_documents("refund eligibility policy 2026")` → policy text
  - Model composes answer grounded in both, with citations

### 7.4 MCP / Tool Gateway Pattern
- Client systems exposed through MCP servers or an API gateway (e.g., Apigee)
- Benefits: central authentication, authorisation, rate limiting, audit logging
- Strengthens the "named mechanism" claim with a clear architectural boundary

### 7.5 Evidence of Agentic Grounding
- Tool registry: tool name, client system, data accessed, read/write
- Execution trace showing tool call → client data returned → answer built from it
- Access-control model (service accounts, per-user OAuth, role-based permissions)

## 8. Fine-Tuning on Client Data (Handle Carefully)

- **Explicitly listed** in the clause, so it is accepted as a mechanism
- **Weakness:** knowledge is baked into model weights during training, not supplied at inference time
  - Cannot reflect data updated after training
  - Cannot cite sources reliably
  - Higher hallucination risk on specific facts
- **Best use:** domain language, tone, formats, classification behaviour
- **Recommendation:** claim fine-tuning **in combination with** RAG or tool access, never alone
  - Example: "Model adapted via LoRA fine-tuning on client case notes for domain terminology; facts grounded at inference time via RAG over the client corpus"

## 9. Common Pitfalls That Can Cause Rejection

- Stating "RAG-based" without naming corpus, embedding model, or vector store
- Grounding on public or sample data instead of real client data
- No access control — evaluators may question data governance
- No citations — weak proof that output is grounded
- Claiming fine-tuning alone while the clause stresses "at inference time"
- Describing a licence rollout of a general-purpose assistant as a project

## 10. Suggested Bid Response for Point 3

> **Context-grounding: Complied.**
> - **Mechanism:** Hybrid — retrieval-augmented generation (RAG) and tool-mediated data access, executed at inference time for every request
> - **Client corpus:** [N] documents ([types: policies, SOPs, circulars, case files]) from [source systems], refreshed [daily / on change]
> - **Structured data:** live access to [system names, e.g., CRM, case-management DB, BigQuery warehouse] via authenticated APIs and parameterised queries
> - **RAG stack:** [parser] → [chunking strategy] → [embedding model + version] → [vector store] → hybrid search + [re-ranker] → [LLM + version]
> - **Agentic access:** agent selects from [N] tools at runtime, including [tool list]
> - **Controls:** answers restricted to retrieved context; citations to source document/record; user-level access filtering; grounding verification; full audit logging
> - **Exclusion check:** the system cannot answer client-specific queries without access to the client's data; it is not a general-purpose assistant

## 11. Evidence Checklist to Attach

- Architecture diagram showing data sources → ingestion → index → retrieval/tools → LLM
- Corpus description (volume, document types, source systems, refresh frequency)
- Named components with versions (LLM, embedding model, vector store, re-ranker)
- Tool registry (for agentic access)
- 2–3 sample Q&A pairs with citations to client documents or records
- Evaluation report (retrieval recall, faithfulness / groundedness scores)
- Client completion certificate referencing the AI capability
