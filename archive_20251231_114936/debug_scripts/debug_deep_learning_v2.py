"""
深度学习检索改进诊断脚本
优化查询排名和上下文提取
"""

from config import Config
from document_processor import DocumentProcessor
from vector_store import VectorStore
from rag_assistant import RAGAssistant
import json

def test_retrieval_ranking():
    """测试检索排名，找出为什么深度学习内容排名不是第一"""
    print("\n" + "="*60)
    print("检索排名分析")
    print("="*60 + "\n")
    
    vector_store = VectorStore()
    
    # 多个角度测试
    test_cases = [
        {
            "query": "深度学习的主要架构",
            "expected_rank": 1,
            "description": "用户原始查询"
        },
        {
            "query": "深度学习",
            "expected_rank": 1,
            "description": "核心概念"
        },
        {
            "query": "CNN RNN Transformer GAN",
            "expected_rank": 1,
            "description": "架构名称"
        },
        {
            "query": "卷积神经网络 循环神经网络 生成对抗网络",
            "expected_rank": 1,
            "description": "中文架构名"
        },
        {
            "query": "主要架构",
            "expected_rank": 1,
            "description": "关键词"
        }
    ]
    
    for case in test_cases:
        query = case["query"]
        print(f"\n【{case['description']}】")
        print(f"查询: '{query}'")
        print("-" * 50)
        
        results = vector_store.similarity_search_with_score(query, k=5)
        
        # 找出深度学习相关的块在第几位
        dl_rank = -1
        for rank, (doc, score) in enumerate(results, 1):
            content = doc.page_content
            is_dl = "深度学习" in content and ("主要架构" in content or "CNN" in content or "RNN" in content)
            
            rank_marker = ""
            if is_dl:
                dl_rank = rank
                rank_marker = "  ← 深度学习内容"
            
            print(f"{rank}. 分数:{score:.3f} | {doc.metadata.get('source', '?')} {rank_marker}")
            print(f"   {content[:80].replace(chr(10), ' ')}...")
        
        if dl_rank > 0:
            print(f"\n✓ 深度学习内容排在第 {dl_rank} 位")
        else:
            print(f"\n❌ 未找到深度学习内容")
    
    return


def test_improved_retrieval():
    """测试改进的检索策略"""
    print("\n" + "="*60)
    print("改进检索策略测试")
    print("="*60 + "\n")
    
    vector_store = VectorStore()
    
    # 原始查询
    original_query = "深度学习的主要架构"
    print(f"原始查询: '{original_query}'")
    
    # 尝试查询变体
    query_variants = [
        original_query,  # 原始
        "深度学习主要架构",  # 去掉"的"
        "深度学习架构",  # 简化
        "deep learning architecture",  # 英文版
    ]
    
    best_score = float('inf')
    best_query = None
    
    for variant in query_variants:
        results = vector_store.similarity_search_with_score(variant, k=1)
        if results:
            doc, score = results[0]
            content = doc.page_content
            
            # 检查是否包含深度学习相关内容
            has_dl_content = "深度学习" in content and ("架构" in content or "CNN" in content or "RNN" in content)
            
            if has_dl_content and score < best_score:
                best_score = score
                best_query = variant
            
            print(f"\n查询: '{variant}'")
            print(f"分数: {score:.3f}")
            print(f"内容: {content[:100].replace(chr(10), ' ')}...")
            print(f"是否包含深度学习架构: {'✓' if has_dl_content else '✗'}")
    
    if best_query:
        print(f"\n✓ 最优查询: '{best_query}' (分数: {best_score:.3f})")
    else:
        print(f"\n⚠️ 所有查询都未返回深度学习架构内容")


