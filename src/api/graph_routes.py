"""GraphRAG API"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from src.core.graph_rag import KnowledgeGraph
from src.api.routes import load_assistant

router = APIRouter(prefix="/graph", tags=["GraphRAG"])


class GraphQueryRequest(BaseModel):
    query: str
    hops: int = 2


@router.get("/stats")
async def graph_stats():
    kg = KnowledgeGraph()
    return kg.to_dict()


@router.post("/build")
async def build_graph():
    """从当前知识库重建图谱"""
    if not load_assistant():
        raise HTTPException(400, "请先构建知识库")
    from src.core.hybrid_retriever import HybridRetriever
    from src.api.routes import get_assistant
    assistant = get_assistant()
    retriever = HybridRetriever(assistant.vector_store)
    chunks = retriever._get_all_chunks()
    if not chunks:
        raise HTTPException(400, "知识库为空")
    kg = KnowledgeGraph()
    stats = kg.build_from_chunks(chunks)
    return {"success": True, **stats}


@router.post("/query")
async def graph_query(req: GraphQueryRequest):
    kg = KnowledgeGraph()
    context = kg.search_context(req.query)
    neighbors = []
    for entity in list(kg.entities.keys())[:20]:
        if entity in req.query:
            neighbors.extend(kg.get_neighbors(entity, hops=req.hops))
    return {
        "context": context,
        "relations": neighbors[:20],
        "entity_count": len(kg.entities),
    }
