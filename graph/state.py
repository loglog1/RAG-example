from dataclasses import dataclass
from typing import TypedDict

from vectorstore.chroma_client import SearchResult


@dataclass
class RecommendItem:
    file_name: str
    relative_dir: str
    score: float


class RAGState(TypedDict):
    query: str
    chunks: list[SearchResult]
    recommend_list: list[RecommendItem]
    answer: str
    final_response: str
