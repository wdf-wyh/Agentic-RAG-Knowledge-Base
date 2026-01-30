"""RAG 检索工具 - 将现有 RAG 系统封装为 Agent 可调用的工具

这个模块是整个Agent系统中处理知识库检索的核心工具集。
它包含三个主要工具类，每个都继承自BaseTool基类：
1. RAGSearchTool: 执行知识库检索和问答生成
2. DocumentListTool: 列出知识库中的所有文档
3. KnowledgeBaseInfoTool: 获取知识库的统计信息

RAG(Retrieval-Augmented Generation)是一种结合检索和生成的AI技术：
- Retrieval: 从知识库中检索相关信息
- Augmented: 用检索到的信息增强
- Generation: 让LLM生成更准确的答案
"""

# ========== 导入类型提示工具 ==========
# typing模块提供类型注解，帮助IDE智能提示和静态类型检查
from typing import List, Dict, Any, Optional
# List: 列表类型，如 List[str] 表示字符串列表
# Dict: 字典类型，如 Dict[str, Any] 表示键为字符串、值为任意类型的字典
# Any: 任意类型
# Optional: 可选类型，Optional[str] 等价于 str | None

# ========== 导入基础工具模块 ==========
# 从base模块导入工具开发所需的基础类
from src.agent.tools.base import BaseTool, ToolResult, ToolCategory
# BaseTool: 所有工具的抽象基类，定义了工具的标准接口
# ToolResult: 工具执行结果的标准数据结构，包含success、output、error等字段
# ToolCategory: 工具分类枚举，用于组织和管理不同类型的工具

# ========== 导入核心功能模块 ==========
from src.core.vector_store import VectorStore
# VectorStore: 向量存储类，封装了ChromaDB向量数据库的操作
# 主要功能：存储文档向量、执行相似度搜索、管理向量索引

from src.services.rag_assistant import RAGAssistant
# RAGAssistant: RAG助手类，提供完整的RAG问答功能
# 主要功能：组合检索器和LLM、生成基于检索的答案、管理问答链

from src.config.settings import Config
# Config: 配置类，存储所有系统配置参数
# 包括：模型路径、数据库路径、API密钥、超参数等


