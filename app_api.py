"""轻量 REST API，包装现有的 RAG 功能，供前端调用"""
from fastapi import FastAPI, HTTPException, UploadFile, File, BackgroundTasks
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional
import traceback
import json
import os
import shutil
import time
from pathlib import Path
import asyncio

from config import Config
from rag_assistant import RAGAssistant
from document_processor import DocumentProcessor
from vector_store import VectorStore
from ollama_client import generate as ollama_generate, OllamaError


class QueryRequest(BaseModel):
    question: str
    provider: Optional[str] = None
    ollama_model: Optional[str] = None
    ollama_api_url: Optional[str] = None
    # 新增检索选项
    method: Optional[str] = None  # 'vector' | 'bm25' | 'hybrid'
    rerank: Optional[bool] = None
    top_k: Optional[int] = None


class BuildRequest(BaseModel):
    documents_path: str


# 全局状态管理
build_progress = {
    "processing": False,
    "progress": 0,
    "total": 0,
    "current_file": "",
    "status": "idle"
}

app = FastAPI(title="RAG Knowledge API")

# 允许前端跨域访问（开发阶段）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


assistant: RAGAssistant = None


def load_assistant() -> bool:
    global assistant
    try:
        Config.validate()
        if assistant is None:
            vector_store = VectorStore()
            vs = vector_store.load_vectorstore()
            if vs is None:
                return False
            assistant = RAGAssistant(vector_store=vector_store)
            assistant.setup_qa_chain()
        return True
    except Exception as e:
        print("加载助手失败:", e)
        return False


@app.get("/api/status")
def status():
    loaded = load_assistant()
    return {"vector_store_loaded": loaded}


@app.post("/api/build")
def build(req: BuildRequest):
    try:
        # 使用 DocumentProcessor 构建知识库
        processor = DocumentProcessor()
        chunks = processor.process_documents(req.documents_path)
        if not chunks:
            return {"success": False, "message": "未找到可处理的文档"}

        vector_store = VectorStore()
        vector_store.create_vectorstore(chunks)
        # 重新加载 assistant 下次查询可用
        global assistant
        assistant = None
        return {"success": True, "processed_chunks": len(chunks)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def build_knowledge_base_background(documents_path: str):
    """后台构建知识库并更新进度"""
    global build_progress
    try:
        build_progress["processing"] = True
        build_progress["status"] = "reading"
        build_progress["current_file"] = "扫描文档..."
        build_progress["progress"] = 0
        build_progress["total"] = 0
        
        processor = DocumentProcessor()
        chunks = processor.process_documents(documents_path)
        
        if not chunks:
            build_progress["status"] = "error"
            build_progress["current_file"] = "未找到可处理的文档"
            build_progress["processing"] = False
            return
        
        build_progress["total"] = len(chunks)
        build_progress["status"] = "building"
        build_progress["current_file"] = "生成向量..."
        
        vector_store = VectorStore()
        
        # 分批添加文档，逐步更新进度（每50个一批）
        batch_size = 50
        for i in range(0, len(chunks), batch_size):
            batch = chunks[i:i+batch_size]
            if i == 0:
                # 第一批：创建向量库
                vector_store.create_vectorstore(batch)
            else:
                # 后续批次：添加到现有向量库
                vector_store.add_documents(batch)
            
            # 更新进度
            build_progress["progress"] = min(i + batch_size, len(chunks))
            build_progress["current_file"] = f"已处理 {build_progress['progress']}/{len(chunks)} 个文档块"
            
            # 模拟进度，避免过快
            time.sleep(0.1)
        
        # 重新加载 assistant
        global assistant
        assistant = None
        load_assistant()
        
        build_progress["progress"] = len(chunks)
        build_progress["status"] = "completed"
        build_progress["current_file"] = "完成"
        build_progress["processing"] = False
        
    except Exception as e:
        build_progress["status"] = "error"
        build_progress["current_file"] = f"错误: {str(e)}"
        build_progress["processing"] = False


@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...)):
    """上传文件到文档目录"""
    try:
        documents_dir = Path("./documents")
        documents_dir.mkdir(exist_ok=True)
        
        file_path = documents_dir / file.filename
        
        # 保存文件
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


