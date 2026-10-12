# Mandatory demo video: Groundwork

Aim for 4-6 minutes. Record your own screen and use your own words. Do not say you manually wrote or independently designed parts you cannot explain. Read `docs/design.md`, run the code and understand the modules before recording.

## Before recording

1. Start Ollama and pull `qwen2.5:3b` (or a stronger instruction model).
2. Set `GENERATION_MODE=llm` and its model/base URL in `.env`; restart the backend.
3. Download the corpus, start backend and frontend, and create one test session to warm the model.
4. Confirm the UI says **Model-powered**, not Practice scaffold. If the model fails, fix it before recording. The mandatory RAG question generation should not be demonstrated with practice templates.
5. Use `examples/resume.txt` or a resume you are comfortable showing. Hide API keys and private browser tabs. Zoom to readable text.

## What to show, in order

**0:00 - 0:25 | Problem and stack**
Show the repository/README, then the entry screen. Say: "This system asks technical questions based on a candidate's resume and selected role. The technical evidence comes from Burkov's ML book. The UI is React and TypeScript, the API is FastAPI, and SQLite persists the interview and vectors."

**0:25 - 1:05 | Candidate entry**
Upload the sample resume. Pick AI / ML Engineer. Point out PDF/TXT validation and the visible model mode. Start the interview. Explain that generation may take a few seconds locally.

**1:05 - 2:00 | RAG trace**
Show extracted skills. Open the evidence drawer on question one. Point to the resume anchor, difficulty, dynamic retrieval query, chunk IDs and PDF page number. Open your local PDF on a cited page so the evaluator can see the question is grounded. Explain: "Page-aware chunks are embedded as TF-IDF vectors and saved in SQLite. Cosine retrieval and BM25 rankings are fused. The model receives retrieved evidence and the resume context, and must return valid source IDs."

**2:00 - 2:50 | Interview and continuity**
Give a thoughtful answer and save it. Refresh to show the saved response and next question remain. Answer the remaining questions. Show that responses are saved in order.

**2:50 - 3:30 | Summary and export**
Show topics, answer count and response lengths. Say these are descriptive insights, not a hiring score. Expand a saved answer and its evidence. Export JSON and briefly show the trace fields (query, model, sources and answers).

**3:30 - 4:15 | Resume + role actually matter**
Start another interview using `examples/backend-resume.txt` and Backend Engineer. Show different anchors (API/SQL), retrieval query and question direction. Explain that this role covers ML-serving/backend concerns because the assigned knowledge base is an ML textbook.

**4:15 - 5:00 | Architecture and verification**
Show the README diagram, service folder and API docs. Show `pytest -q` and `npm run build` results. Briefly show SQLite rows for sessions/questions/answers (no private applicant data). Explain atomic answer transactions and visible provider errors without silent fallback.

**5:00 - 5:20 | Honest limits**
Mention lexical rather than neural embeddings, simple skill extraction, no OCR and no production auth. State that model-generated questions need human review. End on the completed summary or repository.

## If asked in the interview

Be able to trace one question from resume skill → topic query → chunks → model prompt → validated JSON → persisted question → answer. Explain why TF-IDF isn't a neural semantic embedding, why a valid citation ID isn't proof of entailment, and why word count isn't correctness. Do not claim optional adaptive questioning is implemented.
