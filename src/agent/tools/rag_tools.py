"""RAG 检索工具 - 将现有 RAG 系统封装为 Agent 可调用的工具

本模块提供三个工具类:
1. RAGSearchTool: 执行知识库检索和问答生成
2. DocumentListTool: 列出知识库文档
3. KnowledgeBaseInfoTool: 获取知识库统计信息
"""

# 类型提示导入: 用于定义函数参数和返回值类型，提高代码可读性
from typing import List, Dict, Any, Optional

# 基础工具模块: 所有工具的父类和工具结果数据结构
from src.agent.tools.base import BaseTool, ToolResult, ToolCategory
# 向量存储: 封装ChromaDB向量数据库操作
from src.core.vector_store import VectorStore
# RAG助手: 提供问答和文档检索功能
from src.services.rag_assistant import RAGAssistant
# 配置: 系统配置参数(模型名称、路径等)
from src.config.settings import Config



class RAGSearchTool(BaseTool):
    """RAG 知识库搜索工具
    
    核心检索工具，支持:
    - 向量检索(vector): 基于语义相似度
    - BM25检索(bm25): 基于关键词匹配  
    - 混合检索(hybrid): 结合以上两种方法
    - LLM答案生成: 基于检索结果生成答案
    """
    
    def __init__(self, vector_store: VectorStore = None, assistant: RAGAssistant = None):
        """初始化工具
        
        Args:
            vector_store: 向量数据库实例，None时延迟初始化
            assistant: RAG助手实例，用于生成答案
        """
        self._vector_store = vector_store  # 存储向量数据库实例
        self._assistant = assistant  # 存储RAG助手实例
        super().__init__()  # 调用父类初始化
    
    @property
    def name(self) -> str:
        """工具唯一标识名称，Agent通过此名称调用工具"""
        return "rag_search"
    
    @property
    def description(self) -> str:
        """工具功能描述，Agent根据描述判断何时使用此工具"""
        return "搜索本地知识库，根据问题检索相关文档片段。适用于查找项目文档、FAQ、教程等本地存储的知识。"
    
    @property
    def category(self) -> ToolCategory:
        """工具分类: RETRIEVAL表示检索类工具"""
        return ToolCategory.RETRIEVAL
    
    @property
    def parameters(self) -> List[Dict[str, Any]]:
        """定义工具的输入参数，Agent调用时会根据此定义构造参数"""
        return [
            {
                "name": "query",  # 参数名: 搜索查询
                "type": "string",  # 参数类型
                "description": "搜索查询，可以是问题或关键词",  # 参数说明
                "required": True  # 必需参数
            },
            {
                "name": "top_k",  # 返回结果数量
                "type": "integer",
                "description": "返回结果数量，默认 5",
                "required": False  # 可选参数
            },
            {
                "name": "generate_answer",  # 是否生成答案
                "type": "boolean",
                "description": "是否使用 LLM 生成答案，默认 False 只返回检索片段",
                "required": False
            },
            {
                "name": "method",  # 检索方法选择
                "type": "string",
                "description": "检索方法: 'vector'(向量), 'bm25'(关键词), 'hybrid'(混合)，默认 'vector'",
                "required": False
            }
        ]
    
    def _ensure_initialized(self):
        """确保向量数据库和助手已初始化
        
        延迟初始化模式: 只在需要时才创建资源，节省内存和启动时间
        """
        # 初始化向量存储
        if self._vector_store is None:
            self._vector_store = VectorStore()  # 创建向量存储实例
            self._vector_store.load_vectorstore()  # 从磁盘加载向量数据库
        
        # 初始化RAG助手
        if self._assistant is None and self._vector_store.vectorstore is not None:
            self._assistant = RAGAssistant(vector_store=self._vector_store)  # 创建助手
            self._assistant.setup_qa_chain()  # 设置问答链(初始化LLM和提示模板)
    
    def execute(self, **kwargs) -> ToolResult:
        """执行RAG检索 - 工具的主要入口
        
        Args:
            **kwargs: 关键字参数，包括query, top_k, generate_answer, method
        
        Returns:
            ToolResult: 包含success、output、data、error、metadata的结果对象
        """
        # 解析输入参数，使用get方法提供默认值
        query = kwargs.get("query", "")  # 查询字符串
        top_k = kwargs.get("top_k", 5)  # 返回结果数，默认5
        generate_answer = kwargs.get("generate_answer", False)  # 是否生成答案，默认False
        method = kwargs.get("method", "vector")  # 检索方法，默认向量检索
        
        # 参数验证: 查询不能为空
        if not query:
            return ToolResult(
                success=False,
                output="",
                error="查询不能为空"
            )
        
        try:
            # 确保资源已初始化
            self._ensure_initialized()
            
            # 检查向量库是否加载成功
            if self._vector_store.vectorstore is None:
                return ToolResult(
                    success=False,
                    output="",
                    error="知识库未初始化，请先构建知识库"
                )
            
            # 分支1: 生成答案模式 (使用LLM)
            if generate_answer and self._assistant:
                # 调用助手查询: 检索文档 + LLM生成答案
                result = self._assistant.query(
                    question=query,
                    return_sources=True,  # 返回来源文档
                    method=method,
                    k=top_k
                )
                
                # 格式化输出: 答案 + 来源引用
                output_parts = [f"**答案**: {result.get('answer', '无法生成答案')}"]
                
                if result.get("sources"):
                    output_parts.append("\n**参考来源**:")
                    # 只显示前3个来源
                    for i, source in enumerate(result["sources"][:3], 1):
                        source_info = source.get("source", "未知来源")
                        content_preview = source.get("content", "")[:150]  # 内容预览(前150字符)
                        output_parts.append(f"{i}. [{source_info}] {content_preview}...")
                
                return ToolResult(
                    success=True,
                    output="\n".join(output_parts),  # 格式化文本输出
                    data=result,  # 原始结构化数据
                    metadata={"method": method, "top_k": top_k, "generated": True}
                )
            
            # 分支2: 仅检索模式 (不使用LLM)
            else:
                # 执行检索: 获取相关文档片段
                docs = self._assistant.retrieve_documents(
                    query=query,
                    k=top_k,
                    method=method
                ) if self._assistant else self._vector_store.similarity_search(query, k=top_k)
                
                # 未找到文档
                if not docs:
                    return ToolResult(
                        success=True,
                        output="未找到相关文档",
                        data=[],
                        metadata={"method": method, "top_k": top_k}
                    )
                
                # 格式化文档输出
                output_parts = [f"找到 {len(docs)} 个相关片段:\n"]
                doc_data = []
                
                for i, doc in enumerate(docs, 1):
                    # 提取文档内容和元数据
                    content = doc.page_content if hasattr(doc, 'page_content') else str(doc)
                    metadata = doc.metadata if hasattr(doc, 'metadata') else {}
                    source = metadata.get("source", "未知")
                    
                    # 添加格式化片段
                    output_parts.append(f"**片段 {i}** (来源: {source})")
                    output_parts.append(f"{content[:300]}...")  # 显示前300字符
                    output_parts.append("")  # 空行分隔
                    
                    # 保存结构化数据
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
        
        # 异常处理: 捕获所有异常，返回错误信息
        except Exception as e:
            return ToolResult(
                success=False,
                output="",
                error=f"RAG 检索失败: {str(e)}"
            )