@app.post("/api/build-start")
async def build_start(background_tasks: BackgroundTasks):
    """启动后台知识库构建"""
    if build_progress["processing"]:
        return {"success": False, "message": "已有构建任务进行中"}
    
    build_progress["processing"] = True
    build_progress["progress"] = 0
    build_progress["total"] = 0
    build_progress["status"] = "processing"
    build_progress["current_file"] = "初始化..."
    
    background_tasks.add_task(build_knowledge_base_background, "./documents")
    return {"success": True, "message": "构建任务已启动"}


@app.get("/api/build-progress")
async def build_progress_endpoint():
    """获取构建进度"""
    return build_progress


@app.post("/api/query-stream")
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
                    if assistant is None:
                        load_assistant()
                    
                    docs = assistant.retrieve_documents(req.question, k=Config.TOP_K)
                    print(f"[DEBUG] 问题: {req.question}")
                    print(f"[DEBUG] 检索到 {len(docs)} 个文档")
                    
                    # 如果检索结果为空（由于相似度阈值过滤）
                    if not docs:
                        similarity_threshold = getattr(Config, 'SIMILARITY_THRESHOLD', None)
                        if similarity_threshold is not None:
                            error_msg = f"知识库中未找到与您的问题相关的文档（相似度阈值: {similarity_threshold}）。请尝试用不同的关键词进行查询。"
                            print(f"[DEBUG] {error_msg}")
                            yield f"data: {json.dumps({'type': 'sources', 'data': []})}\n\n"
                            yield f"data: {json.dumps({'type': 'content', 'data': '我无法根据现有知识库中的信息回答这个问题'})}\n\n"
                            yield f"data: {json.dumps({'type': 'done'})}\n\n"
                            return
                    
                    contexts = []
                    total_retrieved = len(docs)
                    for doc in docs:
                        if hasattr(doc, "page_content"):
                            contexts.append(doc.page_content)
                        elif isinstance(doc, dict):
                            contexts.append(doc.get("page_content") or doc.get("content") or str(doc))
                        else:
                            contexts.append(str(doc))
                    
                    context_text = "\n\n".join(contexts)
                    print(f"[DEBUG] 上下文总长度: {len(context_text)} 字符")
                    print(f"[DEBUG] 上下文内容 (前500字符): {context_text[:500]}...")
                    prompt = (
                        "你必须只返回一个有效的 JSON 对象，格式严格如下:\n"
                        "{\"answer\": \"这里是你的中文回答\"}\n"
                        "重要规则：\n"
                        "1. 只输出 JSON 对象，不要输出任何其他文本\n"
                        "2. answer 字段的值必须是一段完整、连贯的中文回答\n"
                        "3. 不要在 JSON 前后添加任何额外的字符或解释\n"
                        "4. 确保 JSON 格式完全有效\n"
                        "5. 必须仅基于以下上下文回答，不能使用常识\n"
                        # "6. 如果上下文中没有相关信息，answer 字段应为：'我无法根据现有知识库中的信息回答这个问题'\n\n"
                        # f"上下文信息:\n{context_text}\n\n问题: {req.question}\n\n"
                        # "回答示例：{\"answer\": \"这是示例答案\"}\n"
                        "5. 必须以提供的上下文为唯一信息源，不要引入外部未提供的信息。\n"
                        "6. 如果用户的问题是一个实体名或关键词（例如：\"实体名X\"或\"关键词Y\"），请直接从上下文中提取并用一到两句简短中文陈述该实体的事实（例如：\"实体名X，XXXXXX，XXXXXX\"）。\n"
                        "7. 只有在上下文确实不包含任何与问题相关的事实时，answer 字段才应为：'我无法根据现有知识库中的信息回答这个问题'。\n\n"
                        f"上下文信息:\n{context_text}\n\n问题: {req.question}\n\n"
                        "回答示例：{\"answer\": \"这是示例答案\"}\n"
                    )
                    
                    model_name = req.ollama_model or Config.OLLAMA_MODEL
                    api_url = req.ollama_api_url or Config.OLLAMA_API_URL
                    
                    sources = []
                    returned_count = len(docs)
                    for doc in docs:
                        src = getattr(doc, 'metadata', {}).get('source', '未知来源') if hasattr(doc, 'metadata') else (doc.get('metadata', {}).get('source') if isinstance(doc, dict) and doc.get('metadata') else '未知来源')
                        preview = getattr(doc, 'page_content', '')
                        preview = preview[:200].replace('\n', ' ') if preview else ''
                        sources.append({"source": src, "preview": preview})
                    
                    # 发送源信息，并包含检索计数信息（如果配置了阈值，会影响返回数量）
                    meta_info = {'returned': returned_count}
                    if getattr(Config, 'MAX_DISTANCE', None) is not None:
                        meta_info['note'] = f"应用 MAX_DISTANCE={Config.MAX_DISTANCE} 进行过滤，原始请求 TOP_K={Config.TOP_K}"
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
                    
                    # 解析 Ollama 返回（有时 Ollama 会返回一个 JSON 字符串）
                    final_text = ""
                    s = str(ollama_result).strip()
                    print(f"[DEBUG] Ollama 原始返回 (前200字): {s[:200]}")
                    
                    # 步骤 1: 尝试直接解析为 JSON
                    try:
                        parsed = json.loads(s)
                        if isinstance(parsed, dict) and "answer" in parsed:
                            final_text = str(parsed.get("answer", "")).strip()
                            print(f"[DEBUG] 成功从 JSON 解析 answer")
                        else:
                            # JSON 格式但没有 answer 字段，可能返回的本身是完整答案
                            final_text = s
                    except Exception as parse_err:
                        # 步骤 2: 解析失败，尝试从文本中抽取第一个 JSON 对象
                        start_idx = s.find('{')
                        end_idx = s.rfind('}')
                        if start_idx != -1 and end_idx != -1 and start_idx < end_idx:
                            try:
                                maybe_json = s[start_idx:end_idx+1]
                                parsed2 = json.loads(maybe_json)
                                if isinstance(parsed2, dict) and "answer" in parsed2:
                                    final_text = str(parsed2.get("answer", "")).strip()
                                    print(f"[DEBUG] 从文本中提取 JSON 并解析成功")
                                else:
                                    # 无法找到 answer 字段，返回空白以避免显示 JSON 对象
                                    final_text = ""
                            except Exception:
                                # JSON 解析失败，检查是否存在answer字段的文本模式
                                # 使用正则表达式查找 "answer": "..." 模式
                                import re
                                answer_match = re.search(r'"answer"\s*:\s*"([^"]*(?:\\"[^"]*)*)"', s)
                                if answer_match:
                                    final_text = answer_match.group(1).replace('\\"', '"')
                                    print(f"[DEBUG] 使用正则表达式提取 answer")
                                else:
                                    final_text = ""
                                    print(f"[DEBUG] 无法从 Ollama 返回中解析答案")
                        else:
                            # 找不到 JSON 对象，直接作为文本返回
                            final_text = s
                            print(f"[DEBUG] 未找到 JSON，直接作为文本返回")

                    # 逐字符发送最终文本
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
                # 默认使用 RAGAssistant（LangChain LLM）生成答案
                try:
                    # 在线程中运行同步的 query 方法，避免阻塞事件循环
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
                    # 当启用了距离阈值时，告知前端可能存在过滤
                    if getattr(Config, 'MAX_DISTANCE', None) is not None:
                        # 这里无法直接获取原始候选数量（LangChain retriever 不暴露），
                        # 因此只返回启用阈值的提示信息
                        for s in sources:
                            s.setdefault('note', f"Filtered by MAX_DISTANCE={Config.MAX_DISTANCE}")
                    
                    # 发送源信息
                    yield f"data: {json.dumps({'type': 'sources', 'data': sources})}\n\n"
                    
                    # 流式发送内容
                    for char in answer:
                        yield f"data: {json.dumps({'type': 'content', 'data': char})}\n\n"
                        await asyncio.sleep(0.01)
                    
                    yield f"data: {json.dumps({'type': 'done'})}\n\n"
                except Exception as query_err:
                    print(f"RAG 查询异常: {query_err}")
                    traceback.print_exc()
                    err_detail = str(query_err)
                    # 为常见错误提供更好的提示
                    if "APIConnectionError" in err_detail or "Connection" in err_detail:
                        err_detail = f"模型 API 连接失败。请检查: 1) 网络连接 2) API 密钥配置 3) API 服务状态\n原始错误: {err_detail}"
                    yield f"data: {json.dumps({'type': 'error', 'data': err_detail})}\n\n"
                
        except Exception as e:
            traceback.print_exc()
            err_msg = f"查询处理异常: {str(e)}"
            print(f"致命错误: {err_msg}")
            yield f"data: {json.dumps({'type': 'error', 'data': err_msg})}\n\n"
    
    return StreamingResponse(generate(), media_type="text/event-stream")



