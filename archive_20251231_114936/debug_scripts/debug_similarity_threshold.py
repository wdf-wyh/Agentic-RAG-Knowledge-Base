#!/usr/bin/env python
"""调试相似度阈值问题 - 检查 '严寒叫' 的实际相似度得分"""

from vector_store import VectorStore
from config import Config
from rag_assistant import RAGAssistant

def debug_similarity():
    """检查查询与文档的实际相似度得分"""
    print("=" * 60)
    print("调试相似度问题")
    print("=" * 60)
    
    # 初始化向量数据库
    vector_store = VectorStore()
    vector_store.load_vectorstore()
    
    query = "严寒叫"
    print(f"\n查询词: '{query}'")
    print(f"当前相似度阈值: {Config.SIMILARITY_THRESHOLD}")
    
    # 获取原始分数（不过滤）
    try:
        print("\n【获取原始相似度得分（top 10）】")
        raw_results = vector_store.similarity_search_with_score(query, k=10)
        
        if not raw_results:
            print("❌ 没有结果")
        else:
            for i, (doc, score) in enumerate(raw_results, 1):
                source = getattr(doc, 'metadata', {}).get('source', '未知') if hasattr(doc, 'metadata') else '未知'
                content = getattr(doc, 'page_content', '')[:100]
                print(f"  {i}. 距离={score:.6f}, 来源={source}")
                print(f"     内容: {content}...")
    except Exception as e:
        print(f"❌ 获取原始分数失败: {e}")
    
    # 尝试获取相关度得分（Chroma 可能支持）
    try:
        print("\n【尝试获取相关度得分 (relevance_scores)】")
        if hasattr(vector_store.vectorstore, 'similarity_search_with_relevance_scores'):
            relevance_results = vector_store.vectorstore.similarity_search_with_relevance_scores(query, k=10)
            
            if not relevance_results:
                print("❌ 没有结果")
            else:
                for i, (doc, score) in enumerate(relevance_results, 1):
                    source = getattr(doc, 'metadata', {}).get('source', '未知') if hasattr(doc, 'metadata') else '未知'
                    content = getattr(doc, 'page_content', '')[:100]
                    print(f"  {i}. 相似度={score:.6f}, 来源={source}")
                    print(f"     内容: {content}...")
        else:
            print("⚠️ 向量数据库不支持 similarity_search_with_relevance_scores")
    except Exception as e:
        print(f"❌ 获取相关度分数失败: {e}")
    
    # 过滤后的结果
    print(f"\n【过滤后的结果 (阈值 >= {Config.SIMILARITY_THRESHOLD})】")
    filtered_results = vector_store.similarity_search_with_score_filter(query, k=10, similarity_threshold=Config.SIMILARITY_THRESHOLD)
    
    if not filtered_results:
        print(f"❌ 没有相似度 >= {Config.SIMILARITY_THRESHOLD} 的文档")
    else:
        for i, (doc, score) in enumerate(filtered_results, 1):
            source = getattr(doc, 'metadata', {}).get('source', '未知') if hasattr(doc, 'metadata') else '未知'
            content = getattr(doc, 'page_content', '')[:100]
            print(f"  {i}. 相似度={score:.6f}, 来源={source}")
            print(f"     内容: {content}...")
    
    # 建议
    print("\n【分析建议】")
    if raw_results:
        max_score = max([score for _, score in raw_results])
        print(f"  - 最高相似度得分: {max_score:.6f}")
        
        if max_score < Config.SIMILARITY_THRESHOLD:
            print(f"  - ⚠️  最高得分 ({max_score:.6f}) 仍低于阈值 ({Config.SIMILARITY_THRESHOLD})")
            print(f"  - 建议: 降低 SIMILARITY_THRESHOLD 阈值")
            print(f"    执行: export SIMILARITY_THRESHOLD=0.2")
            print(f"    或修改 .env 文件中的 SIMILARITY_THRESHOLD=0.2")
        else:
            print(f"  - ✅ 最高得分 ({max_score:.6f}) 超过阈值")

if __name__ == "__main__":
    debug_similarity()
