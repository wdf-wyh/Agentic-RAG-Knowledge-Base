"""Agent API 路由 - 提供 Agent 相关的 REST API"""

from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from contextlib import contextmanager
import json
import asyncio
import logging
import time
import threading

from src.agent.rag_agent import RAGAgent, AgentBuilder
from src.agent.base import AgentConfig, AgentResponse, StreamEvent
from src.api.auth import get_current_user
from src.api.permissions import require_roles, require_policy
from src.config.settings import Config
from src.models.auth import UserIdentity
from src.security.guardrails import validate_user_text
from src.security.pii import sanitize_output_text
from src.services.conversation_manager import ConversationManager
from src.services.quota_service import get_quota_service
from src.services.webhook_service import get_webhook_service
from src.utils.tracing import StreamTraceBuilder, record_agent_trace

# 配置日志
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


router = APIRouter(prefix="/agent", tags=["Agent"], dependencies=[Depends(get_current_user)])

# 全局 Agent 实例（按租户隔离）
_agents: Dict[str, RAGAgent] = {}


def get_tenant_id(user: Optional[UserIdentity]) -> str:
    return user.tenant_id if user else Config.DEFAULT_TENANT_ID


def enforce_and_record_query(user: Optional[UserIdentity], question: str, provider: str = "") -> None:
    tenant_id = get_tenant_id(user)
    get_quota_service().ensure_allowed(tenant_id)
    usage = get_quota_service().record_query(
        tenant_id,
        question=question,
        provider=provider or Config.MODEL_PROVIDER,
        estimated_output_tokens=Config.MAX_TOKENS,
    )
    get_webhook_service().emit(
        "query.completed",
        {
            "tenant_id": tenant_id,
            "provider": provider or Config.MODEL_PROVIDER,
            "question_preview": question[:120],
            "usage": usage,
            "source": "agent",
        },
    )


def sanitize_stream_event_data(event_type: str, data: Any) -> Any:
    if isinstance(data, str) and event_type in {"answer", "answer_token", "token", "final_answer", "observation"}:
        return sanitize_output_text(data)
    return data


def _get_conversation_manager(tenant_id: str) -> ConversationManager:
    """与 /conversations 列表共用同一租户级对话存储"""
    from src.api.routes import get_conversation_manager
    return get_conversation_manager(tenant_id)


def get_or_create_agent(
    agent_type: str = "full",
    force_new: bool = False,
    tenant_id: str = Config.DEFAULT_TENANT_ID,
) -> RAGAgent:
    """获取或创建 Agent 实例"""
    agent = _agents.get(tenant_id)
    conv_manager = _get_conversation_manager(tenant_id)
    
    if agent is None or force_new:
        if agent_type == "simple":
            agent = AgentBuilder.create_simple_agent()
        elif agent_type == "research":
            agent = AgentBuilder.create_research_agent()
        elif agent_type == "manager":
            agent = AgentBuilder.create_manager_agent()
        else:
            agent = AgentBuilder.create_full_agent()
        agent._conversation_manager = conv_manager
        _agents[tenant_id] = agent
    elif agent._conversation_manager is not conv_manager:
        # 热更新：确保与历史列表读写同一存储
        agent._conversation_manager = conv_manager
    
    return agent


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
    provider: Optional[str] = Field(None, description="模型提供者: deepseek/ollama/openai/gemini")
    ollama_model: Optional[str] = None
    ollama_api_url: Optional[str] = None
    deepseek_model: Optional[str] = None
    deepseek_api_url: Optional[str] = None
    deepseek_api_key: Optional[str] = None


@contextmanager
def provider_context(req: SmartQueryRequest):
    """临时应用前端传入的模型提供者配置"""
    originals: Dict[str, Any] = {}
    updates: Dict[str, Any] = {}

    if req.provider and req.provider.strip():
        updates["MODEL_PROVIDER"] = req.provider.strip().lower()
    if req.ollama_model and req.ollama_model.strip():
        updates["OLLAMA_MODEL"] = req.ollama_model.strip()
    if req.ollama_api_url and req.ollama_api_url.strip():
        updates["OLLAMA_API_URL"] = req.ollama_api_url.strip()
    if req.deepseek_model and req.deepseek_model.strip():
        updates["LLM_MODEL"] = req.deepseek_model.strip()
    if req.deepseek_api_url and req.deepseek_api_url.strip():
        updates["DEEPSEEK_API_URL"] = req.deepseek_api_url.strip()
    if req.deepseek_api_key and req.deepseek_api_key.strip():
        updates["DEEPSEEK_API_KEY"] = req.deepseek_api_key.strip()

    try:
        for key, value in updates.items():
            originals[key] = getattr(Config, key)
            setattr(Config, key, value)
        yield
    finally:
        for key, value in originals.items():
            setattr(Config, key, value)


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
async def agent_status(user: Optional[UserIdentity] = Depends(get_current_user)):
    """获取 Agent 状态"""
    tenant_id = get_tenant_id(user)
    agent = _agents.get(tenant_id)
    return {
        "initialized": agent is not None,
        "tools_count": len(agent.tools) if agent else 0,
        "tools": list(agent.tools.keys()) if agent else [],
        "tenant_id": tenant_id,
    }


