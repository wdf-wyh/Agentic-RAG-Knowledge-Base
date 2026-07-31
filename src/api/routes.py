"""API 路由定义"""
from fastapi import APIRouter, HTTPException, UploadFile, File, BackgroundTasks, Depends, Request
from fastapi.responses import StreamingResponse, PlainTextResponse, Response
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
from pydantic import BaseModel

from src.config.settings import Config
from src.api.auth import get_current_user
from src.api.dependencies import get_request_context
from src.api.permissions import require_roles, require_policy
from src.core.document_processor import DocumentProcessor
from src.core.vector_store import VectorStore
from src.core.incremental_index import IncrementalIndexer
from src.core.graph_rag import KnowledgeGraph
from src.models.auth import RequestContext, UserIdentity
from src.models.audit import AuditEvent
from src.plugins.base import run_hooks
from src.services.audit_service import get_audit_service
from src.services.quota_service import get_quota_service
from src.services.webhook_service import get_webhook_service
from src.services.retention_service import get_retention_service
from src.services.compliance_export_service import get_compliance_export_service
from src.services.rag_assistant import RAGAssistant
from src.services.conversation_manager import ConversationManager
from src.services.ollama_client import generate as ollama_generate, OllamaError
from src.services.deepseek_client import generate as deepseek_generate, DeepSeekError
from src.security.guardrails import validate_user_text
from src.security.pii import sanitize_output_text
from src.security.abac import get_abac_engine
from src.utils.monitoring import monitor
from src.utils.tenant_monitoring import tenant_monitor
from src.models.schemas import QueryRequest, BuildRequest, ConversationMessage

# 配置日志
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

router = APIRouter(dependencies=[Depends(get_current_user)])

# 全局状态管理（按租户隔离）
_assistants: dict[str, Optional[RAGAssistant]] = {}
_conversation_managers: dict[str, ConversationManager] = {}
_build_progress_by_tenant: dict[str, dict] = {}


def get_tenant_id(user: Optional[UserIdentity]) -> str:
    return user.tenant_id if user else Config.DEFAULT_TENANT_ID


def get_build_progress(tenant_id: str) -> dict:
    if tenant_id not in _build_progress_by_tenant:
        _build_progress_by_tenant[tenant_id] = {
            "processing": False,
            "progress": 0,
            "total": 0,
            "current_file": "",
            "status": "idle",
        }
    return _build_progress_by_tenant[tenant_id]


def format_source(doc) -> dict:
    """格式化来源信息，含页码与块索引"""
    meta = getattr(doc, "metadata", {}) if hasattr(doc, "metadata") else {}
    if not isinstance(meta, dict):
        meta = {}
    src = meta.get("source", "未知来源")
    preview = getattr(doc, "page_content", "") or ""
    preview = preview[:300].replace("\n", " ")
    fname = str(src).replace("\\", "/").split("/")[-1]
    return {
        "source": src,
        "filename": fname,
        "page": meta.get("page"),
        "chunk_index": meta.get("chunk_index"),
        "chunk_id": meta.get("chunk_id"),
        "preview": preview,
        "highlight_text": (getattr(doc, "page_content", "") or "")[:500],
    }


def generate_trace_id() -> str:
    """生成请求追踪 ID"""
    return str(uuid.uuid4())[:8]


def record_audit_event(
    request: Request,
    context: RequestContext,
    action: str,
    resource: str,
    user: Optional[UserIdentity],
    outcome: str = "success",
    details: Optional[dict] = None,
):
    """记录统一审计事件。"""
    get_audit_service().record(
        AuditEvent(
            request_id=context.request_id,
            actor_id=user.user_id if user else "anonymous",
            actor_name=user.username if user else "anonymous",
            tenant_id=user.tenant_id if user else Config.DEFAULT_TENANT_ID,
            action=action,
            resource=resource,
            outcome=outcome,
            path=request.url.path,
            method=request.method,
            client_ip=context.client_ip,
            details=details or {},
        )
    )


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
    safe_text = sanitize_output_text(text)
    for i in range(0, len(safe_text), chunk_size):
        chunk = safe_text[i:i+chunk_size]
        yield f"data: {json.dumps({'type': 'content', 'data': chunk})}\n\n"
        await asyncio.sleep(0.05)  # 每批等待 50ms，比逐字符更高效


