import logging

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage

from config import settings
from graph.state import RAGState, RecommendItem
from vectorstore.chroma_client import ChromaClient, SearchResult

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "あなたは社内ドキュメント検索アシスタントです。\n"
    "必ず日本語で回答してください。\n"
    "提供されたコンテキストのみを根拠として回答し、"
    "コンテキストに情報がない場合は「資料内に該当する情報が見つかりませんでした」と答えてください。"
)

_chroma_client: ChromaClient | None = None


def get_chroma_client() -> ChromaClient:
    global _chroma_client
    if _chroma_client is None:
        _chroma_client = ChromaClient()
    return _chroma_client


def retrieve_node(state: RAGState) -> dict:
    client = get_chroma_client()
    chunks: list[SearchResult] = client.similarity_search(
        state["query"], k=settings.top_k_chunks
    )
    return {"chunks": chunks}


def aggregate_node(state: RAGState) -> dict:
    file_scores: dict[str, dict] = {}
    for chunk in state["chunks"]:
        key = chunk.file_path
        if key not in file_scores or chunk.score > file_scores[key]["score"]:
            file_scores[key] = {
                "file_name": chunk.file_name,
                "relative_dir": chunk.relative_dir,
                "score": chunk.score,
            }

    sorted_files = sorted(file_scores.values(), key=lambda x: x["score"], reverse=True)
    recommend_list = [
        RecommendItem(
            file_name=f["file_name"],
            relative_dir=f["relative_dir"],
            score=f["score"],
        )
        for f in sorted_files[: settings.top_k_recommend]
    ]
    return {"recommend_list": recommend_list}


def generate_node(state: RAGState) -> dict:
    context = "\n\n".join(chunk.text for chunk in state["chunks"])
    llm = ChatOpenAI(
        model=settings.llm_chat_model,
        api_key=settings.llm_api_key,
        base_url=settings.llm_api_base,
    )
    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=f"コンテキスト:\n{context}\n\n質問: {state['query']}"),
    ]
    response = llm.invoke(messages)
    return {"answer": response.content}


def format_node(state: RAGState) -> dict:
    lines = ["【回答】", state["answer"], "", "【関連資料】"]
    for i, item in enumerate(state["recommend_list"], start=1):
        dir_part = f"  ({item.relative_dir})" if item.relative_dir else ""
        lines.append(f"{i}. {item.file_name}  スコア: {item.score:.2f}{dir_part}")
    return {"final_response": "\n".join(lines)}
