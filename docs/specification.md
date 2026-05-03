# RAGシステム 仕様書

## 1. システム概要

指定フォルダ配下のWord・PowerPoint・PDFファイルを読み込み、ユーザーの質問に対して回答を生成するとともに、回答が存在する可能性が高い資料をレコメンドするシステム。

---

## 2. 目的・スコープ

| 項目 | 内容 |
|------|------|
| 目的 | 社内ドキュメントを横断的に検索し、質問への回答と関連資料を提示する |
| 対応言語 | 日本語（入力・出力ともに日本語限定） |
| 対象ファイル形式 | `.docx`（Word）、`.pptx`（PowerPoint）、`.pdf` |

---

## 3. 技術スタック

| 層 | 技術 |
|----|------|
| 言語 | Python 3.11+ |
| フロントエンド | Open WebUI |
| RAGフレームワーク | LangChain, LangGraph |
| LLM | OpenAI API または OpenAI互換API（エンドポイント・モデル名を設定で切替） |
| Embedding | OpenAI API または OpenAI互換API（エンドポイント・モデル名を設定で切替） |
| ベクトルDB | Chroma（ローカル永続化） |
| APIサーバー | FastAPI（OpenAI互換エンドポイント） |
| ドキュメントパーサー | `python-docx`、`python-pptx`、`PyMuPDF` |
| 開発環境 | Docker、Docker Compose |

---

## 4. システム構成

```
Open WebUI
    │ OpenAI互換API（HTTP）
    ▼
FastAPI サーバー
    │
    ▼
LangGraph パイプライン
    ├── クエリ前処理（日本語正規化）
    ├── ベクトル検索（Chroma）
    ├── 関連チャンク取得・スコアリング
    ├── 回答生成（GPT-4o）
    └── レコメンド結果整形
    
Chroma DB（ローカル）
    │
    ▼
インデクサー（週次バッチ）
    ├── フォルダ再帰スキャン
    ├── ファイルパーサー
    │   ├── python-docx（.docx）
    │   ├── python-pptx（.pptx）
    │   └── PyMuPDF（.pdf）
    ├── チャンク分割
    └── Embedding生成・保存
```

---

## 5. 機能仕様

### 5.1 ドキュメントインデックス機能

| 項目 | 仕様 |
|------|------|
| 対象フォルダ | 実行時コマンドライン引数で指定 |
| サブフォルダ | 再帰的に読み込む |
| 想定ファイル数 | 100件以上 |
| 想定ファイルサイズ | 数MB程度／ファイル |
| チャンクサイズ | 500トークン（オーバーラップ50トークン） |
| 更新頻度 | 週1回（手動または cronによるバッチ実行） |
| 差分更新 | ファイルの更新日時を記録し、変更分のみ再インデックス |

**インデックス実行コマンド例**
```bash
python indexer.py --folder /path/to/documents
```

### 5.2 質問応答・レコメンド機能

**入力**
- ユーザーの質問文（日本語）

**処理フロー（LangGraph）**
1. クエリをEmbeddingに変換
2. ChromaDBから類似チャンクをTop-K（デフォルト10件）取得
3. チャンクをファイル単位に集約し関連スコアを算出
4. 上位5ファイルをレコメンドリストとして整形
5. Top-K チャンクをコンテキストとしてGPTに渡し回答生成

**出力フォーマット**
```
【回答】
〇〇については〜〜〜です。

【関連資料】
1. 製品マニュアルv2.pdf         スコア: 0.92  (products/manuals/)
2. 社内規程2024年版.docx        スコア: 0.87  (regulations/)
3. 導入手順書.pptx              スコア: 0.81  (products/setup/)
4. FAQ集.pdf                   スコア: 0.74  (support/)
5. 仕様概要資料.docx            スコア: 0.68  (products/)
```

※ サブディレクトリは指定フォルダからの相対パスで表示する

### 5.3 APIエンドポイント

Open WebUIと接続するためのOpenAI互換APIを提供する。

| エンドポイント | メソッド | 説明 |
|----------------|----------|------|
| `/v1/chat/completions` | POST | チャット形式の質問応答 |
| `/v1/models` | GET | 利用可能モデル一覧 |
| `/health` | GET | ヘルスチェック |

---

## 6. データ設計

### 6.1 Chromaコレクション構造

