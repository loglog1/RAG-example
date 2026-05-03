import argparse
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

from langchain_text_splitters import RecursiveCharacterTextSplitter

from parsers.base import ParsedChunk
from parsers.docx_parser import DocxParser
from parsers.pptx_parser import PptxParser
from parsers.pdf_parser import PdfParser
from vectorstore.chroma_client import ChromaClient

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

SUPPORTED_EXTENSIONS = {".docx", ".pptx", ".pdf"}

PARSERS = {
    ".docx": DocxParser(),
    ".pptx": PptxParser(),
    ".pdf": PdfParser(),
}

TEXT_SPLITTER = RecursiveCharacterTextSplitter(
    chunk_size=500,
    chunk_overlap=50,
    separators=["\n\n", "\n", "。", "、", " ", ""],
)


def scan_files(folder: Path) -> list[Path]:
    return [
        p for p in folder.rglob("*")
        if p.is_file() and p.suffix.lower() in SUPPORTED_EXTENSIONS
    ]


def get_last_modified(file_path: Path) -> str:
    return datetime.fromtimestamp(
        file_path.stat().st_mtime, tz=timezone.utc
    ).isoformat()


def split_chunks(parsed_chunks: list[ParsedChunk]) -> list[tuple[ParsedChunk, str, int]]:
    result: list[tuple[ParsedChunk, str, int]] = []
    for chunk in parsed_chunks:
        splits = TEXT_SPLITTER.split_text(chunk.text)
        for idx, text in enumerate(splits):
            result.append((chunk, text, idx))
    return result


def run_indexer(folder: Path) -> None:
    if not folder.exists():
        logger.error("Folder does not exist: %s", folder)
        sys.exit(1)

    client = ChromaClient()
    indexed_files = client.get_indexed_files()

    current_files = {str(p): p for p in scan_files(folder)}
    logger.info("Found %d files in %s.", len(current_files), folder)

    # 削除されたファイルをChromaから除去
    deleted = set(indexed_files) - set(current_files)
    for file_path in deleted:
        logger.info("Deleting removed file: %s", file_path)
        client.delete_by_file_path(file_path)

    # 新規・更新ファイルを処理
    to_process: list[Path] = []
    for file_path_str, file_path in current_files.items():
        current_mtime = get_last_modified(file_path)
        if file_path_str not in indexed_files or indexed_files[file_path_str] != current_mtime:
            to_process.append(file_path)

    logger.info("%d files to index (new or updated).", len(to_process))

    for file_path in to_process:
        logger.info("Indexing: %s", file_path)
        # 既存チャンクを削除してから再登録
        client.delete_by_file_path(str(file_path))

        parser = PARSERS[file_path.suffix.lower()]
        parsed = parser.parse(file_path, folder)
        if not parsed:
            logger.warning("No content extracted from %s.", file_path)
            continue

        split = split_chunks(parsed)
        client.upsert_chunks(parsed, split)

    logger.info("Indexing complete.")


def main() -> None:
    parser = argparse.ArgumentParser(description="RAGシステム インデクサー")
    parser.add_argument("--folder", required=True, help="インデックス対象フォルダのパス")
    args = parser.parse_args()
    run_indexer(Path(args.folder))


if __name__ == "__main__":
    main()
