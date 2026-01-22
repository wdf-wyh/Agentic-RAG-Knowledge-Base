"""RAG 检索工具 - 将现有 RAG 系统封装为 Agent 可调用的工具"""

from typing import List, Dict, Any, Optional

from src.agent.tools.base import BaseTool, ToolResult, ToolCategory
from src.core.vector_store import VectorStore
from src.services.rag_assistant import RAGAssistant
from src.config.settings import Config


class RAGSearchTool(BaseTool):
    """RAG 知识库搜索工具
    
    使用向量数据库检索相关文档，并可选择使用 LLM 生成答案
    """
    
    def __init__(self, vector_store: VectorStore = None, assistant: RAGAssistant = None):
        self._vector_store = vector_store
        self._assistant = assistant
        super().__init__()
    
    @property
    def name(self) -> str:
        return "rag_search"
    
    @property
    def description(self) -> str:
        return "搜索本地知识库，根据问题检索相关文档片段。适用于查找项目文档、FAQ、教程等本地存储的知识。"
    
    @property
    def category(self) -> ToolCategory:
        return ToolCategory.RETRIEVAL
    
    @property
    def parameters(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": "query",
                "type": "string",
                "description": "搜索查询，可以是问题或关键词",
                "required": True
            },
            {
                "name": "top_k",
                "type": "integer",
                "description": "返回结果数量，默认 5",
                "required": False
            },
            {
                "name": "generate_answer",
                "type": "boolean",
                "description": "是否使用 LLM 生成答案，默认 False 只返回检索片段",
                "required": False
            },
            {
                "name": "method",
                "type": "string",
                "description": "检索方法: 'vector'(向量), 'bm25'(关键词), 'hybrid'(混合)，默认 'vector'",
                "required": False
            }
        ]
    
    def _ensure_initialized(self):
        """确保向量数据库已初始化"""
        if self._vector_store is None:
            self._vector_store = VectorStore()
            self._vector_store.load_vectorstore()
        
        if self._assistant is None and self._vector_store.vectorstore is not None:
            self._assistant = RAGAssistant(vector_store=self._vector_store)
            self._assistant.setup_qa_chain()
    
    def execute(self, **kwargs) -> ToolResult:
        """执行 RAG 检索
        
        Args:
            query: 搜索查询
            top_k: 返回数量
            generate_answer: 是否生成答案
            method: 检索方法
        """
        query = kwargs.get("query", "")
        top_k = kwargs.get("top_k", 5)
        generate_answer = kwargs.get("generate_answer", False)
        method = kwargs.get("method", "vector")
        
        if not query:
            return ToolResult(
                success=False,
                output="",
                error="查询不能为空"
            )
        
        try:
            self._ensure_initialized()
            
            if self._vector_store.vectorstore is None:
                return ToolResult(
                    success=False,
                    output="",
                    error="知识库未初始化，请先构建知识库"
                )
            
            if generate_answer and self._assistant:
                # 使用 RAG Assistant 生成答案
                result = self._assistant.query(
                    question=query,
                    return_sources=True,
                    method=method,
                    k=top_k
                )
                
                output_parts = [f"**答案**: {result.get('answer', '无法生成答案')}"]
                
                if result.get("sources"):
                    output_parts.append("\n**参考来源**:")
                    for i, source in enumerate(result["sources"][:3], 1):
                        source_info = source.get("source", "未知来源")
                        content_preview = source.get("content", "")[:150]
                        output_parts.append(f"{i}. [{source_info}] {content_preview}...")
                
                return ToolResult(
                    success=True,
                    output="\n".join(output_parts),
                    data=result,
                    metadata={"method": method, "top_k": top_k, "generated": True}
                )
            else:
                # 仅检索，不生成答案
                docs = self._assistant.retrieve_documents(
                    query=query,
                    k=top_k,
                    method=method
                ) if self._assistant else self._vector_store.similarity_search(query, k=top_k)
                
                if not docs:
                    return ToolResult(
                        success=True,
                        output="未找到相关文档",
                        data=[],
                        metadata={"method": method, "top_k": top_k}
                    )
                
                output_parts = [f"找到 {len(docs)} 个相关片段:\n"]
                doc_data = []
                
                for i, doc in enumerate(docs, 1):
                    content = doc.page_content if hasattr(doc, 'page_content') else str(doc)
                    metadata = doc.metadata if hasattr(doc, 'metadata') else {}
                    source = metadata.get("source", "未知")
                    
                    output_parts.append(f"**片段 {i}** (来源: {source})")
                    output_parts.append(f"{content[:300]}...")
                    output_parts.append("")
                    
                    doc_data.append({
                        "content": content,
                        "source": source,
                        "metadata": metadata
                    })
                
                return ToolResult(
                    success=True,
                    output="\n".join(output_parts),
                    data=doc_data,
                    metadata={"method": method, "top_k": top_k, "count": len(docs)}
                )
                
        except Exception as e:
            return ToolResult(
                success=False,
                output="",
                error=f"RAG 检索失败: {str(e)}"
            )


