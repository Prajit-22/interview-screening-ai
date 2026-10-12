"""Thin FastAPI transport: validation and lifecycle orchestration."""
from contextlib import asynccontextmanager
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.concurrency import run_in_threadpool
from .config import Settings
from .db import Database
from .models import AnswerRequest
from .services.resume import parse_resume, MAX_UPLOAD
from .services.knowledge import KnowledgeBase
from .services.generation import Generator, ModelUnavailable, ROLES
from .services.interview import InterviewService


def create_app(settings=None):
    settings = settings or Settings()
    db = Database(settings.database)
    kb = KnowledgeBase(db, settings.corpus)
    service = InterviewService(db, kb, Generator(settings), settings)

    @asynccontextmanager
    async def lifespan(app):
        app.state.index_error = None
        try:
            await run_in_threadpool(kb.load)
        except (ValueError, OSError) as exc:
            app.state.index_error = str(exc)
        yield

    app = FastAPI(title='Groundwork Screening API', version='1.0.0', lifespan=lifespan)
    app.state.service = service
    app.add_middleware(CORSMiddleware, allow_origins=list(settings.cors),
                       allow_methods=['GET', 'POST', 'DELETE'], allow_headers=['Content-Type'])

    @app.get('/api/health')
    def health():
        return {'status': 'ready' if kb.chunks else 'not_ready', 'mode': settings.mode,
                'model': settings.model if settings.mode == 'llm' else None,
                'chunks': len(kb.chunks), 'corpus_sha256': kb.digest,
                'error': getattr(app.state, 'index_error', None)}

    @app.get('/api/roles')
    def roles():
        return [{'id': k, **v} for k, v in ROLES.items()]

    @app.post('/api/sessions', status_code=201)
    async def create_session(resume: UploadFile = File(...), role: str = Form(...)):
        if not kb.chunks:
            raise HTTPException(503, getattr(app.state, 'index_error', None) or 'Textbook index is not ready')
        try:
            # Read at most the limit + sentinel byte. Oversized input is never saved.
            content = await resume.read(MAX_UPLOAD + 1)
            profile = await run_in_threadpool(parse_resume, resume.filename or '', content)
            return await run_in_threadpool(service.create, profile, role)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        except ModelUnavailable as exc:
            raise HTTPException(502, str(exc)) from exc
        finally:
            await resume.close()

    @app.get('/api/sessions/{sid}')
    def get_session(sid: str):
        return service.get(sid)

    @app.post('/api/sessions/{sid}/answers')
    def answer(sid: str, request: AnswerRequest):
        return service.answer(sid, request)

    @app.delete('/api/sessions/{sid}', status_code=204)
    def delete(sid: str):
        service.delete(sid)

    return app


app = create_app()
