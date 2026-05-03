import logging
from datetime import datetime, timezone
from pathlib import Path

from docx import Document

from parsers.base import BaseParser, ParsedChunk

logger = logging.getLogger(__name__)


class DocxParser(BaseParser):
    def parse(self, file_path: Path, base_dir: Path) -> list[ParsedChunk]:
        try:
            doc = Document(str(file_path))
        except Exception:
            logger.warning("Failed to parse %s, skipping.", file_path)
            return []

        last_modified = datetime.fromtimestamp(
            file_path.stat().st_mtime, tz=timezone.utc
        ).isoformat()

        chunks: list[ParsedChunk] = []
        page_num = 1
        page_texts: list[str] = []

        for para in doc.paragraphs:
            text = para.text.strip()
            if not text:
                continue
            # ページ区切り判定
            for run in para.runs:
                if run._element.xml.find("w:lastRenderedPageBreak") != -1 or run._element.xml.find("w:pageBreak") != -1:
                    if page_texts:
                        chunks.append(
                            self._make_chunk(
                                "\n".join(page_texts),
                                file_path,
                                base_dir,
                                "docx",
                                page_num,
                                last_modified,
                            )
                        )
                        page_texts = []
                        page_num += 1
            page_texts.append(text)

        if page_texts:
            chunks.append(
                self._make_chunk(
                    "\n".join(page_texts),
                    file_path,
                    base_dir,
                    "docx",
                    page_num,
                    last_modified,
                )
            )

        return chunks
