"""API 路由定义"""
from fastapi import APIRouter, HTTPException, UploadFile, File, BackgroundTasks
from fastapi.responses import StreamingResponse
import json
import os
import re
import time
import asyncio
import traceback
import logging
import uuid
from pathlib import Path
from typing import Optional

from src.config.settings import Config
from src.core.document_processor import DocumentProcessor
from src.core.vector_store import VectorStore
from src.services.rag_assistant import RAGAssistant
from src.services.conversation_manager import ConversationManager
from src.services.ollama_client import generate as ollama_generate, OllamaError
from src.services.deepseek_client import generate as deepseek_generate, DeepSeekError
from src.models.schemas import QueryRequest, BuildRequest, ConversationMessage

# 配置日志
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

router = APIRouter()

# 全局状态管理
_assistant: Optional[RAGAssistant] = None
_conversation_manager: Optional[ConversationManager] = None
_build_progress = {
    "processing": False,
    "progress": 0,
    "total": 0,
    "current_file": "",
    "status": "idle"
}


def generate_trace_id() -> str:
    """生成请求追踪 ID"""
    return str(uuid.uuid4())[:8]


def parse_llm_json_response(response_text: str) -> str:
    """从 LLM 响应中解析 JSON answer 字段
    
    Args:
        response_text: LLM 原始响应文本
        
    Returns:
        解析出的答案文本，如果解析失败则返回原文本
    """
    s = response_text.strip()
    
    # 尝试直接解析完整 JSON
    try:
        parsed = json.loads(s)
        if isinstance(parsed, dict) and "answer" in parsed:
            return str(parsed.get("answer", "")).strip()
        return s
    except json.JSONDecodeError:
        pass
    
    # 尝试从文本中提取 JSON 对象
    start_idx = s.find('{')
    end_idx = s.rfind('}')
    if start_idx != -1 and end_idx != -1 and start_idx < end_idx:
        try:
            maybe_json = s[start_idx:end_idx+1]
            parsed = json.loads(maybe_json)
            if isinstance(parsed, dict) and "answer" in parsed:
                return str(parsed.get("answer", "")).strip()
        except json.JSONDecodeError:
            pass
        
        # 使用正则表达式提取 answer 字段
        answer_match = re.search(r'"answer"\s*:\s*"((?:[^"\\]|\\.)*)"', s)
        if answer_match:
            return answer_match.group(1).replace('\\"', '"').replace('\\n', '\n')
    
    return s


async def stream_text_in_chunks(text: str, chunk_size: int = 20):
    """分批流式发送文本，提高性能
    
    Args:
        text: 要发送的文本
        chunk_size: 每批发送的字符数
        
    Yields:
        SSE 格式的数据块
    """
    for i in range(0, len(text), chunk_size):
        chunk = text[i:i+chunk_size]
        yield f"data: {json.dumps({'type': 'content', 'data': chunk})}\n\n"
        await asyncio.sleep(0.05)  # 每批等待 50ms，比逐字符更高效


def get_conversation_manager() -> ConversationManager:
    """获取对话管理器实例"""
    global _conversation_manager
    if _conversation_manager is None:
        _conversation_manager = ConversationManager()
    return _conversation_manager


def get_assistant() -> Optional[RAGAssistant]:
    """获取 RAG 助手实例"""
    return _assistant


def set_assistant(assistant: Optional[RAGAssistant]):
    """设置 RAG 助手实例"""
    global _assistant
    _assistant = assistant


def load_assistant() -> bool:
    """加载助手"""
    global _assistant
    try:
        Config.validate()
        if _assistant is None:
            vector_store = VectorStore()
            vs = vector_store.load_vectorstore()
            if vs is None:
                return False
            _assistant = RAGAssistant(vector_store=vector_store)
            _assistant.setup_qa_chain()
        return True
    except Exception as e:
        print("加载助手失败:", e)
        return False


@router.get("/status")
def status():
    """获取系统状态"""
    loaded = load_assistant()
    return {"vector_store_loaded": loaded}


