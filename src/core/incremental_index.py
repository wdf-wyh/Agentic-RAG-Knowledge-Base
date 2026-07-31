"""增量索引：仅处理变更文件"""
import hashlib
import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

from src.config.settings import Config
from src.core.document_processor import DocumentProcessor
from src.utils.tenant_paths import tenant_scoped_path

logger = logging.getLogger(__name__)


class IncrementalIndexer:
    """跟踪文件哈希，支持增量构建"""

    def __init__(self, manifest_path: Optional[str] = None, tenant_id: Optional[str] = None):
        self.manifest_path = Path(manifest_path or tenant_scoped_path(Config.INDEX_MANIFEST_PATH, tenant_id))
        self.manifest_path.parent.mkdir(parents=True, exist_ok=True)
        self.manifest: Dict[str, Dict[str, Any]] = {}
        self._load()

    def _load(self):
        if self.manifest_path.exists():
            try:
                self.manifest = json.loads(self.manifest_path.read_text(encoding="utf-8"))
            except Exception:
                self.manifest = {}

    def save(self):
        self.manifest_path.write_text(
            json.dumps(self.manifest, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    @staticmethod
    def file_hash(path: Path) -> str:
        h = hashlib.md5()
        h.update(path.read_bytes())
        return h.hexdigest()

    def scan_changes(self, directory: str) -> Tuple[List[Path], List[str]]:
        """返回 (新增/变更文件, 已删除文件路径)"""
        dir_path = Path(directory)
        if not dir_path.exists():
            return [], []

        supported = set(DocumentProcessor.get_all_supported_extensions())
        current_files: Dict[str, str] = {}

        for fp in dir_path.rglob("*"):
            if not fp.is_file() or fp.suffix.lower() not in supported:
                continue
            rel = str(fp.relative_to(dir_path)).replace("\\", "/")
            current_files[rel] = self.file_hash(fp)

        changed: List[Path] = []
        for rel, fhash in current_files.items():
            prev = self.manifest.get(rel, {})
            if prev.get("hash") != fhash:
                changed.append(dir_path / rel)

        deleted = [rel for rel in self.manifest if rel not in current_files]
        return changed, deleted

    def process_incremental(self, directory: str) -> Dict[str, Any]:
        """处理增量变更，返回新 chunks 与统计"""
        changed_files, deleted = self.scan_changes(directory)
        processor = DocumentProcessor()
        all_chunks: List[Any] = []

        for fp in changed_files:
            docs = processor.load_document(str(fp))
            if docs:
                chunks = processor.split_documents(docs)
                all_chunks.extend(chunks)
                rel = str(fp.relative_to(Path(directory))).replace("\\", "/")
                self.manifest[rel] = {
                    "hash": self.file_hash(fp),
                    "chunks": len(chunks),
                    "path": str(fp),
                }

        for rel in deleted:
            self.manifest.pop(rel, None)

        self.save()
        return {
            "changed_files": [str(f) for f in changed_files],
            "deleted_files": deleted,
            "new_chunks": len(all_chunks),
            "chunks": all_chunks,
        }
