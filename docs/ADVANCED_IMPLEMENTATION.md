# 🔍 工程深度讲解 - 高级实现细节与代码流程

> **面向开发者** | 详细讲解每个模块的代码实现、关键算法、设计模式
>
> 版本: 3.0.0 | 最后更新: 2024年12月31日

---

## 目录

1. [代码组织与导入](#代码组织与导入)
2. [关键类与接口](#关键类与接口)
3. [算法详解](#算法详解)
4. [异常处理与日志](#异常处理与日志)
5. [单元测试](#单元测试)
6. [部署与配置](#部署与配置)
7. [性能基准测试](#性能基准测试)

---

## 代码组织与导入

### 1. 项目目录结构详解

```
RAG知识库/
│
├── src/                           # 源代码根目录
│   ├── __init__.py
│   ├── agent/                    # 🆕 Agent 智能体模块
│   │   ├── __init__.py           # 导出: RAGAgent, AgentBuilder, AgentConfig
│   │   ├── base.py               # 基类与数据结构 (738 行)
│   │   ├── rag_agent.py          # RAG Agent 实现
│   │   ├── intent_router.py      # 意图路由器
│   │   └── tools/
│   │       ├── __init__.py
│   │       ├── base.py           # 工具基类 (Tool ABC)
│   │       ├── rag_tools.py      # RAG 检索工具
│   │       ├── web_tools.py      # 网页搜索工具
│   │       ├── file_tools.py     # 文件操作工具
│   │       └── analysis_tools.py # 分析工具
│   │
│   ├── api/                      # FastAPI 应用层
│   │   ├── __init__.py
│   │   ├── app.py                # FastAPI 工厂函数 (create_app)
│   │   ├── routes.py             # 原有 API 路由
│   │   ├── agent_routes.py       # 🆕 Agent API 路由
│   │   └── v1/                   # 版本化 API
│   │       └── ...
│   │
│   ├── core/                     # 核心数据处理
│   │   ├── __init__.py
│   │   ├── document_processor.py # 文档加载与分块 (243 行)
│   │   ├── vector_store.py       # 向量存储与检索
│   │   ├── bm25_retriever.py     # BM25 关键词检索
│   │   └── reranker.py           # CrossEncoder 精排
│   │
│   ├── services/                 # 业务服务层
│   │   ├── __init__.py
│   │   ├── rag_assistant.py      # RAG 问答服务 (594 行)
│   │   ├── conversation_manager.py  # 对话历史管理
│   │   ├── ollama_client.py      # Ollama 客户端
│   │   └── deepseek_client.py    # DeepSeek 客户端
│   │
│   ├── models/                   # 数据模型与 Schema
│   │   ├── __init__.py
│   │   └── schemas.py            # Pydantic 数据模型
│   │
│   ├── config/                   # 全局配置
│   │   ├── __init__.py
│   │   └── settings.py           # Config 全局配置类
│   │
│   └── utils/                    # 工具函数
│       ├── __init__.py
│       ├── logger.py             # 日志配置
│       └── helpers.py            # 辅助函数
│
├── frontend/                     # Vue.js 3 前端应用
│   ├── index.html
│   ├── package.json
│   ├── vite.config.js
│   ├── src/
│   │   ├── main.js
│   │   ├── App.vue               # 主容器组件 (1907 行)
│   │   └── styles.css            # 样式表
│   │
│   └── dist/                     # 打包输出目录
│
├── documents/                    # 知识库源文件
│   ├── README.md
│   ├── tutorial.md
│   └── ...
│
├── vector_db/                    # 向量数据库存储
│   ├── chroma.sqlite3            # ChromaDB 数据库文件
│   └── *.parquet                 # 向量数据文件
│
├── conversations/                # 对话历史存储
│   ├── 3b733ec7-xxxx.json
│   └── ...
│
├── logs/                         # 日志输出
│   ├── backend.log
│   └── agent.log
│
├── app_api.py                    # FastAPI 启动文件 (兼容层)
├── run_api.py                    # API 服务启动脚本
├── run_cli.py                    # 命令行接口启动脚本
├── run_agent.py                  # Agent 交互式启动脚本
├── run_web.py                    # Streamlit Web 界面启动脚本
├── main.py                       # 主程序入口 (重定向到 run_cli.py)
│
├── requirements.txt              # Python 依赖
├── .env.example                  # 环境变量示例
├── README.md                     # 项目说明
├── START_HERE.md                 # 快速开始指南
└── start.sh                      # 一键启动脚本
```

### 2. 模块导入关系

```
用户输入
  ↓
┌─────────────────────────────────────────────────────┐
│ FastAPI (app_api.py)                                │
│ ├─ routes.py (API 路由)                             │
│ └─ agent_routes.py (Agent 路由)                     │
└─────────────────────┬───────────────────────────────┘
                      ↓
┌─────────────────────────────────────────────────────┐
│ 业务层 Services                                      │
│ ├─ RAGAssistant (src/services/rag_assistant.py)    │
│ ├─ RAGAgent (src/agent/rag_agent.py)               │
│ ├─ IntentRouter (src/agent/intent_router.py)       │
│ └─ ConversationManager (src/services/...)          │
└─────────────────────┬───────────────────────────────┘
                      ↓
┌─────────────────────────────────────────────────────┐
│ 数据处理层 Core                                      │
│ ├─ DocumentProcessor (加载和分块)                   │
│ ├─ VectorStore (向量化和存储)                       │
│ ├─ BM25Retriever (关键词检索)                       │
│ └─ CrossEncoderReranker (精排)                      │
└─────────────────────┬───────────────────────────────┘
                      ↓
┌─────────────────────────────────────────────────────┐
│ 外部服务                                             │
│ ├─ ChromaDB (向量数据库)                            │
│ ├─ OpenAI / Ollama (LLM)                            │
│ ├─ DuckDuckGo / Tavily (网页搜索)                   │
│ └─ Sentence-Transformers (Embedding)               │
└─────────────────────────────────────────────────────┘
```

### 3. 关键导入语句

```python
# src/agent/rag_agent.py
from src.agent.base import BaseAgent, AgentConfig, ThoughtStep, StreamEvent
from src.agent.tools import RAGTool, WebSearchTool, FileTool
from src.services.rag_assistant import RAGAssistant
from src.config.settings import Config

# src/services/rag_assistant.py
from src.core.vector_store import VectorStore
from src.core.bm25_retriever import BM25Retriever
from langchain_classic.chains.retrieval_qa.base import RetrievalQA
from langchain.chat_models import init_chat_model

# src/core/vector_store.py
from langchain_chroma import Chroma
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain.schema import Document

# src/api/app.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.api.routes import router
from src.api.agent_routes import router as agent_router
```

---

## 关键类与接口

### 1. Agent 基类（ReAct 框架核心）

**文件**: `src/agent/base.py`

```python
@dataclass
class StreamEvent:
    """流式事件 - 用于实时推送 Agent 思考过程"""
    type: str  # 'thinking' | 'action' | 'observation' | 'answer' | 'error' | 'done'
    data: Any = None
    step: int = 0
    
    def to_json(self) -> str:
        """转换为 JSON 用于 SSE 推送"""
        return json.dumps({
            'type': self.type,
            'data': self.data,
            'step': self.step
        })


@dataclass
class AgentConfig:
    """Agent 配置参数"""
    max_iterations: int = 5           # 最大推理步数（限制计算）
    temperature: float = 0.7          # LLM 温度参数（创意度）
    enable_reflection: bool = False   # 是否启用反思机制（耗时）
    enable_planning: bool = True      # 是否启用规划能力
    verbose: bool = True              # 详细输出
    llm_timeout: int = 30             # LLM 请求超时（秒）


@dataclass
class ThoughtStep:
    """单个推理步骤的记录"""
    step: int                         # 步骤序号 (1, 2, 3...)
    thought: str                      # "我需要做什么？" - 思考内容
    action: Optional[str] = None      # 工具名 ("rag_search", "web_search")
    action_input: Optional[Dict] = None  # 工具参数 ({"query": "..."})
    observation: Optional[str] = None    # 工具返回结果
    observation_data: Optional[Dict] = None  # 结构化数据 (列表、表格等)
    reflection: Optional[str] = None  # "结果满足了吗？" - 反思内容


class BaseAgent(ABC):
    """Agent 基类 - 实现 ReAct 推理循环"""
    
    def __init__(self, config: AgentConfig = None):
        # AgentConfig 是一个数据类（dataclass），用于配置 RAG Agent 的行为参数
        self.config = config or AgentConfig()
        self.llm = self._init_llm()
        self.tools = self._init_tools()
        self.logger = logging.getLogger(__name__)
    
    def run(self, query: str) -> AgentResponse:
        """执行 ReAct 推理循环"""
        
        thought_process: List[ThoughtStep] = []
        tools_used: List[str] = []
        
        for iteration in range(self.config.max_iterations):
            # 第1步：THINK - 思考
            thought = self._generate_thought(query, thought_process)
            
            # 第2步：PLAN - 规划
            if self.config.enable_planning:
                plan = self._generate_plan(thought)
            else:
                plan = None
            
            # 第3步：ACT - 行动
            action_text = self._parse_action(thought)
            if not action_text:
                # 无需进一步行动，进入最终答案
                break
            
            tool_name, tool_input = self._parse_action_input(action_text)
            
            # 第4步：OBSERVE - 观察
            observation = self._execute_tool(tool_name, tool_input)
            tools_used.append(tool_name)
            
            # 记录本步骤
            step = ThoughtStep(
                step=iteration + 1,
                thought=thought,
                action=tool_name,
                action_input=tool_input,
                observation=observation
            )
            thought_process.append(step)
            
            # 第5步：REFLECT - 反思（可选）
            if self.config.enable_reflection:
                reflection = self._generate_reflection(observation)
                step.reflection = reflection
            
            # 判断是否已得出结论
            if self._is_final_answer(observation):
                break
        
        # 第6步：FINAL ANSWER - 生成最终答案
        final_answer = self._generate_final_answer(
            query=query,
            thought_process=thought_process
        )
        
        return AgentResponse(
            success=True,
            answer=final_answer,
            thought_process=thought_process,
            tools_used=tools_used,
            iterations=len(thought_process)
        )
    
    def run_stream(self, query: str) -> Generator[StreamEvent, None, None]:
        """流式执行 ReAct 推理循环（用于实时推送）"""
        
        try:
            thought_process: List[ThoughtStep] = []
            
            for iteration in range(self.config.max_iterations):
                # 推送思考事件
                thought = self._generate_thought(query, thought_process)
                yield StreamEvent(
                    type='thinking',
                    data={'thought': thought, 'step': iteration + 1}
                )
                
                # 解析行动
                tool_name, tool_input = self._parse_action_input(thought)
                if not tool_name:
                    break
                
                # 推送行动事件
                yield StreamEvent(
                    type='action',
                    data={'tool': tool_name, 'input': tool_input, 'step': iteration + 1}
                )
                
                # 执行工具
                observation = self._execute_tool(tool_name, tool_input)
                
                # 推送观察事件
                yield StreamEvent(
                    type='observation',
                    data={'result': observation, 'step': iteration + 1}
                )
                
                # 记录步骤
                thought_process.append(ThoughtStep(
                    step=iteration + 1,
                    thought=thought,
                    action=tool_name,
                    action_input=tool_input,
                    observation=observation
                ))
                
                if self._is_final_answer(observation):
                    break
            
            # 生成最终答案
            final_answer = self._generate_final_answer(query, thought_process)
            
            # 推送答案事件
            yield StreamEvent(
                type='answer',
                data={'answer': final_answer}
            )
            
            # 推送完成事件
            yield StreamEvent(type='done')
            
        except Exception as e:
            self.logger.error(f"Agent 执行出错: {str(e)}", exc_info=True)
            yield StreamEvent(
                type='error',
                data={'message': str(e)}
            )
```

### 2. RAG 助手类

**文件**: `src/services/rag_assistant.py`

```python
class RAGAssistant:
    """RAG 检索增强生成助手"""
    
    def __init__(
        self,
        vector_store: VectorStore = None,
        model_name: str = None,
        temperature: float = None,
        fast_mode: bool = None
    ):
        """初始化 RAG 助手"""
        self.vector_store = vector_store or VectorStore()
        self.fast_mode = fast_mode if fast_mode is not None else Config.RAG_FAST_MODE
        
        # 初始化 LLM
        self.llm = self._init_llm(model_name, temperature)
        
        # 初始化检索器
        self.bm25_retriever = BM25Retriever()
        
        # 可选：精排模型
        self.reranker = None
        if Config.ENABLE_RERANK:
            try:
                from sentence_transformers import CrossEncoder
                self.reranker = CrossEncoder('cross-encoder/qnli-distilroberta-base')
            except:
                pass
    
    def retrieve_context(self, query: str, top_k: int = None) -> List[Tuple[str, float]]:
        """混合检索 - 结合向量检索和 BM25
        
        Args:
            query: 查询文本
            top_k: 返回文档数（默认3）
        
        Returns:
            [(文本内容, 相似度得分), ...]
        """
        top_k = top_k or Config.TOP_K
        
        # 1️⃣ 向量检索
        vector_results = self.vector_store.similarity_search_with_score(
            query=query,
            k=top_k
        )
        
        # 2️⃣ BM25 检索
        bm25_results = self.bm25_retriever.search(
            query=query,
            k=top_k
        )
        
        # 3️⃣ 结果融合
        # 合并两个结果集，按相关性排序
        merged = {}
        
        for doc, score in vector_results:
            doc_id = doc.metadata.get('source', doc.page_content[:50])
            merged[doc_id] = {
                'doc': doc,
                'vector_score': score,
                'bm25_score': 0.0
            }
        
        for doc, score in bm25_results:
            doc_id = doc.metadata.get('source', doc.page_content[:50])
            if doc_id not in merged:
                merged[doc_id] = {
                    'doc': doc,
                    'vector_score': 0.0,
                    'bm25_score': score
                }
            else:
                merged[doc_id]['bm25_score'] = score
        
        # 计算融合得分
        final_results = [
            (
                item['doc'],
                0.6 * item['vector_score'] + 0.4 * item['bm25_score']
            )
            for item in merged.values()
        ]
        
        # 4️⃣ 精排（可选）
        if self.reranker and len(final_results) > 2:
            reranked = self._rerank(query, final_results)
            final_results = reranked
        
        # 返回前 K 个结果
        return sorted(final_results, key=lambda x: x[1], reverse=True)[:top_k]
    
    def query(
        self,
        query: str,
        conversation_history: str = "",
        stream: bool = True
    ) -> Union[str, Generator[str, None, None]]:
        """执行 RAG 查询
        
        Args:
            query: 用户问题
            conversation_history: 对话历史（格式化字符串）
            stream: 是否使用流式输出
        
        Returns:
            回答（流或字符串）
        """
        
        # 1️⃣ 检索相关文档
        docs = self.retrieve_context(query)
        
        # 2️⃣ 构建 Prompt
        context = "\n\n".join([
            f"【来源: {doc.metadata.get('source', '未知')}】\n{doc.page_content}"
            for doc, _ in docs
        ])
        
        prompt = self.DEFAULT_PROMPT_TEMPLATE.format(
            conversation_history=conversation_history,
            context=context,
            question=query
        )
        
        # 3️⃣ 调用 LLM
        if stream:
            return self._stream_response(prompt)
        else:
            response = self.llm.invoke(prompt)
            return response.content
    
    def _stream_response(self, prompt: str) -> Generator[str, None, None]:
        """流式生成回答"""
        
        try:
            # 使用 LLM 的流式接口
            for chunk in self.llm.stream(prompt):
                if isinstance(chunk, str):
                    yield chunk
                elif hasattr(chunk, 'content'):
                    yield chunk.content
        except Exception as e:
            self.logger.error(f"流式生成出错: {str(e)}")
            yield f"[错误] {str(e)}"
```

### 3. 向量存储类

**文件**: `src/core/vector_store.py`

```python
class VectorStore:
    """向量存储与检索"""
    
    def __init__(self, persist_directory: str = "./vector_db"):
        """初始化向量存储"""
        self.persist_directory = persist_directory
        self.embeddings = HuggingFaceEmbeddings(
            model_name=Config.EMBEDDING_MODEL
        )
        self.vectorstore = None
        self.load_or_create()
    
    def load_or_create(self):
        """加载现有向量库或创建新的"""
        
        # 尝试加载现有向量库
        try:
            self.vectorstore = Chroma(
                persist_directory=self.persist_directory,
                embedding_function=self.embeddings
            )
            self.logger.info(f"✓ 加载现有向量库，共 {self.vectorstore._collection.count()} 个文档")
        except Exception as e:
            self.logger.warning(f"无法加载向量库: {e}，创建新向量库")
            self.vectorstore = Chroma(
                persist_directory=self.persist_directory,
                embedding_function=self.embeddings
            )
    
    def add_documents(self, documents: List[Document]):
        """添加文档到向量库
        
        Args:
            documents: LangChain Document 对象列表
        """
        
        if not documents:
            self.logger.warning("没有文档要添加")
            return
        
        self.logger.info(f"开始向量化 {len(documents)} 个文档块...")
        
        # 使用 Chroma 的 add_documents 方法
        # 内部会自动进行向量化和存储
        ids = self.vectorstore.add_documents(documents)
        
        # 持久化到磁盘
        self.vectorstore.persist()
        
        self.logger.info(f"✓ 成功添加 {len(ids)} 个文档块到向量库")
    
    def similarity_search_with_score(
        self,
        query: str,
        k: int = 3
    ) -> List[Tuple[Document, float]]:
        """相似度搜索（带分数）
        
        Args:
            query: 查询文本
            k: 返回文档数
        
        Returns:
            [(Document, 相似度得分), ...]
            相似度范围：0-1，越接近 1 越相似
        """
        
        if self.vectorstore is None:
            self.logger.warning("向量库为空，返回空结果")
            return []
        
        try:
            # Chroma 使用余弦相似度
            results = self.vectorstore.similarity_search_with_score(query, k=k)
            return results
        except Exception as e:
            self.logger.error(f"相似度搜索失败: {str(e)}")
            return []
    
    def similarity_search(self, query: str, k: int = 3) -> List[Document]:
        """相似度搜索（不带分数）"""
        
        if self.vectorstore is None:
            return []
        
        return self.vectorstore.similarity_search(query, k=k)
    
    def get_stats(self) -> Dict[str, Any]:
        """获取向量库统计信息"""
        
        if self.vectorstore is None:
            return {'status': 'empty'}
        
        try:
            count = self.vectorstore._collection.count()
            return {
                'status': 'loaded',
                'document_count': count,
                'embedding_dim': Config.EMBEDDING_DIM,
                'persist_directory': self.persist_directory
            }
        except Exception as e:
            return {'status': 'error', 'error': str(e)}
```

### 4. 文档处理器类

**文件**: `src/core/document_processor.py`

```python
class DocumentProcessor:
    """文档加载和处理"""
    
    def __init__(
        self,
        chunk_size: int = 1500,
        chunk_overlap: int = 300
    ):
        """初始化文档处理器"""
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        
        # 递归文本分割器
        # 按优先级尝试分割：标题 → 段落 → 句子 → 字符
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            length_function=len,
            separators=[
                "\n## ",      # Markdown 二级标题（优先级最高）
                "\n### ",     # Markdown 三级标题
                "\n#### ",    # Markdown 四级标题
                "\n\n",       # 段落分割
                "\n",         # 换行符
                "。",         # 中文句号
                "！",         # 中文感叹号
                "？",         # 中文问号
                "；",         # 中文分号
                " "           # 空格
            ]
        )
    
    def load_document(self, file_path: str) -> List[Document]:
        """加载单个文档
        
        Args:
            file_path: 文件路径
        
        Returns:
            Document 对象列表，每个对象代表文件的一页/部分
        """
        
        file_path = Path(file_path)
        extension = file_path.suffix.lower()
        
        # 根据文件类型选择加载器
        if extension == ".pdf":
            loader = PyPDFLoader(str(file_path))
        elif extension in [".txt", ".md"]:
            loader = TextLoader(str(file_path), encoding="utf-8")
        elif extension in [".docx", ".doc"]:
            loader = Docx2txtLoader(str(file_path))
        elif extension == ".csv":
            loader = CSVLoader(str(file_path), encoding="utf-8")
        elif extension == ".json":
            loader = JSONLoader(str(file_path), jq_schema=".")
        else:
            raise ValueError(f"不支持的文件类型: {extension}")
        
        # 加载文档
        docs = loader.load()
        
        # 附加元数据
        for doc in docs:
            if 'source' not in doc.metadata:
                doc.metadata['source'] = str(file_path.name)
        
        return docs
    
    def split_documents(self, documents: List[Document]) -> List[Document]:
        """将文档分割成文本块
        
        Args:
            documents: Document 对象列表
        
        Returns:
            分割后的 Document 对象列表
        """
        
        # 使用递归文本分割器
        chunks = self.splitter.split_documents(documents)
        
        # 为每个块添加索引
        for i, chunk in enumerate(chunks):
            chunk.metadata['chunk_index'] = i
        
        return chunks
    
    def process_documents(
        self,
        file_paths: List[str],
        progress_callback=None
    ) -> List[Document]:
        """批处理多个文档
        
        Args:
            file_paths: 文件路径列表
            progress_callback: 进度回调函数 (current, total) -> None
        
        Returns:
            所有分割后的文本块
        """
        
        all_documents = []
        
        for i, file_path in enumerate(file_paths):
            try:
                # 加载文档
                docs = self.load_document(file_path)
                
                # 分割文档
                chunks = self.split_documents(docs)
                
                all_documents.extend(chunks)
                
                # 调用进度回调
                if progress_callback:
                    progress_callback(i + 1, len(file_paths))
                
                print(f"✓ 处理了 {file_path}，生成 {len(chunks)} 个文本块")
                
            except Exception as e:
                print(f"✗ 处理 {file_path} 失败: {str(e)}")
                continue
        
        print(f"✓ 总共处理了 {len(all_documents)} 个文本块")
        return all_documents
```

---

## 算法详解

### 1. 混合检索算法

**混合检索综合了向量检索和 BM25 检索的优点：**

```python
def hybrid_retrieve(query: str, k: int = 3):
    """混合检索算法"""
    
    # 步骤1：向量检索
    vector_results = vector_store.similarity_search_with_score(query, k=k)
    # 返回格式: [(doc1, 0.95), (doc2, 0.87), ...]
    # 分数范围: [0, 1]，使用余弦相似度
    
    # 步骤2：BM25 检索
    bm25_results = bm25_retriever.search(query, k=k)
    # 返回格式: [(doc1, 2.3), (doc2, 1.8), ...]
    # 分数范围: [0, ∞)，使用 TF-IDF 算法
    
    # 步骤3：标准化 BM25 分数到 [0, 1]
    max_bm25_score = max([score for _, score in bm25_results]) if bm25_results else 1
    normalized_bm25 = [
        (doc, score / max_bm25_score)
        for doc, score in bm25_results
    ]
    
    # 步骤4：结果融合
    # 创建文档ID到信息的映射
    merged = {}
    
    for doc, v_score in vector_results:
        doc_id = id(doc)  # 使用对象 ID 作为键
        merged[doc_id] = {
            'doc': doc,
            'vector_score': v_score,
            'bm25_score': 0.0
        }
    
    for doc, b_score in normalized_bm25:
        doc_id = id(doc)
        if doc_id not in merged:
            merged[doc_id] = {
                'doc': doc,
                'vector_score': 0.0,
                'bm25_score': b_score
            }
        else:
            merged[doc_id]['bm25_score'] = b_score
    
    # 步骤5：加权融合
    # 权重设置：向量检索 60% + BM25 检索 40%
    # 理由：向量检索更能理解语义相关性，权重更高
    final_scores = []
    for item in merged.values():
        fused_score = (
            0.6 * item['vector_score'] +
            0.4 * item['bm25_score']
        )
        final_scores.append((item['doc'], fused_score))
    
    # 步骤6：排序并返回前 K 个
    final_scores.sort(key=lambda x: x[1], reverse=True)
    return final_scores[:k]
```

**为什么这样权衡？**

| 权重分配 | 优点 | 缺点 |
|---------|------|------|
| 向量 70% + BM25 30% | 更重视语义 | 可能遗漏关键词精确匹配 |
| 向量 60% + BM25 40% | **平衡** | - |
| 向量 50% + BM25 50% | 平衡 | 可能被关键词搞乱 |

### 2. CrossEncoder 精排算法

**如果启用精排，使用深度模型重新评分**：

```python
def rerank(query: str, candidates: List[Tuple[Document, float]]):
    """使用 CrossEncoder 进行精排
    
    CrossEncoder 不计算相似度，而是直接预测相关性得分
    """
    
    from sentence_transformers import CrossEncoder
    
    # 初始化模型（只加载一次）
    model = CrossEncoder('cross-encoder/qnli-distilroberta-base')
    
    # 准备评分输入
    # 格式: [(query, document_text), ...]
    pairs = [
        [query, doc.page_content]
        for doc, _ in candidates
    ]
    
    # 批量评分
    # 返回: [score1, score2, ...] 范围 [0, 1]
    scores = model.predict(pairs)
    
    # 步骤4：重新排序
    ranked = [
        (doc, score)
        for (doc, _), score in zip(candidates, scores)
    ]
    
    ranked.sort(key=lambda x: x[1], reverse=True)
    
    return ranked
```

**CrossEncoder vs Bi-Encoder（向量检索）**：

| 方面 | Bi-Encoder | CrossEncoder |
|------|-----------|------------|
| **计算方式** | 分别编码 query 和 doc，计算相似度 | 同时编码 query 和 doc，直接预测相关性 |
| **准确度** | 中等 | ✅ 高 |
| **计算量** | 低（向量化 1 次） | 高（逐对计算） |
| **适用** | 初筛（快速） | 精排（准确） |

### 3. ReAct 推理循环的状态机

```
状态转移图：

    ┌─────────────┐
    │   IDLE      │ (初始化)
    │  (空闲)      │
    └──────┬──────┘
           │ 收到问题
           ▼
    ┌─────────────┐
    │  THINKING   │ 思考需要做什么
    │  (思考)      │
    └──────┬──────┘
           │
           ▼
    ┌─────────────────────┐
    │  是否需要工具？      │
    │  (判断)             │
    └────┬────────────┬───┘
    是   │            │   否
        ▼             ▼
    ┌──────────────┐  ┌──────────────┐
    │   ACTING     │  │  COMPLETED   │
    │  (执行工具)   │  │  (完成)       │
    └──────┬───────┘  └──────────────┘
           │                 ▲
           ▼                 │
    ┌──────────────┐        │
    │  REFLECTING  │───────┘ (最终答案)
    │  (反思结果)   │
    └──────┬───────┘
           │ 需要继续？
           ├─ 是 → THINKING
           └─ 否 → COMPLETED
```

### 4. BM25 算法细节

**BM25 是信息检索中的经典算法，使用 TF-IDF 和概率模型**：

```python
def bm25_score(query: str, document: str) -> float:
    """BM25 评分公式"""
    
    # 参数设置（LangChain 默认值）
    k1 = 1.5      # 词频饱和度（越小越快饱和）
    b = 0.75      # 文档长度归一化（0 = 关闭，1 = 完全）
    
    # 步骤1：分词
    query_terms = query.split()  # 实际使用更复杂的分词器
    doc_terms = document.split()
    
    # 步骤2：计算文档长度
    doc_length = len(doc_terms)
    avg_doc_length = 150  # 假设平均文档长度 150
    
    # 步骤3：逐项计算 BM25 分数
    score = 0.0
    idf_cache = {}  # 缓存 IDF 值
    
    for term in query_terms:
        # 计算 IDF（逆文档频率）
        if term not in idf_cache:
            # N = 总文档数, df = 包含该词的文档数
            N = 10000
            df = count_docs_with_term(term)  # 从索引中获取
            idf = log((N - df + 0.5) / (df + 0.5) + 1)
            idf_cache[term] = idf
        else:
            idf = idf_cache[term]
        
        # 计算词频 (TF)
        tf = doc_terms.count(term)
        
        # BM25 公式
        # score = IDF * (TF * (k1 + 1)) / (TF + k1 * (1 - b + b * doc_length / avg_doc_length))
        numerator = tf * (k1 + 1)
        denominator = tf + k1 * (1 - b + b * doc_length / avg_doc_length)
        
        term_score = idf * (numerator / denominator)
        score += term_score
    
    return score
```

**为什么 BM25 在 RAG 中有用？**

- **精确匹配**：对于人名、技术术语等关键词有优势
- **速度快**：不需要神经网络，基于统计学
- **可解释**：可以看到每个词贡献了多少分数

---

## 异常处理与日志

### 1. 自定义异常类

```python
# src/utils/exceptions.py

class RAGException(Exception):
    """RAG 系统基异常"""
    pass

class VectorStoreException(RAGException):
    """向量库异常"""
    pass

class DocumentProcessingException(RAGException):
    """文档处理异常"""
    pass

class LLMException(RAGException):
    """LLM 调用异常"""
    pass

class RetrievalException(RAGException):
    """检索异常"""
    pass

class AgentException(RAGException):
    """Agent 执行异常"""
    pass
```

### 2. 日志配置

```python
# src/utils/logger.py

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

def setup_logging(log_dir: str = "./logs"):
    """配置全局日志系统"""
    
    log_dir = Path(log_dir)
    log_dir.mkdir(exist_ok=True)
    
    # 创建 logger
    logger = logging.getLogger("rag_system")
    logger.setLevel(logging.DEBUG)
    
    # 日志格式
    formatter = logging.Formatter(
        fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # 文件处理器（带轮转）
    file_handler = RotatingFileHandler(
        filename=log_dir / "app.log",
        maxBytes=10 * 1024 * 1024,  # 10 MB
        backupCount=5,               # 保留 5 个备份
        encoding='utf-8'
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    
    # 控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    
    # 添加处理器
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger
```

### 3. 异常处理示例

```python
# src/services/rag_assistant.py

def query(self, question: str) -> str:
    """RAG 查询，包含完整的异常处理"""
    
    logger = logging.getLogger(__name__)
    
    try:
        # 输入验证
        if not question or not isinstance(question, str):
            raise ValueError("问题必须是非空字符串")
        
        logger.info(f"收到查询: {question[:50]}...")
        
        # 检索
        try:
            docs = self.retrieve_context(question)
            if not docs:
                logger.warning("检索返回空结果")
                return "知识库中没有找到相关信息"
        except RetrievalException as e:
            logger.error(f"检索失败: {str(e)}")
            raise
        
        # LLM 生成
        try:
            answer = self.llm.invoke(self._build_prompt(docs, question))
            logger.info(f"生成回答成功，长度: {len(answer)}")
            return answer.content
        except LLMException as e:
            logger.error(f"LLM 调用失败: {str(e)}")
            raise
    
    except ValueError as e:
        logger.error(f"输入验证失败: {str(e)}")
        return f"输入错误: {str(e)}"
    
    except (RetrievalException, LLMException) as e:
        logger.error(f"处理查询时出错: {str(e)}", exc_info=True)
        return f"系统出错: {str(e)}"
    
    except Exception as e:
        logger.error(f"未预期的错误: {str(e)}", exc_info=True)
        return "系统发生未知错误，请重试"
```

---

## 单元测试

### 1. 向量存储测试

```python
# tests/unit/test_vector_store.py

import pytest
from src.core.vector_store import VectorStore
from langchain.schema import Document

@pytest.fixture
def vector_store():
    """创建临时向量存储"""
    store = VectorStore(persist_directory="/tmp/test_vector_db")
    yield store
    # 清理
    import shutil
    shutil.rmtree("/tmp/test_vector_db", ignore_errors=True)

def test_add_documents(vector_store):
    """测试添加文档"""
    
    docs = [
        Document(page_content="Python 是一种编程语言", metadata={"source": "test.txt"}),
        Document(page_content="Java 是企业级开发语言", metadata={"source": "test.txt"}),
    ]
    
    vector_store.add_documents(docs)
    
    # 验证文档已添加
    stats = vector_store.get_stats()
    assert stats['document_count'] == 2

def test_similarity_search(vector_store):
    """测试相似度搜索"""
    
    # 添加测试文档
    docs = [
        Document(page_content="猫是家养宠物", metadata={"source": "animals.txt"}),
        Document(page_content="狗是忠诚的宠物", metadata={"source": "animals.txt"}),
        Document(page_content="Python 编程语言", metadata={"source": "programming.txt"}),
    ]
    vector_store.add_documents(docs)
    
    # 搜索相似文档
    results = vector_store.similarity_search("宠物", k=2)
    
    # 应该返回关于宠物的两个文档
    assert len(results) == 2
    assert "宠物" in results[0].page_content or "宠物" in results[1].page_content
```

### 2. 文档处理测试

```python
# tests/unit/test_document_processor.py

import pytest
from src.core.document_processor import DocumentProcessor
from pathlib import Path

@pytest.fixture
def processor():
    return DocumentProcessor(chunk_size=1000, chunk_overlap=100)

@pytest.fixture
def sample_markdown(tmp_path):
    """创建样本 Markdown 文件"""
    content = """# 标题一

这是第一段内容。

## 小标题

这是第二段内容，更长一些。这是第二段内容，更长一些。
这是第二段内容，更长一些。这是第二段内容，更长一些。

## 另一个小标题

最后一段。
"""
    
    file_path = tmp_path / "test.md"
    file_path.write_text(content, encoding='utf-8')
    return str(file_path)

def test_load_document(processor, sample_markdown):
    """测试加载文档"""
    
    docs = processor.load_document(sample_markdown)
    
    # Markdown 文件应该加载为单个文档
    assert len(docs) > 0
    assert "标题一" in docs[0].page_content

def test_split_documents(processor, sample_markdown):
    """测试分割文档"""
    
    docs = processor.load_document(sample_markdown)
    chunks = processor.split_documents(docs)
    
    # 应该被分割为多个块
    assert len(chunks) > 1
    
    # 每个块应该有元数据
    for chunk in chunks:
        assert 'source' in chunk.metadata
        assert 'chunk_index' in chunk.metadata
        assert len(chunk.page_content) <= 1000 + 100  # chunk_size + overlap
```

### 3. RAG 助手测试

```python
# tests/unit/test_rag_assistant.py

import pytest
from unittest.mock import Mock, patch
from src.services.rag_assistant import RAGAssistant

@pytest.fixture
def mock_vector_store():
    """创建模拟的向量存储"""
    mock = Mock()
    mock.similarity_search_with_score.return_value = [
        (Mock(page_content="向量数据库是...", metadata={'source': 'db.md'}), 0.95),
        (Mock(page_content="ChromaDB 是...", metadata={'source': 'chroma.md'}), 0.87),
    ]
    return mock

def test_retrieve_context(mock_vector_store):
    """测试检索上下文"""
    
    with patch('src.services.rag_assistant.BM25Retriever') as mock_bm25:
        mock_bm25.return_value.search.return_value = [
            (Mock(page_content="向量数据库...", metadata={'source': 'db.md'}), 1.5),
        ]
        
        assistant = RAGAssistant(vector_store=mock_vector_store)
        results = assistant.retrieve_context("什么是向量数据库", top_k=2)
        
        # 应该返回融合后的结果
        assert len(results) > 0
        assert results[0][1] > 0  # 有分数
```

---

## 部署与配置

### 1. 环境变量配置

```bash
# .env 文件示例

# LLM 提供者选择
MODEL_PROVIDER=openai          # 或 ollama, deepseek

# OpenAI 配置
OPENAI_API_KEY=sk-xxxxxxxxxx
OPENAI_MODEL=gpt-4

# Ollama 配置
OLLAMA_API_URL=http://localhost:11434
OLLAMA_MODEL=llama2

# DeepSeek 配置
DEEPSEEK_API_KEY=sk-xxxxxxxxxx
DEEPSEEK_API_URL=https://api.deepseek.com

# 向量化模型
EMBEDDING_MODEL=all-MiniLM-L6-v2

# RAG 配置
RAG_FAST_MODE=true              # 启用快速模式
TOP_K=3                         # 返回文档数
CHUNK_SIZE=1500                 # 文本块大小
CHUNK_OVERLAP=300               # 块之间重叠

# 检索配置
ENABLE_RERANK=false             # 是否启用精排
ENABLE_HYBRID_RETRIEVAL=true    # 启用混合检索

# 路径配置
DOCUMENTS_PATH=./documents
VECTOR_DB_PATH=./vector_db
CONVERSATIONS_PATH=./conversations
LOGS_PATH=./logs

# 服务器配置
API_HOST=0.0.0.0
API_PORT=8000
FRONTEND_URL=http://localhost:5173
```

### 2. Docker 部署

```dockerfile
# Dockerfile

FROM python:3.11-slim

WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件
COPY requirements.txt .

# 安装 Python 依赖
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用代码
COPY . .

# 暴露端口
EXPOSE 8000

# 启动应用
CMD ["uvicorn", "src.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
```

### 3. Docker Compose 配置

```yaml
# docker-compose.yml

version: '3.8'

services:
  backend:
    build: .
    ports:
      - "8000:8000"
    volumes:
      - ./documents:/app/documents
      - ./vector_db:/app/vector_db
      - ./logs:/app/logs
    environment:
      - MODEL_PROVIDER=openai
      - OPENAI_API_KEY=${OPENAI_API_KEY}
    depends_on:
      - chromadb

  frontend:
    image: node:18-alpine
    working_dir: /app
    ports:
      - "5173:5173"
    volumes:
      - ./frontend:/app
    command: npm run dev

  chromadb:
    image: ghcr.io/chroma-core/chroma:latest
    ports:
      - "8001:8000"
    volumes:
      - chroma_data:/chroma/chroma
```

---

## 性能基准测试

### 1. 检索性能测试

```python
# tests/performance/test_retrieval_speed.py

import time
from src.core.vector_store import VectorStore
from src.core.bm25_retriever import BM25Retriever

def benchmark_vector_retrieval(vector_store, queries, iterations=10):
    """基准测试向量检索速度"""
    
    times = []
    
    for _ in range(iterations):
        for query in queries:
            start = time.time()
            results = vector_store.similarity_search(query, k=3)
            elapsed = time.time() - start
            times.append(elapsed)
    
    avg_time = sum(times) / len(times)
    print(f"向量检索平均耗时: {avg_time * 1000:.2f} ms")
    print(f"吞吐量: {1 / avg_time:.0f} QPS")
    
    return avg_time

def benchmark_bm25_retrieval(bm25_retriever, queries, iterations=10):
    """基准测试 BM25 检索速度"""
    
    times = []
    
    for _ in range(iterations):
        for query in queries:
            start = time.time()
            results = bm25_retriever.search(query, k=3)
            elapsed = time.time() - start
            times.append(elapsed)
    
    avg_time = sum(times) / len(times)
    print(f"BM25 检索平均耗时: {avg_time * 1000:.2f} ms")
    print(f"吞吐量: {1 / avg_time:.0f} QPS")
    
    return avg_time

def benchmark_hybrid_retrieval(vector_store, bm25_retriever, queries, iterations=10):
    """基准测试混合检索速度"""
    
    times = []
    
    for _ in range(iterations):
        for query in queries:
            start = time.time()
            v_results = vector_store.similarity_search(query, k=5)
            b_results = bm25_retriever.search(query, k=5)
            # 融合...
            elapsed = time.time() - start
            times.append(elapsed)
    
    avg_time = sum(times) / len(times)
    print(f"混合检索平均耗时: {avg_time * 1000:.2f} ms")
    print(f"吞吐量: {1 / avg_time:.0f} QPS")
    
    return avg_time

# 性能基准结果示例（在测试环境）
"""
向量检索平均耗时: 150 ms
吞吐量: 6-7 QPS

BM25 检索平均耗时: 50 ms
吞吐量: 20 QPS

混合检索平均耗时: 250 ms (100ms 向量 + 50ms BM25 + 100ms 融合)
吞吐量: 4 QPS

LLM 生成平均耗时: 5-10 秒
端到端总耗时: 5-10 秒 (LLM 是主要瓶颈)
"""
```

### 2. 内存占用分析

```python
# tests/performance/test_memory_usage.py

import psutil
import tracemalloc

def measure_memory_usage():
    """测量各模块的内存占用"""
    
    process = psutil.Process()
    
    # 初始内存
    initial_mem = process.memory_info().rss / 1024 / 1024  # MB
    
    # 加载向量存储
    vector_store = VectorStore()
    after_vector = process.memory_info().rss / 1024 / 1024
    
    # 加载 Embedding 模型
    embeddings = HuggingFaceEmbeddings("all-MiniLM-L6-v2")
    after_embeddings = process.memory_info().rss / 1024 / 1024
    
    # 加载 LLM
    llm = ChatOpenAI(model_name="gpt-4")
    after_llm = process.memory_info().rss / 1024 / 1024
    
    print(f"""
    内存占用分析:
    初始: {initial_mem:.1f} MB
    加载向量存储后: {after_vector:.1f} MB (+{after_vector - initial_mem:.1f} MB)
    加载 Embedding 后: {after_embeddings:.1f} MB (+{after_embeddings - after_vector:.1f} MB)
    加载 LLM 后: {after_llm:.1f} MB (+{after_llm - after_embeddings:.1f} MB)
    
    总占用: {after_llm:.1f} MB
    """)

# 输出示例
"""
内存占用分析:
初始: 250 MB
加载向量存储后: 550 MB (+300 MB) - ChromaDB SQLite 和向量数据
加载 Embedding 后: 800 MB (+250 MB) - Sentence-Transformers 模型
加载 LLM 后: 850 MB (+50 MB) - API 调用，不加载本地模型

总占用: 850 MB
"""
```

---

## 总结

本讲解深入讲述了：

1. **代码组织**：清晰的分层架构
2. **关键类**：BaseAgent、RAGAssistant、VectorStore 等
3. **核心算法**：混合检索、CrossEncoder 精排、BM25
4. **异常处理**：自定义异常、日志系统
5. **测试**：单元测试示例
6. **部署**：Docker、环境配置
7. **性能**：基准测试和优化指标

关键数字：
- 响应时间：5-10 秒（大部分时间在 LLM）
- 检索速度：250-300 ms（混合检索）
- 内存占用：~800-1000 MB
- QPS：4-5（受 LLM 限制）

下一步可以：
- 增加缓存层提速
- 使用 GPU 加速 Embedding
- 实现分布式向量检索
- 优化 Prompt 以减少 LLM 输出
