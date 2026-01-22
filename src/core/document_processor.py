"""文档加载和处理模块"""
import os
import json
import csv
from typing import List, Any
from pathlib import Path

from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import (
    PyPDFLoader,
    TextLoader,
    Docx2txtLoader,
    CSVLoader,
    UnstructuredHTMLLoader,
    UnstructuredPowerPointLoader,
    UnstructuredExcelLoader,
    UnstructuredEPubLoader,
    UnstructuredRTFLoader,
    JSONLoader,
)

from src.config.settings import Config


class DocumentProcessor:
    """文档处理器"""
    
    def __init__(self, chunk_size: int = None, chunk_overlap: int = None):
        """初始化文档处理器
        
        Args:
            chunk_size: 文本分块大小
            chunk_overlap: 文本分块重叠大小
        """
        self.chunk_size = chunk_size or Config.CHUNK_SIZE
        self.chunk_overlap = chunk_overlap or Config.CHUNK_OVERLAP
        
        # 优化分割策略：优先按 Markdown 章节、段落分割，保持语义完整性
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
            length_function=len,
            separators=["\n## ", "\n### ", "\n#### ", "\n\n", "\n", "。", "！", "？", "；", " "],
        )
    
    def load_document(self, file_path: str) -> List[Any]:
        """加载单个文档
        
        Args:
            file_path: 文档路径
            
        Returns:
            文档列表
        """
        file_extension = Path(file_path).suffix.lower()
        
        try:
            if file_extension == ".pdf":
                loader = PyPDFLoader(file_path)
            elif file_extension == ".txt":
                loader = TextLoader(file_path, encoding="utf-8")
            elif file_extension in [".doc", ".docx"]:
                loader = Docx2txtLoader(file_path)
            elif file_extension == ".md":
                # 使用 TextLoader 加载 Markdown 文件，避免 UnstructuredMarkdownLoader 的兼容性问题
                loader = TextLoader(file_path, encoding="utf-8")
            elif file_extension == ".csv":
                loader = CSVLoader(file_path, encoding="utf-8")
            elif file_extension == ".json":
                # JSON 文件使用 jq_schema 提取文本内容
                loader = JSONLoader(
                    file_path=file_path,
                    jq_schema=".",
                    text_content=False,
                )
            elif file_extension in [".html", ".htm"]:
                loader = UnstructuredHTMLLoader(file_path)
            elif file_extension in [".ppt", ".pptx"]:
                loader = UnstructuredPowerPointLoader(file_path)
            elif file_extension in [".xls", ".xlsx"]:
                loader = UnstructuredExcelLoader(file_path)
            elif file_extension == ".epub":
                loader = UnstructuredEPubLoader(file_path)
            elif file_extension == ".rtf":
                loader = UnstructuredRTFLoader(file_path)
            elif file_extension in [".py", ".js", ".ts", ".java", ".cpp", ".c", ".h", ".go", ".rs", ".rb", ".php", ".sh", ".sql", ".yaml", ".yml", ".xml", ".ini", ".cfg", ".conf", ".log"]:
                # 支持常见代码和配置文件
                loader = TextLoader(file_path, encoding="utf-8")
            else:
                raise ValueError(f"不支持的文件格式: {file_extension}")
            
            documents = loader.load()
            print(f"✓ 加载文档: {file_path} ({len(documents)} 页)")
            return documents
            
        except Exception as e:
            print(f"✗ 加载文档失败 {file_path}: {str(e)}")
            return []
    
    def load_documents_from_directory(self, directory_path: str) -> List[Any]:
        """从目录加载所有文档
        
        Args:
            directory_path: 目录路径
            
        Returns:
            所有文档列表
        """
        all_documents = []
        # 支持的文件格式列表
        supported_extensions = [
            # 文档格式
            ".pdf", ".txt", ".doc", ".docx", ".md", ".rtf",
            # 数据格式
            ".csv", ".json",
            # 网页格式
            ".html", ".htm",
            # 演示和表格
            ".ppt", ".pptx", ".xls", ".xlsx",
            # 电子书
            ".epub",
            # 代码文件
            ".py", ".js", ".ts", ".java", ".cpp", ".c", ".h", ".go", ".rs", ".rb", ".php", ".sh",
            # 配置文件
            ".sql", ".yaml", ".yml", ".xml", ".ini", ".cfg", ".conf", ".log",
        ]
        
        directory = Path(directory_path)
        if not directory.exists():
            print(f"目录不存在: {directory_path}")
            return []
        
        file_count = 0
        for file_path in directory.rglob("*"):
            if file_path.is_file() and file_path.suffix.lower() in supported_extensions:
                docs = self.load_document(str(file_path))
                all_documents.extend(docs)
                file_count += 1
        
        print(f"\n总计加载 {file_count} 个文件，{len(all_documents)} 个文档")
        return all_documents
    
    def split_documents(self, documents: List[Any]) -> List[Any]:
        """分割文档为小块
        
        Args:
            documents: 文档列表
            
        Returns:
            分割后的文档块列表
        """
        chunks = self.text_splitter.split_documents(documents)

        # 为每个 chunk 注入 source metadata（如果原始文档有 source 或者来自文件加载，则保留）
        for idx, c in enumerate(chunks):
            try:
                # LangChain 的 Document 有 metadata 属性
                src = None
                if hasattr(c, 'metadata') and isinstance(c.metadata, dict):
                    src = c.metadata.get('source')
                # 如果没有 source，尝试从 c.uri 或 c._metadata 中寻找（兼容不同 loader）
                if not src:
                    if hasattr(c, 'uri'):
                        src = getattr(c, 'uri')
                    elif hasattr(c, '_metadata') and isinstance(c._metadata, dict):
                        src = c._metadata.get('source')
                if not src:
                    src = 'unknown'
                # 保证 metadata 存在并注入 source、chunk_id、chunk_index
                meta = None
                if hasattr(c, 'metadata') and isinstance(c.metadata, dict):
                    meta = c.metadata
                else:
                    try:
                        c.metadata = {}
                        meta = c.metadata
                    except Exception:
                        meta = None

                if meta is not None:
                    meta['source'] = src
                    # chunk_id: 文件名 + 块序号，便于定位
                    try:
                        fname = str(src).split('/')[-1]
                    except Exception:
                        fname = str(src)
                    meta['chunk_id'] = f"{fname}::chunk_{idx}"
                    meta['chunk_index'] = idx
            except Exception:
                continue

        print(f"文档分块完成: {len(documents)} 个文档 -> {len(chunks)} 个文本块")
        return chunks
    
    def process_documents(self, directory_path: str) -> List[Any]:
        """处理目录中的所有文档（加载+分割）
        
        Args:
            directory_path: 目录路径
            
        Returns:
            处理后的文档块列表
        """
        print(f"开始处理文档目录: {directory_path}\n")
        documents = self.load_documents_from_directory(directory_path)
        
        if not documents:
            print("未找到任何文档")
            return []
        
        chunks = self.split_documents(documents)
        return chunks
    
    @staticmethod
    def get_supported_extensions() -> dict:
        """获取支持的文件格式列表
        
        Returns:
            按类别分组的支持格式字典
        """
        return {
            "文档": [".pdf", ".txt", ".doc", ".docx", ".md", ".rtf"],
            "数据": [".csv", ".json"],
            "网页": [".html", ".htm"],
            "演示": [".ppt", ".pptx"],
            "表格": [".xls", ".xlsx"],
            "电子书": [".epub"],
            "代码": [".py", ".js", ".ts", ".java", ".cpp", ".c", ".h", ".go", ".rs", ".rb", ".php", ".sh"],
            "配置": [".sql", ".yaml", ".yml", ".xml", ".ini", ".cfg", ".conf", ".log"],
        }
    
    @staticmethod
    def get_all_supported_extensions() -> List[str]:
        """获取所有支持的文件扩展名列表
        
        Returns:
            扩展名列表
        """
        extensions = []
        for exts in DocumentProcessor.get_supported_extensions().values():
            extensions.extend(exts)
        return extensions
