#!/usr/bin/env python3
"""测试相似度阈值过滤功能"""

import os
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent))

from config import Config
from vector_store import VectorStore
from rag_assistant import RAGAssistant

def test_similarity_filter():
    """测试相似度阈值过滤"""
    
    print("=" * 60)
    print("RAG 相似度阈值过滤测试")
    print("=" * 60)
    print(f"\n配置信息:")
    print(f"  TOP_K: {Config.TOP_K}")
    print(f"  SIMILARITY_THRESHOLD: {Config.SIMILARITY_THRESHOLD}")
    print(f"  向量数据库路径: {Config.VECTOR_DB_PATH}")
    print(f"  文档目录: {Config.DOCUMENTS_PATH}")
    
    # 检查向量数据库是否存在
    if not Path(Config.VECTOR_DB_PATH).exists():
        print(f"\n❌ 向量数据库不存在: {Config.VECTOR_DB_PATH}")
        print("请先运行 'python document_processor.py' 构建向量数据库")
        return
    
    # 初始化向量存储和 RAG 助手
    try:
        vector_store = VectorStore()
        vs = vector_store.load_vectorstore()
        if vs is None:
            print("\n❌ 向量数据库加载失败")
            return
        
        assistant = RAGAssistant(vector_store=vector_store)
        print("\n✓ 向量存储已加载")
    except Exception as e:
        print(f"\n❌ 初始化失败: {e}")
        return
    
    # 测试查询
    test_queries = [
        "RAG是什么",      # 应该有结果（文档中有）
        "兴业",           # 应该没有结果（文档中没有）
        "常见问题",       # 应该有结果（FAQ 中有）
        "严寒叫",         # 可能有也可能没有，取决于 yhj.md 的实际内容
    ]
    
    print("\n" + "=" * 60)
    print("开始测试查询（使用相似度阈值过滤）")
    print("=" * 60)
    
    for query in test_queries:
        print(f"\n【查询】{query}")
        print("-" * 40)
        
        try:
            # 使用相似度过滤进行检索
            docs = assistant.retrieve_documents(query, k=Config.TOP_K)
            
            print(f"检索到 {len(docs)} 个文档：")
            
            if not docs:
                print("  ⚠️  没有找到足够相关的文档（可能被阈值过滤）")
            else:
                for i, doc in enumerate(docs, 1):
                    content = doc.page_content if hasattr(doc, 'page_content') else str(doc)
                    source = doc.metadata.get('source', '未知') if hasattr(doc, 'metadata') else '未知'
                    preview = content[:150].replace('\n', ' ')
                    print(f"  {i}. [{source}] {preview}...")
        
        except Exception as e:
            print(f"  ❌ 检索失败: {e}")
    
    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)
    print(f"\n说明：")
    print(f"- 相似度阈值设置为 {Config.SIMILARITY_THRESHOLD}")
    print(f"- 只有相似度 >= {Config.SIMILARITY_THRESHOLD} 的文档才会被返回")
    print(f"- 如果查询返回空结果，表示过滤工作正常")
    print(f"\n可以通过设置环境变量 SIMILARITY_THRESHOLD 来调整阈值:")
    print(f"  export SIMILARITY_THRESHOLD=0.2  # 降低阈值以获得更多结果")
    print(f"  export SIMILARITY_THRESHOLD=     # 禁用过滤")


if __name__ == "__main__":
    test_similarity_filter()
