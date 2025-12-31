"""
最终验证：测试实际的 RAG 查询
"""

from rag_assistant import RAGAssistant
import time

def test_rag_queries():
    """测试各种 RAG 查询"""
    print("\n" + "="*80)
    print("RAG 查询测试（实际用户查询）")
    print("="*80 + "\n")
    
    assistant = RAGAssistant()
    
    queries = [
        "深度学习的主要架构有哪些？",
        "什么是 CNN 和 RNN？",
        "机器学习有哪些类型？",
    ]
    
    for i, query in enumerate(queries, 1):
        print(f"\n【查询 {i}】{query}")
        print("="*80)
        
        start = time.time()
        result = assistant.query(query, return_sources=True, method='vector', k=3)
        elapsed = time.time() - start
        
        print(f"\n📝 答案:")
        print("-"*80)
        answer = result.get('answer', '无答案')
        # 只打印前 500 字符
        if len(answer) > 500:
            print(answer[:500] + "...\n")
        else:
            print(answer + "\n")
        
        # 显示来源
        if 'sources' in result:
            print(f"📚 参考来源 ({len(result['sources'])} 个):")
            print("-"*80)
            for j, doc in enumerate(result['sources'], 1):
                try:
                    if hasattr(doc, 'page_content'):
                        source = doc.metadata.get('source', '未知') if hasattr(doc, 'metadata') else '未知'
                        content = doc.page_content[:80].replace('\n', ' ')
                        print(f"  [{j}] {source}")
                        print(f"      {content}...\n")
                    else:
                        print(f"  [{j}] (无法展示)\n")
                except Exception as e:
                    print(f"  [{j}] 错误: {e}\n")
        
        print(f"⏱️  耗时: {elapsed:.2f}秒\n")


if __name__ == "__main__":
    test_rag_queries()
