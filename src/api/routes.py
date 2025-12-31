"""API 路由定义"""
from fastapi import APIRouter, HTTPException, UploadFile, File, BackgroundTasks
from fastapi.responses import StreamingResponse
import json
import os
import time
import asyncio
import traceback
from pathlib import Path
from typing import Optional

from src.config.settings import Config
from src.core.document_processor import DocumentProcessor
from src.core.vector_store import VectorStore
from src.services.rag_assistant import RAGAssistant
from src.services.ollama_client import generate as ollama_generate, OllamaError
from src.models.schemas import QueryRequest, BuildRequest

router = APIRouter()

# 全局状态管理
_assistant: Optional[RAGAssistant] = None
_build_progress = {
    "processing": False,
    "progress": 0,
    "total": 0,
    "current_file": "",
    "status": "idle"
}


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


@router.post("/query-stream")
async def query_stream(req: QueryRequest):
    """流式查询端点"""
    if not load_assistant():
        error_msg = "向量数据库未加载。请先构建或确认数据库目录。"
        async def error_generate():
            yield f"data: {json.dumps({'type': 'error', 'data': error_msg})}\n\n"
        return StreamingResponse(error_generate(), media_type="text/event-stream")
    
    req_provider = (req.provider or Config.MODEL_PROVIDER or '').strip().lower()
    
    async def generate():
        try:
            if req_provider == 'ollama':
                try:
                    assistant = get_assistant()
                    if assistant is None:
                        load_assistant()
                        assistant = get_assistant()
                    
                    docs = assistant.retrieve_documents(req.question, k=Config.TOP_K)
                    print(f"[DEBUG] 问题: {req.question}")
                    print(f"[DEBUG] 检索到 {len(docs)} 个文档")
                    
                    # 如果检索结果为空（由于相似度阈值过滤）
                    if not docs:
                        similarity_threshold = getattr(Config, 'SIMILARITY_THRESHOLD', None)
                        if similarity_threshold is not None:
                            print(f"[DEBUG] 知识库中未找到与您的问题相关的文档（相似度阈值: {similarity_threshold}）")
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
                    print(f"[DEBUG] 上下文总长度: {len(context_text)} 字符")
                    
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
                        "7. 只有在上下文确实不包含任何与问题相关的事实时，answer 字段才应为：'我无法根据现有知识库中的信息回答这个问题'。\n\n"
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
                    
                    meta_info = {'returned': len(docs)}
                    if getattr(Config, 'MAX_DISTANCE', None) is not None:
                        meta_info['note'] = f"应用 MAX_DISTANCE={Config.MAX_DISTANCE} 进行过滤"
                    yield f"data: {json.dumps({'type': 'sources', 'data': sources, 'meta': meta_info})}\n\n"
                    
                    # 调用 Ollama 生成
                    ollama_result = ollama_generate(
                        model=model_name,
                        prompt=prompt,
                        max_tokens=Config.MAX_TOKENS,
                        temperature=Config.TEMPERATURE,
                        api_url=api_url,
                        stream=False
                    )
                    
                    # 解析 Ollama 返回
                    final_text = ""
                    s = str(ollama_result).strip()
                    print(f"[DEBUG] Ollama 原始返回 (前200字): {s[:200]}")
                    
                    try:
                        parsed = json.loads(s)
                        if isinstance(parsed, dict) and "answer" in parsed:
                            final_text = str(parsed.get("answer", "")).strip()
                        else:
                            final_text = s
                    except Exception:
                        start_idx = s.find('{')
                        end_idx = s.rfind('}')
                        if start_idx != -1 and end_idx != -1 and start_idx < end_idx:
                            try:
                                maybe_json = s[start_idx:end_idx+1]
                                parsed2 = json.loads(maybe_json)
                                if isinstance(parsed2, dict) and "answer" in parsed2:
                                    final_text = str(parsed2.get("answer", "")).strip()
                                else:
                                    final_text = ""
                            except Exception:
                                import re
                                answer_match = re.search(r'"answer"\s*:\s*"([^"]*(?:\\"[^"]*)*)"', s)
                                if answer_match:
                                    final_text = answer_match.group(1).replace('\\"', '"')
                                else:
                                    final_text = ""
                        else:
                            final_text = s

                    # 逐字符发送
                    if final_text:
                        for char in final_text:
                            yield f"data: {json.dumps({'type': 'content', 'data': char})}\n\n"
                            await asyncio.sleep(0.01)

                    yield f"data: {json.dumps({'type': 'done'})}\n\n"
                    
                except OllamaError as oe:
                    print(f"调用本地 Ollama 失败: {oe}")
                    yield f"data: {json.dumps({'type': 'error', 'data': f'Ollama 错误: {str(oe)}'})}\n\n"
                except Exception as e:
                    print(f"Ollama 分支异常: {e}")
                    traceback.print_exc()
                    yield f"data: {json.dumps({'type': 'error', 'data': f'Ollama 处理失败: {str(e)}'})}\n\n"
            else:
                # 默认使用 RAGAssistant
                try:
                    assistant = get_assistant()
                    method = req.method or 'vector'
                    rerank = bool(req.rerank) if req.rerank is not None else False
                    top_k = req.top_k or Config.TOP_K
                    result = await asyncio.to_thread(assistant.query, req.question, True, method, top_k, rerank)
                    answer = result.get("answer", "")
                    sources = []
                    if "sources" in result and result["sources"]:
                        for doc in result["sources"]:
                            src = doc.metadata.get("source", "未知来源")
                            preview = getattr(doc, "page_content", "")
                            preview = preview[:200].replace("\n", " ") if preview else ""
                            sources.append({"source": src, "preview": preview})
                    
                    yield f"data: {json.dumps({'type': 'sources', 'data': sources})}\n\n"
                    
                    for char in answer:
                        yield f"data: {json.dumps({'type': 'content', 'data': char})}\n\n"
                        await asyncio.sleep(0.01)
                    
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
