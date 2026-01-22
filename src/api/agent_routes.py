"""Agent API 路由 - 提供 Agent 相关的 REST API"""

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
import json
import asyncio
import logging
import time

from src.agent.rag_agent import RAGAgent, AgentBuilder
from src.agent.base import AgentConfig, AgentResponse
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
    max_iterations: int = Field(10, description="最大推理迭代次数")
    enable_reflection: bool = Field(True, description="是否启用反思机制")
    enable_planning: bool = Field(True, description="是否启用规划能力")
    chat_history: Optional[str] = Field(None, description="历史对话")


class AgentQueryResponse(BaseModel):
    """Agent 查询响应"""
    success: bool
    answer: str
    thought_process: List[Dict[str, Any]] = []
    tools_used: List[str] = []
    iterations: int = 0
    final_reflection: Optional[str] = None


class SmartQueryRequest(BaseModel):
    """智能查询请求"""
    question: str
    agent_type: str = "full"


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
    
    # 如果指定了 provider，临时设置到 Config 中
    original_provider = Config.MODEL_PROVIDER
    if req.provider:
        Config.MODEL_PROVIDER = req.provider
        logger.info(f"[Agent Query] 已设置 MODEL_PROVIDER = {req.provider}")
    
    try:
        # 创建 Agent
        config = AgentConfig(
            max_iterations=req.max_iterations,
            enable_reflection=req.enable_reflection,
            enable_planning=req.enable_planning,
            verbose=True
        )
        
        agent = RAGAgent(config=config)
        logger.info(f"[Agent Query] Agent已创建，注册工具数: {len(agent.tools)}")
        
        # 执行查询
        logger.info(f"[Agent Query] 开始执行推理循环...")
        result = await asyncio.to_thread(
            agent.run,
            req.question,
            req.chat_history or ""
        )
        
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
    finally:
        # 恢复原来的 provider
        if req.provider:
            Config.MODEL_PROVIDER = original_provider
            logger.info(f"[Agent Query] 已恢复 MODEL_PROVIDER = {original_provider}")


@router.post("/smart-query")
async def smart_query(req: SmartQueryRequest):
    """智能查询 - 自动判断使用 RAG 还是 Agent"""
    try:
        agent = get_or_create_agent(req.agent_type)
        result = await asyncio.to_thread(agent.smart_query, req.question)
        
        return {
            "success": result.success,
            "answer": result.answer,
            "tools_used": result.tools_used,
            "iterations": result.iterations,
            "is_simple": result.iterations == 1 and result.tools_used == ["rag_search"]
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/query-stream")
async def agent_query_stream(req: AgentQueryRequest):
    """流式 Agent 查询 - 实时返回推理过程"""
    start_time = time.time()
    logger.info(f"[Agent Stream] 开始处理流式查询 - 问题: {req.question[:100]}...")
    logger.info(f"[Agent Stream] 配置 - 类型: {req.agent_type}, Provider: {req.provider}")
    
    # 如果指定了 provider，临时设置到 Config 中
    original_provider = Config.MODEL_PROVIDER
    if req.provider:
        Config.MODEL_PROVIDER = req.provider
        logger.info(f"[Agent Stream] 已设置 MODEL_PROVIDER = {req.provider}")
    
    async def generate():
        try:
            config = AgentConfig(
                max_iterations=req.max_iterations,
                enable_reflection=req.enable_reflection,
                enable_planning=req.enable_planning,
                verbose=False  # 禁用控制台输出
            )
            
            agent = RAGAgent(config=config)
            
            yield f"data: {json.dumps({'type': 'start', 'data': '开始推理...'})}\n\n"
            
            # 执行推理
            result = await asyncio.to_thread(
                agent.run,
                req.question,
                req.chat_history or ""
            )
            
            # 发送思考过程
            for step in result.thought_process:
                yield f"data: {json.dumps({'type': 'thought', 'data': {'step': step.step, 'thought': step.thought}}, ensure_ascii=False)}\n\n"
                await asyncio.sleep(0.1)
                
                if step.action:
                    yield f"data: {json.dumps({'type': 'action', 'data': {'tool': step.action, 'input': step.action_input}}, ensure_ascii=False)}\n\n"
                    await asyncio.sleep(0.1)
                
                if step.observation:
                    # 构建观察结果数据，包含文本和结构化数据
                    observation_payload = {
                        'text': step.observation[:500],
                        'data': step.observation_data if hasattr(step, 'observation_data') and step.observation_data else None
                    }
                    yield f"data: {json.dumps({'type': 'observation', 'data': observation_payload}, ensure_ascii=False)}\n\n"
                    await asyncio.sleep(0.1)
            
            # 发送最终答案
            yield f"data: {json.dumps({'type': 'answer', 'data': result.answer}, ensure_ascii=False)}\n\n"
            
            # 发送元信息
            yield f"data: {json.dumps({'type': 'meta', 'data': {'tools_used': result.tools_used, 'iterations': result.iterations}}, ensure_ascii=False)}\n\n"
            
            # 记录完成日志
            total_elapsed = time.time() - start_time
            logger.info(f"[Agent Stream] 查询完成 - 总耗时: {total_elapsed:.2f}秒, Agent类型: {req.agent_type}, 迭代数: {result.iterations}")
            
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
            
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