class DocumentListTool(BaseTool):
    """文档列表工具 - 列出知识库中的所有文档"""
    
    def __init__(self, documents_path: str = None):
        self._documents_path = documents_path or Config.DOCUMENTS_PATH if hasattr(Config, 'DOCUMENTS_PATH') else "./documents"
        super().__init__()
    
    @property
    def name(self) -> str:
        return "list_documents"
    
    @property
    def description(self) -> str:
        return "列出知识库中所有已索引的文档，包括文档名称、类型和摘要信息。"
    
    @property
    def category(self) -> ToolCategory:
        return ToolCategory.RETRIEVAL
    
    @property
    def parameters(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": "include_summary",
                "type": "boolean",
                "description": "是否包含文档摘要，默认 True",
                "required": False
            }
        ]
    
    def execute(self, **kwargs) -> ToolResult:
        """列出所有文档"""
        import os
        from pathlib import Path
        
        include_summary = kwargs.get("include_summary", True)
        
        try:
            docs_path = Path(self._documents_path)
            if not docs_path.exists():
                return ToolResult(
                    success=False,
                    output="",
                    error=f"文档目录不存在: {self._documents_path}"
                )
            
            documents = []
            supported_extensions = {'.txt', '.md', '.pdf', '.docx', '.html'}
            
            for file_path in docs_path.rglob("*"):
                if file_path.is_file() and file_path.suffix.lower() in supported_extensions:
                    doc_info = {
                        "name": file_path.name,
                        "path": str(file_path.relative_to(docs_path)),
                        "type": file_path.suffix.lower()[1:],
                        "size": file_path.stat().st_size
                    }
                    
                    if include_summary and file_path.suffix.lower() in {'.txt', '.md'}:
                        try:
                            with open(file_path, 'r', encoding='utf-8') as f:
                                content = f.read(500)
                                doc_info["summary"] = content[:200] + "..." if len(content) > 200 else content
                        except:
                            doc_info["summary"] = "(无法读取摘要)"
                    
                    documents.append(doc_info)
            
            if not documents:
                return ToolResult(
                    success=True,
                    output="知识库中暂无文档",
                    data=[]
                )
            
            output_parts = [f"知识库共有 {len(documents)} 个文档:\n"]
            for doc in documents:
                size_kb = doc["size"] / 1024
                output_parts.append(f"- **{doc['name']}** ({doc['type']}, {size_kb:.1f}KB)")
                if doc.get("summary"):
                    output_parts.append(f"  摘要: {doc['summary'][:100]}...")
            
            return ToolResult(
                success=True,
                output="\n".join(output_parts),
                data=documents,
                metadata={"total": len(documents)}
            )
            
        except Exception as e:
            return ToolResult(
                success=False,
                output="",
                error=f"获取文档列表失败: {str(e)}"
            )


class KnowledgeBaseInfoTool(BaseTool):
    """知识库信息工具 - 获取知识库的统计信息"""
    
    def __init__(self, vector_store: VectorStore = None):
        self._vector_store = vector_store
        super().__init__()
    
    @property
    def name(self) -> str:
        return "kb_info"
    
    @property
    def description(self) -> str:
        return "获取知识库的统计信息，包括文档块数量、向量维度、存储大小等。"
    
    @property
    def category(self) -> ToolCategory:
        return ToolCategory.RETRIEVAL
    
    @property
    def parameters(self) -> List[Dict[str, Any]]:
        return []
    
    def execute(self, **kwargs) -> ToolResult:
        """获取知识库信息"""
        try:
            if self._vector_store is None:
                self._vector_store = VectorStore()
                self._vector_store.load_vectorstore()
            
            if self._vector_store.vectorstore is None:
                return ToolResult(
                    success=False,
                    output="",
                    error="知识库未初始化"
                )
            
            # 获取向量数据库信息
            collection = self._vector_store.vectorstore._collection
            count = collection.count()
            
            info = {
                "total_chunks": count,
                "embedding_model": Config.EMBEDDING_MODEL,
                "vector_db_path": Config.VECTOR_DB_PATH,
                "llm_model": Config.LLM_MODEL,
                "model_provider": Config.MODEL_PROVIDER
            }
            
            output = f"""知识库统计信息:
- 文档块数量: {count}
- 嵌入模型: {Config.EMBEDDING_MODEL}
- LLM 模型: {Config.LLM_MODEL}
- 模型提供者: {Config.MODEL_PROVIDER}
- 存储路径: {Config.VECTOR_DB_PATH}"""
            
            return ToolResult(
                success=True,
                output=output,
                data=info
            )
            
        except Exception as e:
            return ToolResult(
                success=False,
                output="",
                error=f"获取知识库信息失败: {str(e)}"
            )
