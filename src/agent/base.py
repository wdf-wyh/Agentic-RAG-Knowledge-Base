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


@dataclass
class StreamEvent:
    """流式事件"""
    type: str  # 'thinking', 'action', 'observation', 'answer', 'token', 'error', 'done'
    data: Any = None
    step: int = 0

# 配置日志
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class AgentState(Enum):
    """Agent 状态枚举"""
    IDLE = "idle"
    THINKING = "thinking"
    ACTING = "acting"
    REFLECTING = "reflecting"
    COMPLETED = "completed"
    ERROR = "error"


@dataclass
class AgentConfig:
    """Agent 配置"""
    max_iterations: int = 5  # 最大推理迭代次数（优化：从10降到5以加快响应）
    temperature: float = 0.7
    enable_reflection: bool = False  # 启用反思机制（优化：关闭以加快响应）
    enable_planning: bool = True    # 启用规划能力
    verbose: bool = True            # 详细输出
    llm_timeout: int = 30           # LLM请求超时时间（秒）
    

@dataclass
class ThoughtStep:
    """思考步骤记录"""
    step: int
    thought: str
    action: Optional[str] = None
    action_input: Optional[Dict[str, Any]] = None
    observation: Optional[str] = None
    observation_data: Optional[Dict[str, Any]] = None  # 结构化数据（如工具返回的列表数据）
    reflection: Optional[str] = None


@dataclass
class AgentResponse:
    """Agent 响应结果"""
    success: bool
    answer: str
    thought_process: List[ThoughtStep] = field(default_factory=list)
    tools_used: List[str] = field(default_factory=list)
    iterations: int = 0
    final_reflection: Optional[str] = None


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
1. **仅当历史对话非空且问题明确指代先前内容时**，才可直接从【历史对话上下文】回答；若历史为空/无历史对话，禁止声称基于历史回答，也禁止标注「来源: 对话历史」
2. **实时信息必须重新查询**：对于天气、新闻、股价等实时信息，即使历史对话中有答案，也必须重新执行 web_search 获取最新数据
3. 对于知识查询问题，优先使用 rag_search 工具查询本地知识库
4. 回答必须且只能基于工具返回的实际结果或（有内容时的）历史对话，绝对禁止使用你自己的知识或常识
5. 如果检索结果中没有相关信息，必须明确告知用户"知识库中没有找到相关信息"
6. 绝对禁止编造任何内容，包括来源名称、URL、数据等

【来源引用规则 - 极其重要】
1. 仅当确实依据先前轮次回答时，才可标注"来源: 对话历史"；首轮或无历史时禁止使用
2. 如果使用了 web_search，必须在回答中附上工具返回的真实 URL 链接
3. 如果使用了 rag_search，必须标明来源文件名（从 Observation 中获取）
4. 绝对禁止编造来源名称，如"XX词典"、"XX论坛"等虚假来源
5. 只有在 Observation 中明确出现的 URL 或文件名才能作为来源引用

【重要规则】
1. 你必须严格按照 Thought -> Action -> Observation 的格式输出
2. 仅当历史非空且问题涉及历史对话时，无需使用工具，直接输出 Final Answer
3. 每次只能执行一个 Action
4. 根据 Observation 结果决定下一步行动
5. 只有当 Observation 中明确包含答案时，才输出 Final Answer
6. 如果遇到错误，尝试换一种方法
7. **即使历史对话中显示之前查询失败，也要重新执行工具调用获取最新信息**
8. **对于天气、新闻等实时信息，必须使用 web_search 或 weather 工具，而不是 rag_search**
9. **每次查询都是独立的，不要因为历史中有负面结果就直接回答失败**
10. **查询天气时必须有明确城市/地区**：若用户只说「今天天气」「天气怎么样」等未指明地点，禁止调用 weather，禁止默认任何城市（尤其不要默认北京），必须直接追问；仅当用户本轮或历史对话中已明确给出地点后再调用 weather，且 city 必须与用户说过的地点一致

【输出格式】
Thought: [你的思考过程；仅在有先验历史时才检查历史对话]
Action: [工具名称]
Action Input: {{"param1": "value1", "param2": "value2"}}

等待观察结果后继续：
Observation: [工具返回的结果]

Thought: [根据观察结果的进一步思考，必须分析 Observation 是否包含答案]
...

