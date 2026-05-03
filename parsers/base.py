from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path


@dataclass
class ParsedChunk:
    text: str
    file_path: str
    file_name: str
    relative_dir: str
    file_type: str
    page_or_slide: int
    last_modified: str


class BaseParser(ABC):
    @abstractmethod
    def parse(self, file_path: Path, base_dir: Path) -> list[ParsedChunk]:
        ...

    def _make_chunk(
        self,
        text: str,
        file_path: Path,
        base_dir: Path,
        file_type: str,
        page_or_slide: int,
        last_modified: str,
    ) -> ParsedChunk:
        relative_dir = str(file_path.parent.relative_to(base_dir))
        if relative_dir == ".":
            relative_dir = ""
        return ParsedChunk(
            text=text,
            file_path=str(file_path),
            file_name=file_path.name,
            relative_dir=relative_dir,
            file_type=file_type,
            page_or_slide=page_or_slide,
            last_modified=last_modified,
        )
