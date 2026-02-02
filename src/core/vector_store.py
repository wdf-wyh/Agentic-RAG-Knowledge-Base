"""向量数据库模块"""
import os
from typing import List, Optional, Any

from typing import Any
from langchain_community.vectorstores.chroma import Chroma

try:
    from langchain_community.embeddings.openai import OpenAIEmbeddings
except Exception:
    OpenAIEmbeddings = None

# 当使用 Gemini 或本地嵌入时，使用 sentence-transformers 作为后备实现
try:
    from sentence_transformers import SentenceTransformer
    import numpy as np
except Exception:
    SentenceTransformer = None
    np = None

from src.config.settings import Config


class VectorStore:
    """向量数据库管理器"""
    
    def __init__(self, persist_directory: str = None):
        """初始化向量数据库
        
        Args:
            persist_directory: 数据库持久化目录
        """
        self.persist_directory = persist_directory or Config.VECTOR_DB_PATH
        
        # 初始化 Embedding 模型：根据配置选择实现
        use_local_embeddings = False

        if Config.MODEL_PROVIDER == "openai":
            if not Config.OPENAI_API_KEY:
                # 虽然 provider 是 openai，但没有提供 key，则回退到本地嵌入
                use_local_embeddings = True
            elif OpenAIEmbeddings is None:
                raise ImportError("OpenAIEmbeddings 未安装，请运行 `pip install langchain-openai` 或切换到其他 MODEL_PROVIDER")
            else:
                self.embeddings = OpenAIEmbeddings(
                    model=Config.EMBEDDING_MODEL,
                    openai_api_key=Config.OPENAI_API_KEY,
                    openai_api_base=Config.OPENAI_API_BASE,
                )
        else:
            use_local_embeddings = True

        if use_local_embeddings:
            # 对于 gemini 或本地回退，优先使用 sentence-transformers
            if SentenceTransformer is None:
                raise ImportError("未安装 sentence-transformers，请运行 `pip install sentence-transformers` 或在 .env 中配置有效的 OPENAI_API_KEY/GEMINI_API_KEY")

            class LocalEmbeddings:
                """本地 Embeddings 适配器，提供 embed_documents 与 embed_query 方法"""
                def __init__(self, model_name: str = "BAAI/bge-small-zh-v1.5"):
                    # 使用支持中文的嵌入模型，提升中文语义检索效果
                    self.model = SentenceTransformer(model_name)

                def embed_documents(self, texts):
                    embs = self.model.encode(list(texts), show_progress_bar=False, convert_to_numpy=True)
                    return [list(map(float, e)) for e in embs]

                def embed_query(self, text):
                    emb = self.model.encode([text], show_progress_bar=False, convert_to_numpy=True)[0]
                    return list(map(float, emb))

            self.embeddings = LocalEmbeddings()
        
        self.vectorstore: Optional[Chroma] = None
    
    def create_vectorstore(self, documents: List[Any]) -> Chroma:
        """创建向量数据库
        
        Args:
            documents: 文档列表
            
        Returns:
            向量数据库实例
        """
        print(f"\n开始创建向量数据库...")
        print(f"文档数量: {len(documents)}")
        
        self.vectorstore = Chroma.from_documents(
            documents=documents,
            embedding=self.embeddings,
            persist_directory=self.persist_directory,
        )
        
        print(f"✓ 向量数据库创建成功，保存在: {self.persist_directory}")
        return self.vectorstore
    
    def load_vectorstore(self) -> Optional[Chroma]:
        """加载已存在的向量数据库
        
        Returns:
            向量数据库实例，如果不存在则返回 None
        """
        if not os.path.exists(self.persist_directory):
            print(f"向量数据库不存在: {self.persist_directory}")
            return None
        
        print(f"加载向量数据库: {self.persist_directory}")
        self.vectorstore = Chroma(
            persist_directory=self.persist_directory,
            embedding_function=self.embeddings,
        )
        
        print("✓ 向量数据库加载成功")
        return self.vectorstore
    
    def add_documents(self, documents: List[Any]):
        """向现有数据库添加文档
        
        Args:
            documents: 文档列表
        """
        if self.vectorstore is None:
            self.vectorstore = self.load_vectorstore()
        
        if self.vectorstore is None:
            self.create_vectorstore(documents)
        else:
            print(f"添加 {len(documents)} 个文档到向量数据库...")
            self.vectorstore.add_documents(documents)
            print("✓ 文档添加成功")
    
    def similarity_search(self, query: str, k: int = None) -> List[Any]:
        """相似度搜索
        
        Args:
            query: 查询文本
            k: 返回结果数量
            
        Returns:
            相关文档列表
        """
        if self.vectorstore is None:
            self.load_vectorstore()
        
        if self.vectorstore is None:
            raise ValueError("向量数据库未初始化")
        
        k = k or Config.TOP_K
        results = self.vectorstore.similarity_search(query, k=k)
        return results
    
    def similarity_search_with_score(self, query: str, k: int = None) -> List[tuple]:
        """带分数的相似度搜索
        
        Args:
            query: 查询文本
            k: 返回结果数量
            
        Returns:
            (文档, 分数) 元组列表
        """
        if self.vectorstore is None:
            self.load_vectorstore()
        
        if self.vectorstore is None:
            raise ValueError("向量数据库未初始化")
        
        k = k or Config.TOP_K
        results = self.vectorstore.similarity_search_with_score(query, k=k)
        return results

    def similarity_search_with_score_threshold(self, query: str, k: int = None, max_distance: float = None) -> List[tuple]:
        """带阈值的相似度搜索（基于 Chroma 返回的距离，值越小越相似）

        Args:
            query: 查询文本
            k: 返回结果数量
            max_distance: 最大允许距离（包含），距离越大相关性越低

        Returns:
            (文档, 距离) 元组列表，已按距离升序并过滤超过阈值的项
        """
        if self.vectorstore is None:
            self.load_vectorstore()

        if self.vectorstore is None:
            raise ValueError("向量数据库未初始化")

        k = k or Config.TOP_K
        results = self.vectorstore.similarity_search_with_score(query, k=k)

        if max_distance is None:
            return results

        # Chroma 返回的 score 是距离，越小表示越相似；过滤并保持升序
        filtered = [(doc, score) for doc, score in results if score <= max_distance]
        # 如果过滤后数量少于 k，仍返回过滤后的所有结果
        return filtered
    
    def similarity_search_with_score_filter(self, query: str, k: int = None, similarity_threshold: float = None) -> List[tuple]:
        """带相似度阈值的搜索（过滤低相似度结果）
        
        Chroma 返回的是距离 (distance)，距离越小表示越相似。
        此方法会将距离转换为相似度 (0-1)，并过滤掉相似度低于阈值的结果。
        
        距离到相似度的转换公式: similarity = 1 / (1 + distance)
        - distance=0 -> similarity=1.0（完全匹配）
        - distance=1 -> similarity=0.5（中等相似）
        - distance→∞ -> similarity→0（完全不同）
        
        Args:
            query: 查询文本
            k: 返回结果数量
            similarity_threshold: 相似度阈值 (0-1)，只返回相似度 >= 此值的文档
            
        Returns:
            (文档, 相似度) 元组列表，按相似度从高到低排序，已过滤低相似度项
        """
        if self.vectorstore is None:
            self.load_vectorstore()

        if self.vectorstore is None:
            raise ValueError("向量数据库未初始化")

        k = k or Config.TOP_K
        
        # 先获取更多候选，确保过滤后仍有足够结果
        # 获取 k*3 个候选以增加过滤后的有效结果数
        candidate_k = max(k * 3, 20)
        
        # 直接使用 similarity_search_with_score（返回距离值）
        results = self.vectorstore.similarity_search_with_score(query, k=candidate_k)
        
        # 将距离转换为相似度（similarity = 1 / (1 + distance)）
        # 这样距离 0 变成相似度 1.0，距离越大相似度越低
        results = [(doc, 1.0 / (1.0 + score)) for doc, score in results]
        
        if similarity_threshold is None:
            return results[:k]

        # 过滤：只保留相似度 >= threshold 的结果
        filtered = [(doc, score) for doc, score in results if score >= similarity_threshold]
        
        # 如果过滤结果不足 k 个，仍返回所有过滤结果（不足为奇）
        # 这样调用方可以判断是否有足够的相关文档
        return filtered[:k]
    
    def delete_collection(self):
        """删除向量数据库集合"""
        if self.vectorstore is not None:
            self.vectorstore.delete_collection()
            print("✓ 向量数据库已删除")
    
    def get_document_list(self) -> List[str]:
        """获取知识库中所有文档的列表
        
        Returns:
            文档来源路径列表（去重）
        """
        if self.vectorstore is None:
            self.load_vectorstore()
        
        if self.vectorstore is None:
            return []
        
        try:
            collection = self.vectorstore._collection
            all_docs = collection.get(include=['metadatas'])
            sources = set()
            for meta in all_docs.get('metadatas', []):
                if meta and 'source' in meta:
                    sources.add(meta['source'])
            return sorted(list(sources))
        except Exception:
            return []
    
    def get_retriever(self, k: int = None):
        """获取检索器
        
        Args:
            k: 返回结果数量
            
        Returns:
            检索器实例
        """
        if self.vectorstore is None:
            self.load_vectorstore()
        
        if self.vectorstore is None:
            raise ValueError("向量数据库未初始化")
        
        k = k or Config.TOP_K
        return self.vectorstore.as_retriever(search_kwargs={"k": k})
