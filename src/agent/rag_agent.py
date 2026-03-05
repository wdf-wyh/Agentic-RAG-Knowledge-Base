"""RAG Agent - 具备自主决策能力的 RAG 智能体"""

import logging
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
from src.agent.intent_router import IntentRouter, IntentType, IntentAnalysis

logger = logging.getLogger(__name__)

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
        
        # 智能意图路由器（在 setup_tools 后初始化）
        self._intent_router: Optional[IntentRouter] = None

        super().__init__(config)
        self.setup_tools()
        
        # 初始化意图路由器（在工具注册后）
        self._intent_router = IntentRouter(
            available_tools=list(self.tools.keys())
        )

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
        
        # 7. 新增企业级工具
        try:
            from src.agent.tools.memory_tools import MemoryTool
            self.register_tool(MemoryTool())
        except ImportError:
            pass
        
        try:
            from src.agent.tools.task_tools import TaskTool
            self.register_tool(TaskTool())
        except ImportError:
            pass
        
        try:
            from src.agent.tools.code_tools import CodeExecutorTool, DataAnalysisTool
            self.register_tool(CodeExecutorTool(sandbox_mode=True))
            self.register_tool(DataAnalysisTool())
        except ImportError:
            pass

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
        """智能查询 - 使用大模型分析问题并决定最佳处理方式

        核心流程：
        1. 调用大模型分析用户问题的意图
        2. 根据意图决定使用什么工具（知识库/联网搜索/直接回答等）
        3. 执行相应的处理流程

        Args:
            question: 用户问题
            save_to_history: 是否保存到对话历史

        Returns:
            AgentResponse
        """
        import pytz
        from datetime import datetime
        
        # 保存用户消息到历史
        if save_to_history and self._current_conversation_id:
            self._conversation_manager.add_message(
                self._current_conversation_id, "user", question
            )
        
        # 获取对话历史
        chat_history = ""
        if self._current_conversation_id:
            chat_history = self._conversation_manager.format_history_for_llm(
                self._current_conversation_id,
                max_turns=5
            )
        
        # 获取当前时间
        tz = pytz.timezone('Asia/Shanghai')
        current_date = datetime.now(tz).strftime("%Y年%m月%d日 %H:%M:%S")
        
        # 第一步：使用大模型分析问题意图
        logger.info(f"[SmartQuery] 开始分析问题意图: {question[:50]}...")
        
        if self._intent_router:
            analysis = self._intent_router.analyze_intent(
                question=question,
                chat_history=chat_history,
                current_date=current_date
            )
            
            if self.config.verbose:
                print(f"\n🧠 意图分析结果:")
                print(f"   意图类型: {analysis.intent.value}")
                print(f"   置信度: {analysis.confidence:.2f}")
                print(f"   分析理由: {analysis.reasoning}")
                print(f"   建议工具: {analysis.suggested_tools}")
            
            logger.info(f"[SmartQuery] 意图: {analysis.intent.value}, 置信度: {analysis.confidence}")
            
            # 第二步：根据意图决定处理方式
            routing = self._intent_router.get_routing_decision(analysis)
            
            # 处理直接对话/历史问题
            if analysis.intent == IntentType.CONVERSATION:
                # 直接从历史对话中回答
                response = self._handle_conversation_intent(question, chat_history, analysis)
                if save_to_history and self._current_conversation_id and response.success:
                    self._conversation_manager.add_message(
                        self._current_conversation_id, "assistant", response.answer
                    )
                return response
            
            # 处理直接回答（常识、简单计算等）
            if analysis.intent == IntentType.DIRECT_ANSWER:
                response = self._handle_direct_answer(question, analysis)
                if save_to_history and self._current_conversation_id and response.success:
                    self._conversation_manager.add_message(
                        self._current_conversation_id, "assistant", response.answer
                    )
                return response
            
            # 处理知识库查询（简单RAG）
            if analysis.intent == IntentType.KNOWLEDGE_BASE and analysis.confidence >= 0.8:
                rag_tool = self.tools.get("rag_search")
                if rag_tool:
                    # 只检索文档，不触发 RAGAssistant 内部的 LLM
                    result = rag_tool.execute(query=question, generate_answer=False, top_k=5)
                    if result.success and result.data:
                        # 拼出上下文，用 Agent 自己的 LLM 生成答案
                        docs = result.data
                        context_parts = []
                        for i, d in enumerate(docs[:5], 1):
                            if hasattr(d, 'page_content'):
                                context_parts.append(f"[{i}] {d.page_content}")
                            elif isinstance(d, dict):
                                context_parts.append(f"[{i}] {d.get('content', str(d))}")
                        context = "\n\n".join(context_parts)
                        rag_prompt = (
                            f"请严格根据以下上下文回答问题，不要使用上下文以外的知识。\n\n"
                            f"【上下文】\n{context}\n\n"
                            f"【问题】\n{question}\n\n"
                            f"如果上下文中没有足够信息，请如实说明。"
                        )
                        llm_resp = self.llm.invoke(rag_prompt)
                        answer = llm_resp.content if hasattr(llm_resp, 'content') else str(llm_resp)
                        # 附上来源
                        sources = []
                        for d in docs[:5]:
                            if hasattr(d, 'metadata'):
                                sources.append(d.metadata.get('source', '未知'))
                            elif isinstance(d, dict):
                                sources.append(d.get('source', '未知'))
                        if sources:
                            answer += "\n\n**参考来源**: " + "、".join(dict.fromkeys(sources))
                        response = AgentResponse(
                            success=True,
                            answer=answer,
                            thought_process=[],
                            tools_used=["rag_search"],
                            iterations=1,
                        )
                        if save_to_history and self._current_conversation_id:
                            self._conversation_manager.add_message(
                                self._current_conversation_id, "assistant", answer
                            )
                        return response
        
        # 第三步：复杂问题使用完整 Agent 推理
        logger.info(f"[SmartQuery] 使用完整Agent推理流程")
        response = self.run(question, chat_history)
        
        # 保存助手回复到历史
        if save_to_history and self._current_conversation_id and response.success:
            self._conversation_manager.add_message(
                self._current_conversation_id, "assistant", response.answer
            )
        
        return response

    def smart_query_stream(self, question: str, save_to_history: bool = True):
        """流式智能查询 - 意图路由 + 流式输出答案 token

        与 smart_query 相同的意图路由逻辑，但对 LLM 回答使用流式输出。

        Args:
            question: 用户问题
            save_to_history: 是否保存到对话历史

        Yields:
            StreamEvent 事件
        """
        import pytz
        from datetime import datetime
        from src.agent.base import StreamEvent

        # 保存用户消息到历史
        if save_to_history and self._current_conversation_id:
            self._conversation_manager.add_message(
                self._current_conversation_id, "user", question
            )

        # 获取对话历史
        chat_history = ""
        if self._current_conversation_id:
            chat_history = self._conversation_manager.format_history_for_llm(
                self._current_conversation_id, max_turns=5
            )

        # 获取当前时间
        tz = pytz.timezone('Asia/Shanghai')
        current_date = datetime.now(tz).strftime("%Y年%m月%d日 %H:%M:%S")

        yield StreamEvent(type='start', data='正在分析问题意图...')

        if self._intent_router:
            analysis = self._intent_router.analyze_intent(
                question=question,
                chat_history=chat_history,
                current_date=current_date
            )
            logger.info(f"[SmartStream] 意图: {analysis.intent.value}, 置信度: {analysis.confidence}")

            yield StreamEvent(type='intent', data={
                'intent': analysis.intent.value,
                'confidence': analysis.confidence,
                'reasoning': analysis.reasoning,
            })

            # 直接回答（常识/计算/代码等）
            if analysis.intent == IntentType.DIRECT_ANSWER:
                prompt = (
                    f"请回答以下问题。这是一个可以直接回答的问题（常识/计算/代码等）。\n\n"
                    f"【问题】\n{question}\n\n请给出准确、简洁的答案。"
                )
                yield StreamEvent(type='answer_start')
                full_answer = ""
                for chunk in self.llm_streaming.stream(prompt):
                    token = chunk.content if hasattr(chunk, 'content') else str(chunk)
                    if token:
                        full_answer += token
                        yield StreamEvent(type='answer_token', data=token)
                yield StreamEvent(type='answer', data=full_answer)
                yield StreamEvent(type='done', data={'tools_used': [], 'iterations': 1})
                if save_to_history and self._current_conversation_id and full_answer:
                    self._conversation_manager.add_message(
                        self._current_conversation_id, "assistant", full_answer
                    )
                return

            # 历史对话意图
            if analysis.intent == IntentType.CONVERSATION:
                prompt = (
                    f"请基于以下历史对话，回答用户的问题。\n\n"
                    f"【历史对话】\n{chat_history}\n\n"
                    f"【用户问题】\n{question}\n\n"
                    f"请直接给出答案，如果历史对话中没有相关信息，请诚实说明。"
                )
                yield StreamEvent(type='answer_start')
                full_answer = ""
                for chunk in self.llm_streaming.stream(prompt):
                    token = chunk.content if hasattr(chunk, 'content') else str(chunk)
                    if token:
                        full_answer += token
                        yield StreamEvent(type='answer_token', data=token)
                final = full_answer + "\n\n来源: 对话历史"
                yield StreamEvent(type='answer', data=final)
                yield StreamEvent(type='done', data={'tools_used': [], 'iterations': 1})
                if save_to_history and self._current_conversation_id and full_answer:
                    self._conversation_manager.add_message(
                        self._current_conversation_id, "assistant", final
                    )
                return

            # 知识库查询
            if analysis.intent == IntentType.KNOWLEDGE_BASE and analysis.confidence >= 0.8:
                rag_tool = self.tools.get("rag_search")
                if rag_tool:
                    yield StreamEvent(type='action', data={'tool': 'rag_search', 'input': question})
                    # 只检索文档，不触发 RAGAssistant 内部的 LLM
                    result = rag_tool.execute(query=question, generate_answer=False, top_k=5)
                    if result.success and result.data:
                        yield StreamEvent(type='observation', data={'text': '已检索到相关内容', 'data': None})
                        docs = result.data
                        context_parts = []
                        for i, d in enumerate(docs[:5], 1):
                            if hasattr(d, 'page_content'):
                                context_parts.append(f'[{i}] {d.page_content}')
                            elif isinstance(d, dict):
                                context_parts.append(f'[{i}] {d.get("content", str(d))}')
                        context = '\n\n'.join(context_parts)
                        rag_prompt = (
                            f'请严格根据以下上下文回答问题，不要使用上下文以外的知识。\n\n'
                            f'【上下文】\n{context}\n\n'
                            f'【问题】\n{question}\n\n'
                            f'如果上下文中没有足够信息，请如实说明。'
                        )
                        # 用 Agent 自身的流式 LLM 生成答案
                        sources = []
                        for d in docs[:5]:
                            if hasattr(d, 'metadata'):
                                sources.append(d.metadata.get('source', '未知'))
                            elif isinstance(d, dict):
                                sources.append(d.get('source', '未知'))
                        yield StreamEvent(type='answer_start')
                        full_answer = ''
                        for chunk in self.llm_streaming.stream(rag_prompt):
                            token = chunk.content if hasattr(chunk, 'content') else str(chunk)
                            if token:
                                full_answer += token
                                yield StreamEvent(type='answer_token', data=token)
                        if sources:
                            suffix = '\n\n**参考来源**: ' + '、'.join(dict.fromkeys(sources))
                            full_answer += suffix
                            yield StreamEvent(type='answer_token', data=suffix)
                        yield StreamEvent(type='answer', data=full_answer)
                        yield StreamEvent(type='done', data={'tools_used': ['rag_search'], 'iterations': 1})
                        if save_to_history and self._current_conversation_id:
                            self._conversation_manager.add_message(
                                self._current_conversation_id, 'assistant', full_answer
                            )
                        return

        # 复杂问题：使用完整流式 Agent 推理
        logger.info(f"[SmartStream] 使用完整Agent流式推理")
        final_answer = ""
        for event in self.run_stream(question, chat_history):
            if event.type == 'answer':
                final_answer = event.data
            yield event

        if save_to_history and self._current_conversation_id and final_answer:
            self._conversation_manager.add_message(
                self._current_conversation_id, "assistant", final_answer
            )

    def _handle_conversation_intent(
        self, 
        question: str, 
        chat_history: str,
        analysis: IntentAnalysis
    ) -> AgentResponse:
        """处理涉及历史对话的问题
        
        Args:
            question: 用户问题
            chat_history: 历史对话
            analysis: 意图分析结果
            
        Returns:
            AgentResponse
        """
        # 使用大模型从历史对话中生成回答
        prompt = f"""请基于以下历史对话，回答用户的问题。

【历史对话】
{chat_history}

【用户问题】
{question}

请直接给出答案，如果历史对话中没有相关信息，请诚实说明。"""

        try:
            response = self.llm.invoke(prompt)
            if isinstance(response, str):
                answer = response
            else:
                answer = response.content if hasattr(response, 'content') else str(response)
            
            return AgentResponse(
                success=True,
                answer=answer + "\n\n来源: 对话历史",
                thought_process=[],
                tools_used=[],
                iterations=1,
            )
        except Exception as e:
            logger.error(f"处理对话意图失败: {e}")
            return AgentResponse(
                success=False,
                answer=f"处理问题时出错: {str(e)}",
                thought_process=[],
                tools_used=[],
                iterations=0,
            )
    
    def _handle_direct_answer(
        self, 
        question: str,
        analysis: IntentAnalysis
    ) -> AgentResponse:
        """处理可以直接回答的问题（常识、计算等）
        
        Args:
            question: 用户问题
            analysis: 意图分析结果
            
        Returns:
            AgentResponse
        """
        prompt = f"""请回答以下问题。这是一个可以直接回答的问题（常识/计算/代码等）。

【问题】
{question}

请给出准确、简洁的答案。"""

        try:
            response = self.llm.invoke(prompt)
            if isinstance(response, str):
                answer = response
            else:
                answer = response.content if hasattr(response, 'content') else str(response)
            
            return AgentResponse(
                success=True,
                answer=answer,
                thought_process=[],
                tools_used=[],
                iterations=1,
            )
        except Exception as e:
            logger.error(f"直接回答失败: {e}")
            return AgentResponse(
                success=False,
                answer=f"处理问题时出错: {str(e)}",
                thought_process=[],
                tools_used=[],
                iterations=0,
            )

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