@router.get("/tools")
async def list_tools(user: Optional[UserIdentity] = Depends(get_current_user)) -> List[ToolInfo]:
    """列出所有可用工具"""
    agent = get_or_create_agent(tenant_id=get_tenant_id(user))
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
async def agent_query(req: AgentQueryRequest, user: Optional[UserIdentity] = Depends(get_current_user)):
    """执行 Agent 查询（完整推理循环）"""
    validate_user_text(req.question)
    enforce_and_record_query(user, req.question, req.provider or "")
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
        tenant_id = get_tenant_id(user)
        agent = RAGAgent(config=config, conversation_manager=_get_conversation_manager(tenant_id))
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
        safe_answer = sanitize_output_text(result.answer or "")
        if req.conversation_id and result.success:
            agent._conversation_manager.add_message(
                req.conversation_id, "user", req.question
            )
            agent._conversation_manager.add_message(
                req.conversation_id, "assistant", safe_answer, save_to_disk=True
            )
            logger.info(f"[Agent Query] 已保存对话到历史")
        
        elapsed = time.time() - start_time
        logger.info(f"[Agent Query] 查询完成 - 耗时: {elapsed:.2f}秒, 迭代次数: {result.iterations}, 使用工具: {result.tools_used}")

        # 保存追踪记录
        record_agent_trace(
            req.question,
            mode="agent",
            tenant_id=tenant_id,
            thought_process=result.thought_process,
            answer=safe_answer,
            success=result.success,
            tools_used=result.tools_used,
        )

        return AgentQueryResponse(
            success=result.success,
            answer=safe_answer,
            thought_process=[
                {
                    "step": step.step,
                    "thought": step.thought,
                    "action": step.action,
                    "action_input": step.action_input,
                    "observation": sanitize_output_text(step.observation[:500]) if step.observation else None,
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


@router.post("/smart-query")
async def smart_query(req: SmartQueryRequest, user: Optional[UserIdentity] = Depends(get_current_user)):
    """智能查询 - 使用大模型分析问题意图，自动选择最佳处理方式
    
    工作流程:
    1. 大模型分析用户问题的意图
    2. 根据意图决定使用什么工具（知识库/联网搜索/直接回答等）
    3. 执行相应的处理流程并返回结果
    """
    validate_user_text(req.question)
    tenant_id = get_tenant_id(user)
    enforce_and_record_query(user, req.question, req.provider or "")
    start_time = time.time()
    logger.info(f"[Smart Query] 开始处理 - 问题: {req.question[:100]}...")
    
    try:
        with provider_context(req):
            agent = get_or_create_agent("full", force_new=bool(req.provider), tenant_id=tenant_id)

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

        safe_answer = sanitize_output_text(result.answer or "")
        record_agent_trace(
            req.question,
            mode="smart",
            tenant_id=tenant_id,
            thought_process=result.thought_process,
            answer=safe_answer,
            success=result.success,
            tools_used=result.tools_used,
        )

        return {
            "success": result.success,
            "answer": safe_answer,
            "tools_used": result.tools_used,
            "iterations": result.iterations,
            "is_simple": result.iterations == 1 and len(result.tools_used) <= 1
        }
        
    except Exception as e:
        logger.error(f"[Smart Query] 失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/smart-query-stream")
async def smart_query_stream(req: SmartQueryRequest, user: Optional[UserIdentity] = Depends(get_current_user)):
    """流式智能查询 - 意图路由 + 实时流式输出答案 token"""
    validate_user_text(req.question)
    tenant_id = get_tenant_id(user)
    enforce_and_record_query(user, req.question, req.provider or "")
    logger.info(f"[Smart Stream] 开始处理 - 问题: {req.question[:100]}...")

    async def generate():
        import queue
        import threading

        builder = StreamTraceBuilder(req.question, mode="smart-stream")
        try:
            with provider_context(req):
                agent = get_or_create_agent("full", force_new=bool(req.provider), tenant_id=tenant_id)

                if req.conversation_id:
                    agent.set_conversation(req.conversation_id)

                event_queue: queue.Queue = queue.Queue()

                def stream_worker():
                    try:
                        for event in agent.smart_query_stream(
                            req.question,
                            save_to_history=bool(req.conversation_id)
                        ):
                            event_queue.put(event)
                        event_queue.put(None)  # 结束标记
                    except Exception as e:
                        event_queue.put(e)

                worker_thread = threading.Thread(target=stream_worker, daemon=True)
                worker_thread.start()

                while True:
                    try:
                        event = await asyncio.get_event_loop().run_in_executor(
                            None,
                            lambda: event_queue.get(timeout=0.1)
                        )
                    except queue.Empty:
                        if not worker_thread.is_alive():
                            # 线程已结束，排空残留事件
                            while True:
                                try:
                                    event = event_queue.get_nowait()
                                except queue.Empty:
                                    event = None
                                    break
                                if event is None:
                                    break
                                if isinstance(event, Exception):
                                    builder.ingest(StreamEvent(type="error", data=str(event)))
                                    yield f"data: {json.dumps({'type': 'error', 'data': str(event)}, ensure_ascii=False)}\n\n"
                                    break
                                builder.ingest(event)
                                event_data = {
                                    'type': event.type,
                                    'data': sanitize_stream_event_data(event.type, event.data),
                                    'step': event.step,
                                }
                                yield f"data: {json.dumps(event_data, ensure_ascii=False)}\n\n"
                            break
                        continue

                    if event is None:
                        break
                    if isinstance(event, Exception):
                        builder.ingest(StreamEvent(type="error", data=str(event)))
                        yield f"data: {json.dumps({'type': 'error', 'data': str(event)}, ensure_ascii=False)}\n\n"
                        break

                    builder.ingest(event)
                    event_data = {
                        'type': event.type,
                        'data': sanitize_stream_event_data(event.type, event.data),
                        'step': event.step,
                    }
                    yield f"data: {json.dumps(event_data, ensure_ascii=False)}\n\n"

                    if event.type not in ('answer_token', 'token'):
                        await asyncio.sleep(0.01)

        except Exception as e:
            logger.error(f"[Smart Stream] 失败: {str(e)}")
            builder.ingest(StreamEvent(type="error", data=str(e)))
            yield f"data: {json.dumps({'type': 'error', 'data': str(e)}, ensure_ascii=False)}\n\n"
        finally:
            try:
                if builder.answer:
                    builder.answer = sanitize_output_text(builder.answer)
                builder.save(tenant_id)
            except Exception as save_err:
                logger.warning(f"[Smart Stream] 保存追踪失败: {save_err}")

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/query-stream")
async def agent_query_stream(req: AgentQueryRequest, user: Optional[UserIdentity] = Depends(get_current_user)):
    """流式 Agent 查询 - 实时返回 LLM 推理过程（token 级别）"""
    validate_user_text(req.question)
    enforce_and_record_query(user, req.question, req.provider or "")
    start_time = time.time()
    tenant_id = get_tenant_id(user)
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
        builder = StreamTraceBuilder(req.question, mode="agent-stream")
        try:
            config = AgentConfig(
                max_iterations=req.max_iterations,
                enable_reflection=req.enable_reflection,
                enable_planning=req.enable_planning,
                verbose=False  # 禁用控制台输出
            )
            
            agent = RAGAgent(config=config, conversation_manager=_get_conversation_manager(tenant_id))
            
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
            
            # 在线程中运行流式生成器
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
                    builder.ingest(StreamEvent(type="error", data=str(event)))
                    yield f"data: {json.dumps({'type': 'error', 'data': str(event)}, ensure_ascii=False)}\n\n"
                    break
                
                builder.ingest(event)
                # 将 StreamEvent 转换为 JSON
                event_data = {
                    'type': event.type,
                    'data': sanitize_stream_event_data(event.type, event.data),
                    'step': event.step
                }
                
                # 记录最终答案
                if event.type == 'answer':
                    final_answer = sanitize_stream_event_data(event.type, event.data)
                
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
            builder.ingest(StreamEvent(type="error", data=str(e)))
            yield f"data: {json.dumps({'type': 'error', 'data': str(e)})}\n\n"
        finally:
            try:
                if final_answer and not builder.answer:
                    builder.answer = final_answer
                if builder.answer:
                    builder.answer = sanitize_output_text(builder.answer)
                builder.save(tenant_id)
            except Exception as save_err:
                logger.warning(f"[Agent Stream] 保存追踪失败: {save_err}")
            # 恢复原来的 provider
            if req.provider:
                Config.MODEL_PROVIDER = original_provider
                logger.info(f"[Agent Stream] 已恢复 MODEL_PROVIDER = {original_provider}")
    
    return StreamingResponse(generate(), media_type="text/event-stream")


@router.post("/analyze", dependencies=[Depends(require_roles("admin", "auditor")), Depends(require_policy("read", "eval"))])
async def analyze_knowledge_base(req: AnalyzeRequest, user: Optional[UserIdentity] = Depends(get_current_user)):
    """分析知识库结构"""
    try:
        agent = get_or_create_agent("manager", tenant_id=get_tenant_id(user))
        
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
async def research_topic(req: ResearchRequest, user: Optional[UserIdentity] = Depends(get_current_user)):
    """研究某个主题"""
    try:
        validate_user_text(req.topic, field_name="topic")
        agent = get_or_create_agent(req.agent_type, tenant_id=get_tenant_id(user))
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


@router.post("/execute-tool", dependencies=[Depends(require_roles("admin")), Depends(require_policy("execute", "tools"))])
async def execute_tool(tool_name: str, params: Dict[str, Any], user: Optional[UserIdentity] = Depends(get_current_user)):
    """直接执行单个工具"""
    try:
        agent = get_or_create_agent(tenant_id=get_tenant_id(user))
        
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
async def create_conversation(user: Optional[UserIdentity] = Depends(get_current_user)):
    """创建新的对话会话"""
    try:
        tenant_id = get_tenant_id(user)
        conv_manager = _get_conversation_manager(tenant_id)
        conversation_id = conv_manager.create_conversation()
        # 首条消息写入时再落盘，避免空会话出现在历史列表
        logger.info(f"[Conversation] 创建新会话: {conversation_id}")

        return ConversationCreateResponse(
            conversation_id=conversation_id,
            message="对话已创建"
        )
    except Exception as e:
        logger.error(f"[Conversation] 创建会话失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/conversation/{conversation_id}/history", response_model=ConversationHistoryResponse)
async def get_conversation_history(
    conversation_id: str,
    max_messages: Optional[int] = None,
    user: Optional[UserIdentity] = Depends(get_current_user),
):
    """获取对话历史"""
    try:
        agent = get_or_create_agent(tenant_id=get_tenant_id(user))
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
async def clear_conversation(conversation_id: str, user: Optional[UserIdentity] = Depends(get_current_user)):
    """清空对话历史"""
    try:
        agent = get_or_create_agent(tenant_id=get_tenant_id(user))
        agent.set_conversation(conversation_id)
        agent.clear_conversation()
        
        logger.info(f"[Conversation] 清空会话: {conversation_id}")
        
        return {"success": True, "message": "对话历史已清空"}
    except Exception as e:
        logger.error(f"[Conversation] 清空会话失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/conversation/list")
async def list_conversations(user: Optional[UserIdentity] = Depends(get_current_user)):
    """列出所有对话"""
    try:
        agent = get_or_create_agent(tenant_id=get_tenant_id(user))
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
async def delete_conversation(conversation_id: str, user: Optional[UserIdentity] = Depends(get_current_user)):
    """删除对话"""
    try:
        agent = get_or_create_agent(tenant_id=get_tenant_id(user))
        agent._conversation_manager.delete_conversation(conversation_id)
        
        logger.info(f"[Conversation] 删除会话: {conversation_id}")
        
        return {"success": True, "message": "对话已删除"}
    except Exception as e:
        logger.error(f"[Conversation] 删除会话失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ========================
# 图片生成 API
# ========================

class ImageGenRequest(BaseModel):
    """图片生成请求"""
    prompt: str = Field(..., description="图片描述")
    size: str = Field("1024x1024", description="图片尺寸")
    style: str = Field("vivid", description="风格: vivid/natural")
    quality: str = Field("standard", description="质量: standard/hd")


@router.post("/generate-image")
async def generate_image(req: ImageGenRequest, user: Optional[UserIdentity] = Depends(get_current_user)):
    """直接调用图片生成工具"""
    validate_user_text(req.prompt, field_name="prompt")
    logger.info(f"[ImageGen API] 请求生成图片, prompt: {req.prompt[:80]}...")

    try:
        agent = get_or_create_agent(tenant_id=get_tenant_id(user))
        tool = agent.tools.get("image_generation")
        if not tool:
            raise HTTPException(status_code=500, detail="图片生成工具未初始化")

        result = await asyncio.to_thread(
            tool.execute,
            prompt=req.prompt,
            size=req.size,
            style=req.style,
            quality=req.quality,
        )

        if result.success:
            return {
                "success": True,
                "image_url": result.data.get("image_url", ""),
                "filepath": result.data.get("filepath", ""),
                "revised_prompt": result.data.get("revised_prompt", req.prompt),
                "model": result.data.get("model", ""),
            }
        else:
            return {"success": False, "error": result.error}

    except Exception as e:
        logger.error(f"[ImageGen API] 失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
