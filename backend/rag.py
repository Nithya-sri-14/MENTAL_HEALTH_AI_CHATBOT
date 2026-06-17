from __future__ import annotations

import io
import re
from html.parser import HTMLParser
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

import requests

try:
    from bs4 import BeautifulSoup
except Exception:
    BeautifulSoup = None

try:
    from docx import Document
except Exception:
    Document = None

try:
    from pypdf import PdfReader
except Exception:
    PdfReader = None

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from .storage import list_knowledge_files


def _read_txt(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def _read_docx(path: Path) -> str:
    if Document is None:
        return ""
    doc = Document(str(path))
    return "\n".join(p.text for p in doc.paragraphs if p.text.strip())


def _read_pdf(path: Path) -> str:
    if PdfReader is None:
        return ""
    reader = PdfReader(str(path))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def load_document_text(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in {".txt", ".md"}:
        return _read_txt(path)
    if suffix == ".docx":
        return _read_docx(path)
    if suffix == ".pdf":
        return _read_pdf(path)
    return ""


def load_url_text(url: str, timeout: int = 20) -> str:
    response = requests.get(url, timeout=timeout)
    response.raise_for_status()
    if BeautifulSoup is not None:
        soup = BeautifulSoup(response.text, "html.parser")
        for tag in soup(["script", "style", "noscript"]):
            tag.extract()
        return " ".join(chunk.strip() for chunk in soup.get_text(separator=" ").split())

    class _Stripper(HTMLParser):
        def __init__(self):
            super().__init__()
            self.chunks: list[str] = []

        def handle_data(self, data: str) -> None:
            if data and data.strip():
                self.chunks.append(data)

    stripper = _Stripper()
    stripper.feed(response.text)
    text = " ".join(part.strip() for part in stripper.chunks)
    return re.sub(r"\s+", " ", text).strip()


@dataclass
class KnowledgeItem:
    title: str
    text: str
    source: str = "local"


@dataclass
class SimpleRAGStore:
    items: list[KnowledgeItem] = field(default_factory=list)

    def add_items(self, new_items: Iterable[KnowledgeItem]) -> None:
        for item in new_items:
            if item.text and item.text.strip():
                self.items.append(item)

    def load_local_files(self) -> None:
        self.items = []  # reset and load fresh
        self.add_items(
            KnowledgeItem(title=path.name, text=load_document_text(path), source=str(path))
            for path in list_knowledge_files()
        )

    def search(self, query: str, top_k: int = 3) -> list[dict]:
        if not self.items:
            return []
        corpus = [item.text for item in self.items]
        vectorizer = TfidfVectorizer(stop_words="english")
        try:
            matrix = vectorizer.fit_transform(corpus + [query])
            similarities = cosine_similarity(matrix[-1], matrix[:-1]).flatten()
            ranked = similarities.argsort()[::-1][:top_k]
            results = []
            for idx in ranked:
                score = float(similarities[idx])
                if score <= 0.02:  # ignore low match thresholds
                    continue
                item = self.items[idx]
                results.append(
                    {
                        "title": item.title,
                        "source": item.source,
                        "score": round(score, 3),
                        "excerpt": item.text[:400],
                    }
                )
            return results
        except Exception:
            # Fallback if TF-IDF fails (e.g., vocabulary empty)
            return [
                {
                    "title": item.title,
                    "source": item.source,
                    "score": 0.5,
                    "excerpt": item.text[:400],
                }
                for item in self.items[:top_k]
            ]

    def answer(self, query: str) -> tuple[str, list[dict]]:
        results = self.search(query)
        if not results:
            return (
                "No local knowledge matched this query. Upload a document or add a source file to the knowledge base.",
                [],
            )
        from .gemini_service import generate_rag_answer
        answer_text = generate_rag_answer(query, results)
        return answer_text, results


def build_default_rag_store() -> SimpleRAGStore:
    store = SimpleRAGStore()
    store.load_local_files()
    return store
