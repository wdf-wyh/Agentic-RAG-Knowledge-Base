"""Agent 基础架构 - ReAct 推理框架实现"""

import json
import re
import logging
import time
from typing import List, Dict, Any, Optional, Callable, Generator, AsyncGenerator
from dataclasses import dataclass, field
from enum import Enum
from abc import ABC, abstractmethod
from datetime import datetime
import pytz

from src.config.settings import Config

# 是 Python 的 dataclasses 模块中的装饰器，用于自动生成数据类的常用方法（
# 如 __init__、__repr__、__eq__ 等）。它简化了类的定义，使代码更简洁。无需手动编写初始化方法。


@dataclass
class StreamEvent:
    """流式事件"""

    type: str  # 'thinking', 'action', 'observation', 'answer', 'token', 'error', 'done'
    data: Any = None
    step: int = 0


# StreamEvent 是一个数据类，用于表示 Agent 流式推理过程中的实时事件。主要作用包括：

# type: 事件类型，如 'thinking'（思考）、'action'（行动）、'observation'（观察）、'answer'（答案）、'error'（错误）、'done'（完成）。
# data: 事件数据，包含具体内容（如思考内容、工具输入、观察结果）。
# step: 当前推理步骤编号。
# 它在 run_stream 方法中用于生成器，实时推送推理过程给客户端。


# 配置日志
logger = logging.getLogger(__name__)
# 获取当前模块（base.py）的日志记录器实例，使用 __name__ 确保每个模块有独立的记录器。
logger.setLevel(logging.INFO)
#  设置日志级别为 INFO，表示记录 INFO、WARNING、ERROR、CRITICAL 级别的日志，而忽略 DEBUG 级别


class AgentState(Enum):
    """Agent 状态枚举"""

    IDLE = "idle"
    THINKING = "thinking"
    ACTING = "acting"
    REFLECTING = "reflecting"
    COMPLETED = "completed"
    ERROR = "error"


# AgentState 是一个枚举类，用于表示 Agent 在推理过程中的不同状态。主要状态包括：

# IDLE: 空闲状态。
# THINKING: 正在思考和推理。
# ACTING: 正在执行工具动作。
# REFLECTING: 正在进行反思检查。
# COMPLETED: 执行完成。
# ERROR: 发生错误。
# 它在 BaseAgent 类中用于跟踪和更新 Agent 的当前状态，便于监控和调试推理流程。


@dataclass
class AgentConfig:
    """Agent 配置"""

    max_iterations: int = 5  # 最大推理迭代次数（优化：从10降到5以加快响应）
    temperature: float = 0.7
    enable_reflection: bool = False  # 启用反思机制（优化：关闭以加快响应）
    enable_planning: bool = True  # 启用规划能力
    verbose: bool = True  # 详细输出
    llm_timeout: int = 30  # LLM请求超时时间（秒）


@dataclass
class ThoughtStep:
    """思考步骤记录"""

    step: int
    thought: str
    action: Optional[str] = None
    action_input: Optional[Dict[str, Any]] = None
    observation: Optional[str] = None
    observation_data: Optional[Dict[str, Any]] = (
        None  # 结构化数据（如工具返回的列表数据）
    )
    reflection: Optional[str] = None


# ThoughtStep 是一个数据类，用于记录 Agent 在推理过程中的每个思考步骤。主要字段包括：


# step: 步骤编号（整数）。
# thought: 思考内容（字符串）。
# action: 执行的工具名称（可选）。
# action_input: 工具输入参数（可选字典）。
# observation: 观察结果（可选字符串）。
# observation_data: 结构化数据（如工具返回的列表数据，可选字典）。
# reflection: 反思内容（可选字符串）。
# 它在 BaseAgent 的推理循环中用于跟踪和记录每个迭代步骤，便于调试和输出推理过程
@dataclass
class AgentResponse:
    """Agent 响应结果"""

    success: bool
    answer: str
    thought_process: List[ThoughtStep] = field(default_factory=list)
    tools_used: List[str] = field(default_factory=list)
    iterations: int = 0
    final_reflection: Optional[str] = None


# AgentResponse 是一个数据类，用于封装 Agent 运行后的响应结果。主要字段包括：

# success: 是否成功（布尔值）。
# answer: 最终答案（字符串）。
# thought_process: 推理过程中的思考步骤列表（List[ThoughtStep]）。
# tools_used: 使用的工具列表（List[str]）。
# iterations: 推理迭代次数（整数）。
# final_reflection: 最终反思内容（可选字符串）。
# 它在 run 和 run_stream 方法中作为返回值，用于返回完整的推理结果。

# BaseAgent 是一个抽象基类（ABC），实现了 ReAct 推理框架的核心逻辑。主要作用包括：

# 推理循环: 执行思考（Thought）、行动（Action）、观察（Observation）的循环过程。
# 工具管理: 注册和执行各种工具（如搜索、计算等）。
# 配置管理: 使用 AgentConfig 控制推理参数（如最大迭代次数、温度等）。
# 流式输出: 支持实时推送推理过程的事件。
# 反思机制: 可选的反思检查，确保回答质量。
# 状态跟踪: 使用 AgentState 枚举跟踪当前状态。
# 它是 RAG Agent 等具体 Agent 类的基类，子类需要实现 setup_tools() 方法来配置特定工具。

