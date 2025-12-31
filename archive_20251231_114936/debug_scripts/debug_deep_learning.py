"""
深度学习检索问题诊断脚本
用于排查为什么深度学习相关内容无法被检索
"""

from config import Config
from document_processor import DocumentProcessor
from vector_store import VectorStore
from rag_assistant import RAGAssistant
import json

def debug_documents():
    """检查文档中的深度学习内容"""
    print("\n" + "="*60)
    print("步骤1: 检查源文档中的深度学习内容")
    print("="*60 + "\n")
    
    processor = DocumentProcessor()
    documents = processor.load_documents_from_directory("./documents")
    
    print(f"加载了 {len(documents)} 个文档\n")
    
    # 检查深度学习相关的内容
    deep_learning_count = 0
    for i, doc in enumerate(documents):
        content = doc.page_content
        if "深度学习" in content or "深度学习" in content or "deep learning" in content.lower():
            deep_learning_count += 1
            print(f"文档 {i} 包含深度学习相关内容:")
            print(f"来源: {doc.metadata.get('source', '未知')}")
            # 查找深度学习的位置
            idx = content.find("深度学习")
            if idx != -1:
                print(f"预览: ...{content[max(0, idx-50):idx+100]}...")
            print()
    
    print(f"总共找到 {deep_learning_count} 个包含深度学习的文档片段\n")
    return documents


def debug_chunks():
    """检查分块后的深度学习内容"""
    print("\n" + "="*60)
    print("步骤2: 检查分块中的深度学习内容")
    print("="*60 + "\n")
    
    processor = DocumentProcessor()
    documents = processor.load_documents_from_directory("./documents")
    chunks = processor.split_documents(documents)
    
    print(f"分割后共有 {len(chunks)} 个文本块\n")
    
    # 检查深度学习相关的块
    deep_learning_chunks = []
    for i, chunk in enumerate(chunks):
        content = chunk.page_content
        if "深度学习" in content or "deep learning" in content.lower():
            deep_learning_chunks.append((i, chunk))
            print(f"块 {i}: (长度: {len(content)})")
            print(f"内容: {content[:200]}...")
            print(f"Metadata: {chunk.metadata}")
            print()
    
    print(f"总共找到 {len(deep_learning_chunks)} 个包含深度学习的块\n")
    return chunks, deep_learning_chunks


def debug_vector_db():
    """检查向量数据库中的内容"""
    print("\n" + "="*60)
    print("步骤3: 检查向量数据库的状态")
    print("="*60 + "\n")
    
    vector_store = VectorStore()
    vs = vector_store.load_vectorstore()
    
    if vs is None:
        print("向量数据库不存在或未初始化！")
        return None
    
    # 检查数据库中有多少条记录
    try:
        # 获取所有数据
        db_state = vs.get()
        if db_state:
            print(f"向量数据库中存储了 {len(db_state.get('ids', []))} 条记录")
            print(f"包括 {len(db_state.get('embeddings', []))} 个向量")
            
            # 检查是否有深度学习相关的记录
            documents = db_state.get('documents', [])
            deep_learning_count = 0
            for i, doc in enumerate(documents):
                if "深度学习" in doc or "deep learning" in doc.lower():
                    deep_learning_count += 1
                    print(f"\n找到深度学习内容在记录 {i}:")
                    print(f"预览: {doc[:300]}...")
            
            print(f"\n数据库中共找到 {deep_learning_count} 条包含深度学习的记录\n")
            return db_state
    except Exception as e:
        print(f"获取数据库状态出错: {e}\n")
        return None


def debug_retrieval():
    """检查检索功能"""
    print("\n" + "="*60)
    print("步骤4: 测试检索功能")
    print("="*60 + "\n")
    
    vector_store = VectorStore()
    
    # 测试不同的查询
    test_queries = [
        "深度学习的主要架构",
        "深度学习",
        "CNN RNN Transformer",
        "卷积神经网络循环神经网络",
        "什么是深度学习"
    ]
    
    print(f"配置信息:")
    print(f"- TOP_K: {Config.TOP_K}")
    print(f"- MAX_DISTANCE: {getattr(Config, 'MAX_DISTANCE', None)}")
    print(f"- EMBEDDING_MODEL: {Config.EMBEDDING_MODEL}\n")
    
    for query in test_queries:
        print(f"\n查询: '{query}'")
        print("-" * 40)
        
        try:
            # 使用带分数的搜索
            results = vector_store.similarity_search_with_score(query, k=Config.TOP_K)
            
            if not results:
                print("❌ 未找到任何结果")
            else:
                print(f"✓ 找到 {len(results)} 个结果:")
                for i, (doc, score) in enumerate(results, 1):
                    print(f"\n  [{i}] 分数/距离: {score}")
                    print(f"      来源: {doc.metadata.get('source', '未知')}")
                    content = doc.page_content[:150].replace('\n', ' ')
                    print(f"      内容: {content}...")
        except Exception as e:
            print(f"❌ 检索出错: {e}")


def debug_rag_query():
    """检查RAG查询"""
    print("\n" + "="*60)
    print("步骤5: 测试RAG查询")
    print("="*60 + "\n")
    
    try:
        assistant = RAGAssistant()
        
        queries = [
            "深度学习的主要架构有哪些?",
            "什么是CNN和RNN?"
        ]
        
        for query in queries:
            print(f"\n查询: {query}")
            print("-" * 60)
            
            try:
                result = assistant.query(query, return_sources=True, method='vector', k=3)
                
                print(f"答案: {result.get('answer', '无答案')[:300]}...\n")
                
                if 'sources' in result:
                    print(f"来源数量: {len(result['sources'])}")
                    for i, doc in enumerate(result['sources'], 1):
                        source = doc.metadata.get('source', '未知') if hasattr(doc, 'metadata') else '未知'
                        content = doc.page_content[:100].replace('\n', ' ') if hasattr(doc, 'page_content') else ''
                        print(f"  [{i}] {source}: {content}...")
                
            except Exception as e:
                print(f"❌ RAG查询出错: {e}")
    
    except Exception as e:
        print(f"❌ 初始化RAG助手失败: {e}")


def main():
    """运行所有诊断"""
    print("\n" + "="*80)
    print("深度学习检索问题诊断")
    print("="*80)
    
    # 步骤1: 检查源文档
    debug_documents()
    
    # 步骤2: 检查分块
    chunks, dl_chunks = debug_chunks()
    
    # 步骤3: 检查向量数据库
    db_state = debug_vector_db()
    
    # 步骤4: 测试检索
    debug_retrieval()
    
    # 步骤5: 测试RAG
    debug_rag_query()
    
    print("\n" + "="*80)
    print("诊断完成")
    print("="*80 + "\n")


if __name__ == "__main__":
    main()
