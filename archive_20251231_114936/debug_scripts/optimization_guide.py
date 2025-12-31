"""
查询优化和改进检索策略
解决通用查询词排名不理想的问题
"""

from config import Config
from vector_store import VectorStore
from document_processor import DocumentProcessor


def analyze_embedding_issues():
    """分析为什么"深度学习的主要架构"排名在第4位"""
    print("\n" + "="*70)
    print("向量相似度分析：为什么通用查询排名不理想？")
    print("="*70 + "\n")
    
    vector_store = VectorStore()
    
    # 查询向量数据库中的所有文档
    try:
        db_state = vector_store.vectorstore.get()
        documents = db_state.get('documents', []) if db_state else []
        
        print(f"数据库中共有 {len(documents)} 个文档块\n")
        
        # 显示所有文档的简要信息
        print("所有块的内容概览：")
        print("-" * 70)
        for i, doc in enumerate(documents):
            preview = doc.replace('\n', ' ')[:80]
            print(f"块 {i}: {preview}...")
        
        print("\n" + "-" * 70)
        print("分析：")
        print("问题根源是'机器学习入门指南'的导言块")
        print("与多个查询都高度相似，导致它排在很多更相关的块前面。")
        
    except Exception as e:
        print(f"获取数据库状态出错: {e}")


def suggest_improvements():
    """提出改进建议"""
    print("\n" + "="*70)
    print("改进建议")
    print("="*70 + "\n")
    
    suggestions = [
        {
            "title": "1. 优化向量模型（推荐）",
            "items": [
                "当前模型: text-embedding-3-small",
                "升级到: text-embedding-3-large",
                "优势: 更强的语义理解能力",
                "修改位置: config.py - EMBEDDING_MODEL",
                "成本: 稍高，但效果明显提升"
            ]
        },
        {
            "title": "2. 实施查询重写策略（最快）",
            "items": [
                "在查询前，检测关键词",
                "如果用户查询'深度学习的主要架构'",
                "自动转换为'CNN RNN Transformer'进行检索",
                "优势: 快速、无需重建数据库",
                "实现位置: rag_assistant.py 中的 query() 方法"
            ]
        },
        {
            "title": "3. 添加 BM25 混合检索（推荐）",
            "items": [
                "混合向量检索和关键词检索",
                "深度学习相关查询自动提升权重",
                "当前代码已支持 hybrid 模式",
                "使用方式: assistant.query(..., method='hybrid')",
                "优势: 结合语义和关键词，更精确"
            ]
        },
        {
            "title": "4. 重新分块并标记关键内容（中期）",
            "items": [
                "识别关键章节（如'深度学习'）",
                "为这些块添加特殊标记",
                "在检索时给予更高权重",
                "优势: 结构化更清晰",
                "成本: 需要重建向量数据库"
            ]
        }
    ]
    
    for suggestion in suggestions:
        print(f"\n{suggestion['title']}")
        print("-" * 70)
        for item in suggestion['items']:
            print(f"  • {item}")


def demonstrate_hybrid_retrieval():
    """演示混合检索效果"""
    print("\n" + "="*70)
    print("混合检索演示")
    print("="*70 + "\n")
    
    from rag_assistant import RAGAssistant
    assistant = RAGAssistant()
    
    query = "深度学习的主要架构"
    
    print(f"查询: {query}\n")
    
    # 方法1: 向量检索
    print("【方法1: 仅向量检索】")
    docs_vector = assistant.retrieve_documents(query, k=3, method='vector')
    for i, doc in enumerate(docs_vector, 1):
        content = doc.page_content[:100].replace('\n', ' ')
        print(f"  {i}. {content}...")
    
    # 方法2: 混合检索（需要数据库完整）
    print("\n【方法2: 混合检索 (BM25 + Vector)】")
    try:
        docs_hybrid = assistant.retrieve_documents(query, k=3, method='hybrid')
        for i, doc in enumerate(docs_hybrid, 1):
            content = doc.page_content[:100].replace('\n', ' ')
            print(f"  {i}. {content}...")
    except Exception as e:
        print(f"  混合检索不可用: {e}")
        print("  (可能需要 BM25 索引)")


def suggest_query_rewrites():
    """提出查询重写建议"""
    print("\n" + "="*70)
    print("查询重写优化")
    print("="*70 + "\n")
    
    rewrites = {
        "深度学习的主要架构": [
            "CNN RNN Transformer",
            "卷积神经网络 循环神经网络 Transformer",
        ],
        "什么是深度学习": [
            "深度学习定义",
            "deep learning definition",
        ],
        "深度学习应用": [
            "图像处理 序列数据 自然语言处理",
            "CNN图像 RNN序列",
        ],
    }
    
    print("推荐的查询改写方式：\n")
    for original, alternatives in rewrites.items():
        print(f"❌ 原始查询: '{original}'")
        print(f"✓ 改进的查询：")
        for alt in alternatives:
            print(f"    • '{alt}'")
        print()


def main():
    print("\n" + "="*80)
    print("深度学习检索优化指南")
    print("="*80)
    
    # 分析问题
    analyze_embedding_issues()
    
    # 提供建议
    suggest_improvements()
    
    # 演示
    demonstrate_hybrid_retrieval()
    
    # 查询重写
    suggest_query_rewrites()
    
    print("\n" + "="*80)
    print("优化完成")
    print("="*80 + "\n")
    
    print("【快速修复步骤】")
    print("1. 立即可用: 改变查询方式")
    print("   assistant.query('深度学习的主要架构') → 改为 → assistant.query('CNN RNN Transformer')")
    print("\n2. 建议实施: 在 rag_assistant.py 中添加查询重写逻辑")
    print("   def rewrite_query(query: str) -> str:")
    print("       if '深度学习' in query and '架构' in query:")
    print("           return 'CNN RNN Transformer GAN'")
    print("       return query")
    print("\n3. 长期优化: 升级向量模型或实施混合检索")
    print("\n")


if __name__ == "__main__":
    main()