# ==========================================================================
# RAGSearchTool: RAG知识库搜索工具
# ==========================================================================
class RAGSearchTool(BaseTool):
    """RAG 知识库搜索工具 - Agent的核心检索工具
    
    这个类实现了完整的RAG检索功能，是Agent与知识库交互的主要接口。
    
    核心功能：
    1. 向量检索(Vector Search): 
       - 将查询转换为向量(embedding)
       - 在向量数据库中找到最相似的文档片段
       - 基于余弦相似度排序
    
    2. BM25检索(Keyword Search):
       - 传统的关键词匹配算法
       - 基于TF-IDF(词频-逆文档频率)
       - 适合精确关键词匹配
    
    3. 混合检索(Hybrid Search):
       - 结合向量检索和BM25
       - 使用加权平均融合结果
       - 同时考虑语义和关键词相关性
    
    4. LLM答案生成:
       - 将检索到的文档片段作为上下文
       - 调用大语言模型生成答案
       - 提供答案的来源引用
    
    使用场景：
    - 用户提问时查找相关文档
    - 需要引用本地知识库回答问题
    - 构建基于知识的对话系统
    
    继承关系：
    RAGSearchTool -> BaseTool -> ABC (抽象基类)
    """
    
    def __init__(self, vector_store: VectorStore = None, assistant: RAGAssistant = None):
        """初始化RAG搜索工具
        
        采用依赖注入模式，允许外部传入已初始化的对象，提高灵活性和可测试性。
        使用延迟初始化(Lazy Initialization)模式，只在真正需要时才创建资源。
        
        Args:
            vector_store: VectorStore实例，管理ChromaDB向量数据库
                - 如果为None，会在首次调用execute时自动创建
                - 建议在创建多个工具时共享同一个实例，节省内存
            assistant: RAGAssistant实例，提供LLM问答功能
                - 如果为None，会在需要生成答案时自动创建
                - 内部会使用传入的vector_store进行检索
        
        设计模式：
        - 依赖注入(Dependency Injection): 通过参数传入依赖对象
        - 单例共享: 多个工具可以共享同一个vector_store实例
        - 延迟初始化: 延迟创建昂贵的资源直到真正需要
        """
        # 存储向量数据库实例
        # 使用下划线前缀"_"表示这是私有属性，遵循Python命名约定
        # 私有属性不应该从类外部直接访问，应通过方法访问
        self._vector_store = vector_store
        
        # 存储RAG助手实例，用于生成基于检索结果的答案
        self._assistant = assistant
        
        # 调用父类BaseTool的构造函数
        # super()返回父类的临时对象，__init__()是父类的初始化方法
        # 这确保父类的初始化逻辑被正确执行
        super().__init__()
    
    @property
    def name(self) -> str:
        """返回工具的唯一标识名称
        
        @property装饰器将方法转换为属性，可以像访问属性一样调用：
        tool.name  # 而不是 tool.name()
        
        工具名称规范：
        - 使用小写字母和下划线
        - 简洁且具有描述性
        - 在整个系统中必须唯一
        - Agent通过这个名称来调用工具
        
        Returns:
            str: 工具名称 "rag_search"
        """
        return "rag_search"
    
    @property
    def description(self) -> str:
        """返回工具的功能描述
        
        这个描述非常重要，因为Agent(特别是LLM)会根据描述来判断何时使用这个工具。
        
        描述要求：
        - 清晰说明工具的功能
        - 指出适用的场景
        - 帮助LLM做出正确的工具选择决策
        - 使用自然语言，易于理解
        
        示例场景：
        用户问："项目的FAQ文档里有哪些内容？"
        -> Agent读到"搜索本地知识库"、"FAQ"等关键词，决定使用此工具
        
        Returns:
            str: 工具的功能描述
        """
        return "搜索本地知识库，根据问题检索相关文档片段。适用于查找项目文档、FAQ、教程等本地存储的知识。"
    
    @property
    def category(self) -> ToolCategory:
        """返回工具的分类
        
        工具分类用于组织和管理多个工具，帮助Agent更高效地查找合适的工具。
        
        常见分类：
        - RETRIEVAL: 检索类工具（本工具属于此类）
        - ANALYSIS: 分析类工具
        - GENERATION: 生成类工具
        - COMMUNICATION: 通信类工具
        
        Returns:
            ToolCategory: 工具分类枚举值
        """
        # ToolCategory是一个枚举类(Enum)，RETRIEVAL是其中一个枚举值
        return ToolCategory.RETRIEVAL
    
    @property
    def parameters(self) -> List[Dict[str, Any]]:
        """定义工具的输入参数规范
        
        这个方法返回一个参数列表，每个参数是一个字典，定义了参数的元数据。
        Agent在调用工具时会根据这个定义来构造正确的参数。
        
        参数字典结构：
        {
            "name": "参数名称",         # 参数的标识符
            "type": "数据类型",         # string, integer, boolean等
            "description": "参数说明",   # 告诉Agent这个参数的用途
            "required": True/False      # 是否必须提供
        }
        
        Returns:
            List[Dict[str, Any]]: 参数定义列表
        """
        return [
            {
                # ========== 参数1: query ==========
                "name": "query",  # 参数名，Agent调用时使用此名称传值
                "type": "string",  # 数据类型：字符串
                "description": "搜索查询，可以是问题或关键词",  # 参数说明
                # 例如："什么是RAG?" 或 "文档处理流程"
                "required": True  # 必需参数，Agent必须提供此参数
            },
            {
                # ========== 参数2: top_k ==========
                "name": "top_k",  # 参数名：要返回的文档数量
                "type": "integer",  # 数据类型：整数
                "description": "返回结果数量，默认 5",  # 说明默认值
                # top_k是信息检索中的常用术语，表示"返回前k个最相关的结果"
                "required": False  # 可选参数，不提供时使用默认值5
            },
            {
                # ========== 参数3: generate_answer ==========
                "name": "generate_answer",  # 参数名：是否生成答案
                "type": "boolean",  # 数据类型：布尔值(True/False)
                "description": "是否使用 LLM 生成答案，默认 False 只返回检索片段",
                # False: 只返回原始文档片段，不调用LLM
                # True: 调用LLM基于检索片段生成答案
                "required": False  # 可选参数
            },
            {
                # ========== 参数4: method ==========
                "name": "method",  # 参数名：检索方法
                "type": "string",  # 数据类型：字符串
                "description": "检索方法: 'vector'(向量), 'bm25'(关键词), 'hybrid'(混合)，默认 'vector'",
                # 'vector': 使用向量相似度检索，适合语义搜索
                # 'bm25': 使用关键词匹配，适合精确匹配
                # 'hybrid': 结合两种方法，平衡语义和关键词
                "required": False  # 可选参数，默认使用向量检索
            }
        ]
    
    def _ensure_initialized(self):
        """确保向量数据库和RAG助手已初始化
        
        这是一个私有方法(以下划线开头)，只在类内部使用。
        实现了延迟初始化(Lazy Initialization)模式：
        - 只在真正需要时才创建资源
        - 避免不必要的内存占用
        - 加快工具的初始化速度
        
        执行流程：
        1. 检查vector_store是否为None
        2. 如果是，创建新的VectorStore并加载数据
        3. 检查assistant是否为None且vector_store已加载
        4. 如果满足条件，创建RAGAssistant并设置问答链
        
        为什么要延迟初始化？
        - VectorStore加载向量数据库需要时间和内存
        - RAGAssistant初始化LLM连接也需要资源
        - 如果工具创建后没有被使用，这些初始化就是浪费
        
        调用时机：
        - 在execute方法开始时调用
        - 确保执行检索前资源已准备好
        """
        # ========== 初始化向量存储 ==========
        if self._vector_store is None:  # 检查是否已经有vector_store实例
            # 创建新的VectorStore实例
            # VectorStore封装了ChromaDB向量数据库的操作
            self._vector_store = VectorStore()
            
            # 从磁盘加载已保存的向量数据库
            # 这会加载所有文档的向量表示到内存
            # 加载后可以执行相似度搜索
            self._vector_store.load_vectorstore()
        
        # ========== 初始化RAG助手 ==========
        # 需要同时满足两个条件：
        # 1. assistant还没有创建 (self._assistant is None)
        # 2. 向量数据库已成功加载 (self._vector_store.vectorstore is not None)
        if self._assistant is None and self._vector_store.vectorstore is not None:
            # 创建RAGAssistant实例，传入vector_store
            # assistant会使用vector_store来检索文档
            self._assistant = RAGAssistant(vector_store=self._vector_store)
            
            # 设置问答链(QA Chain)
            # 这会初始化：
            # - LLM客户端连接
            # - 提示词模板(Prompt Template)
            # - 检索增强生成管道
            self._assistant.setup_qa_chain()
    
    def execute(self, **kwargs) -> ToolResult:
        """执行RAG检索 - 工具的核心执行方法
        
        这是工具的主要入口点，Agent调用工具时会执行这个方法。
        
        方法签名说明：
        - **kwargs: 可变关键字参数，接收任意数量的命名参数
          例如：execute(query="什么是RAG?", top_k=3)
          kwargs会是：{"query": "什么是RAG?", "top_k": 3}
        
        - -> ToolResult: 类型注解，表示返回ToolResult对象
        
        执行流程：
        1. 解析和验证输入参数
        2. 确保资源已初始化
        3. 根据参数选择执行路径：
           a. 如果generate_answer=True: 使用LLM生成答案
           b. 否则：只返回检索到的文档片段
        4. 格式化输出结果
        5. 处理异常情况
        
        Args:
            **kwargs: 关键字参数，包括：
                - query (str): 搜索查询，必需
                - top_k (int): 返回数量，默认5
                - generate_answer (bool): 是否生成答案，默认False
                - method (str): 检索方法，默认'vector'
        
        Returns:
            ToolResult: 包含执行结果的标准对象，包括：
                - success (bool): 执行是否成功
                - output (str): 人类可读的输出文本
                - data (Any): 结构化数据
                - error (str): 错误信息(如果失败)
                - metadata (dict): 元数据(如检索方法、结果数量等)
        """
        # ========== 第1步：解析输入参数 ==========
        # 使用get方法安全地获取参数，如果参数不存在则使用默认值
        
        # 获取查询字符串，默认为空字符串
        # kwargs.get("query", "") 的含义：
        # - 如果kwargs中有"query"键，返回对应的值
        # - 如果没有，返回默认值空字符串""
        query = kwargs.get("query", "")
        
        # 获取返回结果数量，默认为5
        top_k = kwargs.get("top_k", 5)
        
        # 获取是否生成答案的标志，默认为False（只检索）
        generate_answer = kwargs.get("generate_answer", False)
        
        # 获取检索方法，默认为"vector"（向量检索）
        method = kwargs.get("method", "vector")
        
        # ========== 第2步：参数验证 ==========
        # 检查query是否为空，query是唯一的必需参数
        if not query:  # 空字符串在Python中等价于False
            # 返回失败的ToolResult
            return ToolResult(
                success=False,  # 标记执行失败
                output="",  # 没有输出内容
                error="查询不能为空"  # 提供错误信息
            )
        
        # ========== 第3步：执行检索（在try块中处理可能的异常）==========
        try:
            # ========== 3.1 确保资源已初始化 ==========
            # 调用私有方法，确保vector_store和assistant已创建并加载
            self._ensure_initialized()
            
            # ========== 3.2 检查向量数据库是否成功加载 ==========
            # vectorstore是VectorStore对象的属性，指向ChromaDB实例
            if self._vector_store.vectorstore is None:
                # 向量库未初始化，无法执行检索
                return ToolResult(
                    success=False,
                    output="",
                    error="知识库未初始化，请先构建知识库"
                    # 提示用户需要先运行文档处理流程构建向量库
                )
            
            # ========== 3.3 根据generate_answer选择执行路径 ==========
            # 路径A：生成答案模式
            if generate_answer and self._assistant:
                """
                使用RAG Assistant生成基于检索的答案
                
                流程：
                1. 执行检索获取相关文档
                2. 构造包含文档的提示词
                3. 调用LLM生成答案
                4. 返回答案和来源引用
                """
                # 调用assistant的query方法
                result = self._assistant.query(
                    question=query,  # 用户的问题
                    return_sources=True,  # 返回来源文档信息
                    method=method,  # 使用指定的检索方法
                    k=top_k  # 检索top_k个文档
                )
                # result是一个字典，包含：
                # - 'answer': LLM生成的答案
                # - 'sources': 来源文档列表
                # - 'method': 使用的检索方法
                
                # ========== 格式化输出 ==========
                # 创建输出部分列表，使用f-string格式化
                output_parts = [f"**答案**: {result.get('answer', '无法生成答案')}"]
                # result.get('answer', '无法生成答案') 安全地获取答案，如果没有则显示默认文本
                # **答案**: 使用Markdown粗体格式，在界面上显示更清晰
                
                # 如果有来源文档，添加引用信息
                if result.get("sources"):
                    output_parts.append("\n**参考来源**:")  # 添加来源标题
                    # 遍历前3个来源文档（enumerate从1开始计数）
                    for i, source in enumerate(result["sources"][:3], 1):
                        # 获取来源信息（文件名或路径）
                        source_info = source.get("source", "未知来源")
                        # 获取内容预览（前150个字符）
                        content_preview = source.get("content", "")[:150]
                        # 添加格式化的来源条目
                        output_parts.append(f"{i}. [{source_info}] {content_preview}...")
                
                # 返回成功结果
                return ToolResult(
                    success=True,  # 执行成功
                    output="\n".join(output_parts),  # 将输出列表连接成字符串
                    data=result,  # 原始结构化数据
                    metadata={  # 元数据，提供额外信息
                        "method": method,  # 使用的检索方法
                        "top_k": top_k,  # 检索的文档数量
                        "generated": True  # 标记使用了LLM生成
                    }
                )
            
            # 路径B：仅检索模式（不生成答案）
            else:
                """
                只检索文档片段，不调用LLM生成答案
                
                流程：
                1. 执行检索获取相关文档
                2. 格式化文档内容
                3. 返回文档列表
                
                优势：
                - 速度更快（不需要LLM推理）
                - 成本更低（不消耗LLM API）
                - 适合只需要看原始文档的场景
                """
                # 根据assistant是否可用选择检索方法
                if self._assistant:
                    # 使用assistant的retrieve_documents方法
                    # 这个方法支持多种检索策略
                    docs = self._assistant.retrieve_documents(
                        query=query,
                        k=top_k,
                        method=method
                    )
                else:
                    # 如果没有assistant，直接使用vector_store的相似度搜索
                    # 这是最基本的向量检索方法
                    docs = self._vector_store.similarity_search(query, k=top_k)
                
                # ========== 检查是否找到文档 ==========
                if not docs:  # 空列表等价于False
                    # 没有找到相关文档
                    return ToolResult(
                        success=True,  # 仍然标记为成功（没有错误发生）
                        output="未找到相关文档",
                        data=[],  # 空数据列表
                        metadata={"method": method, "top_k": top_k}
                    )
                
                # ========== 格式化文档输出 ==========
                output_parts = [f"找到 {len(docs)} 个相关片段:\n"]
                doc_data = []  # 存储结构化的文档数据
                
                # 遍历所有文档（enumerate从1开始）
                for i, doc in enumerate(docs, 1):
                    # 获取文档内容
                    # hasattr检查对象是否有某个属性
                    # 不同的检索方法可能返回不同结构的文档对象
                    content = doc.page_content if hasattr(doc, 'page_content') else str(doc)
                    
                    # 获取文档元数据（如来源文件、页码等）
                    metadata = doc.metadata if hasattr(doc, 'metadata') else {}
                    
                    # 从元数据中获取来源信息
                    source = metadata.get("source", "未知")
                    
                    # 添加格式化的文档片段
                    output_parts.append(f"**片段 {i}** (来源: {source})")
                    # 只显示前300个字符，避免输出过长
                    output_parts.append(f"{content[:300]}...")
                    output_parts.append("")  # 添加空行分隔
                    
                    # 保存结构化数据，供后续处理使用
                    doc_data.append({
                        "content": content,  # 完整内容
                        "source": source,  # 来源
                        "metadata": metadata  # 所有元数据
                    })
                
                # 返回成功结果
                return ToolResult(
                    success=True,
                    output="\n".join(output_parts),  # 格式化的文本输出
                    data=doc_data,  # 结构化数据
                    metadata={
                        "method": method,
                        "top_k": top_k,
                        "count": len(docs)  # 实际找到的文档数量
                    }
                )
        
        # ========== 第4步：异常处理 ==========
        except Exception as e:
            """
            捕获所有异常，确保工具不会崩溃
            
            可能的异常：
            - 向量库连接失败
            - LLM API调用失败
            - 内存不足
            - 文件读取错误
            等等
            """
            # 返回失败结果，包含详细错误信息
            return ToolResult(
                success=False,
                output="",
                error=f"RAG 检索失败: {str(e)}"  # 将异常对象转换为字符串
                # str(e) 会调用异常的__str__方法，获取错误描述
            )


