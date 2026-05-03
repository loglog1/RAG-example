import time
import uuid
import logging

from fastapi import FastAPI
from pydantic import BaseModel

from graph.pipeline import pipeline

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(title="RAG API Server")

MODEL_ID = "rag-model"


# --- リクエスト/レスポンスモデル ---

class ChatMessage(BaseModel):
    role: str
    content: str


class ChatCompletionRequest(BaseModel):
    model: str = MODEL_ID
    messages: list[ChatMessage]
    stream: bool = False


class ChatCompletionChoice(BaseModel):
    index: int
    message: ChatMessage
    finish_reason: str


class ChatCompletionResponse(BaseModel):
    id: str
    object: str = "chat.completion"
    created: int
    model: str
    choices: list[ChatCompletionChoice]


# --- エンドポイント ---

@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/v1/models")
def list_models():
    return {
        "object": "list",
        "data": [{"id": MODEL_ID, "object": "model"}],
    }


@app.post("/v1/chat/completions", response_model=ChatCompletionResponse)
def chat_completions(request: ChatCompletionRequest):
    # 末尾のuserメッセージをクエリとして使用
    query = ""
    for msg in reversed(request.messages):
        if msg.role == "user":
            query = msg.content
            break

    logger.info("Query: %s", query)

    result = pipeline.invoke({"query": query})
    final_response = result["final_response"]

    return ChatCompletionResponse(
        id=f"chatcmpl-{uuid.uuid4().hex}",
        created=int(time.time()),
        model=MODEL_ID,
        choices=[
            ChatCompletionChoice(
                index=0,
                message=ChatMessage(role="assistant", content=final_response),
                finish_reason="stop",
            )
        ],
    )