# @app.post("/api/query")

# def query(req: QueryRequest):
#     if not load_assistant():
#         raise HTTPException(status_code=500, detail="向量数据库未加载。请先构建或确认数据库目录。")

#     # 请求优先使用查询中指定的 provider，否则使用全局配置
#     req_provider = (req.provider or Config.MODEL_PROVIDER or '').strip().lower()

#     try:
#         # 本地 Ollama 分支：仅检索文档并把上下文发给本地 Ollama 模型
#         if req_provider == 'ollama':
#             try:
#                 if assistant is None:
#                     load_assistant()

#                 method = req.method or 'vector'
#                 rerank = bool(req.rerank) if req.rerank is not None else False
#                 top_k = req.top_k or Config.TOP_K
#                 docs = assistant.retrieve_documents(req.question, k=top_k, method=method, rerank=rerank)
#                 print(f"[DEBUG /api/query] 问题: {req.question}")
#                 print(f"[DEBUG /api/query] 检索到 {len(docs)} 个文档")
#                 # 调试: 检查文档格式 (应该都是 Document 对象，有 metadata)
#                 # print(f"[DEBUG /api/query] 文档类型: {[type(d).__name__ for d in docs]}")
#                 # for idx, doc in enumerate(docs):
#                 #     print(f"[DEBUG /api/query] docs[{idx}] 有 metadata: {hasattr(doc, 'metadata')}, metadata 内容: {getattr(doc, 'metadata', None)}")

