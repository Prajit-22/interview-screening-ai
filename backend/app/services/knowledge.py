"""Page-aware chunks + ragkit TF-IDF vectors + BM25 reciprocal-rank fusion.

SQLite is a persistent vector store here, not an ANN engine. NumPy scans its
small matrix exactly. This keeps a one-book assignment easy to inspect.
"""
import hashlib
import json
import re
from pypdf import PdfReader
import numpy as np
from vendor.ragkit.embeddings import TfIdfEmbedder
from vendor.ragkit.chunking import fixed_size_chunks
from vendor.ragkit.retrieval import BM25Retriever
from vendor.ragkit.vectorstore import Document

BOOK_SOURCE = 'The Hundred-Page Machine Learning Book, Andriy Burkov (2019)'
BOOK_URL = 'https://themlbook.com/'
INDEX_VERSION = 'page-char-1100-overlap-180-tfidf-2048-v1'


class KnowledgeBase:
    def __init__(self, db, corpus):
        self.db, self.corpus = db, corpus
        self.embedder = TfIdfEmbedder(max_features=2048)
        self.bm25 = BM25Retriever()
        self.chunks = []
        self.matrix = None
        self.digest = None

    def load(self):
        if not self.corpus.exists():
            raise ValueError('Textbook missing. Run python scripts/download_corpus.py from the repo root')
        digest = hashlib.sha256(self.corpus.read_bytes()).hexdigest()
        with self.db.connect() as conn:
            rows = conn.execute('SELECT * FROM chunks ORDER BY page,id').fetchall()
            meta = {r['key']: r['value'] for r in conn.execute('SELECT * FROM index_metadata')}
        if meta.get('digest') != digest or meta.get('version') != INDEX_VERSION or not rows:
            reader = PdfReader(self.corpus)
            chunks = []
            # Skip cover, preface and TOC; pages retain PDF (not printed) numbering.
            for page_no, page in enumerate(reader.pages, 1):
                text = re.sub(r'\s+', ' ', page.extract_text() or '').strip()
                if page_no < 12 or len(text) < 180:
                    continue
                for i, text_chunk in enumerate(fixed_size_chunks(text, 1100, 180)):
                    chunks.append({'id': f'p{page_no}-c{i}', 'page': page_no,
                                   'source': BOOK_SOURCE, 'text': text_chunk})
            if not chunks:
                raise ValueError('No textbook text could be extracted')
            self.embedder.fit([c['text'] for c in chunks])
            with self.db.connect() as conn:
                conn.execute('DELETE FROM chunks')
                conn.execute('DELETE FROM index_metadata')
                conn.executemany('INSERT INTO chunks VALUES (?,?,?,?,?)',
                                 [(c['id'], c['page'], c['source'], c['text'],
                                   json.dumps(self.embedder.embed(c['text']))) for c in chunks])
                conn.executemany('INSERT INTO index_metadata VALUES (?,?)',
                                 [('digest', digest), ('version', INDEX_VERSION),
                                  ('vocabulary', json.dumps(self.embedder.vocabulary)),
                                  ('idf', json.dumps(self.embedder.idf))])
            return self.load()
        self.embedder.vocabulary = json.loads(meta['vocabulary'])
        self.embedder.idf = json.loads(meta['idf'])
        self.chunks = [{k: r[k] for k in ('id', 'page', 'source', 'text')} for r in rows]
        self.matrix = np.array([json.loads(r['embedding']) for r in rows], dtype=np.float32)
        for c in self.chunks:
            self.bm25.add(Document(id=c['id'], text=c['text']))
        self.digest = digest

    def search(self, query: str, k=3):
        if not self.chunks:
            raise ValueError('Knowledge index is not ready')
        vector = np.array(self.embedder.embed(query), dtype=np.float32)
        sims = self.matrix @ vector
        vector_order = [int(i) for i in np.argsort(-sims)[:20] if sims[i] > 0]
        lexical = self.bm25.search(query, k=20)
        by_id = {c['id']: i for i, c in enumerate(self.chunks)}
        fused = {}
        for ranking in (vector_order, [by_id[r.document.id] for r in lexical if r.score > 0]):
            for rank, i in enumerate(ranking, 1):
                fused[i] = fused.get(i, 0) + 1 / (60 + rank)
        results = []
        for i in sorted(fused, key=lambda x: (-fused[x], self.chunks[x]['id'])):
            # Avoid near-duplicate overlapping windows from the same page.
            if any(r['page'] == self.chunks[i]['page'] for r in results):
                continue
            results.append({**self.chunks[i], 'score': round(fused[i], 6), 'url': BOOK_URL})
            if len(results) == k:
                break
        return results
