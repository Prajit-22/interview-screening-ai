"""Fetch the assignment's primary book over verified TLS; never commit its bytes."""
import hashlib
from pathlib import Path
import urllib.request

URL = ('https://raw.githubusercontent.com/lyric12345/'
       'The-Hundred-Page-Machine-Learning-Book-by-Andriy-Burkov/master/'
       'The%20Hundred%20Page%20Machine%20Learning%20Book.pdf')
EXPECTED_SHA256 = '06552f7f9aa900702a5c04c882558563586098bfa280c7c8bdc8133ca4a17c8b'
ROOT = Path(__file__).resolve().parents[1]


def main():
    dest = ROOT / 'data/hundred-page-ml.pdf'
    dest.parent.mkdir(exist_ok=True)
    data = urllib.request.urlopen(URL, timeout=60).read()
    if not data.startswith(b'%PDF-') or hashlib.sha256(data).hexdigest() != EXPECTED_SHA256:
        raise ValueError('Textbook checksum changed. Inspect the source before accepting new bytes')
    dest.write_bytes(data)
    print(f'Saved {dest.name}: {len(data):,} bytes; SHA256 {EXPECTED_SHA256}')


if __name__ == '__main__':
    main()