| フィールド | 型 | 内容 |
|----------|------|------|
| `id` | string | `{ファイルパス}_{チャンク番号}` |
| `document` | string | チャンクテキスト |
| `embedding` | vector | text-embedding-3-smallによるベクトル |
| `metadata.file_path` | string | ファイルの絶対パス |
| `metadata.file_name` | string | ファイル名 |
| `metadata.relative_dir` | string | 指定フォルダからのサブディレクトリ相対パス |
| `metadata.file_type` | string | `docx` / `pptx` / `pdf` |
| `metadata.page_or_slide` | int | ページ番号またはスライド番号 |
| `metadata.last_modified` | string | ファイル更新日時（ISO8601） |
| `metadata.indexed_at` | string | インデックス日時（ISO8601） |

---

## 7. 非機能要件

| 項目 | 要件 |
|------|------|
| 実行環境 | ローカルPC（Windows / Mac）、Docker コンテナ上で動作 |
| 開発環境構築 | Docker Compose による一括起動（RAG APIサーバー、Open WebUI） |
| ネットワーク | OpenAI API使用時はインターネット接続が必要。OpenAI互換API使用時はローカルネットワークのみで完結可能 |
| LLM接続先切替 | `.env` の `LLM_API_BASE` / `EMBEDDING_API_BASE` を変更するだけで接続先を切替可能。LLMとEmbeddingは独立して設定できる |
| データ保管 | すべてローカルに保存（クラウド不使用） |
| 応答言語 | 日本語固定（システムプロンプトで指定） |
| 応答時間 | 目標10秒以内（ネットワーク遅延依存） |
| セキュリティ | APIキーは`.env`ファイルで管理、Gitに含めない |

---

## 8. ディレクトリ構成（案）

```
RAG-example/
├── indexer.py              # インデックス作成バッチ
├── server.py               # FastAPI サーバー（OpenAI互換API）
├── graph/
│   ├── pipeline.py         # LangGraphパイプライン定義
│   ├── nodes.py            # 各ノード（検索・生成・整形）
│   └── state.py            # ステート定義
├── parsers/
│   ├── docx_parser.py      # Word パーサー
│   ├── pptx_parser.py      # PowerPoint パーサー
│   └── pdf_parser.py       # PDF パーサー
├── vectorstore/
│   └── chroma_client.py    # Chroma操作ユーティリティ
├── chroma_db/              # Chromaの永続化データ（Git管理外）
├── documents/              # 検索対象ドキュメント格納フォルダ（Git管理外）
├── Dockerfile              # RAG APIサーバー用イメージ定義
├── docker-compose.yml      # 全サービス一括起動定義
├── .env                    # APIキー等（Git管理外）
├── .env.example            # 環境変数テンプレート
├── requirements.txt
└── docs/
    └── specification.md    # 本仕様書
```

---

## 9. 環境変数

`.env.example`

```env
# --- LLM接続設定 ---
# OpenAI APIを使用する場合
LLM_API_KEY=sk-xxxx
LLM_API_BASE=https://api.openai.com/v1
LLM_CHAT_MODEL=gpt-4o

# OpenAI互換APIを使用する場合の例（上記3つを書き換える）
# LLM_API_KEY=your-key-or-dummy
# LLM_API_BASE=http://localhost:11434/v1
# LLM_CHAT_MODEL=llama3

# --- Embedding接続設定 ---
# OpenAI APIを使用する場合
EMBEDDING_API_KEY=sk-xxxx
EMBEDDING_API_BASE=https://api.openai.com/v1
EMBEDDING_MODEL=text-embedding-3-small

# OpenAI互換APIを使用する場合の例（上記3つを書き換える）
# EMBEDDING_API_KEY=your-key-or-dummy
# EMBEDDING_API_BASE=http://localhost:11434/v1
# EMBEDDING_MODEL=nomic-embed-text

# --- その他 ---
CHROMA_PERSIST_DIR=./chroma_db
TOP_K_CHUNKS=10
TOP_K_RECOMMEND=5
```

> LLMとEmbeddingは独立して接続先を設定できる。例えばLLMはOpenAI、EmbeddingはローカルのOllamaといった組み合わせも可能。

---

## 10. 今後の拡張候補（スコープ外）

- Webブラウザからフォルダパス指定・インデックス実行
- ファイルのプレビュー表示
- 多言語対応
- 認証機能（アクセス制限）
- クラウドデプロイ対応
