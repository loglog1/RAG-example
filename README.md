# RAG-example

社内ドキュメント（Word / PowerPoint / PDF）を横断検索し、質問への回答と関連資料をレコメンドするRAGシステムです。

## 必要環境

- Docker
- Docker Compose

## セットアップ

### 1. 環境変数の設定

```bash
cp .env.example .env
```

`.env` を開き、APIキーとモデル名を設定してください。

**OpenAI APIを使用する場合**
```env
LLM_API_KEY=sk-xxxx
LLM_API_BASE=https://api.openai.com/v1
LLM_CHAT_MODEL=gpt-4o

EMBEDDING_API_KEY=sk-xxxx
EMBEDDING_API_BASE=https://api.openai.com/v1
EMBEDDING_MODEL=text-embedding-3-small
```

**OpenAI互換API（Ollama等）を使用する場合**
```env
LLM_API_KEY=dummy
LLM_API_BASE=http://host.docker.internal:11434/v1
LLM_CHAT_MODEL=llama3

EMBEDDING_API_KEY=dummy
EMBEDDING_API_BASE=http://host.docker.internal:11434/v1
EMBEDDING_MODEL=nomic-embed-text
```

### 2. ドキュメントフォルダの準備

```bash
mkdir -p documents chroma_db
```

`documents/` フォルダに検索対象の `.docx` / `.pptx` / `.pdf` ファイルを配置してください。サブフォルダも再帰的に読み込まれます。

```
documents/
├── 製品マニュアル.pdf
├── regulations/
│   └── 社内規程2024.docx
└── products/
    └── 導入手順書.pptx
```

### 3. インデックスの作成

```bash
docker compose run --rm rag-api python indexer.py --folder /app/documents
```

ファイル数に応じて数分かかります。週次で再実行することで差分のみ更新されます。

### 4. サービスの起動

```bash
docker compose up -d
```

起動後、ブラウザで [http://localhost:3000](http://localhost:3000) を開くとOpen WebUIにアクセスできます。

初回起動時はOpen WebUIのアカウント作成画面が表示されます。ローカル環境用のアカウントを作成してください。

## 使い方

1. Open WebUI（http://localhost:3000）にアクセス
2. モデルとして `rag-model` を選択
3. 日本語で質問を入力すると、回答と関連資料が表示されます

**出力例**
```
【回答】
有給休暇の申請は、申請フォームに必要事項を記入のうえ...

【関連資料】
1. 就業規則.pdf          スコア: 0.91  (regulations/)
2. 有給申請手順書.docx   スコア: 0.85  (hr/)
3. FAQ集.pdf             スコア: 0.72  (support/)
```

## 週次インデックス更新

`documents/` フォルダのファイルを追加・更新・削除した後、以下を実行してください。変更のあったファイルのみ再インデックスされます。

```bash
docker compose run --rm rag-api python indexer.py --folder /app/documents
```

## サービスの停止

```bash
docker compose down
```

## ファイル構成

```
RAG-example/
├── indexer.py              # インデックス作成バッチ
├── server.py               # FastAPI サーバー（OpenAI互換API）
├── config.py               # 環境変数管理
├── graph/                  # LangGraphパイプライン
├── parsers/                # ドキュメントパーサー
├── vectorstore/            # Chroma操作
├── Dockerfile
├── docker-compose.yml
├── .env.example
└── docs/
    ├── specification.md    # 仕様書
    └── design.md           # 設計書
```