#                 contexts = []
#                 for doc in docs:
#                     if hasattr(doc, "page_content"):
#                         contexts.append(doc.page_content)
#                     elif isinstance(doc, dict):
#                         contexts.append(doc.get("page_content") or doc.get("content") or str(doc))
#                     else:
#                         contexts.append(str(doc))

#                 context_text = "\n\n".join(contexts)
#                 print(f"[DEBUG /api/query] 上下文总长度: {len(context_text)} 字符")
#                 print(f"[DEBUG /api/query] 上下文内容 (前500字符): {context_text[:500]}...")

#                 # 改进的提示词，确保 Ollama 返回一致的格式
#                 prompt = (
#                     "你是一个专业的信息提取助手。\n"
#                     "请仔细阅读下方的上下文信息，然后回答问题。\n\n"
#                     "【重要指示】\n"
#                     "你的回答必须严格遵循以下格式：\n"
#                     "{\"answer\": \"你的完整中文回答\"}\n\n"
#                     "【要求】\n"
#                     "1. 只返回JSON对象，不要有任何其他文本或解释\n"
#                     "2. answer字段必须包含完整、连贯的中文回答\n"
#                     "3. 必须仅基于以下上下文回答，不能添加常识或推测\n"
#                     "4. 如果上下文中没有信息回答问题，必须返回：{\"answer\": \"我无法根据现有知识库中的信息回答这个问题\"}\n"
#                     "5. 回答应该专业、准确、简洁\n\n"
#                     "【上下文信息】\n"
#                     f"{context_text}\n\n"
#                     "【问题】\n"
#                     f"{req.question}\n\n"
#                     "【回答】\n"
#                     "只返回JSON格式的回答，例如：{\"answer\": \"答案内容\"}\n"
#                 )

