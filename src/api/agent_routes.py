"""Agent API 路由 - 提供 Agent 相关的 REST API"""

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
import json
import asyncio
import logging
import time
import threading

from src.agent.rag_agent import RAGAgent, AgentBuilder
from src.agent.base import AgentConfig, AgentResponse, StreamEvent
from src.config.settings import Config

# 配置日志
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


router = APIRouter(prefix="/agent", tags=["Agent"])

# 全局 Agent 实例
_agent: Optional[RAGAgent] = None


def get_or_create_agent(
    agent_type: str = "full",
    force_new: bool = False
) -> RAGAgent:
    """获取或创建 Agent 实例"""
    global _agent
    
    if _agent is None or force_new:
        if agent_type == "simple":
            _agent = AgentBuilder.create_simple_agent()
        elif agent_type == "research":
            _agent = AgentBuilder.create_research_agent()
        elif agent_type == "manager":
            _agent = AgentBuilder.create_manager_agent()
        else:
            _agent = AgentBuilder.create_full_agent()
    
    return _agent


# ========================
# Request/Response Models
# ========================

class AgentQueryRequest(BaseModel):
    """Agent 查询请求"""
    question: str = Field(..., description="用户问题或任务描述")
    agent_type: str = Field("full", description="Agent 类型: simple/full/research/manager")
    provider: Optional[str] = Field(None, description="模型提供者: deepseek/ollama/openai/gemini")
    max_iterations: int = Field(5, description="最大推理迭代次数")
    enable_reflection: bool = Field(True, description="是否启用反思机制")
    enable_planning: bool = Field(True, description="是否启用规划能力")
    conversation_id: Optional[str] = Field(None, description="会话ID（用于多轮对话）")
    chat_history: Optional[str] = Field(None, description="历史对话（已废弃，请使用conversation_id）")


class AgentQueryResponse(BaseModel):
    """Agent 查询响应"""
    success: bool
    answer: str
    thought_process: List[Dict[str, Any]] = []
    tools_used: List[str] = []
    iterations: int = 0
    final_reflection: Optional[str] = None


class SmartQueryRequest(BaseModel):
    """智能查询请求 - 大模型分析意图后自动选择处理方式"""
    question: str = Field(..., description="用户问题")
    conversation_id: Optional[str] = Field(None, description="会话ID（用于多轮对话）")


class ConversationCreateResponse(BaseModel):
    """创建对话响应"""
    conversation_id: str
    message: str = "对话已创建"


class ConversationHistoryResponse(BaseModel):
    """对话历史响应"""
    conversation_id: str
    messages: List[Dict[str, Any]]
    total: int


class ToolInfo(BaseModel):
    """工具信息"""
    name: str
    description: str
    category: str
    parameters: List[Dict[str, Any]]


class AnalyzeRequest(BaseModel):
    """分析请求"""
    analysis_type: str = Field("structure", description="分析类型: structure/content/coverage/all")


class ResearchRequest(BaseModel):
    """研究请求"""
    topic: str
    use_web: bool = True
    agent_type: str = "research"


# ========================
# API Endpoints
# ========================

@router.get("/status")
async def agent_status():
    """获取 Agent 状态"""
    global _agent
    return {
        "initialized": _agent is not None,
        "tools_count": len(_agent.tools) if _agent else 0,
        "tools": list(_agent.tools.keys()) if _agent else []
    }


@router.get("/tools")
async def list_tools() -> List[ToolInfo]:
    """列出所有可用工具"""
    agent = get_or_create_agent()
    return [
        ToolInfo(
            name=tool.name,
            description=tool.description,
            category=tool.category.value,
            parameters=tool.parameters
        )
        for tool in agent.tools.values()
    ]


