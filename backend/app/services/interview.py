"""Business logic separated from API, model client and repository connections."""
import json
import uuid
from fastapi import HTTPException
from .generation import ROLES, plan


class InterviewService:
    def __init__(self, db, knowledge, generator, settings):
        self.db, self.knowledge, self.generator, self.settings = db, knowledge, generator, settings

    def create(self, profile, role):
        if role not in ROLES:
            raise HTTPException(422, 'Select a supported role')
        plans = plan(profile, role, self.settings.question_count)
        evidence = [self.knowledge.search(p['query']) for p in plans]
        if any(not chunks for chunks in evidence):
            raise HTTPException(503, 'No relevant textbook context was found. No session was created')
        generated = self.generator.generate(profile, role, plans, evidence)
        sid = uuid.uuid4().hex
        with self.db.connect() as conn:
            conn.execute('INSERT INTO sessions (id,role,profile,status,mode) VALUES (?,?,?,?,?)',
                         (sid, role, json.dumps(profile), 'active', self.settings.mode))
            for i, (q, p, sources) in enumerate(zip(generated, plans, evidence)):
                payload = {**q, 'plan': p, 'sources': sources, 'corpus_sha256': self.knowledge.digest,
                           'model': self.settings.model if self.settings.mode == 'llm' else None,
                           'generation_mode': self.settings.mode}
                conn.execute('INSERT INTO questions (id,session_id,ordinal,payload) VALUES (?,?,?,?)',
                             (uuid.uuid4().hex, sid, i, json.dumps(payload)))
        return self.get(sid)

    def get(self, sid):
        with self.db.connect() as conn:
            session = conn.execute('SELECT * FROM sessions WHERE id=?', (sid,)).fetchone()
            if session is None:
                raise HTTPException(404, 'Session not found')
            rows = conn.execute('SELECT * FROM questions WHERE session_id=? ORDER BY ordinal', (sid,)).fetchall()
        questions = [{'id': r['id'], 'number': r['ordinal'] + 1, **json.loads(r['payload']),
                      'answer': r['answer'], 'answered_at': r['answered_at']} for r in rows]
        return {'id': sid, 'role': ROLES[session['role']]['name'], 'status': session['status'],
                'mode': session['mode'], 'profile': json.loads(session['profile']),
                'created_at': session['created_at'], 'questions': questions,
                'summary': json.loads(session['summary']) if session['summary'] else None}

    def answer(self, sid, request):
        # A write lock covers read + check + answer + completion. Concurrent submissions
        # cannot overwrite a response or advance the wrong question.
        with self.db.connect() as conn:
            conn.execute('BEGIN IMMEDIATE')
            s = conn.execute('SELECT * FROM sessions WHERE id=?', (sid,)).fetchone()
            if not s:
                raise HTTPException(404, 'Session not found')
            current = conn.execute('SELECT * FROM questions WHERE session_id=? AND answer IS NULL ORDER BY ordinal LIMIT 1', (sid,)).fetchone()
            if s['status'] != 'active' or not current or current['id'] != request.question_id:
                raise HTTPException(409, 'Question already answered or not the current question. Refresh the session')
            conn.execute("UPDATE questions SET answer=?,answered_at=strftime('%Y-%m-%dT%H:%M:%fZ','now') WHERE id=?",
                         (request.answer, current['id']))
            rows = conn.execute('SELECT * FROM questions WHERE session_id=? ORDER BY ordinal', (sid,)).fetchall()
            if all(r['answer'] is not None for r in rows):
                summary = self.summarize(rows, json.loads(s['profile']))
                conn.execute('UPDATE sessions SET status=?,summary=? WHERE id=?', ('complete', json.dumps(summary), sid))
        return self.get(sid)

    @staticmethod
    def summarize(rows, profile):
        # Honest descriptive insights, not keyword grading or an automated hiring score.
        word_counts = [len(r['answer'].split()) for r in rows]
        return {'answered': len(rows), 'total_words': sum(word_counts),
                'topics': [json.loads(r['payload'])['focus'] for r in rows],
                'response_lengths': word_counts, 'skills_explored': profile['skills'],
                'short_responses': [r['ordinal'] + 1 for r, n in zip(rows, word_counts) if n < 25],
                'note': 'Response length describes engagement, not correctness. No hiring decision or technical score is inferred. A reviewer should compare answers with cited passages.',
                'next_step': 'Review the sources and explain one concrete example, assumption and tradeoff for each answer.'}

    def delete(self, sid):
        with self.db.connect() as conn:
            changed = conn.execute('DELETE FROM sessions WHERE id=?', (sid,)).rowcount
        if not changed:
            raise HTTPException(404, 'Session not found')
