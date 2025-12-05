"""文档加载和处理模块"""
import os
from typing import List
from pathlib import Path

from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import (
    PyPDFLoader,
    TextLoader,
    Docx2txtLoader,
    UnstructuredMarkdownLoader,
)
from typing import Any

from config import Config


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
        
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
            length_function=len,
            separators=["\n\n", "\n", "。", "！", "？", "；", " ", ""],
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
                loader = UnstructuredMarkdownLoader(file_path)
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
        supported_extensions = [".pdf", ".txt", ".doc", ".docx", ".md"]
        
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