@router.post("/query", response_model=AgentQueryResponse)
async def agent_query(req: AgentQueryRequest):
    """执行 Agent 查询（完整推理循环）"""
    start_time = time.time()
    logger.info(f"[Agent Query] 开始处理请求 - 问题: {req.question[:100]}...")
    logger.info(f"[Agent Query] 配置 - 类型: {req.agent_type}, Provider: {req.provider}, 最大迭代: {req.max_iterations}")
    if req.conversation_id:
        logger.info(f"[Agent Query] 使用会话ID: {req.conversation_id}")
    
    # 注意：不再临时修改全局 Config.MODEL_PROVIDER，这在多线程环境下不安全
    # 如果需要指定 provider，应该在创建 Agent 时传入或使用请求上下文
    provider_to_use = req.provider or Config.MODEL_PROVIDER
    logger.info(f"[Agent Query] 使用 Provider: {provider_to_use}")
    
    try:
        # 创建 Agent
        config = AgentConfig(
            max_iterations=req.max_iterations,
            enable_reflection=req.enable_reflection,
            enable_planning=req.enable_planning,
            verbose=True
        )
        
        # TODO: 未来应该支持在 RAGAgent 初始化时传入 provider 参数
        agent = RAGAgent(config=config)
        logger.info(f"[Agent Query] Agent已创建，注册工具数: {len(agent.tools)}")
        
        # 如果提供了 conversation_id，设置当前会话
        if req.conversation_id:
            agent.set_conversation(req.conversation_id)
            logger.info(f"[Agent Query] 已设置会话ID: {req.conversation_id}")
            # 获取历史上下文
            history = agent._conversation_manager.format_history_for_llm(
                req.conversation_id, 
                max_turns=3
            )
        else:
            # 如果没有 conversation_id，使用传统的 chat_history（向后兼容）
            history = req.chat_history or ""
        
        # 执行查询
        logger.info(f"[Agent Query] 开始执行推理循环...")
        result = await asyncio.to_thread(
            agent.run,
            req.question,
            history
        )
        
        # 如果使用了 conversation_id，保存对话到历史
        if req.conversation_id and result.success:
            agent._conversation_manager.add_message(
                req.conversation_id, "user", req.question
            )
            agent._conversation_manager.add_message(
                req.conversation_id, "assistant", result.answer, save_to_disk=True
            )
            logger.info(f"[Agent Query] 已保存对话到历史")
        
        elapsed = time.time() - start_time
        logger.info(f"[Agent Query] 查询完成 - 耗时: {elapsed:.2f}秒, 迭代次数: {result.iterations}, 使用工具: {result.tools_used}")
        
        return AgentQueryResponse(
            success=result.success,
            answer=result.answer,
            thought_process=[
                {
                    "step": step.step,
                    "thought": step.thought,
                    "action": step.action,
                    "action_input": step.action_input,
                    "observation": step.observation[:500] if step.observation else None,
                    "reflection": step.reflection
                }
                for step in result.thought_process
            ],
            tools_used=result.tools_used,
            iterations=result.iterations,
            final_reflection=result.final_reflection
        )
        
    except Exception as e:
        elapsed = time.time() - start_time
        logger.error(f"[Agent Query] 执行失败 - 耗时: {elapsed:.2f}秒, 错误: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
        logger.info(f"[Agent Query] 已恢复 MODEL_PROVIDER = {original_provider}")


@router.post("/smart-query")
async def smart_query(req: SmartQueryRequest):
    """智能查询 - 使用大模型分析问题意图，自动选择最佳处理方式
    
    工作流程:
    1. 大模型分析用户问题的意图
    2. 根据意图决定使用什么工具（知识库/联网搜索/直接回答等）
    3. 执行相应的处理流程并返回结果
    """
    start_time = time.time()
    logger.info(f"[Smart Query] 开始处理 - 问题: {req.question[:100]}...")
    
    try:
        agent = get_or_create_agent("full")  # 智能模式使用完整 Agent
        
        # 如果提供了 conversation_id，设置当前会话
        if req.conversation_id:
            agent.set_conversation(req.conversation_id)
            logger.info(f"[Smart Query] 使用会话ID: {req.conversation_id}")
            # 使用带保存历史的查询
            result = await asyncio.to_thread(
                agent.smart_query, 
                req.question, 
                save_to_history=True
            )
        else:
            # 不保存历史
            result = await asyncio.to_thread(
                agent.smart_query, 
                req.question,
                save_to_history=False
            )
        
        elapsed = time.time() - start_time
        logger.info(f"[Smart Query] 完成 - 耗时: {elapsed:.2f}秒, 工具: {result.tools_used}")
        
        return {
            "success": result.success,
            "answer": result.answer,
            "tools_used": result.tools_used,
            "iterations": result.iterations,
            "is_simple": result.iterations == 1 and len(result.tools_used) <= 1
        }
        
    except Exception as e:
        logger.error(f"[Smart Query] 失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/query-stream")
async def agent_query_stream(req: AgentQueryRequest):
    """流式 Agent 查询 - 实时返回 LLM 推理过程（token 级别）"""
    start_time = time.time()
    logger.info(f"[Agent Stream] 开始处理流式查询 - 问题: {req.question[:100]}...")
    logger.info(f"[Agent Stream] 配置 - 类型: {req.agent_type}, Provider: {req.provider}")
    if req.conversation_id:
        logger.info(f"[Agent Stream] 使用会话ID: {req.conversation_id}")
    
    # 如果指定了 provider，临时设置到 Config 中
    original_provider = Config.MODEL_PROVIDER
    if req.provider:
        Config.MODEL_PROVIDER = req.provider
        logger.info(f"[Agent Stream] 已设置 MODEL_PROVIDER = {req.provider}")
    
    async def generate():
        final_answer = None
        try:
            config = AgentConfig(
                max_iterations=req.max_iterations,
                enable_reflection=req.enable_reflection,
                enable_planning=req.enable_planning,
                verbose=False  # 禁用控制台输出
            )
            
            agent = RAGAgent(config=config)
            
            # 如果提供了 conversation_id，设置当前会话
            if req.conversation_id:
                agent.set_conversation(req.conversation_id)
                # 获取历史上下文
                history = agent._conversation_manager.format_history_for_llm(
                    req.conversation_id, 
                    max_turns=3
                )
            else:
                history = req.chat_history or ""
            
            # 使用真正的流式推理
            def run_stream_sync():
                results = []
                for event in agent.run_stream(req.question, history):
                    results.append(event)
                return results
            
            # 在线程中运行流式生成器
            import concurrent.futures
            import queue
            
            event_queue = queue.Queue()
            
            def stream_worker():
                try:
                    for event in agent.run_stream(req.question, history):
                        event_queue.put(event)
                    event_queue.put(None)  # 结束标记
                except Exception as e:
                    event_queue.put(Exception(str(e)))
            
            # 启动后台线程
            import threading
            worker_thread = threading.Thread(target=stream_worker, daemon=True)
            worker_thread.start()
            
            # 从队列中读取事件并发送
            while True:
                try:
                    # 使用短超时以便能够响应
                    event = await asyncio.get_event_loop().run_in_executor(
                        None, 
                        lambda: event_queue.get(timeout=0.1)
                    )
                except:
                    # 超时，继续检查
                    if not worker_thread.is_alive():
                        break
                    continue
                
                if event is None:
                    break
                    
                if isinstance(event, Exception):
                    yield f"data: {json.dumps({'type': 'error', 'data': str(event)}, ensure_ascii=False)}\n\n"
                    break
                
                # 将 StreamEvent 转换为 JSON
                event_data = {
                    'type': event.type,
                    'data': event.data,
                    'step': event.step
                }
                
                # 记录最终答案
                if event.type == 'answer':
                    final_answer = event.data
                
                yield f"data: {json.dumps(event_data, ensure_ascii=False)}\n\n"
                
                # 对于 token 事件，不需要额外延迟
                if event.type != 'token':
                    await asyncio.sleep(0.01)
            
            # 如果使用了 conversation_id，保存对话到历史
            if req.conversation_id and final_answer:
                agent._conversation_manager.add_message(
                    req.conversation_id, "user", req.question
                )
                agent._conversation_manager.add_message(
                    req.conversation_id, "assistant", final_answer, save_to_disk=True
                )
                logger.info(f"[Agent Stream] 已保存对话到历史")
            
            # 记录完成日志
            total_elapsed = time.time() - start_time
            logger.info(f"[Agent Stream] 查询完成 - 总耗时: {total_elapsed:.2f}秒")
            
        except Exception as e:
            logger.error(f"[Agent Stream] 执行失败 - 错误: {str(e)}")
            yield f"data: {json.dumps({'type': 'error', 'data': str(e)})}\n\n"
        finally:
            # 恢复原来的 provider
            if req.provider:
                Config.MODEL_PROVIDER = original_provider
                logger.info(f"[Agent Stream] 已恢复 MODEL_PROVIDER = {original_provider}")
    
    return StreamingResponse(generate(), media_type="text/event-stream")


@router.post("/analyze")
async def analyze_knowledge_base(req: AnalyzeRequest):
    """分析知识库结构"""
    try:
        agent = get_or_create_agent("manager")
        
        # 直接使用分析工具
        analyze_tool = agent.tools.get("analyze_documents")
        if not analyze_tool:
            raise HTTPException(status_code=500, detail="分析工具未初始化")
        
        result = analyze_tool.execute(analysis_type=req.analysis_type)
        
        return {
            "success": result.success,
            "report": result.output,
            "data": result.data,
            "error": result.error
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/research")
async def research_topic(req: ResearchRequest):
    """研究某个主题"""
    try:
        agent = get_or_create_agent(req.agent_type)
        result = await asyncio.to_thread(
            agent.research_topic,
            req.topic,
            req.use_web
        )
        
        return {
            "success": result.success,
            "report": result.answer,
            "tools_used": result.tools_used,
            "iterations": result.iterations
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/execute-tool")
async def execute_tool(tool_name: str, params: Dict[str, Any]):
    """直接执行单个工具"""
    try:
        agent = get_or_create_agent()
        
        tool = agent.tools.get(tool_name)
        if not tool:
            raise HTTPException(
                status_code=404,
                detail=f"工具 '{tool_name}' 不存在，可用工具: {list(agent.tools.keys())}"
            )
        
        result = tool.execute(**params)
        
        return {
            "success": result.success,
            "output": result.output,
            "data": result.data,
            "error": result.error,
            "metadata": result.metadata
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ========================
# 对话管理 API
# ========================

@router.post("/conversation/create", response_model=ConversationCreateResponse)
async def create_conversation():
    """创建新的对话会话"""
    try:
        agent = get_or_create_agent()
        conversation_id = agent.start_conversation()
        logger.info(f"[Conversation] 创建新会话: {conversation_id}")
        
        return ConversationCreateResponse(
            conversation_id=conversation_id,
            message="对话已创建"
        )
    except Exception as e:
        logger.error(f"[Conversation] 创建会话失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/conversation/{conversation_id}/history", response_model=ConversationHistoryResponse)
async def get_conversation_history(conversation_id: str, max_messages: Optional[int] = None):
    """获取对话历史"""
    try:
        agent = get_or_create_agent()
        agent.set_conversation(conversation_id)
        
        history = agent.get_conversation_history(max_messages=max_messages)
        
        messages = [
            {
                "role": msg.role,
                "content": msg.content,
                "timestamp": msg.timestamp
            }
            for msg in history
        ]
        
        logger.info(f"[Conversation] 获取会话历史: {conversation_id}, 消息数: {len(messages)}")
        
        return ConversationHistoryResponse(
            conversation_id=conversation_id,
            messages=messages,
            total=len(messages)
        )
    except Exception as e:
        logger.error(f"[Conversation] 获取历史失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/conversation/{conversation_id}/clear")
async def clear_conversation(conversation_id: str):
    """清空对话历史"""
    try:
        agent = get_or_create_agent()
        agent.set_conversation(conversation_id)
        agent.clear_conversation()
        
        logger.info(f"[Conversation] 清空会话: {conversation_id}")
        
        return {"success": True, "message": "对话历史已清空"}
    except Exception as e:
        logger.error(f"[Conversation] 清空会话失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/conversation/list")
async def list_conversations():
    """列出所有对话"""
    try:
        agent = get_or_create_agent()
        conversations = agent._conversation_manager.list_conversations()
        
        logger.info(f"[Conversation] 列出所有会话，共 {len(conversations)} 个")
        
        return {
            "success": True,
            "conversations": conversations,
            "total": len(conversations)
        }
    except Exception as e:
        logger.error(f"[Conversation] 列出会话失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/conversation/{conversation_id}")
async def delete_conversation(conversation_id: str):
    """删除对话"""
    try:
        agent = get_or_create_agent()
        agent._conversation_manager.delete_conversation(conversation_id)
        
        logger.info(f"[Conversation] 删除会话: {conversation_id}")
        
        return {"success": True, "message": "对话已删除"}
    except Exception as e:
        logger.error(f"[Conversation] 删除会话失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
