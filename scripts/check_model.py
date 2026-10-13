"""Read-only model preflight. Never print keys, headers, prompts or raw bodies."""
import sys
from pathlib import Path
import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
from app.config import Settings


def check(settings, client):
    endpoint = settings.base_url + '/chat/completions'
    print('Endpoint:', endpoint)
    print('Model:', settings.model)
    if not settings.api_key or settings.api_key == 'ollama':
        print('No hosted-model key loaded. Check LLM_API_KEY in root .env locally. Do not share it.')
        return 1
    try:
        response = client.get(settings.base_url + '/models',
                              headers={'Authorization': 'Bearer ' + settings.api_key})
        print('Models HTTP:', response.status_code)
        if response.status_code != 200:
            print({401: 'Key rejected. Fix the saved key locally; do not share it.',
                   403: 'Account access denied.',
                   404: 'Models endpoint not found. Verify the printed Endpoint.',
                   429: 'Provider rate limit. Wait before retrying.'}.get(response.status_code,
                   'Provider check failed. No response body printed.'))
            return 1
        data = response.json()
        if not isinstance(data, dict) or not isinstance(data.get('data'), list):
            raise ValueError()
        models = {item.get('id') for item in data['data'] if isinstance(item, dict)}
        if settings.model not in models:
            print('Configured model is not listed for this account.')
            for alternative in ('llama-3.3-70b-versatile', 'openai/gpt-oss-20b'):
                if alternative in models:
                    print('Listed alternative:', alternative)
            return 1
        print('Configured model is listed. This checks access/listing, not successful question generation.')
        return 0
    except (httpx.HTTPError, ValueError, TypeError):
        print('Model-list check failed. No key or provider response body printed.')
        return 1


if __name__ == '__main__':
    try:
        settings = Settings()
        with httpx.Client(timeout=25, trust_env=False) as client:
            sys.exit(check(settings, client))
    except (ValueError, OSError):
        print('Invalid local settings. Check root .env locally; do not share it.')
        sys.exit(1)
