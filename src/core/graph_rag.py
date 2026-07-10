"""GraphRAG 基础知识图谱：实体抽取与多跳检索"""
import json
import logging
import re
from pathlib import Path
from typing import List, Dict, Any, Optional, Set, Tuple

from src.config.settings import Config

logger = logging.getLogger(__name__)

# 简单中文实体模式
ENTITY_PATTERNS = [
    re.compile(r"[\u4e00-\u9fff]{2,8}(?:公司|集团|部门|团队|项目|系统|平台|模型|算法|框架)"),
    re.compile(r"(?:CNN|RNN|LSTM|Transformer|GAN|BERT|GPT|RAG|Agent)(?:[-\w]*)?", re.I),
    re.compile(r"[\u4e00-\u9fff]{2,6}(?:是|为|属于|位于|负责)"),
]

RELATION_MARKERS = ["是", "属于", "包含", "负责", "位于", "使用", "基于", "实现", "支持"]


class KnowledgeGraph:
    """轻量知识图谱"""

    def __init__(self, graph_path: Optional[str] = None):
        self.graph_path = Path(graph_path or Config.GRAPH_RAG_PATH)
        self.graph_path.parent.mkdir(parents=True, exist_ok=True)
        self.entities: Dict[str, Dict[str, Any]] = {}
        self.relations: List[Dict[str, str]] = []
        self._load()

    def _load(self):
        if self.graph_path.exists():
            try:
                data = json.loads(self.graph_path.read_text(encoding="utf-8"))
                self.entities = data.get("entities", {})
                self.relations = data.get("relations", [])
            except Exception as e:
                logger.warning("加载知识图谱失败: %s", e)

    def save(self):
        payload = {"entities": self.entities, "relations": self.relations}
        self.graph_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def extract_entities(self, text: str, source: str = "") -> List[str]:
        found: Set[str] = set()
        for pattern in ENTITY_PATTERNS:
            for match in pattern.findall(text):
                entity = match.strip()
                if len(entity) >= 2:
                    found.add(entity)
                    if entity not in self.entities:
                        self.entities[entity] = {"sources": [], "mentions": 0}
                    if source and source not in self.entities[entity]["sources"]:
                        self.entities[entity]["sources"].append(source)
                    self.entities[entity]["mentions"] += 1
        return list(found)

    def extract_relations(self, text: str, source: str = "") -> List[Dict[str, str]]:
        new_relations = []
        entities = self.extract_entities(text, source=source)
        for marker in RELATION_MARKERS:
            if marker not in text:
                continue
            parts = text.split(marker, 1)
            if len(parts) != 2:
                continue
            left, right = parts[0].strip()[-20:], parts[1].strip()[:40]
            for e1 in entities:
                if e1 in left:
                    for e2 in entities:
                        if e2 != e1 and e2 in right:
                            rel = {"subject": e1, "predicate": marker, "object": e2, "source": source}
                            if rel not in self.relations:
                                self.relations.append(rel)
                                new_relations.append(rel)
        return new_relations

    def build_from_chunks(self, chunks: List[Any]) -> Dict[str, int]:
        """从文档块构建图谱"""
        for chunk in chunks:
            text = getattr(chunk, "page_content", "") if hasattr(chunk, "page_content") else str(chunk)
            meta = getattr(chunk, "metadata", {}) if hasattr(chunk, "metadata") else {}
            source = meta.get("source", "unknown") if isinstance(meta, dict) else "unknown"
            self.extract_entities(text, source=source)
            self.extract_relations(text, source=source)
        self.save()
        return {"entities": len(self.entities), "relations": len(self.relations)}

    def get_neighbors(self, entity: str, hops: int = 1) -> List[Dict[str, str]]:
        """多跳邻居查询"""
        results = []
        current = {entity}
        visited = set()

        for _ in range(hops):
            next_level = set()
            for e in current:
                if e in visited:
                    continue
                visited.add(e)
                for rel in self.relations:
                    if rel["subject"] == e or rel["object"] == e:
                        results.append(rel)
                        next_level.add(rel["subject"])
                        next_level.add(rel["object"])
            current = next_level - visited
        return results

    def search_context(self, query: str, max_relations: int = 10) -> str:
        """根据查询实体生成图谱上下文"""
        query_entities = self.extract_entities(query)
        if not query_entities:
            # 尝试子串匹配
            query_entities = [e for e in self.entities if e in query or any(c in e for c in query[:4])]

        lines = []
        for entity in query_entities[:5]:
            neighbors = self.get_neighbors(entity, hops=2)
            for rel in neighbors[:max_relations]:
                lines.append(f"{rel['subject']} {rel['predicate']} {rel['object']} (来源: {rel.get('source', '')})")

        return "\n".join(lines[:max_relations])

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entity_count": len(self.entities),
            "relation_count": len(self.relations),
            "entities": list(self.entities.keys())[:100],
            "relations": self.relations[:50],
        }
