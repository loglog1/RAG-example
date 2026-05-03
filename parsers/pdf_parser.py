import logging
from datetime import datetime, timezone
from pathlib import Path

import fitz  # PyMuPDF

from parsers.base import BaseParser, ParsedChunk

logger = logging.getLogger(__name__)


class PdfParser(BaseParser):
    def parse(self, file_path: Path, base_dir: Path) -> list[ParsedChunk]:
        try:
            doc = fitz.open(str(file_path))
        except Exception:
            logger.warning("Failed to parse %s, skipping.", file_path)
            return []

        last_modified = datetime.fromtimestamp(
            file_path.stat().st_mtime, tz=timezone.utc
        ).isoformat()

        chunks: list[ParsedChunk] = []
        for page_num, page in enumerate(doc, start=1):
            text = page.get_text().strip()
            if text:
                chunks.append(
                    self._make_chunk(
                        text,
                        file_path,
                        base_dir,
                        "pdf",
                        page_num,
                        last_modified,
                    )
                )

        doc.close()
        return chunks