# ==========================================================================
# DocumentListTool: 文档列表工具
# ==========================================================================
class DocumentListTool(BaseTool):
    """文档列表工具 - 列出知识库中的所有文档
    
    这个工具用于查看知识库中有哪些文档，类似于文件管理器的功能。
    
    功能：
    - 扫描文档目录
    - 列出所有支持的文件
    - 显示文件大小、类型
    - 可选显示内容摘要
    
    使用场景：
    - 用户想知道知识库里有什么内容
    - 查看某个文档是否已经被索引
    - 了解知识库的覆盖范围
    
    支持的文件类型：
    - .txt: 纯文本文件
    - .md: Markdown文档
    - .pdf: PDF文档
    - .docx: Word文档
    - .html: HTML网页
    """
    
    def __init__(self, documents_path: str = None):
        """初始化文档列表工具
        
        Args:
            documents_path: 文档目录路径，默认使用配置中的路径
                - 如果为None，尝试从Config.DOCUMENTS_PATH获取
                - 如果Config中也没有，使用"./documents"
        """
        # 三元表达式链，依次尝试三个可能的值
        # 1. 如果documents_path有值，使用它
        # 2. 否则，如果Config有DOCUMENTS_PATH属性，使用它
        # 3. 否则，使用默认值"./documents"
        self._documents_path = documents_path or \
            (Config.DOCUMENTS_PATH if hasattr(Config, 'DOCUMENTS_PATH') else "./documents")
        
        # 调用父类初始化
        super().__init__()
    
    @property
    def name(self) -> str:
        """工具名称"""
        return "list_documents"  # 清晰表达"列出文档"的功能
    
    @property
    def description(self) -> str:
        """工具描述"""
        return "列出知识库中所有已索引的文档，包括文档名称、类型和摘要信息。"
    
    @property
    def category(self) -> ToolCategory:
        """工具分类"""
        return ToolCategory.RETRIEVAL  # 也属于检索类（信息获取）
    
    @property
    def parameters(self) -> List[Dict[str, Any]]:
        """参数定义"""
        return [
            {
                "name": "include_summary",  # 参数名：是否包含摘要
                "type": "boolean",  # 布尔类型
                "description": "是否包含文档摘要，默认 True",
                # True: 读取并显示文件开头的内容
                # False: 只显示文件名和大小
                "required": False  # 可选参数
            }
        ]
    
    def execute(self, **kwargs) -> ToolResult:
        """执行文档列表获取
        
        执行流程：
        1. 获取参数
        2. 检查文档目录是否存在
        3. 遍历目录找到所有支持的文件
        4. 收集文件信息（名称、大小、类型）
        5. 可选读取文件摘要
        6. 格式化并返回结果
        
        Args:
            **kwargs: 关键字参数
                - include_summary (bool): 是否包含摘要，默认True
        
        Returns:
            ToolResult: 包含文档列表的结果对象
        """
        # ========== 导入必要的模块 ==========
        # os: 操作系统接口，提供文件和目录操作
        import os
        # Path: pathlib模块的路径对象，更现代的路径操作方式
        from pathlib import Path
        
        # ========== 获取参数 ==========
        include_summary = kwargs.get("include_summary", True)
        
        # ========== 执行文档扫描 ==========
        try:
            # 创建Path对象，表示文档目录路径
            # Path提供面向对象的路径操作，比os.path更直观
            docs_path = Path(self._documents_path)
            
            # 检查目录是否存在
            if not docs_path.exists():
                # 目录不存在，返回错误
                return ToolResult(
                    success=False,
                    output="",
                    error=f"文档目录不存在: {self._documents_path}"
                )
            
            # 初始化文档列表
            documents = []
            
            # 定义支持的文件扩展名集合
            # 使用集合(set)而不是列表(list)，因为成员检查更快 O(1) vs O(n)
            supported_extensions = {'.txt', '.md', '.pdf', '.docx', '.html'}
            
            # ========== 遍历目录 ==========
            # rglob("*") 递归遍历所有文件和子目录
            # "*" 是通配符，匹配所有文件名
            for file_path in docs_path.rglob("*"):
                # 检查是否是文件（不是目录）且扩展名在支持列表中
                # suffix.lower() 获取小写的文件扩展名，如 .TXT -> .txt
                if file_path.is_file() and file_path.suffix.lower() in supported_extensions:
                    # ========== 收集文件信息 ==========
                    doc_info = {
                        "name": file_path.name,  # 文件名（包含扩展名）
                        # relative_to() 获取相对于docs_path的路径
                        "path": str(file_path.relative_to(docs_path)),
                        # suffix[1:] 去掉扩展名开头的点，如 .txt -> txt
                        "type": file_path.suffix.lower()[1:],
                        # stat().st_size 获取文件大小（字节）
                        "size": file_path.stat().st_size
                    }
                    
                    # ========== 读取文件摘要（如果需要且是文本文件）==========
                    # 只为txt和md文件读取摘要，因为它们是纯文本
                    if include_summary and file_path.suffix.lower() in {'.txt', '.md'}:
                        try:
                            # 打开文件，使用utf-8编码
                            # 'r' 表示只读模式
                            # encoding='utf-8' 指定字符编码，支持中文
                            with open(file_path, 'r', encoding='utf-8') as f:
                                # 读取前500个字符
                                content = f.read(500)
                                # 如果内容超过200字符，截断并添加省略号
                                doc_info["summary"] = content[:200] + "..." if len(content) > 200 else content
                        except:
                            # 读取失败（可能是编码问题或权限问题）
                            # 使用裸except，捕获所有异常，确保不会因为一个文件失败而中断
                            doc_info["summary"] = "(无法读取摘要)"
                    
                    # 将文件信息添加到列表
                    documents.append(doc_info)
            
            # ========== 检查是否找到文档 ==========
            if not documents:
                # 没有找到任何文档
                return ToolResult(
                    success=True,  # 仍然是成功的（没有错误发生）
                    output="知识库中暂无文档",
                    data=[]
                )
            
            # ========== 格式化输出 ==========
            output_parts = [f"知识库共有 {len(documents)} 个文档:\n"]
            
            # 遍历所有文档，生成格式化的输出
            for doc in documents:
                # 将字节转换为KB（除以1024）
                size_kb = doc["size"] / 1024
                # 添加文档条目，使用Markdown格式
                # - 表示列表项
                # ** ** 表示粗体
                # {size_kb:.1f} 格式化为保留1位小数的浮点数
                output_parts.append(f"- **{doc['name']}** ({doc['type']}, {size_kb:.1f}KB)")
                
                # 如果有摘要，添加摘要信息
                if doc.get("summary"):
                    # 截断摘要到100字符，避免输出过长
                    output_parts.append(f"  摘要: {doc['summary'][:100]}...")
            
            # ========== 返回结果 ==========
            return ToolResult(
                success=True,
                output="\n".join(output_parts),  # 将输出列表连接为字符串
                data=documents,  # 原始结构化数据
                metadata={"total": len(documents)}  # 文档总数
            )
        
        # ========== 异常处理 ==========
        except Exception as e:
            # 捕获所有异常，返回错误信息
            return ToolResult(
                success=False,
                output="",
                error=f"获取文档列表失败: {str(e)}"
            )