#                 model_name = req.ollama_model or Config.OLLAMA_MODEL
#                 api_url = req.ollama_api_url or Config.OLLAMA_API_URL

#                 ollama_text = ollama_generate(
#                     model=model_name,
#                     prompt=prompt,
#                     max_tokens=Config.MAX_TOKENS,
#                     temperature=Config.TEMPERATURE,
#                     api_url=api_url,
#                 )
                
#                 print(f"[DEBUG /api/query] Ollama 原始返回 (前200字): {str(ollama_text)[:200]}")

#                 # 解析并规范化 Ollama 同步返回，确保返回给前端的 `answer` 为纯文本
#                 final_answer = ""
#                 try:
#                     parsed = json.loads(ollama_text)
#                     if isinstance(parsed, dict) and "answer" in parsed:
#                         final_answer = str(parsed.get("answer", "")).strip()
#                         print(f"[DEBUG /api/query] ✅ 成功从 JSON 解析")
#                     else:
#                         final_answer = str(parsed).strip()
#                         print(f"[DEBUG /api/query] ⚠️ JSON 格式但无 'answer' 字段，使用整个值")
#                 except json.JSONDecodeError:
#                     # 尝试从文本中提取 JSON
#                     print(f"[DEBUG /api/query] ⚠️ JSON 解析失败，尝试提取...")
#                     s = str(ollama_text)
#                     start_idx = s.find('{')
#                     end_idx = s.rfind('}')
#                     if start_idx != -1 and end_idx != -1 and start_idx < end_idx:
#                         try:
#                             maybe_json = s[start_idx:end_idx+1]
#                             parsed2 = json.loads(maybe_json)
#                             if isinstance(parsed2, dict) and "answer" in parsed2:
#                                 final_answer = str(parsed2.get("answer", "")).strip()
#                                 print(f"[DEBUG /api/query] ✅ 从文本中提取 JSON 成功")
#                             else:
#                                 # JSON 格式正确但无 answer 字段，使用整个文本
#                                 final_answer = s.strip()
#                                 print(f"[DEBUG /api/query] ⚠️ 提取的 JSON 无 'answer' 字段，使用原始文本")
#                         except json.JSONDecodeError:
#                             # JSON 提取失败，直接使用文本
#                             final_answer = s.strip()
#                             print(f"[DEBUG /api/query] ⚠️ JSON 提取也失败，使用原始文本作为答案")
#                     else:
#                         # 没有找到 JSON 结构，直接使用原始文本
#                         final_answer = s.strip()
#                         print(f"[DEBUG /api/query] ⚠️ 未找到 JSON 结构，使用原始文本作为答案")
#                 except Exception as e:
#                     # 其他异常
#                     final_answer = str(ollama_text).strip()
#                     print(f"[DEBUG /api/query] ❌ 解析异常: {e}，使用原始文本作为答案")

#                 # 确保 final_answer 不为空
#                 if not final_answer:
#                     final_answer = "我无法根据现有知识库中的信息回答这个问题"
#                     print(f"[DEBUG /api/query] ❌ 最终答案为空，使用默认拒绝消息")
#                 else:
#                     print(f"[DEBUG /api/query] ✅ 最终答案长度: {len(final_answer)} 字符")

#                 sources = []
#                 for doc in docs:
#                     src = getattr(doc, 'metadata', {}).get('source', '未知来源') if hasattr(doc, 'metadata') else (doc.get('metadata', {}).get('source') if isinstance(doc, dict) and doc.get('metadata') else '未知来源')
#                     preview = getattr(doc, 'page_content', '')
#                     preview = preview[:200].replace('\n', ' ') if preview else ''
#                     sources.append({"source": src, "preview": preview})

#                 return {"question": req.question, "answer": final_answer, "sources": sources}

#             except OllamaError as oe:
#                 # 本地 Ollama 调用失败，记录并回退到默认 RAGAssistant
#                 print(f"调用本地 Ollama 失败: {oe}")

#         # 默认使用 RAGAssistant（LangChain LLM）生成答案，传入检索参数以确保生成链使用指定上下文
#         method = req.method or 'vector'
#         rerank = bool(req.rerank) if req.rerank is not None else False
#         top_k = req.top_k or Config.TOP_K

