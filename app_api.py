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
                    contexts = []
                    for doc in docs:
                        if hasattr(doc, "page_content"):
                            contexts.append(doc.page_content)
                        elif isinstance(doc, dict):
                            contexts.append(doc.get("page_content") or doc.get("content") or str(doc))
                        else:
                            contexts.append(str(doc))
                    
                    context_text = "\n\n".join(contexts)
                    prompt = (
                        "请只返回一个 JSON 对象，格式为 {\"answer\": \"...\"}，其中 answer 是一段完整、连贯的中文回答。不要输出其他文本或解释。\n"
                        + f"基于以下上下文回答问题:\n{context_text}\n\n问题: {req.question}\n\n"
                        + "回答示例：{\"answer\": \"这是示例答案\"}\n"
                    )
                    
                    model_name = req.ollama_model or Config.OLLAMA_MODEL
                    api_url = req.ollama_api_url or Config.OLLAMA_API_URL
                    
                    sources = []
                    for doc in docs:
                        src = getattr(doc, 'metadata', {}).get('source', '未知来源') if hasattr(doc, 'metadata') else (doc.get('metadata', {}).get('source') if isinstance(doc, dict) and doc.get('metadata') else '未知来源')
                        preview = getattr(doc, 'page_content', '')
                        preview = preview[:200].replace('\n', ' ') if preview else ''
                        sources.append({"source": src, "preview": preview})
                    
                    # 发送源信息
                    yield f"data: {json.dumps({'type': 'sources', 'data': sources})}\n\n"
                    
                    # 调用 Ollama 生成
                    ollama_result = ollama_generate(
                        model=model_name,
                        prompt=prompt,
                        max_tokens=Config.MAX_TOKENS,
                        temperature=Config.TEMPERATURE,
                        api_url=api_url,
                        stream=False
                    )
                    
                    # 逐字符发送内容
                    if ollama_result:
                        for char in ollama_result:
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
                    result = await asyncio.to_thread(assistant.query, req.question)
                    answer = result.get("answer", "")
                    sources = []
                    if "sources" in result and result["sources"]:
                        for doc in result["sources"]:
                            src = doc.metadata.get("source", "未知来源")
                            preview = getattr(doc, "page_content", "")
                            preview = preview[:200].replace("\n", " ") if preview else ""
                            sources.append({"source": src, "preview": preview})
                    
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



@app.post("/api/query")

def query(req: QueryRequest):
    if not load_assistant():
        raise HTTPException(status_code=500, detail="向量数据库未加载。请先构建或确认数据库目录。")

    # 请求优先使用查询中指定的 provider，否则使用全局配置
    req_provider = (req.provider or Config.MODEL_PROVIDER or '').strip().lower()

    try:
        # 本地 Ollama 分支：仅检索文档并把上下文发给本地 Ollama 模型
        if req_provider == 'ollama':
            try:
                if assistant is None:
                    load_assistant()

                docs = assistant.retrieve_documents(req.question, k=Config.TOP_K)

                contexts = []
                for doc in docs:
                    if hasattr(doc, "page_content"):
                        contexts.append(doc.page_content)
                    elif isinstance(doc, dict):
                        contexts.append(doc.get("page_content") or doc.get("content") or str(doc))
                    else:
                        contexts.append(str(doc))

                context_text = "\n\n".join(contexts)

                prompt = (
                    "请只返回一个 JSON 对象，格式为 {\"answer\": \"...\"}，其中 answer 是一段完整、连贯的中文回答。不要输出其他文本或解释。\n"
                    + f"基于以下上下文回答问题:\n{context_text}\n\n问题: {req.question}\n\n"
                    + "回答示例：{\"answer\": \"这是示例答案\"}\n"
                )

                model_name = req.ollama_model or Config.OLLAMA_MODEL
                api_url = req.ollama_api_url or Config.OLLAMA_API_URL

                ollama_text = ollama_generate(
                    model=model_name,
                    prompt=prompt,
                    max_tokens=Config.MAX_TOKENS,
                    temperature=Config.TEMPERATURE,
                    api_url=api_url,
                )

                sources = []
                for doc in docs:
                    src = getattr(doc, 'metadata', {}).get('source', '未知来源') if hasattr(doc, 'metadata') else (doc.get('metadata', {}).get('source') if isinstance(doc, dict) and doc.get('metadata') else '未知来源')
                    preview = getattr(doc, 'page_content', '')
                    preview = preview[:200].replace('\n', ' ') if preview else ''
                    sources.append({"source": src, "preview": preview})

                return {"question": req.question, "answer": ollama_text, "sources": sources}

            except OllamaError as oe:
                # 本地 Ollama 调用失败，记录并回退到默认 RAGAssistant
                print(f"调用本地 Ollama 失败: {oe}")

        # 默认使用 RAGAssistant（LangChain LLM）生成答案
        result = assistant.query(req.question)
        answer = result.get("answer", "")
        sources = []
        if "sources" in result and result["sources"]:
            for doc in result["sources"]:
                src = doc.metadata.get("source", "未知来源")
                preview = getattr(doc, "page_content", "")
                preview = preview[:200].replace("\n", " ") if preview else ""
                sources.append({"source": src, "preview": preview})

        return {"question": req.question, "answer": answer, "sources": sources}

    except Exception as e:
        # 打印完整 traceback 到服务端日志，便于定位问题
        traceback.print_exc()
        # 如果是网络连接相关的错误，给出更明确的提示
        err_msg = str(e)
        if "Connection" in err_msg or "ConnectionError" in err_msg or "APIConnectionError" in err_msg:
            extra = (
                "可能是模型提供者无法连接。请检查网络、模型提供者配置（MODEL_PROVIDER、OPENAI_API_BASE、OLLAMA_API_URL）\n"
                f"当前 OpenAI API Base: {Config.OPENAI_API_BASE}\n"
                f"当前 Ollama API URL: {Config.OLLAMA_API_URL}\n"
                "如果使用本地 Ollama，请确认 Ollama 服务已启动并监听对应端口（默认 http://localhost:11434）。"
            )
            err_msg = err_msg + "\n" + extra

        raise HTTPException(status_code=500, detail=err_msg)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app_api:app", host="0.0.0.0", port=8000, reload=True)
