# RAGシステム 設計書

## 1. アーキテクチャ設計

### 1.1 コンポーネント構成

```
┌─────────────────────────────────────────────────────────┐
│  Docker Compose ネットワーク                              │
│                                                         │
│  ┌──────────────────┐       ┌──────────────────────┐   │
│  │   Open WebUI     │──────▶│   RAG API Server     │   │
│  │  (port: 3000)    │ HTTP  │   FastAPI             │   │
│  │                  │◀──────│  (port: 8000)         │   │
│  └──────────────────┘       └──────────┬─────────────┘  │
│                                        │                │
│                             ┌──────────▼─────────────┐  │
│                             │   LangGraph Pipeline   │  │
│                             └──────────┬─────────────┘  │
│                                        │                │
│                             ┌──────────▼─────────────┐  │
│                             │   Chroma DB            │  │
│                             │  (volume mount)        │  │
│                             └────────────────────────┘  │
│                                                         │
│  ┌──────────────────────────────────────────────────┐   │
│  │  Indexer（バッチ実行、同一コンテナ or 手動起動）     │   │
│  └──────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
          │ OpenAI API / OpenAI互換API
          ▼
    外部LLM・Embeddingエンドポイント
```

### 1.2 Docker Compose サービス構成

| サービス名 | イメージ | ポート | 役割 |
|-----------|---------|--------|------|
| `rag-api` | `./Dockerfile` でビルド | 8000 | FastAPI + LangGraph |
| `open-webui` | `ghcr.io/open-webui/open-webui:main` | 3000 | フロントエンド |

**ボリューム**

| ボリューム名 | マウント先（コンテナ内） | 内容 |
|------------|----------------------|------|
| `./chroma_db` | `/app/chroma_db` | Chroma永続化データ |
| `./documents` | `/app/documents` | 検索対象ドキュメント |
| `open-webui-data` | `/app/backend/data` | Open WebUI設定・履歴 |

---

## 2. モジュール設計

### 2.1 モジュール一覧と責務

```
RAG-example/
├── indexer.py              # インデックス作成バッチ（CLIエントリポイント）
├── server.py               # FastAPIサーバー（APIエントリポイント）
├── config.py               # 環境変数読み込み・設定管理
├── graph/
│   ├── state.py            # LangGraphステート型定義
│   ├── nodes.py            # 各処理ノード関数
│   └── pipeline.py         # グラフ構築・コンパイル
├── parsers/
│   ├── base.py             # パーサー基底クラス
│   ├── docx_parser.py      # Word (.docx) パーサー
│   ├── pptx_parser.py      # PowerPoint (.pptx) パーサー
│   └── pdf_parser.py       # PDF パーサー
├── vectorstore/
│   └── chroma_client.py    # Chroma CRUD操作
├── chroma_db/              # （Git管理外）
├── documents/              # （Git管理外）
├── Dockerfile
├── docker-compose.yml
├── .env
├── .env.example
├── requirements.txt
└── docs/
```

### 2.2 config.py

環境変数を一元管理する。全モジュールはここからのみ設定値を取得する。

```python
class Settings(BaseSettings):
    # LLM
    llm_api_key: str
    llm_api_base: str = "https://api.openai.com/v1"
    llm_chat_model: str = "gpt-4o"

    # Embedding
    embedding_api_key: str
    embedding_api_base: str = "https://api.openai.com/v1"
    embedding_model: str = "text-embedding-3-small"

    # Chroma
    chroma_persist_dir: str = "./chroma_db"

    # 検索パラメータ
    top_k_chunks: int = 10
    top_k_recommend: int = 5

    model_config = SettingsConfigDict(env_file=".env")

settings = Settings()
```

### 2.3 parsers/

#### 基底クラス（base.py）

```python
@dataclass
class ParsedChunk:
    text: str
    file_path: str        # 絶対パス
    file_name: str
    relative_dir: str     # 指定フォルダからの相対ディレクトリ
    file_type: str        # docx / pptx / pdf
    page_or_slide: int
    last_modified: str    # ISO8601

class BaseParser(ABC):
    @abstractmethod
    def parse(self, file_path: Path, base_dir: Path) -> list[ParsedChunk]:
        ...
```

#### 各パーサーの実装方針

| パーサー | ライブラリ | テキスト抽出単位 |
|---------|-----------|----------------|
| `DocxParser` | `python-docx` | 段落単位で抽出、ページ番号は連番付与 |
| `PptxParser` | `python-pptx` | スライド単位で全テキストボックスを結合 |
| `PdfParser` | `PyMuPDF` | ページ単位で抽出 |

### 2.4 vectorstore/chroma_client.py

