#!/usr/bin/env python3
"""
简化的 RAG 查询方式
使用 Ollama 本地 LLM 直接处理上下文，避免复杂的链问题
"""

from config import Config
from vector_store import VectorStore
from rag_assistant import RAGAssistant
from langchain_community.llms import Ollama
import time


def simple_rag_query(question: str, k: int = 3) -> dict:
    """简化的 RAG 查询
    
    Args:
        question: 用户问题
        k: 检索的文档数量
        
    Returns:
        包含答案和来源的字典
    """
    print(f"\n📝 问题: {question}\n")
    
    # 0. 优化查询
    optimized_q = RAGAssistant.optimize_query(question)
    if optimized_q != question:
        print(f"✓ 查询优化: '{question}' → '{optimized_q}'")
        search_query = optimized_q
    else:
        search_query = question
    
    # 1. 检索相关文档
    print("🔍 检索相关文档...")
    vector_store = VectorStore()
    docs = vector_store.similarity_search(search_query, k=k)
    
    if not docs:
        print("❌ 未找到相关文档")
        return {"question": question, "answer": "抱歉，我在知识库中未找到相关信息。", "sources": []}
    
    print(f"✅ 找到 {len(docs)} 个相关文档\n")
    
    # 2. 组织上下文
    context_parts = []
    sources = []
    for i, doc in enumerate(docs, 1):
        content = doc.page_content
        source = doc.metadata.get('source', '未知') if hasattr(doc, 'metadata') else '未知'
        context_parts.append(f"【文档{i}】{source}\n{content}")
        sources.append(doc)
    
    context = "\n\n".join(context_parts)
    
    # 3. 构建提示
    prompt = f"""根据以下上下文信息回答问题。

【上下文信息】
{context}

【问题】
{question}

【回答】
请基于上述上下文信息给出准确的回答。如果上下文中没有相关信息，请明确说明。"""
    
    # 4. 调用 LLM
    print("🤖 LLM 生成答案...")
    start = time.time()
    
    llm = Ollama(
        base_url=Config.OLLAMA_API_URL,
        model=Config.OLLAMA_MODEL,
        temperature=Config.TEMPERATURE,
        num_predict=Config.MAX_TOKENS,
    )
    
    try:
        answer = llm.invoke(prompt)
        elapsed = time.time() - start
        
        print(f"✅ 生成完成（耗时 {elapsed:.2f}秒）\n")
        
        return {
            "question": question,
            "answer": answer,
            "sources": sources,
            "elapsed": elapsed
        }
        
    except Exception as e:
        print(f"❌ LLM 生成失败: {e}\n")
        return {
            "question": question,
            "answer": f"LLM 生成失败，请检查 Ollama 连接。错误: {e}",
            "sources": sources,
            "error": str(e)
        }


def main():
    print("\n" + "="*80)
    print("简化 RAG 查询测试")
    print("="*80)
    
    queries = [
        "深度学习的主要架构有哪些？",
        "什么是 CNN 和 RNN？",
        "机器学习和深度学习有什么区别？",
    ]
    
    for query in queries:
        result = simple_rag_query(query, k=3)
        
        print("="*80)
        print(f"\n答案:")
        print("-"*80)
        answer = result.get('answer', '无答案')
        print(answer)
        
        if 'sources' in result and result['sources']:
            print(f"\n📚 参考来源 ({len(result['sources'])} 个):")
            print("-"*80)
            for i, doc in enumerate(result['sources'], 1):
                if hasattr(doc, 'metadata'):
                    source = doc.metadata.get('source', '未知')
                else:
                    source = '未知'
                content = doc.page_content[:100].replace('\n', ' ') if hasattr(doc, 'page_content') else ''
                print(f"  [{i}] {source}")
                print(f"      {content}...\n")
        
        if 'elapsed' in result:
            print(f"⏱️  耗时: {result['elapsed']:.2f}秒\n")
        
        print("\n")


if __name__ == "__main__":
    main()
