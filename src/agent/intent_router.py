"""智能意图路由器 - 让大模型分析问题并决定使用什么工具

这个模块实现了一个智能意图识别系统：
1. 大模型先分析用户的问题
2. 判断问题的类型和意图
3. 决定使用什么工具（知识库/联网搜索/直接回答）
4. 然后执行相应的处理流程
"""

import json
import logging
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from enum import Enum

from src.config.settings import Config


logger = logging.getLogger(__name__)


class IntentType(Enum):
    """意图类型枚举"""
    KNOWLEDGE_BASE = "knowledge_base"     # 需要查询知识库
    WEB_SEARCH = "web_search"             # 需要联网搜索
    DIRECT_ANSWER = "direct_answer"       # 大模型直接回答
    CONVERSATION = "conversation"          # 涉及历史对话
    FILE_OPERATION = "file_operation"     # 文件操作
    MULTI_STEP = "multi_step"             # 复杂多步骤任务
    TRENDING = "trending"                  # 热搜/趋势查询


@dataclass
class IntentAnalysis:
    """意图分析结果"""
    intent: IntentType
    confidence: float           # 置信度 0-1
    reasoning: str              # 分析理由
    suggested_tools: List[str]  # 建议使用的工具
    sub_questions: List[str]    # 分解的子问题（如果是复杂问题）
    needs_realtime: bool        # 是否需要实时信息
    topic_keywords: List[str]   # 问题的关键词