class DocumentListTool(BaseTool):
    """文档列表工具 - 列出知识库中的所有文档
    
    功能:
    - 扫描文档目录
    - 列出所有支持的文件(.txt, .md, .pdf, .docx, .html)
    - 显示文件大小、类型
    - 可选显示内容摘要
    """
    
    def __init__(self, documents_path: str = None):
        """初始化文档列表工具
        
        Args:
            documents_path: 文档目录路径，默认使用配置中的路径或"./documents"
        """
        # 三元表达式: 依次尝试 传入值 -> Config配置 -> 默认值
        self._documents_path = documents_path or Config.DOCUMENTS_PATH if hasattr(Config, 'DOCUMENTS_PATH') else "./documents"
        super().__init__()
    
    @property
    def name(self) -> str:
        """工具名称"""
        return "list_documents"
    
    @property
    def description(self) -> str:
        """工具描述"""
        return "列出知识库中所有已索引的文档，包括文档名称、类型和摘要信息。"
    
    @property
    def category(self) -> ToolCategory:
        """工具分类"""
        return ToolCategory.RETRIEVAL
    
    @property
    def parameters(self) -> List[Dict[str, Any]]:
        """参数定义"""
        return [
            {
                "name": "include_summary",  # 是否包含文件摘要
                "type": "boolean",
                "description": "是否包含文档摘要，默认 True",
                "required": False
            }
        ]
    
    def execute(self, **kwargs) -> ToolResult:
        """执行文档列表获取
        
        流程:
        1. 检查文档目录是否存在
        2. 递归遍历目录
        3. 收集支持格式的文件信息
        4. 可选读取文本文件的摘要
        5. 格式化并返回结果
        """
        import os  # 操作系统接口
        from pathlib import Path  # 面向对象的路径操作
        
        include_summary = kwargs.get("include_summary", True)  # 是否包含摘要
        
        try:
            # 创建Path对象
            docs_path = Path(self._documents_path)
            
            # 检查目录是否存在
            if not docs_path.exists():
                return ToolResult(
                    success=False,
                    output="",
                    error=f"文档目录不存在: {self._documents_path}"
                )
            
            documents = []  # 文档信息列表
            supported_extensions = {'.txt', '.md', '.pdf', '.docx', '.html'}  # 支持的文件类型
            
            # 递归遍历目录下的所有文件
            for file_path in docs_path.rglob("*"):  # rglob("*")递归匹配所有文件
                # 检查是否是文件且扩展名在支持列表中
                if file_path.is_file() and file_path.suffix.lower() in supported_extensions:
                    # 收集文件信息
                    doc_info = {
                        "name": file_path.name,  # 文件名
                        "path": str(file_path.relative_to(docs_path)),  # 相对路径
                        "type": file_path.suffix.lower()[1:],  # 文件类型(去掉点号)
                        "size": file_path.stat().st_size  # 文件大小(字节)
                    }
                    
                    # 为文本文件读取摘要
                    if include_summary and file_path.suffix.lower() in {'.txt', '.md'}:
                        try:
                            with open(file_path, 'r', encoding='utf-8') as f:
                                content = f.read(500)  # 读取前500字符
                                # 如果超过200字符则截断
                                doc_info["summary"] = content[:200] + "..." if len(content) > 200 else content
                        except:
                            doc_info["summary"] = "(无法读取摘要)"
                    
                    documents.append(doc_info)
            
            # 未找到文档
            if not documents:
                return ToolResult(
                    success=True,
                    output="知识库中暂无文档",
                    data=[]
                )
            
            # 格式化输出
            output_parts = [f"知识库共有 {len(documents)} 个文档:\n"]
            for doc in documents:
                size_kb = doc["size"] / 1024  # 转换为KB
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
    """知识库信息工具 - 获取知识库的统计信息
    
    功能:
    - 显示文档块(chunk)数量
    - 显示使用的模型信息
    - 显示存储路径和配置
    
    注: 文档块(chunk)是将长文档分割后的片段，是检索的基本单位
    """
    
    def __init__(self, vector_store: VectorStore = None):
        """初始化知识库信息工具
        
        Args:
            vector_store: VectorStore实例，如果为None会延迟创建
        """
        self._vector_store = vector_store  # 存储向量库实例
        super().__init__()
    
    @property
    def name(self) -> str:
        """工具名称"""
        return "kb_info"  # kb = knowledge base(知识库)
    
    @property
    def description(self) -> str:
        """工具描述"""
        return "获取知识库的统计信息，包括文档块数量、向量维度、存储大小等。"
    
    @property
    def category(self) -> ToolCategory:
        """工具分类"""
        return ToolCategory.RETRIEVAL
    
    @property
    def parameters(self) -> List[Dict[str, Any]]:
        """参数定义 - 此工具不需要参数"""
        return []
    
    def execute(self, **kwargs) -> ToolResult:
        """获取知识库信息
        
        流程:
        1. 确保向量库已初始化
        2. 从ChromaDB获取文档数量
        3. 从Config获取模型和路径配置
        4. 格式化并返回统计信息
        """
        try:
            # 如果向量库未初始化，创建并加载
            if self._vector_store is None:
                self._vector_store = VectorStore()
                self._vector_store.load_vectorstore()
            
            # 检查向量库是否成功加载
            if self._vector_store.vectorstore is None:
                return ToolResult(
                    success=False,
                    output="",
                    error="知识库未初始化"
                )
            
            # 获取向量数据库信息
            # _collection是ChromaDB的底层集合对象
            collection = self._vector_store.vectorstore._collection
            count = collection.count()  # 获取文档块总数
            
            # 构建信息字典
            info = {
                "total_chunks": count,  # 文档块总数
                "embedding_model": Config.EMBEDDING_MODEL,  # 嵌入模型(用于生成向量)
                "vector_db_path": Config.VECTOR_DB_PATH,  # 向量库存储路径
                "llm_model": Config.LLM_MODEL,  # LLM模型(用于生成答案)
                "model_provider": Config.MODEL_PROVIDER  # 模型提供商(ollama/openai等)
            }
            
            # 格式化输出文本
            output = f"""知识库统计信息:
- 文档块数量: {count}
- 嵌入模型: {Config.EMBEDDING_MODEL}
- LLM 模型: {Config.LLM_MODEL}
- 模型提供者: {Config.MODEL_PROVIDER}
- 存储路径: {Config.VECTOR_DB_PATH}"""
            
            return ToolResult(
                success=True,
                output=output,  # 格式化的文本
                data=info  # 结构化数据
            )
            
        except Exception as e:
            return ToolResult(
                success=False,
                output="",
                error=f"获取知识库信息失败: {str(e)}"
            )
