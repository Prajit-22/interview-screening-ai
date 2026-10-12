"""Small explicit settings object. No keys, resumes or prompts in logs."""
import os
from dataclasses import dataclass
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / '.env')


def root_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


@dataclass(frozen=True)
class Settings:
    database: Path = root_path(os.getenv('DATABASE_PATH', 'data/screening.db'))
    corpus: Path = root_path(os.getenv('CORPUS_PATH', 'data/hundred-page-ml.pdf'))
    mode: str = os.getenv('GENERATION_MODE', 'practice')
    base_url: str = os.getenv('LLM_BASE_URL', 'http://localhost:11434/v1').rstrip('/')
    model: str = os.getenv('LLM_MODEL', 'qwen2.5:3b')
    api_key: str = os.getenv('LLM_API_KEY', 'ollama')
    json_schema: bool = os.getenv('LLM_JSON_SCHEMA', 'false').lower() == 'true'
    timeout: float = float(os.getenv('LLM_TIMEOUT', '90'))
    question_count: int = int(os.getenv('QUESTION_COUNT', '3'))
    cors: tuple = tuple(os.getenv('CORS_ORIGINS', 'http://localhost:5173,http://127.0.0.1:5173').split(','))

    def __post_init__(self):
        if self.mode not in {'practice', 'llm'}:
            raise ValueError('GENERATION_MODE must be practice or llm')
        if not 1 <= self.question_count <= 8:
            raise ValueError('QUESTION_COUNT must be between 1 and 8')
        if self.timeout <= 0:
            raise ValueError('LLM_TIMEOUT must be positive')