class IntentRouter:
    """智能意图路由器
    
    使用大模型分析用户问题，决定最佳处理方式
    """
    
    INTENT_ANALYSIS_PROMPT = """你是一个智能问题分析助手。你的任务是分析用户的问题，判断应该如何处理。

【当前信息】
当前日期: {current_date}
可用工具: {available_tools}

【历史对话】
{chat_history}

【用户问题】
{question}

请分析这个问题并返回 JSON 格式的结果：

```json
{{
    "intent": "意图类型",
    "confidence": 0.9,
    "reasoning": "分析理由",
    "suggested_tools": ["建议的工具列表"],
    "sub_questions": ["如果是复杂问题，分解成子问题"],
    "needs_realtime": true/false,
    "topic_keywords": ["问题关键词"]
}}
```

【意图类型说明】
- "knowledge_base": 用户问的是专业知识、概念解释、教程内容等，需要查询本地知识库
- "web_search": 用户问的是实时信息（天气、新闻、股价、最新事件等）或需要最新数据
- "direct_answer": 用户问的是常识问题、简单计算、代码问题等，你可以直接回答
- "conversation": 用户问的涉及之前的对话（如"刚才说的是什么"、"上个问题"）
- "file_operation": 用户需要读取、创建、修改、移动文件
- "multi_step": 复杂任务需要多步骤完成（如"分析文档并生成报告"）
- "trending": 用户想了解热搜、热门话题、趋势

【判断原则】
1. 如果问题包含"今天"、"现在"、"最新"、"实时"等时间词汇，且涉及天气、新闻、股价等变化信息 → web_search
2. 如果问题是关于某个专业概念、技术知识、文档内容 → knowledge_base  
3. 如果问题是简单的问候、常识、数学计算、代码编写 → direct_answer
4. 如果问题涉及"刚才"、"之前"、"上一个" → conversation
5. 如果问题需要创建/读取/修改文件 → file_operation
6. 如果问题需要多步骤完成（分析+总结+生成等） → multi_step
7. 如果问题涉及热搜、热点、趋势 → trending

【重要提醒】
- 你只需要分析问题，不需要回答问题
- 请严格输出 JSON 格式，不要有其他内容
- confidence 应该反映你对判断的确信程度

请开始分析："""

    def __init__(self, available_tools: List[str] = None):
        """初始化意图路由器
        
        Args:
            available_tools: 可用工具列表
        """
        self.available_tools = available_tools or []
        self.llm = self._init_llm()
        
    def _init_llm(self):
        """初始化 LLM"""
        if Config.MODEL_PROVIDER == "ollama":
            from langchain_community.llms import Ollama
            return Ollama(
                base_url=Config.OLLAMA_API_URL,
                model=Config.OLLAMA_MODEL,
                temperature=0.1,  # 低温度以获得更确定的分析
            )
        elif Config.MODEL_PROVIDER == "deepseek":
            from langchain_deepseek import ChatDeepSeek
            return ChatDeepSeek(
                model=Config.LLM_MODEL,
                temperature=0.1,
                api_key=Config.DEEPSEEK_API_KEY,
            )
        else:
            from langchain.chat_models import init_chat_model
            return init_chat_model(
                Config.LLM_MODEL,
                temperature=0.1,
                model_provider=Config.MODEL_PROVIDER,
            )
    
    def analyze_intent(
        self, 
        question: str, 
        chat_history: str = "",
        current_date: str = ""
    ) -> IntentAnalysis:
        """分析用户问题的意图
        
        Args:
            question: 用户问题
            chat_history: 历史对话
            current_date: 当前日期
            
        Returns:
            IntentAnalysis 意图分析结果
        """
        import pytz
        from datetime import datetime
        
        if not current_date:
            tz = pytz.timezone('Asia/Shanghai')
            current_date = datetime.now(tz).strftime("%Y年%m月%d日 %H:%M:%S")
        
        # 构建提示词
        prompt = self.INTENT_ANALYSIS_PROMPT.format(
            current_date=current_date,
            available_tools=", ".join(self.available_tools) if self.available_tools else "rag_search, web_search, 文件操作工具",
            chat_history=chat_history or "无历史对话",
            question=question
        )
        
        try:
            # 调用大模型分析
            logger.info(f"[IntentRouter] 分析问题意图: {question[:50]}...")
            response = self.llm.invoke(prompt)
            
            if isinstance(response, str):
                result_text = response
            else:
                result_text = response.content if hasattr(response, 'content') else str(response)
            
            # 解析 JSON 结果
            analysis = self._parse_analysis_result(result_text)
            logger.info(f"[IntentRouter] 意图分析完成: {analysis.intent.value}, 置信度: {analysis.confidence}")
            
            return analysis
            
        except Exception as e:
            logger.error(f"[IntentRouter] 意图分析失败: {e}")
            # 返回默认分析结果
            return IntentAnalysis(
                intent=IntentType.MULTI_STEP,  # 默认使用完整Agent流程
                confidence=0.5,
                reasoning=f"意图分析失败，使用默认Agent流程: {str(e)}",
                suggested_tools=["rag_search"],
                sub_questions=[question],
                needs_realtime=False,
                topic_keywords=[]
            )
    
    def _parse_analysis_result(self, result_text: str) -> IntentAnalysis:
        """解析大模型返回的分析结果
        
        Args:
            result_text: 大模型返回的文本
            
        Returns:
            IntentAnalysis 对象
        """
        import re
        
        # 尝试提取 JSON
        json_match = re.search(r'```json\s*([\s\S]*?)\s*```', result_text)
        if json_match:
            json_str = json_match.group(1)
        else:
            # 尝试直接解析
            json_match = re.search(r'\{[\s\S]*\}', result_text)
            if json_match:
                json_str = json_match.group(0)
            else:
                raise ValueError("无法从响应中提取 JSON")
        
        try:
            data = json.loads(json_str)
        except json.JSONDecodeError as e:
            logger.warning(f"JSON 解析失败: {e}")
            raise
        
        # 解析意图类型
        intent_str = data.get("intent", "multi_step")
        intent_map = {
            "knowledge_base": IntentType.KNOWLEDGE_BASE,
            "web_search": IntentType.WEB_SEARCH,
            "direct_answer": IntentType.DIRECT_ANSWER,
            "conversation": IntentType.CONVERSATION,
            "file_operation": IntentType.FILE_OPERATION,
            "multi_step": IntentType.MULTI_STEP,
            "trending": IntentType.TRENDING,
        }
        intent = intent_map.get(intent_str, IntentType.MULTI_STEP)
        
        return IntentAnalysis(
            intent=intent,
            confidence=float(data.get("confidence", 0.5)),
            reasoning=data.get("reasoning", ""),
            suggested_tools=data.get("suggested_tools", []),
            sub_questions=data.get("sub_questions", []),
            needs_realtime=data.get("needs_realtime", False),
            topic_keywords=data.get("topic_keywords", [])
        )
    
    def get_routing_decision(self, analysis: IntentAnalysis) -> Dict[str, Any]:
        """根据意图分析结果，返回路由决策
        
        Args:
            analysis: 意图分析结果
            
        Returns:
            路由决策字典
        """
        decision = {
            "use_agent": True,  # 是否使用完整Agent流程
            "primary_tool": None,  # 主要工具
            "skip_rag": False,  # 是否跳过RAG
            "skip_web": False,  # 是否跳过网页搜索
            "direct_llm": False,  # 是否直接使用LLM回答
            "priority_tools": [],  # 优先使用的工具列表
        }
        
        if analysis.intent == IntentType.KNOWLEDGE_BASE:
            decision["use_agent"] = False  # 简单RAG查询不需要完整Agent
            decision["primary_tool"] = "rag_search"
            decision["skip_web"] = True
            decision["priority_tools"] = ["rag_search"]
            
        elif analysis.intent == IntentType.WEB_SEARCH:
            decision["use_agent"] = True
            decision["primary_tool"] = "web_search"
            decision["skip_rag"] = True
            decision["priority_tools"] = ["web_search", "fetch_webpage"]
            
        elif analysis.intent == IntentType.DIRECT_ANSWER:
            decision["use_agent"] = False
            decision["direct_llm"] = True
            decision["skip_rag"] = True
            decision["skip_web"] = True
            
        elif analysis.intent == IntentType.CONVERSATION:
            decision["use_agent"] = False  # 从历史对话直接回答
            decision["skip_rag"] = True
            decision["skip_web"] = True
            
        elif analysis.intent == IntentType.FILE_OPERATION:
            decision["use_agent"] = True
            decision["primary_tool"] = "file_tools"
            decision["skip_rag"] = True
            decision["skip_web"] = True
            decision["priority_tools"] = [
                "read_file", "write_file", "list_directory", 
                "move_file", "create_directory", "delete_file"
            ]
            
        elif analysis.intent == IntentType.TRENDING:
            decision["use_agent"] = True
            decision["primary_tool"] = "trending"
            decision["skip_rag"] = True
            decision["priority_tools"] = ["baidu_trending", "trending_news", "web_search"]
            
        elif analysis.intent == IntentType.MULTI_STEP:
            decision["use_agent"] = True
            decision["priority_tools"] = analysis.suggested_tools
        
        return decision
