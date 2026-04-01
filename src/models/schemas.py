"""Pydantic 数据模型"""
from pydantic import BaseModel, Field, field_validator
from typing import List, Optional, Any
from datetime import datetime
import re


class ConversationMessage(BaseModel):
    """对话消息模型"""
    role: str = Field(..., description="消息角色: 'user' 或 'assistant'")
    content: str = Field(..., description="消息内容")
    timestamp: Optional[str] = Field(default=None, description="消息时间戳")
    

class QueryRequest(BaseModel):
    """查询请求模型"""
    question: str
    provider: Optional[str] = None
    ollama_model: Optional[str] = None
    ollama_api_url: Optional[str] = None
    # DeepSeek 可选配置
    deepseek_model: Optional[str] = None
    deepseek_api_url: Optional[str] = None
    deepseek_api_key: Optional[str] = None
    # 检索选项
    method: Optional[str] = None  # 'vector' | 'bm25' | 'hybrid'
    rerank: Optional[bool] = None
    top_k: Optional[int] = None
    # 对话历史
    conversation_id: Optional[str] = Field(default=None, description="会话ID，用于维护连续对话")
    history: Optional[List[ConversationMessage]] = Field(default=None, description="历史对话消息列表")

    @field_validator('conversation_id')
    @classmethod
    def validate_conversation_id(cls, v):
        if v is not None:
            # 只允许 UUID 格式
            uuid_pattern = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', re.I)
            if not uuid_pattern.match(v):
                raise ValueError('conversation_id 必须是有效的 UUID 格式')
        return v


class QueryResponse(BaseModel):
    """查询响应模型"""
    answer: str
    sources: Optional[List[dict]] = None
    metadata: Optional[dict] = None


class BuildRequest(BaseModel):
    """构建知识库请求模型"""
    documents_path: str

    @field_validator('documents_path')
    @classmethod
    def validate_documents_path(cls, v):
        # 禁止路径遍历
        if '..' in v:
            raise ValueError('路径不能包含 ..')
        return v


class BuildResponse(BaseModel):
    """构建知识库响应模型"""
    success: bool
    message: Optional[str] = None
    processed_chunks: Optional[int] = None


class UploadResponse(BaseModel):
    """文件上传响应模型"""
    success: bool
    filename: str
    size: int
    path: str


class StatusResponse(BaseModel):
    """状态响应模型"""
    vector_store_loaded: bool


class BuildProgress(BaseModel):
    """构建进度模型"""
    processing: bool
    progress: int
    total: int
    current_file: str
    status: str
