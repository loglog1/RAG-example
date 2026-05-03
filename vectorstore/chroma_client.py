import hashlib
import logging
from dataclasses import dataclass

import chromadb
from langchain_openai import OpenAIEmbeddings
from langchain_chroma import Chroma

from config import settings
from parsers.base import ParsedChunk

logger = logging.getLogger(__name__)

COLLECTION_NAME = "rag_documents"


@dataclass
class SearchResult:
    text: str
    score: float
    file_name: str
    relative_dir: str
    file_path: str
    page_or_slide: int


def _make_chunk_id(file_path: str, page_or_slide: int, chunk_index: int) -> str:
    path_hash = hashlib.md5(file_path.encode()).hexdigest()[:8]
    return f"{path_hash}_{page_or_slide:03d}_{chunk_index:03d}"


def _build_embeddings() -> OpenAIEmbeddings:
    return OpenAIEmbeddings(
        model=settings.embedding_model,
        api_key=settings.embedding_api_key,
        base_url=settings.embedding_api_base,
    )


class ChromaClient:
    def __init__(self) -> None:
        self._client = chromadb.PersistentClient(path=settings.chroma_persist_dir)
        self._embeddings = _build_embeddings()
        self._store = Chroma(
            client=self._client,
            collection_name=COLLECTION_NAME,
            embedding_function=self._embeddings,
        )

    def upsert_chunks(self, chunks: list[ParsedChunk], split_chunks: list[tuple[ParsedChunk, str, int]]) -> None:
        """split_chunks: (元ParsedChunk, 分割後テキスト, チャンク連番) のリスト"""
        ids = []
        texts = []
        metadatas = []

        for original, text, idx in split_chunks:
            chunk_id = _make_chunk_id(original.file_path, original.page_or_slide, idx)
            ids.append(chunk_id)
            texts.append(text)
            metadatas.append({
                "file_path": original.file_path,
                "file_name": original.file_name,
                "relative_dir": original.relative_dir,
                "file_type": original.file_type,
                "page_or_slide": original.page_or_slide,
                "last_modified": original.last_modified,
            })

        if ids:
            self._store.add_texts(texts=texts, metadatas=metadatas, ids=ids)
            logger.info("Upserted %d chunks.", len(ids))

    def delete_by_file_path(self, file_path: str) -> None:
        collection = self._client.get_or_create_collection(COLLECTION_NAME)
        results = collection.get(where={"file_path": file_path}, include=[])
        if results["ids"]:
            collection.delete(ids=results["ids"])
            logger.info("Deleted %d chunks for %s.", len(results["ids"]), file_path)

    def similarity_search(self, query: str, k: int) -> list[SearchResult]:
        results = self._store.similarity_search_with_relevance_scores(query, k=k)
        search_results: list[SearchResult] = []
        for doc, score in results:
            m = doc.metadata
            search_results.append(SearchResult(
                text=doc.page_content,
                score=score,
                file_name=m.get("file_name", ""),
                relative_dir=m.get("relative_dir", ""),
                file_path=m.get("file_path", ""),
                page_or_slide=m.get("page_or_slide", 0),
            ))
        return search_results

    def get_indexed_files(self) -> dict[str, str]:
        """インデックス済みファイルの {絶対パス: last_modified} を返す"""
        collection = self._client.get_or_create_collection(COLLECTION_NAME)
        results = collection.get(include=["metadatas"])
        file_map: dict[str, str] = {}
        for meta in results.get("metadatas") or []:
            if meta and "file_path" in meta:
                file_map[meta["file_path"]] = meta.get("last_modified", "")
        return file_map
