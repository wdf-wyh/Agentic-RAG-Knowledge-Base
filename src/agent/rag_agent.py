"""RAG Agent - 具备自主决策能力的 RAG 智能体"""

from typing import List, Dict, Any, Optional

from src.agent.base import BaseAgent, AgentConfig, AgentResponse
from src.agent.tools.base import BaseTool
from src.agent.tools.rag_tools import (
    RAGSearchTool,
    DocumentListTool,
    KnowledgeBaseInfoTool,
)
from src.agent.tools.file_tools import (
    ReadFileTool,
    WriteFileTool,
    ListDirectoryTool,
    MoveFileTool,
    CreateDirectoryTool,
    DeleteFileTool,
)
from src.agent.tools.web_tools import WebSearchTool, FetchWebpageTool
from src.agent.tools.trending_tools import BaiduTrendingTool, TrendingNewsAggregatorTool
from src.agent.tools.analysis_tools import (
    DocumentAnalysisTool,
    SummarizeTool,
    GenerateReportTool,
)

from src.core.vector_store import VectorStore
from src.services.rag_assistant import RAGAssistant
from src.services.conversation_manager import ConversationManager
from src.models.schemas import ConversationMessage


class RAGAgent(BaseAgent):
    """RAG 智能体

    将 RAG 检索能力与 Agent 自主决策结合，具备：
    - 自主判断是否需要查询知识库
    - 多步骤推理和规划
    - 自动纠错和反思
    - 多工具协调使用

    示例用法:
        agent = RAGAgent()
        result = agent.run("帮我分析知识库的文档结构，并提出优化建议")
    """

    def __init__(
        self,
        config: AgentConfig = None,
        vector_store: VectorStore = None,
        assistant: RAGAssistant = None,
        enable_web_search: bool = True,
        enable_file_ops: bool = True,
        web_search_provider: str = "duckduckgo",
        conversation_manager: ConversationManager = None,
    ):
        """初始化 RAG Agent

        Args:
            config: Agent 配置
            vector_store: 向量数据库实例
            assistant: RAG 助手实例
            enable_web_search: 是否启用网页搜索
            enable_file_ops: 是否启用文件操作
            web_search_provider: 搜索提供者 ('duckduckgo', 'tavily', 'serpapi')
            conversation_manager: 对话管理器实例（可选）
        """
        self._vector_store = vector_store
        self._assistant = assistant
        self._enable_web_search = enable_web_search
        self._enable_file_ops = enable_file_ops
        self._web_search_provider = web_search_provider
        
        # 对话管理
        self._conversation_manager = conversation_manager or ConversationManager()
        self._current_conversation_id: Optional[str] = None

        super().__init__(config)
        self.setup_tools()

    def setup_tools(self):
        """设置 Agent 可用的工具"""

        # 1. RAG 检索工具（核心能力）
        rag_search = RAGSearchTool(
            vector_store=self._vector_store, assistant=self._assistant
        )
        self.register_tool(rag_search)

        # 2. 文档列表工具
        doc_list = DocumentListTool()
        self.register_tool(doc_list)

        # 3. 知识库信息工具
        kb_info = KnowledgeBaseInfoTool(vector_store=self._vector_store)
        self.register_tool(kb_info)

        # 4. 文件操作工具
        if self._enable_file_ops:
            import os
            from pathlib import Path
            
            # 定义允许的文件操作路径
            home_dir = str(Path.home())
            desktop_dir = str(Path.home() / "Desktop")
            documents_dir = str(Path.home() / "Documents")
            allowed_paths = [
                "./documents",
                "./uploads", 
                "./output",
                home_dir,
                desktop_dir,
                documents_dir
            ]
            
            self.register_tool(ReadFileTool(allowed_paths=allowed_paths))
            self.register_tool(WriteFileTool(allowed_paths=allowed_paths))
            self.register_tool(ListDirectoryTool(allowed_paths=allowed_paths))
            self.register_tool(MoveFileTool(allowed_paths=allowed_paths))
            self.register_tool(CreateDirectoryTool(allowed_paths=allowed_paths))
            self.register_tool(DeleteFileTool(allowed_paths=allowed_paths))

        # 5. 网页搜索工具
        if self._enable_web_search:
            web_search = WebSearchTool(provider=self._web_search_provider)
            self.register_tool(web_search)
            self.register_tool(FetchWebpageTool())
            
            # 添加热搜工具
            self.register_tool(BaiduTrendingTool())
            self.register_tool(TrendingNewsAggregatorTool())

        # 6. 分析工具
        self.register_tool(DocumentAnalysisTool())
        self.register_tool(SummarizeTool())
        self.register_tool(GenerateReportTool())

        if self.config.verbose:
            print(f"\n✓ RAG Agent 初始化完成，共注册 {len(self.tools)} 个工具")

    def start_conversation(self) -> str:
        """开始新的对话会话
        
        Returns:
            会话ID
        """
        self._current_conversation_id = self._conversation_manager.create_conversation()
        return self._current_conversation_id
    
    def set_conversation(self, conversation_id: str):
        """设置当前会话ID
        
        Args:
            conversation_id: 会话ID
        """
        self._current_conversation_id = conversation_id
    
    def get_conversation_history(self, max_messages: Optional[int] = None) -> List[ConversationMessage]:
        """获取当前会话的历史消息
        
        Args:
            max_messages: 最多返回的消息数量
            
        Returns:
            消息列表
        """
        if not self._current_conversation_id:
            return []
        return self._conversation_manager.get_history(
            self._current_conversation_id, 
            max_messages=max_messages
        )
    
    def clear_conversation(self):
        """清空当前会话的历史"""
        if self._current_conversation_id:
            self._conversation_manager.clear_conversation(self._current_conversation_id)

    def smart_query(self, question: str, save_to_history: bool = True) -> AgentResponse:
        """智能查询 - 自动判断最佳处理方式

        根据问题类型自动选择：
        1. 简单问题：直接 RAG 检索
        2. 复杂问题：使用 Agent 推理
        3. 需要最新信息：结合网页搜索

        Args:
            question: 用户问题
            save_to_history: 是否保存到对话历史

        Returns:
            AgentResponse
        """
        # 保存用户消息到历史
        if save_to_history and self._current_conversation_id:
            self._conversation_manager.add_message(
                self._current_conversation_id, "user", question
            )
        
        # 简单问题检测（可以直接 RAG 回答）
        simple_indicators = ["是什么", "什么是", "怎么用", "如何", "为什么"]
        complex_indicators = [
            "分析",
            "对比",
            "总结",
            "生成",
            "创建",
            "修改",
            "帮我",
            "整理",
        ]

        is_complex = any(ind in question for ind in complex_indicators)

        if not is_complex:
            # 尝试直接 RAG 检索
            rag_tool = self.tools.get("rag_search")
            if rag_tool:
                result = rag_tool.execute(query=question, generate_answer=True, top_k=5)
                if result.success and result.output:
                    response = AgentResponse(
                        success=True,
                        answer=result.output,
                        thought_process=[],
                        tools_used=["rag_search"],
                        iterations=1,
                    )
                    
                    # 保存助手回复到历史
                    if save_to_history and self._current_conversation_id:
                        self._conversation_manager.add_message(
                            self._current_conversation_id, "assistant", result.output
                        )
                    
                    return response

        # 复杂问题使用完整 Agent 推理
        response = self.run(question)
        
        # 保存助手回复到历史
        if save_to_history and self._current_conversation_id and response.success:
            self._conversation_manager.add_message(
                self._current_conversation_id, "assistant", response.answer
            )
        
        return response

    def analyze_knowledge_base(self) -> AgentResponse:
        """分析知识库并提供优化建议

        这是一个预定义的复杂任务，展示 Agent 的能力
        """
        task = """请帮我完成以下任务：
1. 首先列出知识库中的所有文档
2. 分析文档的目录结构
3. 检查是否有组织不合理的地方
4. 生成一份优化建议报告

请详细说明你的分析过程和建议。"""

        return self.run(task)

    def reorganize_documents(self, strategy: str = "topic") -> AgentResponse:
        """重新组织文档结构

        Args:
            strategy: 组织策略 ('topic'按主题, 'type'按类型, 'date'按日期)
        """
        task = f"""请帮我重新组织知识库的文档结构，使用"{strategy}"策略：

1. 首先分析现有的文档结构
2. 根据文档内容识别合适的分类
3. 创建新的目录结构
4. 将文档移动到对应目录
5. 生成一份重组报告

注意：在执行文件操作前，请先告诉我你的计划，等我确认后再执行。"""

        return self.run(task)

    def research_topic(self, topic: str, use_web: bool = True) -> AgentResponse:
        """研究某个主题

        结合本地知识库和网络资源进行深度研究

        Args:
            topic: 研究主题
            use_web: 是否使用网络搜索
        """
        task = f"""请帮我研究以下主题："{topic}"

研究步骤：
1. 首先在本地知识库中搜索相关内容
2. {"如果本地信息不足，使用网页搜索获取更多信息" if use_web else "仅使用本地知识库"}
3. 综合所有信息，生成一份详细的研究报告

报告应包含：
- 主题概述
- 核心要点
- 详细分析
- 参考来源"""

        return self.run(task)