# ABC 是 Python 的 abc 模块中的抽象基类（Abstract Base Class）装饰器，用于定义抽象基类。它允许类包含
# 抽象方法（使用 @abstractmethod 装饰），这些方法必须在子类中实现。

# 在 BaseAgent 类中，ABC 确保子类（如 RAGAgent）必须实现 setup_tools() 方法，从而强制接口一致性。

# REACT_PROMPT 是 BaseAgent 类中的提示词模板，用于指导 LLM 进行 ReAct 推理循环。主要作用包括：

# 定义推理格式：指定 Thought -> Action -> Observation 的结构。
# 提供系统信息：包含当前日期、历史对话、可用工具等上下文。
# 设置核心原则：强调必须基于工具结果回答，禁止编造内容。
# 规则约束：如优先检查历史对话、实时信息重新查询、来源引用规则等。
# 输出格式：确保 LLM 按指定格式输出思考、行动和最终答案。
# 它在 run 和 run_stream 方法中被格式化后发送给 LLM，以控制推理过程。


class BaseAgent(ABC):
    """Agent 基类 - 实现 ReAct 推理循环"""

    # ReAct 提示词模板
    REACT_PROMPT = """你是一个知识库助手，具备多种工具和能力。请按照以下格式进行推理和行动：

【系统信息】
当前日期和时间: {current_datetime}

【历史对话上下文】
{chat_history}

【可用工具】
{tools_description}

【核心原则 - 必须严格遵守】
1. **首先检查历史对话**：如果用户问题涉及之前的对话内容（如"我刚才问了什么"、"上一个问题"等），直接从【历史对话上下文】中查找答案，不要使用任何工具
2. **实时信息必须重新查询**：对于天气、新闻、股价等实时信息，即使历史对话中有答案，也必须重新执行 web_search 获取最新数据
3. 对于知识查询问题，优先使用 rag_search 工具查询本地知识库
4. 回答必须且只能基于工具返回的实际结果或历史对话，绝对禁止使用你自己的知识或常识
5. 如果检索结果中没有相关信息，必须明确告知用户"知识库中没有找到相关信息"
6. 绝对禁止编造任何内容，包括来源名称、URL、数据等

【来源引用规则 - 极其重要】
1. 如果回答来自历史对话，标注"来源: 对话历史"
2. 如果使用了 web_search，必须在回答中附上工具返回的真实 URL 链接
3. 如果使用了 rag_search，必须标明来源文件名（从 Observation 中获取）
4. 绝对禁止编造来源名称，如"XX词典"、"XX论坛"等虚假来源
5. 只有在 Observation 中明确出现的 URL 或文件名才能作为来源引用

【重要规则】
1. 你必须严格按照 Thought -> Action -> Observation 的格式输出
2. 如果问题涉及历史对话，无需使用工具，直接输出 Final Answer
3. 每次只能执行一个 Action
4. 根据 Observation 结果决定下一步行动
5. 只有当 Observation 中明确包含答案时，才输出 Final Answer
6. 如果遇到错误，尝试换一种方法
7. **即使历史对话中显示之前查询失败，也要重新执行工具调用获取最新信息**
8. **对于天气、新闻等实时信息，必须使用 web_search 而不是 rag_search**
9. **每次查询都是独立的，不要因为历史中有负面结果就直接回答失败**

【输出格式】
Thought: [你的思考过程，首先检查是否能从历史对话中找到答案]
Action: [工具名称]
Action Input: {{"param1": "value1", "param2": "value2"}}

等待观察结果后继续：
Observation: [工具返回的结果]

Thought: [根据观察结果的进一步思考，必须分析 Observation 是否包含答案]
...

当能从历史对话中直接回答时：
Thought: 这个问题涉及历史对话，我可以从【历史对话上下文】中直接找到答案
Final Answer: [基于历史对话的答案]
来源: 对话历史

当 Observation 中包含明确答案时：
Thought: 我在工具返回的结果中找到了相关信息，可以基于此回答问题
Final Answer: [基于 Observation 的答案]
来源: [从 Observation 中提取的真实 URL 或文件名]

当 Observation 中没有相关信息时：
Thought: 工具返回的结果中没有找到与问题相关的信息
Final Answer: 抱歉，未能找到关于这个问题的相关信息。

【当前任务】
用户问题: {question}

请开始推理（记住：优先检查历史对话，答案和来源必须完全来自历史对话或工具返回的 Observation，禁止编造）："""

    # REFLECTION_PROMPT 是 BaseAgent 类中的反思提示词模板，用于检查 Agent 回答的质量。主要作用包括：

    # 评估回答基础：检查回答是否完全基于工具返回的结果，禁止使用外部知识。
    # 验证来源真实性：确保引用的来源是真实的 URL 链接或文件名，禁止编造来源。
    # 检测编造内容：识别是否存在编造、推测或使用常识的痕迹。
    # 输出格式：如果通过输出 "APPROVED"，否则输出 "RETRY: [建议]"。
    # 它在反思检查中被格式化后发送给 LLM，以确保回答质量和真实性。

    REFLECTION_PROMPT = """请反思以下回答的质量：

问题: {question}
回答: {answer}
使用的工具: {tools_used}

请严格评估：
1. 回答是否完全基于工具返回的结果？（绝不能使用外部知识）
2. 如果引用了来源，这些来源是否是真实的 URL 链接或文件名？
3. 是否存在编造的来源名称（如"XX词典"、"XX论坛"等没有具体 URL 的来源）？
4. 回答内容是否确实在工具返回的 Observation 中出现过？
5. 是否有编造、推测或使用常识的痕迹？

如果回答完全基于工具结果且来源真实，输出: APPROVED
如果发现有编造来源或使用外部知识，输出: RETRY: 来源必须是真实的 URL 或文件名，禁止编造
如果需要其他改进，输出: RETRY: [改进建议]"""

    # PLANNING_PROMPT 是 BaseAgent 类中的规划提示词模板，用于分析复杂任务并制定执行计划。主要作用包括：

    # 任务分析：分析用户任务的复杂性。
    # 工具利用：考虑可用工具来制定计划。
    # 步骤制定：输出分步骤的执行计划，格式如 "Step 1: [具体行动]"。
    # 依赖考虑：考虑步骤之间的依赖关系，优先使用最直接有效的方法。
    # 它在 _create_plan 方法中被格式化后发送给 LLM，以生成任务执行计划。

    PLANNING_PROMPT = """请分析以下复杂任务，并制定执行计划：

任务: {task}

可用工具: {tools}

请输出一个分步骤的执行计划，格式如下：
Step 1: [具体行动]
Step 2: [具体行动]
...

注意：
- 每个步骤应该是可执行的具体行动
- 考虑步骤之间的依赖关系
- 优先使用最直接有效的方法"""

    def __init__(self, config: AgentConfig = None):
        """初始化 Agent

        Args:
            config: Agent 配置
        """
        self.config = config or AgentConfig()
        self.tools: Dict[str, "BaseTool"] = {}
        #         类型注解：Dict[str, 'BaseTool'] 表示字典的键是字符串（工具名称），值是 BaseTool 实例（使用字符串引用以避免循环导入）。
        # 初始化：{} 创建一个空字典，用于存储注册的工具。
        # 作用：作为工具注册表，允许 Agent 动态注册和访问各种工具（如搜索、计算等），便于在推理循环中调用工具执行动作。
        self.state = AgentState.IDLE
        #         设置初始状态：将 Agent 的状态设置为 IDLE（空闲状态），表示 Agent 尚未开始执行任务。
        # 状态管理：self.state 用于跟踪 Agent 在推理过程中的当前状态，如 THINKING（思考中）、ACTING（执行工具）、COMPLETED（完成）等。
        self.thought_history: List[ThoughtStep] = []
        #         类型注解：List[ThoughtStep] 表示这是一个列表，元素类型为 ThoughtStep 数据类。
        # 初始化：[] 创建一个空列表。
        # 作用：用于存储 Agent 在推理循环中的每个思考步骤，包括思考内容、执行的工具、观察结果等。
        # 在 run 和 run_stream 方法中，每次迭代都会创建一个 ThoughtStep 实例并追加到 self.thought_history，
        # 最终在 AgentResponse 中返回完整的推理过程，便于调试和展示推理链路。
        self.llm = self._init_llm()
        # 初始化标准（非流式）LLM 实例
        self.llm_streaming = self._init_llm(streaming=True)

    def _init_llm(self, streaming: bool = False):
        """初始化 LLM

        Args:
            streaming: 是否启用流式输出
        """
        if Config.MODEL_PROVIDER == "ollama":
            from langchain_community.llms import Ollama

            return Ollama(
                base_url=Config.OLLAMA_API_URL,
                model=Config.OLLAMA_MODEL,
                temperature=self.config.temperature,
            )
        elif Config.MODEL_PROVIDER == "deepseek":
            from langchain_deepseek import ChatDeepSeek

            return ChatDeepSeek(
                model=Config.LLM_MODEL,
                temperature=self.config.temperature,
                api_key=Config.DEEPSEEK_API_KEY,
                streaming=streaming,
            )
        else:
            from langchain.chat_models import init_chat_model

            #             是 LangChain 框架中的函数，用于初始化聊天模型实例。主要作用包括：

            # 统一接口：提供统一的方式初始化不同提供商的 LLM（如 OpenAI、Anthropic 等）。
            # 参数配置：接受模型名称、温度、提供商和流式输出等参数。
            # 自动选择：根据 model_provider 参数自动选择相应的模型类。
            # 在代码中的使用：
            # 它简化了多提供商模型的初始化过程。
            return init_chat_model(
                Config.LLM_MODEL,
                temperature=self.config.temperature,
                model_provider=Config.MODEL_PROVIDER,
                streaming=streaming,
            )

    def register_tool(self, tool: "BaseTool"):
        """注册工具

        Args:
            tool: 工具实例
        """
        self.tools[tool.name] = tool
        if self.config.verbose:
            # 用于控制是否启用详细输出。
            print(f"✓ 注册工具: {tool.name}")

    def get_tools_description(self) -> str:
        """获取所有工具的描述"""
        descriptions = []
        for name, tool in self.tools.items():
            #  返回字典的键值对迭代器，每个元素是 (name, tool) 元组
            params_desc = ", ".join(
                [
                    f"{p['name']}: {p['type']} - {p['description']}"
                    for p in tool.parameters
                    #                 tool.parameters: 一个列表，包含工具的参数信息，每个参数是一个字典（如 {'name': 'param_name', 'type': 'str', 'description': 'param desc'}）。
                    # 作用：遍历参数列表，生成参数描述字符串（如 "param1: str - 参数描述, param2: int - 参数描述"）。
                    # 用途：构建工具的完整描述文本，供 LLM 在推理过程中了解工具的参数要求。
                ]
            )
            descriptions.append(f"- {name}: {tool.description}\n  参数: {params_desc}")
        return "\n".join(descriptions)

    # 字典格式为 {'键': '值'}，用于存储工具输入参数。

    def _parse_action(self, response: str) -> tuple:
        """解析 LLM 响应中的 Action

        Returns:
            (action_name, action_input) 或 (None, None)
        """
        # 匹配 Final Answer - 使用贪婪匹配获取完整答案内容
        # 从 "Final Answer:" 开始一直匹配到字符串末尾
        # 查找文本中 "Final Answer:" 后面的内容，re.DOTALL 使得点号 . 能匹配换行，(.+) 捕获所有字符（贪婪）。
        final_match = re.search(r"Final Answer:\s*(.+)", response, re.DOTALL)
        if final_match:
            #             返回：如果匹配成功返回 Match 对象，使用 match.group(1).strip() 获取捕获的答案；否则返回 None。
            # 风险：(.+) 是贪婪的，可能会捕获超过期望的内容（例如后面还有其他章节）。可用非贪婪或锚点改进。
            return ("__final__", final_match.group(1).strip())

        # 匹配 Action 和 Action Input
        action_match = re.search(r"Action:\s*(\w+)", response)

        # 改进的 JSON 解析：支持嵌套对象
        input_match = None
        if "Action Input:" in response:
            # 找到 Action Input: 后的 JSON 对象
            # 找到 "Action Input:" 的位置，并计算内容起始索引。
            input_start = response.find("Action Input:") + len("Action Input:")
            # 从起始位置截取剩余字符串，并去除空白字符
            remaining = response[input_start:].strip()

            # 使用括号匹配来找到完整的 JSON
            # 检查 remaining 字符串是否以 '{' 开头
            if remaining.startswith("{"):
                brace_count = 0
                json_end = 0
                # 返回索引 i 和字符 char 的迭代器。
                for i, char in enumerate(remaining):
                    if char == "{":
                        brace_count += 1
                    elif char == "}":
                        brace_count -= 1
                        if brace_count == 0:
                            # 记录结束位置并跳出循环
                            json_end = i + 1
                            break
                if json_end > 0:
                    json_str = remaining[:json_end]
                    #                     type('obj', (object,), {'group': lambda self, x: json_str})(): 创建一个匿名类的实例，名为 'obj'，继承自 object，并添加一个 group 方法，该方法返回 json_str。
                    # 作用：模拟 re.match 返回的 Match 对象，使后续代码可以统一调用 input_match.group(1) 获取解析出的 JSON 字符串。
                    # 用途：便于代码复用，避免为手动解析的 JSON 单独处理逻辑。
                    # 是一个临时创建的对象，用于模拟正则匹配的结果。它是一个匿名类的实例（继承自 object）
                    # ，具有一个 group 方法，该方法返回解析出的 JSON 字符串 json_str。
                    input_match = type(
                        "obj", (object,), {"group": lambda self, x: json_str}
                    )()

        if action_match:
            #             action_match.group(1): 从正则匹配结果中获取第一个捕获组的内容，即 Action: 后面的工具名称（如 web_search）。
            # 作用：获取 LLM 输出中的工具名称，用于后续执行工具动作。
            # 示例：如果 LLM 输出 Action: web_search，则 group(1) 返回 "web_search"。

            action_name = action_match.group(1)
            action_input = {}

            if input_match:
                try:
                    #                     这段代码在 _parse_action 方法中提取 Action Input 的 JSON 字符串：

                    # input_match.group(1): 返回解析出的 JSON 字符串（如 {"param1": "value1"}）。
                    # 作用：将字符串传递给 json.loads() 解析为字典，作为工具输入参数。
                    action_input = json.loads(input_match.group(1))
                except json.JSONDecodeError:
                    # 尝试更宽松的解析
                    input_text = input_match.group(1)
                    # 简单的键值对解析
                    #                     re.findall(r'"(\w+)":\s*"([^"]*)"', input_text): 使用正则表达式查找所有 "key": "value" 格式的键值对。
                    # (\w+): 捕获键（单词字符）。
                    # \s*: 可选空白。
                    # "([^"]*)"：捕获值（双引号内的字符串）。
                    pairs = re.findall(r'"(\w+)":\s*"([^"]*)"', input_text)
                    #                     pairs: re.findall 返回的列表，包含键值对元组，如 [('key1', 'value1'), ('key2', 'value2')]。
                    # dict(pairs): 将列表转换为字典，如 {'key1': 'value1', 'key2': 'value2'}。
                    action_input = dict(pairs)
                    # 也尝试解析数字和布尔值
                    num_pairs = re.findall(r'"(\w+)":\s*(\d+(?:\.\d+)?)', input_text)
                    #                     num_pairs: re.findall 返回的数字键值对列表，如 [('key1', '123'), ('key2', '45.67')]。
                    # 循环处理：遍历每个对，如果 key 不在 action_input 中，则将 val 转换为 float（如果包含 '.'）或 int，并添加到字典。
                    # 作用：扩展 action_input 以支持数字类型的工具参数。
                    for key, val in num_pairs:
                        if key not in action_input:
                            action_input[key] = float(val) if "." in val else int(val)
                    #                     使用正则表达式查找所有 "key": true/false 格式的键值对。
                    # (\w+): 捕获键（单词字符）。
                    # \s*: 可选空白。
                    # (true|false): 捕获布尔值（忽略大小写）。
                    # 作用：提取字符串中的布尔键值对，并转换为字典。
                    bool_pairs = re.findall(
                        r'"(\w+)":\s*(true|false)', input_text, re.IGNORECASE
                    )

                    for key, val in bool_pairs:
                        if key not in action_input:
                            action_input[key] = val.lower() == "true"
            #             action_input = {
            #     "query": "天气查询",
            #     "location": "北京",
            #     "limit": 10,
            #     "include_details": True
            # }
            return (action_name, action_input)

        return (None, None)

    def _execute_action(self, action_name: str, action_input: Dict) -> tuple:
        """执行工具动作

        Args:
            action_name: 工具名称
            action_input: 工具输入参数

        Returns:
            (tool_output: str, structured_data: dict) 工具输出文本和结构化数据
        """
        if action_name not in self.tools:
            error_msg = (
                f"错误: 未知工具 '{action_name}'，可用工具: {list(self.tools.keys())}"
            )
            return (error_msg, {"error": error_msg})

        tool = self.tools[action_name]
        try:
            #             这段代码在 _execute_action 方法中调用工具的 execute 方法：

            # tool.execute(**action_input): 使用 ** 解包字典 action_input，将其作为关键字参数传递给工具的 execute 方法。
            # 作用：动态执行工具，传入解析出的参数（如 {"query": "天气", "location": "北京"} 解包为 execute(query="天气", location="北京")）。
            # 用途：支持灵活的工具调用，根据 LLM 解析的参数执行相应操作。
            result = tool.execute(**action_input)
            if result.success:
                # 返回文本输出和结构化数据
                # hasattr对象是否具有特定属性
                structured_data = {
                    "success": True,
                    "output": result.output,
                    "data": result.data if hasattr(result, "data") else None,
                    "metadata": (
                        result.metadata if hasattr(result, "metadata") else None
                    ),
                }
                return (result.output, structured_data)
            else:
                error_output = f"工具执行失败: {result.error}"
                return (error_output, {"error": result.error, "success": False})
        except Exception as e:
            error_msg = f"工具执行异常: {str(e)}"
            return (error_msg, {"error": error_msg, "success": False})

    def _reflect(self, question: str, answer: str, tools_used: List[str]) -> tuple:
        """反思检查

        Returns:
            (approved: bool, suggestion: str)
        """
        if not self.config.enable_reflection:
            return (True, None)
        # 格式化反思提示词：
        # 生成完整的反思提示词，发送给 LLM 检查回答质量。
        prompt = self.REFLECTION_PROMPT.format(
            question=question,
            answer=answer,
            tools_used=", ".join(tools_used) if tools_used else "无",
        )

        try:
            #             self.llm.invoke(prompt): 使用非流式 LLM 实例，传入格式化的反思提示词。
            # 作用：发送提示词给 LLM，获取反思结果（如 "APPROVED" 或 "RETRY: [建议]"）。
            # 用途：评估 Agent 回答的质量，确保基于工具结果且来源真实
            # invoke
            # 是 LangChain LLM 实例的方法，用于非流式调用大语言模型生成完整响应。主要作用包括：

            # 输入：接受提示词字符串。
            # 输出：返回完整的 LLM 响应，通常是字符串或包含 content 属性的对象。
            # 用途：在 run、run_stream（反思部分）和 _create_plan 方法中使用，获取推理结果、反思建议或执行计划。
            # 它与流式方法 stream 相对，用于一次性获取完整输出。
            reflection = self.llm.invoke(prompt)
            # isinstance(reflection, str): 检查 reflection 是否为字符串类型
            if isinstance(reflection, str):
                result = reflection
            else:
                result = (
                    reflection.content
                    if hasattr(reflection, "content")
                    else str(reflection)
                )
            # 转换为大写
            if "APPROVED" in result.upper():
                # 表示批准且无建议。
                return (True, None)
            # 使用正则表达式从反思结果中提取重试建议
            #  re.search(r'RETRY:\s*(.+)', result, re.DOTALL): 查找 "RETRY:" 后面的内容。
            # \s*: 可选空白。
            # (.+): 捕获所有字符（贪婪匹配）。
            # re.DOTALL: 使 . 匹配换行符。
            # 作用：如果匹配成功，retry_match.group(1).strip() 提取建议内容，返回 (False, suggestion) 表示需要重试。
            # 用途：解析 LLM 的反思输出，获取改进建议。
            retry_match = re.search(r"RETRY:\s*(.+)", result, re.DOTALL)
            if retry_match:
                return (False, retry_match.group(1).strip())

            return (True, None)  # 默认通过
        except Exception as e:
            print(f"反思检查失败: {e}")
            return (True, None)

    def _create_plan(self, task: str) -> List[str]:
        # 方法的返回类型是一个字符串列表
        """创建执行计划

        Args:
            task: 任务描述

        Returns:
            步骤列表
        """
        #         如果为 False，直接返回空列表 []，表示禁用规划功能，不生成执行计划。
        # 否则，继续执行后续代码，通过 LLM 生成计划步骤列表。
        if not self.config.enable_planning:
            return []
        #         这段代码格式化 PLANNING_PROMPT 模板，生成完整的规划提示词字符串。

        # task=task: 替换模板中的 {task} 为传入的任务描述。
        # tools=", ".join(self.tools.keys()): 将工具字典的键（工具名称）用逗号连接成字符串，替换 {tools}，如 "tool1, tool2, tool3"。
        # 作用：构建发送给 LLM 的提示词，用于分析任务并制定执行计划。
        prompt = self.PLANNING_PROMPT.format(
            task=task, tools=", ".join(self.tools.keys())
        )

        try:
            response = self.llm.invoke(prompt)
            if isinstance(response, str):
                result = response
            else:
                result = (
                    response.content if hasattr(response, "content") else str(response)
                )

            # 解析步骤
            steps = re.findall(r"Step \d+:\s*(.+?)(?=Step \d+:|$)", result, re.DOTALL)
            return [s.strip() for s in steps if s.strip()]
        except Exception as e:
            print(f"规划失败: {e}")
            return []

    def run(self, question: str, chat_history: str = "") -> AgentResponse:
        """运行 Agent 推理循环

        Args:
            question: 用户问题
            chat_history: 历史对话

        Returns:
            Agent 响应结果
        """
        start_time = time.time()
        logger.info(f"[Agent] 开始执行 - 问题: {question[:100]}...")
        logger.info(
            f"[Agent] 配置 - 最大迭代: {self.config.max_iterations}, 反思: {self.config.enable_reflection}"
        )

        self.state = AgentState.THINKING
        self.thought_history = []
        tools_used = []

        # 获取当前日期和时间（中国时区）
        # 创建中国时区对象
        tz = pytz.timezone("Asia/Shanghai")
        # 获取当前时间并格式化为 "2026年2月5日 14:30:00" 格式
        current_datetime = datetime.now(tz).strftime("%Y年%m月%d日 %H:%M:%S")
        # 作用：在 Agent 提示词中提供当前日期和时间，确保 LLM 知道系统时间。
        # 构建初始提示
        prompt = self.REACT_PROMPT.format(
            tools_description=self.get_tools_description(),
            chat_history=chat_history or "无",
            current_datetime=current_datetime,
            question=question,
        )

        current_prompt = prompt
        # 是推理循环的迭代计数器
        iterations = 0
        # 是变量，用于存储 Agent 推理循环中的最终答案
        final_answer = None

        while iterations < self.config.max_iterations:
            iterations += 1
            iteration_start = time.time()
            # 当为 True 时，打印推理过程、LLM输出、工具执行等信息，便于调试
            if self.config.verbose:
                print(f"\n{'='*50}")
                print(f"🔄 迭代 {iterations}/{self.config.max_iterations}")

            logger.info(f"[Agent] 迭代 {iterations} 开始")

            # 调用 LLM 进行推理
            try:
                logger.info(f"[Agent] 调用LLM进行推理...")
                llm_start = time.time()
                response = self.llm.invoke(current_prompt)
                llm_elapsed = time.time() - llm_start
                logger.info(f"[Agent] LLM调用完成 - 耗时: {llm_elapsed:.2f}秒")

                if isinstance(response, str):
                    llm_output = response
                else:
                    llm_output = (
                        response.content
                        if hasattr(response, "content")
                        else str(response)
                    )
            except Exception as e:
                self.state = AgentState.ERROR
                logger.error(f"[Agent] LLM调用失败: {str(e)}")
                return AgentResponse(
                    success=False,
                    answer=f"LLM 调用失败: {str(e)}",
                    thought_process=self.thought_history,
                    tools_used=tools_used,
                    iterations=iterations,
                )

            if self.config.verbose:
                print(f"💭 LLM 输出:\n{llm_output[:500]}...")

            # 解析动作
            action_name, action_input = self._parse_action(llm_output)

            # 记录思考步骤
            thought_match = re.search(
                r"Thought:\s*(.+?)(?=Action:|Final Answer:|$)", llm_output, re.DOTALL
            )
            # 用于记录 Agent 推理过程中的每个思考步骤
            thought_step = ThoughtStep(
                step=iterations,
                thought=thought_match.group(1).strip() if thought_match else llm_output,
                action=action_name,
                action_input=action_input if action_name != "__final__" else None,
            )

            # 检查是否是最终答案
            if action_name == "__final__":
                final_answer = action_input  # action_input 实际上是 final answer 内容
                thought_step.observation = "已得出最终答案"
                self.thought_history.append(thought_step)
                break

            # 执行工具
            if action_name:
                self.state = AgentState.ACTING
                if self.config.verbose:
                    print(f"🔧 执行工具: {action_name}")
                    print(f"   输入: {action_input}")

                logger.info(f"[Agent] 执行工具: {action_name}, 参数: {action_input}")
                tool_start = time.time()
                observation_text, structured_data = self._execute_action(
                    action_name, action_input
                )
                tool_elapsed = time.time() - tool_start
                logger.info(
                    f"[Agent] 工具执行完成 - 耗时: {tool_elapsed:.2f}秒, 结果长度: {len(str(observation_text))}"
                )

                # 存储观察结果（包含文本和结构化数据）
                thought_step.observation = observation_text
                # 添加结构化数据到thought_step中以供后续使用
                if not hasattr(thought_step, "observation_data"):
                    thought_step.observation_data = structured_data
                else:
                    thought_step.observation_data = structured_data

                tools_used.append(action_name)

                if self.config.verbose:
                    print(f"👁️ 观察结果: {observation_text[:200]}...")

                # 更新提示，加入观察结果
                current_prompt = f"{current_prompt}\n\n{llm_output}\n\nObservation: {observation_text}\n\n请继续推理："
            else:
                # 没有明确的动作，可能需要重新引导
                thought_step.observation = (
                    "未识别到有效动作，请按格式输出 Action 或 Final Answer"
                )
                current_prompt = f"{current_prompt}\n\n{llm_output}\n\n请按照正确格式输出 Action 或 Final Answer："

            self.thought_history.append(thought_step)
            self.state = AgentState.THINKING

            iteration_elapsed = time.time() - iteration_start
            logger.info(
                f"[Agent] 迭代 {iterations} 完成 - 耗时: {iteration_elapsed:.2f}秒"
            )

        # 反思检查
        reflection_result = None
        if final_answer and self.config.enable_reflection:
            self.state = AgentState.REFLECTING
            approved, suggestion = self._reflect(question, final_answer, tools_used)

            if not approved and suggestion:
                reflection_result = suggestion
                if self.config.verbose:
                    print(f"🔍 反思建议: {suggestion}")
                # 可以在这里添加重试逻辑

        self.state = AgentState.COMPLETED

        total_elapsed = time.time() - start_time
        logger.info(
            f"[Agent] 执行完成 - 总耗时: {total_elapsed:.2f}秒, 迭代次数: {iterations}, 使用工具: {list(set(tools_used))}"
        )

        return AgentResponse(
            success=final_answer is not None,
            answer=final_answer or "无法得出答案，已达到最大迭代次数",
            thought_process=self.thought_history,
            tools_used=list(set(tools_used)),
            iterations=iterations,
            final_reflection=reflection_result,
        )

    def run_stream(
        self, question: str, chat_history: str = ""
    ) -> Generator[StreamEvent, None, AgentResponse]:
        """流式运行 Agent 推理循环

        Args:
            question: 用户问题
            chat_history: 历史对话

        Yields:
            StreamEvent 事件，包含实时的推理过程

        Returns:
            Agent 响应结果
        """
        start_time = time.time()
        logger.info(f"[Agent Stream] 开始执行 - 问题: {question[:100]}...")

        self.state = AgentState.THINKING
        self.thought_history = []
        tools_used = []

        # 获取当前日期和时间（中国时区）
        tz = pytz.timezone("Asia/Shanghai")
        current_datetime = datetime.now(tz).strftime("%Y年%m月%d日 %H:%M:%S")

        # 构建初始提示
        prompt = self.REACT_PROMPT.format(
            tools_description=self.get_tools_description(),
            chat_history=chat_history or "无",
            current_datetime=current_datetime,
            question=question,
        )

        current_prompt = prompt
        iterations = 0
        final_answer = None

        yield StreamEvent(type="start", data="开始推理...")

        while iterations < self.config.max_iterations:
            iterations += 1

            yield StreamEvent(
                type="iteration",
                data={"iteration": iterations, "max": self.config.max_iterations},
                step=iterations,
            )

            # 流式调用 LLM
            try:
                llm_output = ""
                yield StreamEvent(type="thinking_start", step=iterations)

                # 使用流式 LLM
                is_final_answer = False  # 标记是否进入 Final Answer 阶段
                final_answer_buffer = ""  # 累积最终答案

                for chunk in self.llm_streaming.stream(current_prompt):
                    # 处理不同类型的响应
                    if isinstance(chunk, str):
                        token = chunk
                    elif hasattr(chunk, "content"):
                        token = chunk.content
                    else:
                        token = str(chunk)

                    llm_output += token

                    # 检测是否进入 Final Answer 阶段
                    if not is_final_answer and "Final Answer:" in llm_output:
                        is_final_answer = True
                        # 提取 Final Answer 之后的部分
                        final_start = llm_output.find("Final Answer:")
                        final_answer_buffer = llm_output[
                            final_start + len("Final Answer:") :
                        ].lstrip()
                        yield StreamEvent(type="answer_start", step=iterations)
                        # 发送已有的答案部分
                        if final_answer_buffer:
                            yield StreamEvent(
                                type="answer_token",
                                data=final_answer_buffer,
                                step=iterations,
                            )
                    elif is_final_answer:
                        # 已经在 Final Answer 阶段，流式输出答案 token
                        final_answer_buffer += token
                        yield StreamEvent(
                            type="answer_token", data=token, step=iterations
                        )
                    else:
                        # 思考过程，发送状态更新（不逐字输出）
                        pass

                yield StreamEvent(type="thinking_end", data=llm_output, step=iterations)

            except Exception as e:
                self.state = AgentState.ERROR
                logger.error(f"[Agent Stream] LLM调用失败: {str(e)}")
                yield StreamEvent(type="error", data=f"LLM 调用失败: {str(e)}")
                return AgentResponse(
                    success=False,
                    answer=f"LLM 调用失败: {str(e)}",
                    thought_process=self.thought_history,
                    tools_used=tools_used,
                    iterations=iterations,
                )

            # 解析动作
            action_name, action_input = self._parse_action(llm_output)

            # 记录思考步骤
            thought_match = re.search(
                r"Thought:\s*(.+?)(?=Action:|Final Answer:|$)", llm_output, re.DOTALL
            )
            thought_step = ThoughtStep(
                step=iterations,
                thought=thought_match.group(1).strip() if thought_match else llm_output,
                action=action_name,
                action_input=action_input if action_name != "__final__" else None,
            )

            # 检查是否是最终答案
            if action_name == "__final__":
                final_answer = action_input
                thought_step.observation = "已得出最终答案"
                self.thought_history.append(thought_step)

                yield StreamEvent(type="answer", data=final_answer, step=iterations)
                break

            # 执行工具
            if action_name:
                self.state = AgentState.ACTING

                yield StreamEvent(
                    type="action",
                    data={"tool": action_name, "input": action_input},
                    step=iterations,
                )

                logger.info(f"[Agent Stream] 执行工具: {action_name}")
                observation_text, structured_data = self._execute_action(
                    action_name, action_input
                )

                thought_step.observation = observation_text
                thought_step.observation_data = structured_data
                tools_used.append(action_name)

                yield StreamEvent(
                    type="observation",
                    data={"text": observation_text[:500], "data": structured_data},
                    step=iterations,
                )

                # 更新提示
                current_prompt = f"{current_prompt}\n\n{llm_output}\n\nObservation: {observation_text}\n\n请继续推理："
            else:
                thought_step.observation = (
                    "未识别到有效动作，请按格式输出 Action 或 Final Answer"
                )
                current_prompt = f"{current_prompt}\n\n{llm_output}\n\n请按照正确格式输出 Action 或 Final Answer："

            self.thought_history.append(thought_step)
            self.state = AgentState.THINKING

        # 反思检查
        reflection_result = None
        if final_answer and self.config.enable_reflection:
            self.state = AgentState.REFLECTING
            yield StreamEvent(type="reflecting", data="正在反思检查...")

            approved, suggestion = self._reflect(question, final_answer, tools_used)

            if not approved and suggestion:
                reflection_result = suggestion
                yield StreamEvent(type="reflection_result", data=suggestion)

        self.state = AgentState.COMPLETED

        total_elapsed = time.time() - start_time
        logger.info(f"[Agent Stream] 执行完成 - 总耗时: {total_elapsed:.2f}秒")

        yield StreamEvent(
            type="meta",
            data={
                "tools_used": list(set(tools_used)),
                "iterations": iterations,
                "elapsed": total_elapsed,
            },
        )

        yield StreamEvent(type="done")

        return AgentResponse(
            success=final_answer is not None,
            answer=final_answer or "无法得出答案，已达到最大迭代次数",
            thought_process=self.thought_history,
            tools_used=list(set(tools_used)),
            iterations=iterations,
            final_reflection=reflection_result,
        )

    @abstractmethod
    def setup_tools(self):
        """设置工具 - 子类实现"""
        pass
