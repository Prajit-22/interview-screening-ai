"""Bounded upload parsing, intentionally explainable skill extraction."""
import io
import re
from pypdf import PdfReader

MAX_UPLOAD = 2 * 1024 * 1024
SKILLS = {
    'Python': r'\bpython\b', 'SQL': r'\bsql\b', 'FastAPI': r'\bfastapi\b',
    'Django': r'\bdjango\b', 'React': r'\breact\b', 'Java': r'\bjava\b',
    'Spring Boot': r'\bspring\s+boot\b', 'Docker': r'\bdocker\b',
    'NLP': r'\bnlp\b|natural language', 'RAG': r'\brag\b|retrieval.augmented',
    'Machine Learning': r'machine learning|\bscikit.learn\b',
    'TensorFlow': r'\btensorflow\b', 'PyTorch': r'\bpytorch\b',
    '.NET': r'\.net\b', 'Node.js': r'\bnode(?:\.js)?\b',
    'Cybersecurity': r'cyber.?security|\bstride\b',
}


def parse_resume(filename: str, content: bytes) -> dict:
    if not content or len(content) > MAX_UPLOAD:
        raise ValueError('Upload a non-empty resume smaller than 2 MB')
    try:
        if filename.lower().endswith('.pdf'):
            if not content.startswith(b'%PDF-'):
                raise ValueError('This file is not a PDF')
            reader = PdfReader(io.BytesIO(content))
            if reader.is_encrypted or len(reader.pages) > 10:
                raise ValueError('Use an unencrypted PDF with at most 10 pages')
            text = '\n'.join(page.extract_text() or '' for page in reader.pages)
        elif filename.lower().endswith('.txt'):
            text = content.decode('utf-8')
        else:
            raise ValueError('Supported resume formats: PDF and UTF-8 TXT')
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError('Could not read this resume; try a text-based PDF or TXT') from exc
    text = text.strip()
    if len(text) < 40:
        raise ValueError('Resume has too little readable text. Scanned PDFs need OCR first')
    if len(text) > 40000:
        raise ValueError('Resume text is too long (maximum 40,000 characters)')
    skills = [name for name, pattern in SKILLS.items() if re.search(pattern, text, re.I)]
    domains = [x for x in ['NLP', 'RAG', 'Machine Learning', 'Cybersecurity'] if x in skills]
    advanced = bool(re.search(r'\bsenior\b|\blead\b|[3-9]\+?\s+years', text, re.I))
    # A heuristic, never a claim about the candidate's real competence.
    return {'skills': skills, 'domains': domains, 'difficulty': 'applied' if advanced else 'foundational',
            'background': [line.strip()[:220] for line in text.splitlines()
                           if re.search(r'project|built|develop|pipeline|rag|api|model', line, re.I)][:6],
            'difficulty_basis': 'Resume seniority keywords' if advanced else 'Default early-career level'}
