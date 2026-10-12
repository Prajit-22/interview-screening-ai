# Design notes and interview preparation

## How to explain it

Start with the lifecycle: upload → parse → plan → retrieve → generate → store → answer → summarize. Routes should not contain retrieval or model details; that is why the services are separate.

**What is the embedding?** A TF-IDF vector with one dimension per fitted vocabulary token. Term frequency is weighted by inverse document frequency and normalized to unit length. It is deterministic and lexical. It does not understand paraphrases as well as a neural embedding.

**Why combine BM25 and vectors if both are lexical?** They use different scoring/normalization. BM25 emphasizes rare terms and document length; normalized vectors compare weighted term direction. RRF combines rank positions without assuming their score scales match. A neural embedding is the natural next experiment, measured on a small labelled query set.

**Why SQLite instead of Chroma?** One corpus, 321 chunks and a local demo. SQLite makes sessions and the vector store inspectable with one dependency-free database. Exact matrix scanning is fine at this size. It is not suitable for millions of vectors without an ANN index.

**How does resume influence output?** Known skills become anchors; the role prioritizes those anchors differently. ML prioritizes RAG/NLP, backend prioritizes FastAPI/Django/SQL. Role topics and anchors construct retrieval queries. Difficulty is only a keyword hint, not a competence score. The model also sees selected project lines. Replace the heuristic with validated structured extraction if the project grows.

**How are hallucinations limited?** Only textbook excerpts are supplied; a schema and chunk-ID check reject invalid outputs. Citations do not prove that every claim is supported. A stronger version would check entailment and measure grounding with a labelled test set.

**Why generate before inserting?** Avoid abandoned partially-created sessions if question 2 or 3 fails. A production version would use a background job with explicit `generating` / `failed` states and idempotency keys to handle long requests.

**What prevents two answers racing?** A SQLite write transaction (`BEGIN IMMEDIATE`) reads the first unanswered question and updates it under the same lock. The second stale submission gets a 409 instead of overwriting the first answer.

**Why no automatic score?** Reliable technical grading needs an explicit rubric and validation. Descriptive insights are preferable to a misleading keyword score, especially in a hiring context.

**What is not done?** OCR, neural embeddings, adaptive follow-ups, real authentication, a semantic grounding evaluator, multi-tenant access control and deployment. Do not claim these as implemented.

## Vendored code provenance

`backend/vendor/ragkit/` contains the original MIT license and these unchanged source modules from Prajit-22/ragkit: `chunking.py`, `embeddings.py`, `retrieval.py`, `vectorstore.py`. The package initializer is intentionally minimal because this application uses only retrieval components. Snapshot commit: dc5f69cf9c9a0496414f4b51e970a719a96448b6. No runtime GitHub dependency is needed.

## Storage sketch

- sessions: random ID, selected role, extracted profile JSON, lifecycle status, mode, timestamp, persisted summary JSON.
- questions: random ID, owning session, ordinal, generation/evidence trace JSON, answer, answer timestamp. Foreign-key cascade and unique session/ordinal.
- chunks: deterministic page/chunk ID, PDF page, book title, text, normalized vector JSON.
- index_metadata: PDF SHA-256, chunking/index version, fitted vocabulary and IDF values. A changed corpus rebuilds the index transactionally. Historical questions retain their original source excerpts/checksum.