class AgentBuilder:
    """Agent 构建器 - 便捷创建不同配置的 Agent"""

    @staticmethod
    def create_simple_agent() -> RAGAgent:
        """创建简单 Agent（仅 RAG 能力）"""
        config = AgentConfig(
            max_iterations=5,
            enable_reflection=False,
            enable_planning=False,
            verbose=False,
        )
        return RAGAgent(config=config, enable_web_search=False, enable_file_ops=False)

    @staticmethod
    def create_full_agent() -> RAGAgent:
        """创建完整 Agent（所有能力）"""
        config = AgentConfig(
            max_iterations=10,
            enable_reflection=True,
            enable_planning=True,
            verbose=True,
        )
        return RAGAgent(config=config, enable_web_search=True, enable_file_ops=True)

    @staticmethod
    def create_research_agent(web_provider: str = "tavily") -> RAGAgent:
        """创建研究型 Agent（强化网络搜索）"""
        config = AgentConfig(
            max_iterations=15,
            enable_reflection=True,
            enable_planning=True,
            verbose=True,
        )
        return RAGAgent(
            config=config,
            enable_web_search=True,
            enable_file_ops=False,
            web_search_provider=web_provider,
        )

    @staticmethod
    def create_manager_agent() -> RAGAgent:
        """创建管理型 Agent（强化文件操作）"""
        config = AgentConfig(
            max_iterations=10,
            enable_reflection=True,
            enable_planning=True,
            verbose=True,
        )
        return RAGAgent(config=config, enable_web_search=False, enable_file_ops=True)