@router.post("/build")
def build(req: BuildRequest):
    """构建知识库"""
    try:
        processor = DocumentProcessor()
        chunks = processor.process_documents(req.documents_path)
        if not chunks:
            return {"success": False, "message": "未找到可处理的文档"}

        vector_store = VectorStore()
        vector_store.create_vectorstore(chunks)
        
        # 重新加载 assistant
        global _assistant
        _assistant = None
        load_assistant()  # 立即重新加载
        return {"success": True, "processed_chunks": len(chunks)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def build_knowledge_base_background(documents_path: str):
    """后台构建知识库并更新进度"""
    global _build_progress, _assistant
    try:
        _build_progress["processing"] = True
        _build_progress["status"] = "reading"
        _build_progress["current_file"] = "扫描文档..."
        _build_progress["progress"] = 0
        _build_progress["total"] = 0
        
        processor = DocumentProcessor()
        chunks = processor.process_documents(documents_path)
        
        if not chunks:
            _build_progress["status"] = "error"
            _build_progress["current_file"] = "未找到可处理的文档"
            _build_progress["processing"] = False
            return
        
        _build_progress["total"] = len(chunks)
        _build_progress["status"] = "building"
        _build_progress["current_file"] = "生成向量..."
        
        vector_store = VectorStore()
        
        # 分批添加文档，逐步更新进度（每50个一批）
        batch_size = 50
        for i in range(0, len(chunks), batch_size):
            batch = chunks[i:i+batch_size]
            if i == 0:
                vector_store.create_vectorstore(batch)
            else:
                vector_store.add_documents(batch)
            
            _build_progress["progress"] = min(i + batch_size, len(chunks))
            _build_progress["current_file"] = f"已处理 {_build_progress['progress']}/{len(chunks)} 个文档块"
            time.sleep(0.1)
        
        # 重新加载 assistant
        _assistant = None
        load_assistant()
        
        _build_progress["progress"] = len(chunks)
        _build_progress["status"] = "completed"
        _build_progress["current_file"] = "完成"
        _build_progress["processing"] = False
        
    except Exception as e:
        _build_progress["status"] = "error"
        _build_progress["current_file"] = f"错误: {str(e)}"
        _build_progress["processing"] = False


@router.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    """上传文件到文档目录"""
    try:
        documents_dir = Path("./documents")
        documents_dir.mkdir(exist_ok=True)
        
        file_path = documents_dir / file.filename
        contents = await file.read()
        with open(file_path, "wb") as f:
            f.write(contents)
        
        return {
            "success": True,
            "filename": file.filename,
            "size": len(contents),
            "path": str(file_path)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/build-start")
async def build_start(background_tasks: BackgroundTasks):
    """启动后台知识库构建"""
    if _build_progress["processing"]:
        return {"success": False, "message": "已有构建任务进行中"}
    
    _build_progress["processing"] = True
    _build_progress["progress"] = 0
    _build_progress["total"] = 0
    _build_progress["status"] = "processing"
    _build_progress["current_file"] = "初始化..."
    
    background_tasks.add_task(build_knowledge_base_background, "./documents")
    return {"success": True, "message": "构建任务已启动"}


@router.get("/build-progress")
async def build_progress_endpoint():
    """获取构建进度"""
    return _build_progress


@router.get("/conversations")
async def list_conversations():
    """列出所有对话历史"""
    try:
        conv_manager = get_conversation_manager()
        conversation_ids = conv_manager.list_conversations()
        
        conversations = []
        for conv_id in conversation_ids:
            # 加载对话以获取摘要信息
            conv_manager.load_conversation(conv_id)
            history = conv_manager.get_history(conv_id, max_messages=2)
            
            # 获取第一条用户消息作为标题
            title = "新对话"
            last_time = None
            message_count = len(conv_manager.get_history(conv_id))
            
            for msg in history:
                if msg.role == "user":
                    title = msg.content[:50] + ("..." if len(msg.content) > 50 else "")
                    break
            
            # 获取最后消息时间
            full_history = conv_manager.get_history(conv_id)
            if full_history:
                last_time = full_history[-1].timestamp
            
            conversations.append({
                "id": conv_id,
                "title": title,
                "message_count": message_count,
                "last_time": last_time
            })
        
        # 按时间倒序排列
        conversations.sort(key=lambda x: x["last_time"] or "", reverse=True)
        
        return {"success": True, "conversations": conversations}
    except Exception as e:
        logger.error(f"获取对话列表失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/conversations/{conversation_id}")
async def get_conversation(conversation_id: str):
    """获取单个对话的详细内容"""
    try:
        conv_manager = get_conversation_manager()
        
        # 尝试加载对话
        if not conv_manager.load_conversation(conversation_id):
            raise HTTPException(status_code=404, detail="对话不存在")
        
        history = conv_manager.get_history(conversation_id)
        
        # 转换为可序列化的格式
        messages = [
            {
                "role": msg.role,
                "content": msg.content,
                "timestamp": msg.timestamp
            }
            for msg in history
        ]
        
        return {
            "success": True,
            "conversation_id": conversation_id,
            "messages": messages
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取对话详情失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/conversations/{conversation_id}")
async def delete_conversation(conversation_id: str):
    """删除指定对话"""
    try:
        conv_manager = get_conversation_manager()
        conv_manager.delete_conversation(conversation_id)
        return {"success": True, "message": "对话已删除"}
    except Exception as e:
        logger.error(f"删除对话失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/query-stream")
async def query_stream(req: QueryRequest):
    """流式查询知识库（SSE）"""
    trace_id = generate_trace_id()
    start_time = time.time()
    logger.info(f"[{trace_id}] 开始处理查询 - 问题: {req.question[:100]}..., Provider: {req.provider}")
    
    if not load_assistant():
        error_msg = "向量数据库未加载。请先构建或确认数据库目录。"
        async def error_generate():
            yield f"data: {json.dumps({'type': 'error', 'data': error_msg})}\n\n"
        return StreamingResponse(error_generate(), media_type="text/event-stream")
    
    req_provider = (req.provider or Config.MODEL_PROVIDER or '').strip().lower()
    
    # 获取对话管理器并处理对话历史
    conv_manager = get_conversation_manager()
    conversation_id = req.conversation_id
    
    # 如果没有提供会话ID，创建新会话
    if not conversation_id:
        conversation_id = conv_manager.create_conversation()
        logger.info(f"[{trace_id}] 创建新会话: {conversation_id}")
    
    # 添加用户消息到历史
    conv_manager.add_message(conversation_id, "user", req.question)
    
    # 获取历史消息
    history = req.history if req.history else conv_manager.get_history(conversation_id, max_messages=6)
    logger.info(f"[{trace_id}] 会话 {conversation_id} - 历史消息数: {len(history)}")
    
    async def generate():
        try:
            if req_provider == 'ollama':
                try:
                    assistant = get_assistant()
                    if assistant is None:
                        load_assistant()
                        assistant = get_assistant()
                    
                    logger.info(f"[Ollama] 开始检索文档...")
                    docs = assistant.retrieve_documents(req.question, k=Config.TOP_K)
                    logger.info(f"[Ollama] 问题: {req.question}")
                    logger.info(f"[Ollama] 检索到 {len(docs)} 个文档")
                    logger.debug(f"[Ollama] 问题: {req.question}")
                    logger.debug(f"[Ollama] 检索到 {len(docs)} 个文档")
                    
                    # 如果检索结果为空（由于相似度阈值过滤）
                    if not docs:
                        similarity_threshold = getattr(Config, 'SIMILARITY_THRESHOLD', None)
                        if similarity_threshold is not None:
                            logger.debug(f"[Ollama] 知识库中未找到与您的问题相关的文档（相似度阈值: {similarity_threshold})")
                            yield f"data: {json.dumps({'type': 'sources', 'data': []})}\n\n"
                            yield f"data: {json.dumps({'type': 'content', 'data': '我无法根据现有知识库中的信息回答这个问题'})}\n\n"
                            yield f"data: {json.dumps({'type': 'done'})}\n\n"
                            return
                    
                    contexts = []
                    for doc in docs:
                        if hasattr(doc, "page_content"):
                            contexts.append(doc.page_content)
                        elif isinstance(doc, dict):
                            contexts.append(doc.get("page_content") or doc.get("content") or str(doc))
                        else:
                            contexts.append(str(doc))
                    
                    context_text = "\n\n".join(contexts)
                    logger.debug(f"[Ollama] 上下文总长度: {len(context_text)} 字符")
                    
                    # 构建对话历史上下文
                    conversation_context = ""
                    if history and len(history) > 0:
                        # 前端已经排除了当前用户消息，这里直接使用
                        recent_history = history[-6:]  # 最多6条消息（3轮对话）
                        logger.info(f"[Conversation] 使用历史消息数: {len(recent_history)}")
                        if recent_history:
                            conversation_context = "【对话历史】\n"
                            for msg in recent_history:
                                role_name = "用户" if msg.role == "user" else "助手"
                                conversation_context += f"{role_name}: {msg.content}\n"
                            conversation_context += "\n"
                            logger.info(f"[Conversation] 对话历史上下文:\n{conversation_context}")
                    
                    prompt = (
                        "你必须只返回一个有效的 JSON 对象，格式严格如下:\n"
                        "{\"answer\": \"这里是你的中文回答\"}\n"
                        "重要规则：\n"
                        "1. 只输出 JSON 对象，不要输出任何其他文本\n"
                        "2. answer 字段的值必须是一段完整、连贯的中文回答\n"
                        "3. 不要在 JSON 前后添加任何额外的字符或解释\n"
                        "4. 确保 JSON 格式完全有效\n"
                        "5. 必须仅基于以下上下文回答，不能使用常识\n"
                        "5. 必须以提供的上下文为唯一信息源，不要引入外部未提供的信息。\n"
                        "6. 如果用户的问题是一个实体名或关键词，请直接从上下文中提取并用一到两句简短中文陈述该实体的事实。\n"
                        "7. 只有在上下文确实不包含任何与问题相关的事实时，answer 字段才应为：'我无法根据现有知识库中的信息回答这个问题'。\n"
                        f"{conversation_context}"
                        f"上下文信息:\n{context_text}\n\n问题: {req.question}\n\n"
                        "回答示例：{\"answer\": \"这是示例答案\"}\n"
                    )
                    
                    model_name = req.ollama_model or Config.OLLAMA_MODEL
                    api_url = req.ollama_api_url or Config.OLLAMA_API_URL
                    
                    sources = []
                    for doc in docs:
                        src = getattr(doc, 'metadata', {}).get('source', '未知来源') if hasattr(doc, 'metadata') else '未知来源'
                        preview = getattr(doc, 'page_content', '')
                        preview = preview[:200].replace('\n', ' ') if preview else ''
                        sources.append({"source": src, "preview": preview})
                    
                    # 先发送会话ID，确保前端立即获取
                    yield f"data: {json.dumps({'type': 'conversation_id', 'data': conversation_id})}\n\n"
                    
                    meta_info = {'returned': len(docs)}
                    if getattr(Config, 'MAX_DISTANCE', None) is not None:
                        meta_info['note'] = f"应用 MAX_DISTANCE={Config.MAX_DISTANCE} 进行过滤"
                    yield f"data: {json.dumps({'type': 'sources', 'data': sources, 'meta': meta_info})}\n\n"
                    
                    # 调用 Ollama 生成
                    logger.info(f"[Ollama] 开始调用AI生成答案 - 模型: {model_name}")
                    ai_start = time.time()
                    ollama_result = ollama_generate(
                        model=model_name,
                        prompt=prompt,
                        max_tokens=Config.MAX_TOKENS,
                        temperature=Config.TEMPERATURE,
                        api_url=api_url,
                        stream=False
                    )
                    
                    ai_elapsed = time.time() - ai_start
                    logger.info(f"[{trace_id}] Ollama AI调用完成 - 耗时: {ai_elapsed:.2f}秒")
                    
                    # 使用公共函数解析 Ollama 返回
                    s = str(ollama_result).strip()
                    logger.info(f"[{trace_id}] Ollama 原始返回长度: {len(s)} 字符")
                    logger.debug(f"[{trace_id}] Ollama 原始返回 (前200字): {s[:200]}")
                    
                    final_text = parse_llm_json_response(s)

                    # 分批流式发送（性能优化：每批20字符）
                    if final_text:
                        logger.info(f"[{trace_id}] 开始流式返回答案，长度: {len(final_text)} 字符")
                        async for chunk in stream_text_in_chunks(final_text, chunk_size=20):
                            yield chunk
                        
                        # 保存助手的回复到对话历史
                        conv_manager.add_message(conversation_id, "assistant", final_text, save_to_disk=True)
                        logger.info(f"[Conversation] 保存助手回复到会话 {conversation_id}")

                    total_elapsed = time.time() - start_time
                    logger.info(f"[Ollama] 完整流程完成 - 总耗时: {total_elapsed:.2f}秒")
                    
                    yield f"data: {json.dumps({'type': 'done'})}\n\n"
                    
                except OllamaError as oe:
                    print(f"调用本地 Ollama 失败: {oe}")
                    yield f"data: {json.dumps({'type': 'error', 'data': f'Ollama 错误: {str(oe)}'})}\n\n"
                except Exception as e:
                    print(f"Ollama 分支异常: {e}")
                    traceback.print_exc()
                    yield f"data: {json.dumps({'type': 'error', 'data': f'Ollama 处理失败: {str(e)}'})}\n\n"
            elif req_provider == 'deepseek':
                try:
                    logger.info(f"[DeepSeek] 开始处理请求")
                    assistant = get_assistant()
                    if assistant is None:
                        load_assistant()
                        assistant = get_assistant()

                    logger.info(f"[DeepSeek] 开始检索文档...")
                    docs = assistant.retrieve_documents(req.question, k=Config.TOP_K)
                    logger.info(f"[DeepSeek] 检索到 {len(docs)} 个文档")
                    if not docs:
                        similarity_threshold = getattr(Config, 'SIMILARITY_THRESHOLD', None)
                        if similarity_threshold is not None:
                            yield f"data: {json.dumps({'type': 'sources', 'data': []})}\n\n"
                            yield f"data: {json.dumps({'type': 'content', 'data': '我无法根据现有知识库中的信息回答这个问题'})}\n\n"
                            yield f"data: {json.dumps({'type': 'done'})}\n\n"
                            return

                    contexts = []
                    for doc in docs:
                        if hasattr(doc, 'page_content'):
                            contexts.append(doc.page_content)
                        elif isinstance(doc, dict):
                            contexts.append(doc.get('page_content') or doc.get('content') or str(doc))
                        else:
                            contexts.append(str(doc))

                    context_text = "\n\n".join(contexts)

                    # 构建对话历史上下文
                    conversation_context = ""
                    if history and len(history) > 0:
                        recent_history = history[-6:]  # 最多6条消息（3轮对话）
                        logger.info(f"[Conversation] 使用历史消息数: {len(recent_history)}")
                        if recent_history:
                            conversation_context = "【对话历史】\n"
                            for msg in recent_history:
                                role_name = "用户" if msg.role == "user" else "助手"
                                conversation_context += f"{role_name}: {msg.content}\n"
                            conversation_context += "\n"

                    prompt = (
                        "你必须只返回一个有效的 JSON 对象，格式严格如下:\n"
                        '{"answer": "这里是你的中文回答"}\n'
                        "重要规则：只能基于下面的上下文回答，不要添加外部信息。\n\n"
                        f"{conversation_context}"
                        f"上下文信息:\n{context_text}\n\n问题: {req.question}\n"
                    )

                    model_name = req.deepseek_model or Config.LLM_MODEL
                    api_url = req.deepseek_api_url or Config.DEEPSEEK_API_URL
                    api_key = req.deepseek_api_key or Config.DEEPSEEK_API_KEY

                    sources = []
                    for doc in docs:
                        src = getattr(doc, 'metadata', {}).get('source', '未知来源') if hasattr(doc, 'metadata') else '未知来源'
                        preview = getattr(doc, 'page_content', '')
                        preview = preview[:200].replace('\n', ' ') if preview else ''
                        sources.append({"source": src, "preview": preview})

                    # 先发送会话ID，确保前端立即获取
                    yield f"data: {json.dumps({'type': 'conversation_id', 'data': conversation_id})}\n\n"
                    
                    yield f"data: {json.dumps({'type': 'sources', 'data': sources})}\n\n"

                    # 调用 DeepSeek
                    logger.info(f"[{trace_id}] DeepSeek 开始调用AI生成答案 - 模型: {model_name}")
                    ai_start = time.time()
                    ds_result = deepseek_generate(
                        model=model_name,
                        prompt=prompt,
                        max_tokens=Config.MAX_TOKENS,
                        temperature=Config.TEMPERATURE,
                        api_url=api_url,
                        api_key=api_key,
                        stream=False,
                    )
                    
                    ai_elapsed = time.time() - ai_start
                    logger.info(f"[{trace_id}] DeepSeek AI调用完成 - 耗时: {ai_elapsed:.2f}秒")

                    # 使用公共函数解析 DeepSeek 返回
                    s = str(ds_result).strip()
                    logger.info(f"[{trace_id}] DeepSeek 原始返回长度: {len(s)} 字符")
                    
                    final_text = parse_llm_json_response(s)

                    # 分批流式发送（性能优化：每批20字符）
                    if final_text:
                        async for chunk in stream_text_in_chunks(final_text, chunk_size=20):
                            yield chunk
                        
                        # 保存助手的回复到对话历史
                        conv_manager.add_message(conversation_id, "assistant", final_text, save_to_disk=True)
                        logger.info(f"[{trace_id}] 保存助手回复到会话 {conversation_id}")

                    yield f"data: {json.dumps({'type': 'done'})}\n\n"
                except DeepSeekError as dse:
                    yield f"data: {json.dumps({'type': 'error', 'data': f'DeepSeek 错误: {str(dse)}'})}\n\n"
                except Exception as e:
                    traceback.print_exc()
                    yield f"data: {json.dumps({'type': 'error', 'data': f'DeepSeek 处理失败: {str(e)}'})}\n\n"
            else:
                # 默认使用 RAGAssistant
                try:
                    assistant = get_assistant()
                    method = req.method or 'vector'
                    rerank = bool(req.rerank) if req.rerank is not None else False
                    top_k = req.top_k or Config.TOP_K
                    
                    # 使用对话历史调用query
                    # 前端已经排除了当前用户消息，直接使用
                    if history and len(history) > 0:
                        logger.info(f"[Conversation] 使用历史消息数: {len(history)}")
                    result = await asyncio.to_thread(
                        assistant.query, 
                        req.question, 
                        True, 
                        method, 
                        top_k, 
                        rerank, 
                        history if history else None
                    )
                    answer = result.get("answer", "")
                    sources = []
                    if "sources" in result and result["sources"]:
                        for doc in result["sources"]:
                            src = doc.metadata.get("source", "未知来源")
                            preview = getattr(doc, "page_content", "")
                            preview = preview[:200].replace("\n", " ") if preview else ""
                            sources.append({"source": src, "preview": preview})
                    
                    # 先发送会话ID，确保前端立即获取
                    yield f"data: {json.dumps({'type': 'conversation_id', 'data': conversation_id})}\n\n"
                    
                    yield f"data: {json.dumps({'type': 'sources', 'data': sources})}\n\n"
                    
                    for char in answer:
                        yield f"data: {json.dumps({'type': 'content', 'data': char})}\n\n"
                        await asyncio.sleep(0.01)
                    
                    # 保存助手的回复到对话历史
                    conv_manager.add_message(conversation_id, "assistant", answer, save_to_disk=True)
                    logger.info(f"[Conversation] 保存助手回复到会话 {conversation_id}")
                    
                    yield f"data: {json.dumps({'type': 'done'})}\n\n"
                except Exception as query_err:
                    print(f"RAG 查询异常: {query_err}")
                    traceback.print_exc()
                    err_detail = str(query_err)
                    if "APIConnectionError" in err_detail or "Connection" in err_detail:
                        err_detail = f"模型 API 连接失败。请检查网络连接和 API 配置\n原始错误: {err_detail}"
                    yield f"data: {json.dumps({'type': 'error', 'data': err_detail})}\n\n"
                
        except Exception as e:
            traceback.print_exc()
            yield f"data: {json.dumps({'type': 'error', 'data': f'查询处理异常: {str(e)}'})}\n\n"
    
    return StreamingResponse(generate(), media_type="text/event-stream")