# ==========================================================================
# KnowledgeBaseInfoTool: 知识库信息工具
# ==========================================================================
class KnowledgeBaseInfoTool(BaseTool):
    """知识库信息工具 - 获取知识库的统计信息
    
    这个工具提供知识库的元信息和统计数据，帮助用户了解系统配置。
    
    功能：
    - 显示文档块（chunk）数量
    - 显示使用的模型信息
    - 显示存储路径
    - 显示系统配置
    
    使用场景：
    - 诊断知识库问题
    - 了解系统配置
    - 检查向量库是否正常加载
    - 查看使用的模型版本
    
    什么是文档块（chunk）？
    - 长文档会被分割成小片段
    - 每个片段称为一个chunk
    - chunk是检索的基本单位
    - 通常每个chunk包含几百到几千字
    """
    
    def __init__(self, vector_store: VectorStore = None):
        """初始化知识库信息工具
        
        Args:
            vector_store: VectorStore实例，如果为None会延迟创建
        """
        # 存储vector_store实例
        self._vector_store = vector_store
        # 调用父类初始化
        super().__init__()
    
    @property
    def name(self) -> str:
        """工具名称"""
        return "kb_info"  # kb是knowledge base的缩写
    
    @property
    def description(self) -> str:
        """工具描述"""
        return "获取知识库的统计信息，包括文档块数量、向量维度、存储大小等。"
    
    @property
    def category(self) -> ToolCategory:
        """工具分类"""
        return ToolCategory.RETRIEVAL  # 属于检索类（信息获取）
    
    @property
    def parameters(self) -> List[Dict[str, Any]]:
        """参数定义"""
        return []  # 这个工具不需要参数
    
    def execute(self, **kwargs) -> ToolResult:
        """获取知识库信息
        
        执行流程：
        1. 确保vector_store已初始化
        2. 检查向量库是否已加载
        3. 从ChromaDB获取统计信息
        4. 从Config获取配置信息
        5. 格式化并返回结果
        
        Returns:
            ToolResult: 包含知识库信息的结果对象
        """
        try:
            # ========== 确保向量库已初始化 ==========
            if self._vector_store is None:
                # 如果没有传入vector_store，创建新实例
                self._vector_store = VectorStore()
                # 加载向量数据库
                self._vector_store.load_vectorstore()
            
            # ========== 检查向量库是否成功加载 ==========
            if self._vector_store.vectorstore is None:
                # 向量库未初始化，返回错误
                return ToolResult(
                    success=False,
                    output="",
                    error="知识库未初始化"
                )
            
            # ========== 获取向量数据库信息 ==========
            # vectorstore是LangChain的Chroma对象
            # _collection是ChromaDB的底层集合对象
            collection = self._vector_store.vectorstore._collection
            
            # 获取集合中的文档数量
            # count()返回向量库中的文档块总数
            count = collection.count()
            
            # ========== 构建信息字典 ==========
            info = {
                "total_chunks": count,  # 文档块总数
                "embedding_model": Config.EMBEDDING_MODEL,  # 嵌入模型名称
                "vector_db_path": Config.VECTOR_DB_PATH,  # 向量库存储路径
                "llm_model": Config.LLM_MODEL,  # LLM模型名称
                "model_provider": Config.MODEL_PROVIDER  # 模型提供商
            }
            # 这些配置信息从Config类中获取，Config在settings.py中定义
            
            # ========== 格式化输出 ==========
            # 使用三引号字符串，保留换行和格式
            # f-string允许在字符串中嵌入变量
            output = f"""知识库统计信息:
- 文档块数量: {count}
- 嵌入模型: {Config.EMBEDDING_MODEL}
- LLM 模型: {Config.LLM_MODEL}
- 模型提供者: {Config.MODEL_PROVIDER}
- 存储路径: {Config.VECTOR_DB_PATH}"""
            
            # ========== 返回结果 ==========
            return ToolResult(
                success=True,
                output=output,  # 格式化的文本输出
                data=info  # 结构化数据
            )
        
        # ========== 异常处理 ==========
        except Exception as e:
            # 捕获所有可能的异常
            return ToolResult(
                success=False,
                output="",
                error=f"获取知识库信息失败: {str(e)}"
            )