def get_conversation_manager(tenant_id: str = Config.DEFAULT_TENANT_ID) -> ConversationManager:
    """获取对话管理器实例"""
    manager = _conversation_managers.get(tenant_id)
    if manager is None:
        manager = ConversationManager(tenant_id=tenant_id)
        _conversation_managers[tenant_id] = manager
    return manager


def get_assistant(tenant_id: str = Config.DEFAULT_TENANT_ID) -> Optional[RAGAssistant]:
    """获取 RAG 助手实例"""
    return _assistants.get(tenant_id)


def set_assistant(assistant: Optional[RAGAssistant], tenant_id: str = Config.DEFAULT_TENANT_ID):
    """设置 RAG 助手实例"""
    _assistants[tenant_id] = assistant


def load_assistant(tenant_id: str = Config.DEFAULT_TENANT_ID) -> bool:
    """加载助手"""
    try:
        Config.validate()
        assistant = _assistants.get(tenant_id)
        if assistant is None:
            vector_store = VectorStore(tenant_id=tenant_id)
            vs = vector_store.load_vectorstore()
            if vs is None:
                return False
            assistant = RAGAssistant(vector_store=vector_store)
            assistant.setup_qa_chain()
            _assistants[tenant_id] = assistant
        return True
    except Exception as e:
        print("加载助手失败:", e)
        return False


@router.get("/status")
def status(user: Optional[UserIdentity] = Depends(get_current_user)):
    """获取系统状态"""
    tenant_id = get_tenant_id(user)
    loaded = load_assistant(tenant_id)
    return {"vector_store_loaded": loaded, "tenant_id": tenant_id}


