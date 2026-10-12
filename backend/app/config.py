"""Small explicit settings object. No keys, resumes or prompts in logs."""
import os
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / '.env', encoding='utf-8-sig')


def clean_value(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
        value = value[1:-1].strip()
    return value


def model_base_url(value: str) -> str:
    value = clean_value(value).rstrip('/')
    parts = urlsplit(value)
    path = parts.path.rstrip('/')
    # Accept a pasted completion URL, but store only its API base.
    if path.endswith('/chat/completions'):
        path = path[:-len('/chat/completions')]
    # These common partial Groq bases all refer to the same API.
    # Do not repair arbitrary hosts or unknown paths.
    if parts.hostname == 'api.groq.com' and path in ('', '/v1', '/openai', '/openai/v1'):
        path = '/openai/v1'
    return urlunsplit((parts.scheme, parts.netloc, path, parts.query, parts.fragment))


def root_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


@dataclass(frozen=True)
class Settings:
    database: Path = root_path(os.getenv('DATABASE_PATH', 'data/screening.db'))
    corpus: Path = root_path(os.getenv('CORPUS_PATH', 'data/hundred-page-ml.pdf'))
    mode: str = os.getenv('GENERATION_MODE', 'practice')
    base_url: str = field(default_factory=lambda: os.getenv('LLM_BASE_URL', 'http://localhost:11434/v1'))
    model: str = field(default_factory=lambda: os.getenv('LLM_MODEL', 'qwen2.5:3b'))
    api_key: str = os.getenv('LLM_API_KEY', 'ollama')
    json_schema: bool = os.getenv('LLM_JSON_SCHEMA', 'false').lower() == 'true'
    timeout: float = float(os.getenv('LLM_TIMEOUT', '90'))
    question_count: int = int(os.getenv('QUESTION_COUNT', '3'))
    cors: tuple = tuple(os.getenv('CORS_ORIGINS', 'http://localhost:5173,http://127.0.0.1:5173').split(','))

    def __post_init__(self):
        object.__setattr__(self, 'base_url', model_base_url(self.base_url))
        object.__setattr__(self, 'model', clean_value(self.model))
        parts = urlsplit(self.base_url)
        if parts.scheme not in {'http', 'https'} or not parts.netloc or parts.query or parts.fragment or parts.username or parts.password:
            raise ValueError('LLM_BASE_URL must be an http(s) API base without credentials, a query or a fragment')
        if not self.model:
            raise ValueError('LLM_MODEL must not be empty')
        if self.mode not in {'practice', 'llm'}:
            raise ValueError('GENERATION_MODE must be practice or llm')
        if not 1 <= self.question_count <= 8:
            raise ValueError('QUESTION_COUNT must be between 1 and 8')
        if self.timeout <= 0:
            raise ValueError('LLM_TIMEOUT must be positive')