# ==========================================================================
# 文件结束
# ==========================================================================
"""
总结：这个模块实现了三个RAG相关的Agent工具

1. RAGSearchTool - 核心检索工具
   - 支持向量检索、BM25、混合检索
   - 可选LLM答案生成
   - 返回检索结果和来源引用

2. DocumentListTool - 文档管理工具
   - 列出知识库中的所有文档
   - 显示文件信息和摘要
   - 帮助用户了解知识库内容

3. KnowledgeBaseInfoTool - 系统信息工具
   - 显示知识库统计信息
   - 显示系统配置
   - 用于诊断和监控

设计模式：
- 策略模式：支持多种检索策略（vector/bm25/hybrid）
- 模板方法：继承BaseTool，实现统一接口
- 依赖注入：通过构造函数注入依赖对象
- 延迟初始化：只在需要时创建资源

关键技术：
- 向量检索：使用embedding进行语义搜索
- BM25算法：传统的关键词检索
- RAG：结合检索和生成的AI技术
- ChromaDB：向量数据库
- LangChain：LLM应用开发框架

使用示例：
```python
# 创建工具
rag_tool = RAGSearchTool()

# 执行检索
result = rag_tool.execute(
    query="什么是RAG?",
    top_k=3,
    generate_answer=True,
    method="hybrid"
)

# 查看结果
if result.success:
    print(result.output)  # 打印格式化的答案
    print(result.data)    # 查看结构化数据
else:
    print(result.error)   # 打印错误信息
```
"""