当用户问天气但未说明地点时：
Thought: 用户没有说明要查询哪个城市的天气，我需要先追问地点，不能默认城市
Final Answer: 请问您想查询哪个城市或地区的天气？例如：广州、上海、深圳等。

当能从历史对话中直接回答时（历史必须非空）：
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

请开始推理（记住：无先验历史时不要引用对话历史；答案和来源必须完全来自历史对话或工具返回的 Observation，禁止编造）："""

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
        self.tools: Dict[str, 'BaseTool'] = {}
        self.state = AgentState.IDLE
        self.thought_history: List[ThoughtStep] = []
        self.llm = self._init_llm()
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
            return init_chat_model(
                Config.LLM_MODEL,
                temperature=self.config.temperature,
                model_provider=Config.MODEL_PROVIDER,
                streaming=streaming,
            )
    
    def register_tool(self, tool: 'BaseTool'):
        """注册工具
        
        Args:
            tool: 工具实例
        """
        self.tools[tool.name] = tool
        if self.config.verbose:
            print(f"[ok] 注册工具: {tool.name}")
    
    def get_tools_description(self) -> str:
        """获取所有工具的描述"""
        descriptions = []
        for name, tool in self.tools.items():
            params_desc = ", ".join([
                f"{p['name']}: {p['type']} - {p['description']}"
                for p in tool.parameters
            ])
            descriptions.append(
                f"- {name}: {tool.description}\n  参数: {params_desc}"
            )
        return "\n".join(descriptions)
    
    def _parse_action(self, response: str) -> tuple:
        """解析 LLM 响应中的 Action
        
        Returns:
            (action_name, action_input) 或 (None, None)
        """
        # 匹配 Final Answer - 使用贪婪匹配获取完整答案内容
        # 从 "Final Answer:" 开始一直匹配到字符串末尾
        final_match = re.search(r'Final Answer:\s*(.+)', response, re.DOTALL)
        if final_match:
            return ("__final__", final_match.group(1).strip())
        
        # 匹配 Action 和 Action Input
        action_match = re.search(r'Action:\s*(\w+)', response)
        
        # 改进的 JSON 解析：支持嵌套对象
        input_match = None
        if 'Action Input:' in response:
            # 找到 Action Input: 后的 JSON 对象
            input_start = response.find('Action Input:') + len('Action Input:')
            remaining = response[input_start:].strip()
            
            # 使用括号匹配来找到完整的 JSON
            if remaining.startswith('{'):
                brace_count = 0
                json_end = 0
                for i, char in enumerate(remaining):
                    if char == '{':
                        brace_count += 1
                    elif char == '}':
                        brace_count -= 1
                        if brace_count == 0:
                            json_end = i + 1
                            break
                if json_end > 0:
                    json_str = remaining[:json_end]
                    input_match = type('obj', (object,), {'group': lambda self, x: json_str})()
        
        if action_match:
            action_name = action_match.group(1)
            action_input = {}
            
            if input_match:
                try:
                    action_input = json.loads(input_match.group(1))
                except json.JSONDecodeError:
                    # 尝试更宽松的解析
                    input_text = input_match.group(1)
                    # 简单的键值对解析
                    pairs = re.findall(r'"(\w+)":\s*"([^"]*)"', input_text)
                    action_input = dict(pairs)
                    # 也尝试解析数字和布尔值
                    num_pairs = re.findall(r'"(\w+)":\s*(\d+(?:\.\d+)?)', input_text)
                    for key, val in num_pairs:
                        if key not in action_input:
                            action_input[key] = float(val) if '.' in val else int(val)
                    bool_pairs = re.findall(r'"(\w+)":\s*(true|false)', input_text, re.IGNORECASE)
                    for key, val in bool_pairs:
                        if key not in action_input:
                            action_input[key] = val.lower() == 'true'
            
            return (action_name, action_input)
        
        return (None, None)
    
    def _validate_weather_city(self, action_input: Dict) -> Optional[str]:
        """天气工具硬校验：city 必须出现在用户问题或历史对话中。"""
        city = str((action_input or {}).get("city") or "").strip()
        if not city:
            return "缺少城市参数。请先询问用户要查询哪个城市/地区的天气，不要默认任何城市。"

        context = f"{getattr(self, '_current_question', '')}\n{getattr(self, '_current_chat_history', '')}"
        try:
            from src.agent.tools.weather_tools import WeatherTool
            allowed = WeatherTool.is_city_in_context(city, context)
        except Exception:
            # 兜底：至少要求 city 原文出现在上下文中
            allowed = city in context or city.lower() in context.lower()

        if not allowed:
            return (
                f"用户未提及城市「{city}」，禁止猜测或默认城市。"
                "请不要再次调用 weather，直接用 Final Answer 追问用户要查询哪个城市/地区的天气。"
            )
        return None

    def _execute_action(self, action_name: str, action_input: Dict) -> tuple:
        """执行工具动作
        
        Args:
            action_name: 工具名称
            action_input: 工具输入参数
            
        Returns:
            (tool_output: str, structured_data: dict) 工具输出文本和结构化数据
        """
        if action_name not in self.tools:
            error_msg = f"错误: 未知工具 '{action_name}'，可用工具: {list(self.tools.keys())}"
            return (error_msg, {"error": error_msg})

        if action_name == "weather":
            weather_error = self._validate_weather_city(action_input or {})
            if weather_error:
                logger.warning(f"[Agent] 拦截天气查询: {weather_error}")
                return (f"工具执行失败: {weather_error}", {"error": weather_error, "success": False})
        
        tool = self.tools[action_name]
        try:
            result = tool.execute(**action_input)
            if result.success:
                # 返回文本输出和结构化数据
                structured_data = {
                    "success": True,
                    "output": result.output,
                    "data": result.data if hasattr(result, 'data') else None,
                    "metadata": result.metadata if hasattr(result, 'metadata') else None
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
        
        prompt = self.REFLECTION_PROMPT.format(
            question=question,
            answer=answer,
            tools_used=", ".join(tools_used) if tools_used else "无"
        )
        
        try:
            reflection = self.llm.invoke(prompt)
            if isinstance(reflection, str):
                result = reflection
            else:
                result = reflection.content if hasattr(reflection, 'content') else str(reflection)
            
            if "APPROVED" in result.upper():
                return (True, None)
            
            retry_match = re.search(r'RETRY:\s*(.+)', result, re.DOTALL)
            if retry_match:
                return (False, retry_match.group(1).strip())
            
            return (True, None)  # 默认通过
        except Exception as e:
            print(f"反思检查失败: {e}")
            return (True, None)
    
    def _create_plan(self, task: str) -> List[str]:
        """创建执行计划
        
        Args:
            task: 任务描述
            
        Returns:
            步骤列表
        """
        if not self.config.enable_planning:
            return []
        
        prompt = self.PLANNING_PROMPT.format(
            task=task,
            tools=", ".join(self.tools.keys())
        )
        
        try:
            response = self.llm.invoke(prompt)
            if isinstance(response, str):
                result = response
            else:
                result = response.content if hasattr(response, 'content') else str(response)
            
            # 解析步骤
            steps = re.findall(r'Step \d+:\s*(.+?)(?=Step \d+:|$)', result, re.DOTALL)
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
        logger.info(f"[Agent] 配置 - 最大迭代: {self.config.max_iterations}, 反思: {self.config.enable_reflection}")
        
        self.state = AgentState.THINKING
        self.thought_history = []
        self._current_question = question or ""
        self._current_chat_history = chat_history or ""
        tools_used = []
        
        # 获取当前日期和时间（中国时区）
        tz = pytz.timezone('Asia/Shanghai')
        current_datetime = datetime.now(tz).strftime("%Y年%m月%d日 %H:%M:%S")
        
        # 构建初始提示
        prompt = self.REACT_PROMPT.format(
            tools_description=self.get_tools_description(),
            chat_history=chat_history or "无",
            current_datetime=current_datetime,
            question=question
        )
        
        current_prompt = prompt
        iterations = 0
        final_answer = None
        
        while iterations < self.config.max_iterations:
            iterations += 1
            iteration_start = time.time()
            
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
                    llm_output = response.content if hasattr(response, 'content') else str(response)
            except Exception as e:
                self.state = AgentState.ERROR
                logger.error(f"[Agent] LLM调用失败: {str(e)}")
                return AgentResponse(
                    success=False,
                    answer=f"LLM 调用失败: {str(e)}",
                    thought_process=self.thought_history,
                    tools_used=tools_used,
                    iterations=iterations
                )
            
            if self.config.verbose:
                print(f"💭 LLM 输出:\n{llm_output[:500]}...")
            
            # 解析动作
            action_name, action_input = self._parse_action(llm_output)
            
            # 记录思考步骤
            thought_match = re.search(r'Thought:\s*(.+?)(?=Action:|Final Answer:|$)', llm_output, re.DOTALL)
            thought_step = ThoughtStep(
                step=iterations,
                thought=thought_match.group(1).strip() if thought_match else llm_output,
                action=action_name,
                action_input=action_input if action_name != "__final__" else None
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
                observation_text, structured_data = self._execute_action(action_name, action_input)
                tool_elapsed = time.time() - tool_start
                logger.info(f"[Agent] 工具执行完成 - 耗时: {tool_elapsed:.2f}秒, 结果长度: {len(str(observation_text))}")
                
                # 存储观察结果（包含文本和结构化数据）
                thought_step.observation = observation_text
                # 添加结构化数据到thought_step中以供后续使用
                if not hasattr(thought_step, 'observation_data'):
                    thought_step.observation_data = structured_data
                else:
                    thought_step.observation_data = structured_data
                    
                tools_used.append(action_name)
                
                if self.config.verbose:
                    print(f"[observe] {observation_text[:200]}...")
                
                # 更新提示，加入观察结果
                current_prompt = f"{current_prompt}\n\n{llm_output}\n\nObservation: {observation_text}\n\n请继续推理："
            else:
                # 没有明确的动作，可能需要重新引导
                thought_step.observation = "未识别到有效动作，请按格式输出 Action 或 Final Answer"
                current_prompt = f"{current_prompt}\n\n{llm_output}\n\n请按照正确格式输出 Action 或 Final Answer："
            
            self.thought_history.append(thought_step)
            self.state = AgentState.THINKING
            
            iteration_elapsed = time.time() - iteration_start
            logger.info(f"[Agent] 迭代 {iterations} 完成 - 耗时: {iteration_elapsed:.2f}秒")
        
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
        logger.info(f"[Agent] 执行完成 - 总耗时: {total_elapsed:.2f}秒, 迭代次数: {iterations}, 使用工具: {list(set(tools_used))}")
        
        return AgentResponse(
            success=final_answer is not None,
            answer=final_answer or "无法得出答案，已达到最大迭代次数",
            thought_process=self.thought_history,
            tools_used=list(set(tools_used)),
            iterations=iterations,
            final_reflection=reflection_result
        )
    
    def run_stream(self, question: str, chat_history: str = "") -> Generator[StreamEvent, None, AgentResponse]:
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
        self._current_question = question or ""
        self._current_chat_history = chat_history or ""
        tools_used = []
        
        # 获取当前日期和时间（中国时区）
        tz = pytz.timezone('Asia/Shanghai')
        current_datetime = datetime.now(tz).strftime("%Y年%m月%d日 %H:%M:%S")
        
        # 构建初始提示
        prompt = self.REACT_PROMPT.format(
            tools_description=self.get_tools_description(),
            chat_history=chat_history or "无",
            current_datetime=current_datetime,
            question=question
        )
        
        current_prompt = prompt
        iterations = 0
        final_answer = None
        
        yield StreamEvent(type='start', data='开始推理...')
        
        while iterations < self.config.max_iterations:
            iterations += 1
            
            yield StreamEvent(type='iteration', data={'iteration': iterations, 'max': self.config.max_iterations}, step=iterations)
            
            # 流式调用 LLM
            try:
                llm_output = ""
                yield StreamEvent(type='thinking_start', step=iterations)
                
                # 使用流式 LLM
                is_final_answer = False  # 标记是否进入 Final Answer 阶段
                final_answer_buffer = ""  # 累积最终答案
                
                for chunk in self.llm_streaming.stream(current_prompt):
                    # 处理不同类型的响应
                    if isinstance(chunk, str):
                        token = chunk
                    elif hasattr(chunk, 'content'):
                        token = chunk.content
                    else:
                        token = str(chunk)
                    
                    llm_output += token
                    
                    # 检测是否进入 Final Answer 阶段
                    if not is_final_answer and "Final Answer:" in llm_output:
                        is_final_answer = True
                        # 提取 Final Answer 之后的部分
                        final_start = llm_output.find("Final Answer:")
                        final_answer_buffer = llm_output[final_start + len("Final Answer:"):].lstrip()
                        yield StreamEvent(type='answer_start', step=iterations)
                        # 发送已有的答案部分
                        if final_answer_buffer:
                            yield StreamEvent(type='answer_token', data=final_answer_buffer, step=iterations)
                    elif is_final_answer:
                        # 已经在 Final Answer 阶段，流式输出答案 token
                        final_answer_buffer += token
                        yield StreamEvent(type='answer_token', data=token, step=iterations)
                    else:
                        # 思考过程，发送状态更新（不逐字输出）
                        pass
                
                yield StreamEvent(type='thinking_end', data=llm_output, step=iterations)
                
            except Exception as e:
                self.state = AgentState.ERROR
                logger.error(f"[Agent Stream] LLM调用失败: {str(e)}")
                yield StreamEvent(type='error', data=f"LLM 调用失败: {str(e)}")
                return AgentResponse(
                    success=False,
                    answer=f"LLM 调用失败: {str(e)}",
                    thought_process=self.thought_history,
                    tools_used=tools_used,
                    iterations=iterations
                )
            
            # 解析动作
            action_name, action_input = self._parse_action(llm_output)
            
            # 记录思考步骤
            thought_match = re.search(r'Thought:\s*(.+?)(?=Action:|Final Answer:|$)', llm_output, re.DOTALL)
            thought_step = ThoughtStep(
                step=iterations,
                thought=thought_match.group(1).strip() if thought_match else llm_output,
                action=action_name,
                action_input=action_input if action_name != "__final__" else None
            )
            
            # 检查是否是最终答案
            if action_name == "__final__":
                final_answer = action_input
                thought_step.observation = "已得出最终答案"
                self.thought_history.append(thought_step)
                
                yield StreamEvent(type='answer', data=final_answer, step=iterations)
                break
            
            # 执行工具
            if action_name:
                self.state = AgentState.ACTING
                
                yield StreamEvent(type='action', data={'tool': action_name, 'input': action_input}, step=iterations)
                
                logger.info(f"[Agent Stream] 执行工具: {action_name}")
                observation_text, structured_data = self._execute_action(action_name, action_input)
                
                thought_step.observation = observation_text
                thought_step.observation_data = structured_data
                tools_used.append(action_name)
                
                yield StreamEvent(type='observation', data={'text': observation_text[:500], 'data': structured_data}, step=iterations)
                
                # 更新提示
                current_prompt = f"{current_prompt}\n\n{llm_output}\n\nObservation: {observation_text}\n\n请继续推理："
            else:
                thought_step.observation = "未识别到有效动作，请按格式输出 Action 或 Final Answer"
                current_prompt = f"{current_prompt}\n\n{llm_output}\n\n请按照正确格式输出 Action 或 Final Answer："
            
            self.thought_history.append(thought_step)
            self.state = AgentState.THINKING
        
        # 反思检查
        reflection_result = None
        if final_answer and self.config.enable_reflection:
            self.state = AgentState.REFLECTING
            yield StreamEvent(type='reflecting', data='正在反思检查...')
            
            approved, suggestion = self._reflect(question, final_answer, tools_used)
            
            if not approved and suggestion:
                reflection_result = suggestion
                yield StreamEvent(type='reflection_result', data=suggestion)
        
        self.state = AgentState.COMPLETED
        
        total_elapsed = time.time() - start_time
        logger.info(f"[Agent Stream] 执行完成 - 总耗时: {total_elapsed:.2f}秒")
        
        yield StreamEvent(type='meta', data={
            'tools_used': list(set(tools_used)),
            'iterations': iterations,
            'elapsed': total_elapsed
        })
        
        yield StreamEvent(type='done')
        
        return AgentResponse(
            success=final_answer is not None,
            answer=final_answer or "无法得出答案，已达到最大迭代次数",
            thought_process=self.thought_history,
            tools_used=list(set(tools_used)),
            iterations=iterations,
            final_reflection=reflection_result
        )
    
    @abstractmethod
    def setup_tools(self):
        """设置工具 - 子类实现"""
        pass