@router.post("/build", dependencies=[Depends(require_roles("admin")), Depends(require_policy("write", "knowledge_base"))])
def build(
    req: BuildRequest,
    request: Request,
    context: RequestContext = Depends(get_request_context),
    user: Optional[UserIdentity] = Depends(get_current_user),
):
    """构建知识库"""
    try:
        # 安全: 验证文档路径在允许范围内
        doc_path = Path(req.documents_path).resolve()
        allowed_roots = [Path("./documents").resolve(), Path("./uploads").resolve()]
        if not any(doc_path == root or doc_path.is_relative_to(root) for root in allowed_roots):
            raise HTTPException(status_code=400, detail="文档路径不在允许范围内，只允许 ./documents 或 ./uploads")
        
        processor = DocumentProcessor()
        chunks = processor.process_documents(req.documents_path)
        if not chunks:
            return {"success": False, "message": "未找到可处理的文档"}

        tenant_id = get_tenant_id(user)
        vector_store = VectorStore(tenant_id=tenant_id)
        vector_store.create_vectorstore(chunks)

        # 构建知识图谱
        if Config.ENABLE_GRAPH_RAG:
            try:
                kg = KnowledgeGraph()
                kg.build_from_chunks(chunks)
            except Exception as ge:
                logger.warning("知识图谱构建失败: %s", ge)

        run_hooks("after_build", chunks)
        
        # 重新加载 assistant
        set_assistant(None, tenant_id)
        load_assistant(tenant_id)  # 立即重新加载
        record_audit_event(
            request,
            context,
            action="knowledge_base.build",
            resource="documents",
            user=user,
            details={"documents_path": req.documents_path, "processed_chunks": len(chunks)},
        )
        return {"success": True, "processed_chunks": len(chunks)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def build_knowledge_base_background(documents_path: str, tenant_id: str):
    """后台构建知识库并更新进度"""
    progress = get_build_progress(tenant_id)
    try:
        progress["processing"] = True
        progress["status"] = "reading"
        progress["current_file"] = "扫描文档..."
        progress["progress"] = 0
        progress["total"] = 0
        
        processor = DocumentProcessor()
        chunks = processor.process_documents(documents_path)
        
        if not chunks:
            progress["status"] = "error"
            progress["current_file"] = "未找到可处理的文档"
            progress["processing"] = False
            return
        
        progress["total"] = len(chunks)
        progress["status"] = "building"
        progress["current_file"] = "生成向量..."
        
        vector_store = VectorStore(tenant_id=tenant_id)
        
        # 分批添加文档，逐步更新进度（每50个一批）
        batch_size = 50
        for i in range(0, len(chunks), batch_size):
            batch = chunks[i:i+batch_size]
            if i == 0:
                vector_store.create_vectorstore(batch)
            else:
                vector_store.add_documents(batch)
            
            progress["progress"] = min(i + batch_size, len(chunks))
            progress["current_file"] = f"已处理 {progress['progress']}/{len(chunks)} 个文档块"
            time.sleep(0.1)
        
        set_assistant(None, tenant_id)
        load_assistant(tenant_id)
        
        progress["progress"] = len(chunks)
        progress["status"] = "completed"
        progress["current_file"] = "完成"
        progress["processing"] = False
        try:
            from src.services.webhook_service import get_webhook_service

            get_webhook_service().emit(
                "build.completed",
                {"tenant_id": tenant_id, "processed_chunks": len(chunks), "documents_path": documents_path},
            )
        except Exception:
            pass
        
    except Exception as e:
        progress["status"] = "error"
        progress["current_file"] = f"错误: {str(e)}"
        progress["processing"] = False


@router.post("/upload", dependencies=[Depends(require_roles("admin")), Depends(require_policy("write", "knowledge_base"))])
async def upload_file(
    request: Request,
    file: UploadFile = File(...),
    context: RequestContext = Depends(get_request_context),
    user: Optional[UserIdentity] = Depends(get_current_user),
):
    """上传文件到文档目录"""
    MAX_UPLOAD_SIZE = 50 * 1024 * 1024  # 50MB
    ALLOWED_EXTENSIONS = {".md", ".pdf", ".docx", ".doc", ".txt", ".csv", ".json", ".html", ".htm", ".epub", ".rtf", ".pptx", ".xlsx"}
    
    try:
        # 安全: 防止路径遍历攻击，只保留文件名部分
        safe_filename = Path(file.filename).name
        if not safe_filename or safe_filename.startswith('.'):
            raise HTTPException(status_code=400, detail="无效的文件名")
        
        # 检查文件扩展名
        file_ext = Path(safe_filename).suffix.lower()
        if file_ext not in ALLOWED_EXTENSIONS:
            raise HTTPException(status_code=400, detail=f"不支持的文件类型: {file_ext}")
        
        documents_dir = Path("./documents")
        documents_dir.mkdir(exist_ok=True)
        
        contents = await file.read()
        
        # 文件大小限制
        if len(contents) > MAX_UPLOAD_SIZE:
            raise HTTPException(status_code=413, detail=f"文件大小超过限制 ({MAX_UPLOAD_SIZE // 1024 // 1024}MB)")
        
        file_path = documents_dir / safe_filename
        # 安全: 确认解析后路径仍在 documents 目录内
        if not file_path.resolve().is_relative_to(documents_dir.resolve()):
            raise HTTPException(status_code=400, detail="无效的文件路径")
        
        with open(file_path, "wb") as f:
            f.write(contents)
        record_audit_event(
            request,
            context,
            action="knowledge_base.upload",
            resource=safe_filename,
            user=user,
            details={"size": len(contents), "path": str(file_path)},
        )
        
        return {
            "success": True,
            "filename": safe_filename,
            "size": len(contents),
            "path": str(file_path)
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/build-incremental", dependencies=[Depends(require_roles("admin")), Depends(require_policy("write", "knowledge_base"))])
async def build_incremental(
    background_tasks: BackgroundTasks,
    request: Request,
    context: RequestContext = Depends(get_request_context),
    user: Optional[UserIdentity] = Depends(get_current_user),
):
    """增量构建知识库（仅处理变更文件）"""
    tenant_id = get_tenant_id(user)
    progress = get_build_progress(tenant_id)
    if progress["processing"]:
        return {"success": False, "message": "已有构建任务进行中"}

    def _incremental_task():
        current_progress = get_build_progress(tenant_id)
        try:
            current_progress.update({"processing": True, "status": "incremental", "progress": 0})
            indexer = IncrementalIndexer(tenant_id=tenant_id)
            result = indexer.process_incremental("./documents")
            chunks = result["chunks"]
            if not chunks and not result["deleted_files"]:
                current_progress.update({"status": "completed", "current_file": "无变更", "processing": False})
                return
            vs = VectorStore(tenant_id=tenant_id)
            if vs.load_vectorstore() is None:
                vs.create_vectorstore(chunks)
            else:
                vs.add_documents(chunks)
            if Config.ENABLE_GRAPH_RAG and chunks:
                KnowledgeGraph().build_from_chunks(chunks)
            set_assistant(None, tenant_id)
            load_assistant(tenant_id)
            current_progress.update({
                "status": "completed",
                "progress": result["new_chunks"],
                "total": result["new_chunks"],
                "current_file": f"变更 {len(result['changed_files'])} 文件",
                "processing": False,
            })
        except Exception as e:
            current_progress.update({"status": "error", "current_file": str(e), "processing": False})

    background_tasks.add_task(_incremental_task)
    record_audit_event(
        request,
        context,
        action="knowledge_base.build_incremental",
        resource="documents",
        user=user,
    )
    return {"success": True, "message": "增量构建已启动"}


@router.post("/build-start", dependencies=[Depends(require_roles("admin")), Depends(require_policy("write", "knowledge_base"))])
async def build_start(
    background_tasks: BackgroundTasks,
    request: Request,
    context: RequestContext = Depends(get_request_context),
    user: Optional[UserIdentity] = Depends(get_current_user),
):
    """启动后台知识库构建"""
    tenant_id = get_tenant_id(user)
    progress = get_build_progress(tenant_id)
    if progress["processing"]:
        return {"success": False, "message": "已有构建任务进行中"}
    
    progress["processing"] = True
    progress["progress"] = 0
    progress["total"] = 0
    progress["status"] = "processing"
    progress["current_file"] = "初始化..."
    
    background_tasks.add_task(build_knowledge_base_background, "./documents", tenant_id)
    record_audit_event(
        request,
        context,
        action="knowledge_base.build_async",
        resource="documents",
        user=user,
    )
    return {"success": True, "message": "构建任务已启动"}


@router.get("/build-progress")
async def build_progress_endpoint(user: Optional[UserIdentity] = Depends(get_current_user)):
    """获取构建进度"""
    return get_build_progress(get_tenant_id(user))


@router.get("/conversations")
async def list_conversations(user: Optional[UserIdentity] = Depends(get_current_user)):
    """列出所有对话历史"""
    try:
        conv_manager = get_conversation_manager(get_tenant_id(user))
        conversation_ids = conv_manager.list_conversations()
        
        conversations = []
        for conv_id in conversation_ids:
            # 加载对话以获取摘要信息
            conv_manager.load_conversation(conv_id)
            full_history = conv_manager.get_history(conv_id)
            message_count = len(full_history)
            if message_count == 0:
                continue

            # 获取第一条用户消息作为标题
            title = "新对话"
            last_time = full_history[-1].timestamp if full_history else None

            for msg in full_history:
                if msg.role == "user":
                    title = msg.content[:50] + ("..." if len(msg.content) > 50 else "")
                    break

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
async def get_conversation(conversation_id: str, user: Optional[UserIdentity] = Depends(get_current_user)):
    """获取单个对话的详细内容"""
    try:
        conv_manager = get_conversation_manager(get_tenant_id(user))
        
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
async def delete_conversation(
    conversation_id: str,
    request: Request,
    context: RequestContext = Depends(get_request_context),
    user: Optional[UserIdentity] = Depends(get_current_user),
):
    """删除指定对话"""
    try:
        conv_manager = get_conversation_manager(get_tenant_id(user))
        conv_manager.delete_conversation(conversation_id)
        record_audit_event(
            request,
            context,
            action="conversation.delete",
            resource=conversation_id,
            user=user,
        )
        return {"success": True, "message": "对话已删除"}
    except Exception as e:
        logger.error(f"删除对话失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 文件管理 API ====================

DOCUMENTS_DIR = Path("./documents").resolve()


def _safe_file_path(filename: str) -> Path:
    """验证文件名安全性，返回安全的文件路径"""
    safe_name = Path(filename).name
    if not safe_name or safe_name.startswith('.') or '..' in filename:
        raise HTTPException(status_code=400, detail="无效的文件名")
    file_path = (DOCUMENTS_DIR / safe_name).resolve()
    if not file_path.is_relative_to(DOCUMENTS_DIR):
        raise HTTPException(status_code=400, detail="无效的文件路径")
    return file_path


@router.get("/files")
async def list_files():
    """列出文档目录下所有文件"""
    try:
        DOCUMENTS_DIR.mkdir(exist_ok=True)
        files = []
        for item in sorted(DOCUMENTS_DIR.iterdir()):
            if item.is_file() and not item.name.startswith('.'):
                stat = item.stat()
                files.append({
                    "name": item.name,
                    "size": stat.st_size,
                    "modified": stat.st_mtime,
                    "ext": item.suffix.lower(),
                })
        return {"success": True, "files": files}
    except Exception as e:
        logger.error(f"列出文件失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/files/{filename:path}")
async def read_file_content(filename: str):
    """读取指定文件内容"""
    file_path = _safe_file_path(filename)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="文件不存在")

    # 只允许读取文本类文件
    text_exts = {'.md', '.txt', '.json', '.csv', '.html', '.htm', '.xml',
                 '.yaml', '.yml', '.ini', '.cfg', '.conf', '.log',
                 '.py', '.js', '.ts', '.java', '.cpp', '.c', '.h',
                 '.go', '.rs', '.rb', '.php', '.sh', '.sql', '.rtf'}
    if file_path.suffix.lower() not in text_exts:
        raise HTTPException(status_code=400, detail=f"不支持在线编辑此文件类型: {file_path.suffix}")

    try:
        content = file_path.read_text(encoding='utf-8')
        return {"success": True, "name": file_path.name, "content": content, "size": len(content)}
    except UnicodeDecodeError:
        try:
            content = file_path.read_text(encoding='gbk')
            return {"success": True, "name": file_path.name, "content": content, "size": len(content)}
        except Exception:
            raise HTTPException(status_code=400, detail="无法读取此文件，编码不支持")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class FileSaveRequest(BaseModel):
    content: str


@router.put("/files/{filename:path}", dependencies=[Depends(require_roles("admin")), Depends(require_policy("write", "files"))])
async def save_file_content(
    filename: str,
    req: FileSaveRequest,
    request: Request,
    context: RequestContext = Depends(get_request_context),
    user: Optional[UserIdentity] = Depends(get_current_user),
):
    """保存文件内容"""
    file_path = _safe_file_path(filename)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="文件不存在")
    try:
        file_path.write_text(req.content, encoding='utf-8')
        record_audit_event(
            request,
            context,
            action="file.update",
            resource=file_path.name,
            user=user,
            details={"size": len(req.content)},
        )
        return {"success": True, "message": "文件已保存", "size": len(req.content)}
    except Exception as e:
        logger.error(f"保存文件失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


class FileCreateRequest(BaseModel):
    name: str
    content: str = ""


@router.post("/files", dependencies=[Depends(require_roles("admin")), Depends(require_policy("write", "files"))])
async def create_file_endpoint(
    req: FileCreateRequest,
    request: Request,
    context: RequestContext = Depends(get_request_context),
    user: Optional[UserIdentity] = Depends(get_current_user),
):
    """创建新文件"""
    file_path = _safe_file_path(req.name)
    if file_path.exists():
        raise HTTPException(status_code=409, detail="文件已存在")
    try:
        DOCUMENTS_DIR.mkdir(exist_ok=True)
        file_path.write_text(req.content, encoding='utf-8')
        record_audit_event(
            request,
            context,
            action="file.create",
            resource=file_path.name,
            user=user,
            details={"size": len(req.content)},
        )
        return {"success": True, "message": "文件已创建", "name": file_path.name, "size": len(req.content)}
    except Exception as e:
        logger.error(f"创建文件失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/files/{filename:path}", dependencies=[Depends(require_roles("admin")), Depends(require_policy("delete", "files"))])
async def delete_file(
    filename: str,
    request: Request,
    context: RequestContext = Depends(get_request_context),
    user: Optional[UserIdentity] = Depends(get_current_user),
):
    """删除指定文件"""
    file_path = _safe_file_path(filename)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="文件不存在")
    try:
        file_path.unlink()
        record_audit_event(
            request,
            context,
            action="file.delete",
            resource=file_path.name,
            user=user,
        )
        return {"success": True, "message": "文件已删除"}
    except Exception as e:
        logger.error(f"删除文件失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 查询 API ====================


@router.post("/query-stream")
async def query_stream(
    req: QueryRequest,
    request: Request,
    context: RequestContext = Depends(get_request_context),
    user: Optional[UserIdentity] = Depends(get_current_user),
):
    """流式查询知识库（SSE）"""
    try:
        validate_user_text(req.question)
    except HTTPException:
        record_audit_event(
            request,
            context,
            action="query.blocked",
            resource="query_stream",
            user=user,
            outcome="blocked",
            details={"reason": "guardrail_violation"},
        )
        raise
    tenant_id = get_tenant_id(user)
    get_quota_service().ensure_allowed(tenant_id)
    req_provider = (req.provider or Config.MODEL_PROVIDER or '').strip().lower()
    usage = get_quota_service().record_query(
        tenant_id,
        question=req.question,
        provider=req_provider,
        estimated_output_tokens=Config.MAX_TOKENS,
    )
    get_webhook_service().emit(
        "query.completed",
        {
            "tenant_id": tenant_id,
            "provider": req_provider,
            "question_preview": req.question[:120],
            "usage": usage,
        },
    )
    trace_id = generate_trace_id()
    start_time = time.time()
    logger.info(f"[{trace_id}] 开始处理查询 - 问题: {req.question[:100]}..., Provider: {req.provider}")
    
    if not load_assistant(tenant_id):
        error_msg = "向量数据库未加载。请先构建或确认数据库目录。"
        async def error_generate():
            yield f"data: {json.dumps({'type': 'error', 'data': error_msg})}\n\n"
        return StreamingResponse(error_generate(), media_type="text/event-stream")
    
    # 获取对话管理器并处理对话历史
    conv_manager = get_conversation_manager(tenant_id)
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
                    assistant = get_assistant(tenant_id)
                    if assistant is None:
                        load_assistant(tenant_id)
                        assistant = get_assistant(tenant_id)
                    
                    logger.info(f"[Ollama] 开始检索文档...")
                    docs = assistant.retrieve_documents(
                        req.question, k=Config.TOP_K,
                        method=req.method or Config.DEFAULT_RETRIEVAL_METHOD,
                        rerank=req.rerank if req.rerank is not None else Config.ENABLE_RERANK,
                    )
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
                        "6. 如果用户的问题是一个实体名或关键词，请直接从上下文中提取并用一到两句简短中文陈述该实体的事实。\n"
                        "7. 只有在上下文确实不包含任何与问题相关的事实时，answer 字段才应为：'我无法根据现有知识库中的信息回答这个问题'。\n"
                        f"{conversation_context}"
                        f"上下文信息:\n{context_text}\n\n问题: {req.question}\n\n"
                        "回答示例：{\"answer\": \"这是示例答案\"}\n"
                    )
                    
                    model_name = req.ollama_model or Config.OLLAMA_MODEL
                    api_url = req.ollama_api_url or Config.OLLAMA_API_URL
                    
                    sources = [format_source(doc) for doc in docs]

                    # 先发送会话ID
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
                        conv_manager.add_message(conversation_id, "assistant", sanitize_output_text(final_text), save_to_disk=True)
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
                    assistant = get_assistant(tenant_id)
                    if assistant is None:
                        load_assistant(tenant_id)
                        assistant = get_assistant(tenant_id)

                    logger.info(f"[DeepSeek] 开始检索文档...")
                    docs = assistant.retrieve_documents(
                        req.question, k=Config.TOP_K,
                        method=req.method or Config.DEFAULT_RETRIEVAL_METHOD,
                        rerank=req.rerank if req.rerank is not None else Config.ENABLE_RERANK,
                    )
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

                    sources = [format_source(doc) for doc in docs]

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
                        conv_manager.add_message(conversation_id, "assistant", sanitize_output_text(final_text), save_to_disk=True)
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
                    assistant = get_assistant(tenant_id)
                    method = req.method or Config.DEFAULT_RETRIEVAL_METHOD
                    rerank = req.rerank if req.rerank is not None else Config.ENABLE_RERANK
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
                    answer = sanitize_output_text(result.get("answer", ""))
                    sources = [format_source(doc) for doc in result.get("sources", [])]
                    
                    # 先发送会话ID，确保前端立即获取
                    yield f"data: {json.dumps({'type': 'conversation_id', 'data': conversation_id})}\n\n"
                    
                    yield f"data: {json.dumps({'type': 'sources', 'data': sources})}\n\n"
                    
                    async for chunk in stream_text_in_chunks(answer, chunk_size=20):
                        yield chunk
                    
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


@router.get("/admin/summary", dependencies=[Depends(require_roles("admin", "auditor")), Depends(require_policy("read", "metrics"))])
async def admin_summary(
    request: Request,
    context: RequestContext = Depends(get_request_context),
    user: Optional[UserIdentity] = Depends(get_current_user),
):
    """企业管理侧最小观测摘要。"""
    tenant_id = get_tenant_id(user)
    summary = {
        "request_id": context.request_id,
        "tenant_id": tenant_id,
        "auth": {
            "enabled": Config.ENABLE_AUTH,
            "current_user": user.model_dump() if user else None,
        },
        "build": get_build_progress(tenant_id),
        "monitoring": monitor.get_summary(),
        "quota": {
            "limits": get_quota_service().limits(),
            "usage": get_quota_service().snapshot(tenant_id).get(tenant_id),
        },
        "webhook": get_webhook_service().status(),
        "security": {
            "pii_redaction_enabled": Config.ENABLE_PII_REDACTION,
            "abac_enabled": Config.ENABLE_ABAC,
            "guardrails_enabled": Config.ENABLE_SECURITY_GUARDRAILS,
            "policy_count": len(get_abac_engine().list_policies()),
        },
        "retention": get_retention_service().status(),
        "audit": {
            "enabled": True,
            "log_path": Config.AUDIT_LOG_PATH,
        },
    }
    record_audit_event(
        request,
        context,
        action="admin.summary.read",
        resource="admin_summary",
        user=user,
    )
    return summary


@router.get("/admin/audit-events", dependencies=[Depends(require_roles("admin", "auditor")), Depends(require_policy("read", "audit"))])
async def admin_audit_events(
    request: Request,
    limit: int = 50,
    context: RequestContext = Depends(get_request_context),
    user: Optional[UserIdentity] = Depends(get_current_user),
):
    """读取最近审计事件，供后续管理台接入。"""
    events = get_audit_service().list_events(limit=limit)
    record_audit_event(
        request,
        context,
        action="admin.audit.read",
        resource="audit_events",
        user=user,
        details={"limit": limit},
    )
    return {"events": events}


@router.get("/admin/tenant-metrics", dependencies=[Depends(require_roles("admin", "auditor")), Depends(require_policy("read", "metrics"))])
async def admin_tenant_metrics(
    request: Request,
    context: RequestContext = Depends(get_request_context),
    user: Optional[UserIdentity] = Depends(get_current_user),
):
    """查看租户级监控指标。"""
    metrics = tenant_monitor.snapshot()
    record_audit_event(
        request,
        context,
        action="admin.metrics.read",
        resource="tenant_metrics",
        user=user,
    )
    return {"tenants": metrics}


@router.get("/admin/metrics-prometheus", dependencies=[Depends(require_roles("admin", "auditor")), Depends(require_policy("read", "metrics"))], response_class=PlainTextResponse)
async def admin_metrics_prometheus(
    request: Request,
    context: RequestContext = Depends(get_request_context),
    user: Optional[UserIdentity] = Depends(get_current_user),
):
    """Prometheus 文本格式指标。"""
    record_audit_event(
        request,
        context,
        action="admin.metrics.export",
        resource="prometheus_metrics",
        user=user,
    )
    return tenant_monitor.to_prometheus()


@router.get("/admin/quota", dependencies=[Depends(require_roles("admin", "auditor")), Depends(require_policy("read", "quota"))])
async def admin_quota(
    request: Request,
    context: RequestContext = Depends(get_request_context),
    user: Optional[UserIdentity] = Depends(get_current_user),
):
    """查看租户配额与成本估算。"""
    data = {
        "limits": get_quota_service().limits(),
        "tenants": get_quota_service().snapshot(),
    }
    record_audit_event(
        request,
        context,
        action="admin.quota.read",
        resource="quota",
        user=user,
    )
    return data


@router.get("/admin/webhooks", dependencies=[Depends(require_roles("admin", "auditor")), Depends(require_policy("read", "webhook"))])
async def admin_webhooks(
    request: Request,
    context: RequestContext = Depends(get_request_context),
    user: Optional[UserIdentity] = Depends(get_current_user),
):
    """查看 Webhook 配置与最近投递结果。"""
    status_data = get_webhook_service().status()
    record_audit_event(
        request,
        context,
        action="admin.webhook.read",
        resource="webhooks",
        user=user,
    )
    return status_data


@router.post("/admin/webhooks/test", dependencies=[Depends(require_roles("admin")), Depends(require_policy("admin", "webhook"))])
async def admin_webhook_test(
    request: Request,
    context: RequestContext = Depends(get_request_context),
    user: Optional[UserIdentity] = Depends(get_current_user),
):
    """发送一条测试 Webhook 事件。"""
    result = get_webhook_service().emit(
        "webhook.test",
        {
            "tenant_id": get_tenant_id(user),
            "actor": user.username if user else "anonymous",
            "message": "manual webhook test",
        },
        async_delivery=False,
    )
    record_audit_event(
        request,
        context,
        action="admin.webhook.test",
        resource="webhooks",
        user=user,
        details={"result": result},
    )
    return {"result": result}


@router.get("/admin/security", dependencies=[Depends(require_roles("admin", "auditor")), Depends(require_policy("read", "security"))])
async def admin_security(
    request: Request,
    context: RequestContext = Depends(get_request_context),
    user: Optional[UserIdentity] = Depends(get_current_user),
):
    """查看 PII / ABAC 安全策略状态。"""
    data = {
        "pii_redaction_enabled": Config.ENABLE_PII_REDACTION,
        "abac_enabled": Config.ENABLE_ABAC,
        "guardrails_enabled": Config.ENABLE_SECURITY_GUARDRAILS,
        "policies": get_abac_engine().list_policies(),
    }
    record_audit_event(
        request,
        context,
        action="admin.security.read",
        resource="security",
        user=user,
    )
    return data


class RetentionCleanupRequest(BaseModel):
    tenant_id: Optional[str] = None
    dry_run: bool = False


@router.get("/admin/retention", dependencies=[Depends(require_roles("admin", "auditor")), Depends(require_policy("read", "retention"))])
async def admin_retention_status(
    request: Request,
    context: RequestContext = Depends(get_request_context),
    user: Optional[UserIdentity] = Depends(get_current_user),
):
    """查看数据保留策略状态。"""
    data = get_retention_service().status()
    record_audit_event(
        request,
        context,
        action="admin.retention.read",
        resource="retention",
        user=user,
    )
    return data


@router.post("/admin/retention/cleanup", dependencies=[Depends(require_roles("admin")), Depends(require_policy("admin", "retention"))])
async def admin_retention_cleanup(
    req: RetentionCleanupRequest,
    request: Request,
    context: RequestContext = Depends(get_request_context),
    user: Optional[UserIdentity] = Depends(get_current_user),
):
    """执行（或预演）数据保留清理。"""
    tenant_id = req.tenant_id or get_tenant_id(user)
    result = get_retention_service().cleanup(tenant_id=tenant_id, dry_run=req.dry_run)
    record_audit_event(
        request,
        context,
        action="admin.retention.cleanup",
        resource="retention",
        user=user,
        details=result,
    )
    get_webhook_service().emit("retention.cleanup", result)
    return result


@router.get("/admin/compliance-export", dependencies=[Depends(require_roles("admin", "auditor")), Depends(require_policy("read", "compliance"))])
async def admin_compliance_export(
    request: Request,
    tenant_id: Optional[str] = None,
    context: RequestContext = Depends(get_request_context),
    user: Optional[UserIdentity] = Depends(get_current_user),
):
    """导出当前（或指定）租户的合规数据包。"""
    target_tenant = tenant_id or get_tenant_id(user)
    content, filename = get_compliance_export_service().build_zip(target_tenant)
    record_audit_event(
        request,
        context,
        action="admin.compliance.export",
        resource="compliance",
        user=user,
        details={"tenant_id": target_tenant, "filename": filename, "bytes": len(content)},
    )
    get_webhook_service().emit(
        "compliance.exported",
        {"tenant_id": target_tenant, "filename": filename, "bytes": len(content)},
    )
    return Response(
        content=content,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