```python
class ChromaClient:
    COLLECTION_NAME = "rag_documents"

    def __init__(self, persist_dir: str): ...

    def upsert_chunks(self, chunks: list[ParsedChunk]) -> None:
        """チャンクをEmbeddingしてChromaに保存（IDが同じなら上書き）"""

    def delete_by_file_path(self, file_path: str) -> None:
        """指定ファイルの全チャンクを削除"""

    def similarity_search(self, query: str, k: int) -> list[SearchResult]:
        """類似チャンクをスコア付きで返す"""

    def get_indexed_files(self) -> dict[str, str]:
        """インデックス済みファイルの {絶対パス: last_modified} を返す"""
```

---

## 3. インデックス処理設計（indexer.py）

### 3.1 処理フロー

```
indexer.py --folder <path>
    │
    ├─ 1. フォルダを再帰スキャン
    │       対象拡張子: .docx / .pptx / .pdf
    │
    ├─ 2. 差分検出
    │       Chromaに保存済みの {ファイルパス: last_modified} と比較
    │       ├─ 新規ファイル    → 追加対象
    │       ├─ 更新ファイル    → 削除→再追加対象
    │       └─ 削除ファイル    → 削除対象（Chromaから除去）
    │
    ├─ 3. 削除処理
    │       delete_by_file_path() で対象ファイルのチャンクを削除
    │
    ├─ 4. パース & チャンク分割
    │       各ファイルをパーサーで ParsedChunk リストに変換
    │       RecursiveCharacterTextSplitter で分割
    │           chunk_size=500, chunk_overlap=50, 区切り文字=["\n\n", "\n", "。", "、"]
    │
    └─ 5. Embedding & 保存
            upsert_chunks() でChromaに保存
```

### 3.2 チャンクID設計

```
{ファイル絶対パスのMD5ハッシュ}_{page_or_slide}_{チャンク連番}
例: a3f2c1d4_03_002
```

ファイルパスのMD5を使用することでパス変更時の衝突を回避しつつIDを一定長に保つ。

---

## 4. LangGraphパイプライン設計

### 4.1 ステート定義（graph/state.py）

```python
class RAGState(TypedDict):
    query: str                          # ユーザーの質問
    chunks: list[SearchResult]          # 検索で取得したチャンク（スコア付き）
    recommend_list: list[RecommendItem] # ファイル単位に集約したレコメンド
    answer: str                         # LLMが生成した回答
    final_response: str                 # 最終出力テキスト

@dataclass
class SearchResult:
    text: str
    score: float
    file_name: str
    relative_dir: str
    file_path: str
    page_or_slide: int

@dataclass
class RecommendItem:
    file_name: str
    relative_dir: str
    score: float            # ファイル内チャンクの最大スコアを採用
```

### 4.2 グラフ構造（graph/pipeline.py）

```
[START]
   │
   ▼
[retrieve_node]      Chromaからチャンクを取得
   │
   ▼
[aggregate_node]     チャンクをファイル単位に集約・ランキング
   │
   ▼
[generate_node]      LLMで回答生成
   │
   ▼
[format_node]        回答＋レコメンドリストを最終テキストに整形
   │
   ▼
[END]
```

### 4.3 各ノードの責務（graph/nodes.py）

#### retrieve_node
- `ChromaClient.similarity_search(query, k=TOP_K_CHUNKS)` を呼び出す
- 結果を `state["chunks"]` にセット

#### aggregate_node
- `chunks` をファイルパスでグループ化
- ファイルごとにチャンクスコアの **最大値** を代表スコアとして採用
- スコア降順でソートし、上位 `TOP_K_RECOMMEND` 件を `state["recommend_list"]` にセット

#### generate_node
- `chunks` からテキストを結合しコンテキストを構築
- 下記システムプロンプトと合わせてLLMに送信
- 生成結果を `state["answer"]` にセット

**システムプロンプト**
```
あなたは社内ドキュメント検索アシスタントです。
必ず日本語で回答してください。
提供されたコンテキストのみを根拠として回答し、
コンテキストに情報がない場合は「資料内に該当する情報が見つかりませんでした」と答えてください。
```

#### format_node
- `answer` と `recommend_list` を整形して `state["final_response"]` にセット

```
【回答】
{answer}

【関連資料】
1. {file_name}  スコア: {score:.2f}  ({relative_dir})
...
```

---

## 5. APIサーバー設計（server.py）

### 5.1 エンドポイント詳細

#### `POST /v1/chat/completions`

Open WebUIから受け取るリクエスト形式（OpenAI互換）。

**リクエスト（抜粋）**
```json
{
  "model": "rag-model",
  "messages": [
    {"role": "user", "content": "有給休暇の申請方法は？"}
  ],
  "stream": false
}
```

**処理フロー**
1. `messages` の末尾 `user` ロールのコンテンツをクエリとして抽出
2. LangGraphパイプラインを実行
3. `final_response` をOpenAI互換レスポンス形式にラップして返す