#         result = assistant.query(req.question, True, method, top_k, rerank)
#         answer = result.get("answer", "")
#         sources = []
#         if "sources" in result and result["sources"]:
#             for doc in result["sources"]:
#                 src = doc.metadata.get("source", "未知来源")
#                 preview = getattr(doc, "page_content", "")
#                 preview = preview[:200].replace("\n", " ") if preview else ""
#                 sources.append({"source": src, "preview": preview})

#         return {"question": req.question, "answer": answer, "sources": sources}

#     except Exception as e:
#         # 打印完整 traceback 到服务端日志，便于定位问题
#         traceback.print_exc()
#         # 如果是网络连接相关的错误，给出更明确的提示
#         err_msg = str(e)
#         if "Connection" in err_msg or "ConnectionError" in err_msg or "APIConnectionError" in err_msg:
#             extra = (
#                 "可能是模型提供者无法连接。请检查网络、模型提供者配置（MODEL_PROVIDER、OPENAI_API_BASE、OLLAMA_API_URL）\n"
#                 f"当前 OpenAI API Base: {Config.OPENAI_API_BASE}\n"
#                 f"当前 Ollama API URL: {Config.OLLAMA_API_URL}\n"
#                 "如果使用本地 Ollama，请确认 Ollama 服务已启动并监听对应端口（默认 http://localhost:11434）。"
#             )
#             err_msg = err_msg + "\n" + extra

#         raise HTTPException(status_code=500, detail=err_msg)


# @app.post("/api/debug-retrieve")
# def debug_retrieve(req: QueryRequest):
#     """调试检索：返回候选文档及其距离分数（不进行生成）。"""
#     if not load_assistant():
#         raise HTTPException(status_code=500, detail="向量数据库未加载")

#     try:
#         method = req.method or 'vector'
#         top_k = req.top_k or 10
#         rerank = bool(req.rerank) if req.rerank is not None else False

#         out = []
#         if method == 'bm25':
#             bm_results = assistant.retrieve_documents(req.question, k=top_k, method='bm25')
#             # bm_results is list of (doc, score)
#             for item in bm_results:
#                 if isinstance(item, tuple) and len(item) == 2:
#                     doc, score = item
#                 else:
#                     doc, score = item, None
#                 preview = getattr(doc, 'page_content', '')
#                 preview = preview[:300].replace('\n', ' ') if preview else ''
#                 source = getattr(doc, 'metadata', {}).get('source', '未知来源') if hasattr(doc, 'metadata') else '未知来源'
#                 out.append({'score': float(score) if score is not None else None, 'source': source, 'preview': preview})
#         elif method == 'hybrid':
#             docs = assistant.retrieve_documents(req.question, k=top_k, method='hybrid', rerank=rerank)
#             # hybrid 返回的是文档列表 (after possible rerank), we don't have BM25 score here
#             for doc in docs:
#                 preview = getattr(doc, 'page_content', '')
#                 preview = preview[:300].replace('\n', ' ') if preview else ''
#                 out.append({'score': None, 'source': getattr(doc, 'metadata', {}).get('source', '未知来源') if hasattr(doc, 'metadata') else '未知来源', 'preview': preview})
#         else:
#             # vector 默认返回带分数的候选
#             vs = assistant.vector_store
#             raw = vs.similarity_search_with_score(req.question, k=top_k)
#             for doc, score in raw:
#                 src = getattr(doc, 'metadata', {}).get('source', '未知来源') if hasattr(doc, 'metadata') else (doc.get('metadata', {}).get('source') if isinstance(doc, dict) and doc.get('metadata') else '未知来源')
#                 preview = getattr(doc, 'page_content', '')
#                 preview = preview[:300].replace('\n', ' ') if preview else ''
#                 out.append({'score': float(score), 'source': src, 'preview': preview})

#         return {'query': req.question, 'candidates': out, 'config_MAX_DISTANCE': getattr(Config, 'MAX_DISTANCE', None)}
#     except Exception as e:
#         traceback.print_exc()
#         raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app_api:app", host="0.0.0.0", port=8000, reload=True)