def test_content_extraction():
    """测试内容提取是否正确"""
    print("\n" + "="*60)
    print("内容提取测试")
    print("="*60 + "\n")
    
    vector_store = VectorStore()
    
    # 获取深度学习相关的文档
    query = "CNN RNN Transformer"
    results = vector_store.similarity_search(query, k=3)
    
    print(f"查询: '{query}'")
    print(f"返回 {len(results)} 个结果\n")
    
    for i, doc in enumerate(results, 1):
        print(f"【结果 {i}】")
        print(f"类型: {type(doc).__name__}")
        print(f"有 page_content: {hasattr(doc, 'page_content')}")
        print(f"有 metadata: {hasattr(doc, 'metadata')}")
        
        if hasattr(doc, 'page_content'):
            content = doc.page_content
            print(f"内容长度: {len(content)}")
            print(f"内容预览: {content[:150]}...")
        
        if hasattr(doc, 'metadata'):
            print(f"Metadata: {doc.metadata}")
        
        print()


def test_rag_with_debug():
    """使用调试模式测试 RAG"""
    print("\n" + "="*60)
    print("RAG 查询测试（带调试）")
    print("="*60 + "\n")
    
    assistant = RAGAssistant()
    
    query = "深度学习的主要架构有哪些?"
    print(f"查询: {query}\n")
    
    try:
        # 先测试检索
        print("【步骤1: 检索文档】")
        docs = assistant.retrieve_documents(query, k=3, method='vector', rerank=False)
        
        if docs:
            print(f"✓ 检索到 {len(docs)} 个文档\n")
            for i, doc in enumerate(docs, 1):
                content = doc.page_content if hasattr(doc, 'page_content') else str(doc)
                source = doc.metadata.get('source', '未知') if hasattr(doc, 'metadata') else '未知'
                print(f"  [{i}] {source}")
                print(f"      {content[:100].replace(chr(10), ' ')}...\n")
        else:
            print(f"❌ 未检索到任何文档\n")
        
        # 然后测试完整查询
        print("【步骤2: RAG 完整查询】")
        result = assistant.query(query, return_sources=True, method='vector', k=3)
        
        print(f"答案: {result.get('answer', '无答案')[:200]}...\n")
        
        if 'sources' in result:
            print(f"来源数量: {len(result['sources'])}")
            for i, doc in enumerate(result['sources'], 1):
                source = doc.metadata.get('source', '未知') if hasattr(doc, 'metadata') else '未知'
                content = doc.page_content[:100].replace('\n', ' ') if hasattr(doc, 'page_content') else '无内容'
                print(f"  [{i}] {source}: {content}...\n")
    
    except Exception as e:
        print(f"❌ 查询出错: {e}")


def analyze_chunk_quality():
    """分析分块质量，检查是否是分块过程的问题"""
    print("\n" + "="*60)
    print("分块质量分析")
    print("="*60 + "\n")
    
    processor = DocumentProcessor()
    
    # 显示当前配置
    print(f"分块配置:")
    print(f"- CHUNK_SIZE: {processor.chunk_size}")
    print(f"- CHUNK_OVERLAP: {processor.chunk_overlap}")
    print(f"- 分割符策略: 优先使用 Markdown 章节\n")
    
    documents = processor.load_documents_from_directory("./documents")
    chunks = processor.split_documents(documents)
    
    print(f"总分块数: {len(chunks)}\n")
    
    # 显示包含深度学习的块
    print("【包含深度学习的块】")
    for i, chunk in enumerate(chunks):
        if "深度学习" in chunk.page_content:
            print(f"\n块 {i}:")
            print(f"长度: {len(chunk.page_content)}")
            print(f"Metadata: {chunk.metadata}")
            print(f"内容:\n{chunk.page_content[:300]}")
            print("\n" + "-"*50)


def main():
    print("\n" + "="*80)
    print("深度学习检索改进诊断")
    print("="*80)
    
    # 分析分块质量
    analyze_chunk_quality()
    
    # 测试检索排名
    test_retrieval_ranking()
    
    # 测试改进的检索策略
    test_improved_retrieval()
    
    # 测试内容提取
    test_content_extraction()
    
    # 测试 RAG 查询
    test_rag_with_debug()
    
    print("\n" + "="*80)
    print("诊断完成")
    print("="*80 + "\n")


if __name__ == "__main__":
    main()