**レスポンス**
```json
{
  "id": "chatcmpl-xxxx",
  "object": "chat.completion",
  "model": "rag-model",
  "choices": [{
    "index": 0,
    "message": {
      "role": "assistant",
      "content": "【回答】\n有給休暇の申請は...\n\n【関連資料】\n1. ..."
    },
    "finish_reason": "stop"
  }]
}
```

#### `GET /v1/models`

```json
{
  "object": "list",
  "data": [{"id": "rag-model", "object": "model"}]
}
```

#### `GET /health`

```json
{"status": "ok"}
```

---

## 6. Docker設計

### 6.1 Dockerfile

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# システム依存ライブラリ（PyMuPDF用）
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 libglib2.0-0 && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000"]
```

### 6.2 docker-compose.yml 構成

```yaml
services:
  rag-api:
    build: .
    ports:
      - "8000:8000"
    volumes:
      - ./chroma_db:/app/chroma_db
      - ./documents:/app/documents
    env_file:
      - .env
    restart: unless-stopped

  open-webui:
    image: ghcr.io/open-webui/open-webui:main
    ports:
      - "3000:8080"
    volumes:
      - open-webui-data:/app/backend/data
    environment:
      - OPENAI_API_BASE_URL=http://rag-api:8000/v1
      - OPENAI_API_KEY=dummy
    depends_on:
      - rag-api
    restart: unless-stopped

volumes:
  open-webui-data:
```

> Open WebUIの `OPENAI_API_BASE_URL` にRAG APIサーバーのURLを指定することで接続する。

---

## 7. シーケンス図

### 7.1 質問応答フロー

```
Open WebUI    FastAPI     LangGraph      Chroma      LLM API
    │             │            │             │           │
    │─POST /v1/──▶│            │             │           │
    │ chat/       │            │             │           │
    │ completions │            │             │           │
    │             │─invoke()──▶│             │           │
    │             │            │─similarity_▶│           │
    │             │            │  search()   │           │
    │             │            │◀────────────│           │
    │             │            │  chunks     │           │
    │             │            │─aggregate───│           │
    │             │            │  (内部処理)  │           │
    │             │            │─────────────────────────▶│
    │             │            │  chat/completions        │
    │             │            │◀─────────────────────────│
    │             │            │  answer                  │
    │             │            │─format──────│           │
    │             │            │  (内部処理)  │           │
    │             │◀───────────│             │           │
    │             │  final_response          │           │
    │◀────────────│            │             │           │
    │  response   │            │             │           │
```

### 7.2 インデックス処理フロー

```
indexer.py    FileSystem    Parsers     ChromaClient   Embedding API
    │             │            │             │              │
    │─scan()─────▶│            │             │              │
    │◀────────────│            │             │              │
    │  file list  │            │             │              │
    │─get_indexed_────────────▶│             │              │
    │  files()                 │             │              │
    │◀─────────────────────────│             │              │
    │  indexed map             │             │              │
    │─diff check──│            │             │              │
    │  (内部処理)  │            │             │              │
    │─delete_by───────────────▶│             │              │
    │  file_path()             │             │              │
    │─parse()─────────────────▶│             │              │
    │◀─────────────────────────│             │              │
    │  ParsedChunk[]           │             │              │
    │─upsert_chunks()─────────▶│             │              │
    │                          │─embed()─────────────────────▶│
    │                          │◀─────────────────────────────│
    │                          │  vectors                     │
    │                          │─add()       │              │
    │◀─────────────────────────│             │              │
    │  完了                    │             │              │
```

---

## 8. requirements.txt（主要ライブラリ）

```
# Web Framework
fastapi>=0.111.0
uvicorn[standard]>=0.29.0

# LangChain / LangGraph
langchain>=0.2.0
langgraph>=0.1.0
langchain-openai>=0.1.0
langchain-chroma>=0.1.0

# Document Parsers
python-docx>=1.1.0
python-pptx>=0.6.23
pymupdf>=1.24.0

# Config
pydantic-settings>=2.0.0
python-dotenv>=1.0.0
```

---

## 9. エラーハンドリング方針

| 発生箇所 | エラー内容 | 対応 |
|---------|-----------|------|
| パーサー | 破損・読み取り不可ファイル | ログ出力してスキップ、処理継続 |
| Embedding API | タイムアウト・レート制限 | 指数バックオフで最大3回リトライ |
| LLM API | タイムアウト・レート制限 | 指数バックオフで最大3回リトライ |
| LLM API | コンテキスト長超過 | チャンク数を減らして再試行 |
| Chroma | DB読み書きエラー | 例外をHTTP 500に変換してクライアントに返す |
| インデックス時 | フォルダが存在しない | エラーメッセージを表示して即時終了 |
