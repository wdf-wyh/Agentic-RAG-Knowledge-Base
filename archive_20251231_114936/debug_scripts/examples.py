"""示例：如何使用 RAG 知识库助手"""

from config import Config
from document_processor import DocumentProcessor
from vector_store import VectorStore
from rag_assistant import RAGAssistant


def example_1_build_knowledge_base():
    """示例1: 构建知识库"""
    print("\n" + "="*60)
    print("示例1: 构建知识库")
    print("="*60 + "\n")
    
    # 1. 创建文档处理器
    processor = DocumentProcessor(chunk_size=500, chunk_overlap=50)
    
    # 2. 处理文档目录
    documents_path = "./documents"
    chunks = processor.process_documents(documents_path)
    
    print(f"处理完成，共 {len(chunks)} 个文本块")
    
    # 3. 创建向量数据库
    vector_store = VectorStore(persist_directory="./vector_db")
    vector_store.create_vectorstore(chunks)
    
    print("\n知识库构建完成！")


def example_2_simple_query():
    """示例2: 简单查询"""
    print("\n" + "="*60)
    print("示例2: 简单查询")
    print("="*60 + "\n")
    
    # 1. 加载向量数据库
    vector_store = VectorStore()
    vector_store.load_vectorstore()
    
    # 2. 创建 RAG 助手
    assistant = RAGAssistant(vector_store=vector_store)
    
    # 3. 查询
    question = "什么是机器学习？"
    answer = assistant.simple_query(question)
    
    print(f"问题: {question}")
    print(f"回答: {answer}")


def example_3_detailed_query():
    """示例3: 详细查询（包含来源）"""
    print("\n" + "="*60)
    print("示例3: 详细查询")
    print("="*60 + "\n")
    
    # 创建助手
    assistant = RAGAssistant()
    
    # 查询问题
    question = "深度学习和机器学习有什么区别？"
    result = assistant.query(question, return_sources=True)
    
    # 显示结果
    print(f"问题: {result['question']}\n")
    print(f"回答:\n{result['answer']}\n")
    
    if "sources" in result:
        print("参考来源:")
        for i, doc in enumerate(result["sources"], 1):
            source = doc.metadata.get("source", "未知")
            content_preview = doc.page_content[:100].replace("\n", " ")
            print(f"\n[{i}] 来源: {source}")
            print(f"    内容预览: {content_preview}...")


def example_4_custom_prompt():
    """示例4: 自定义提示词"""
    print("\n" + "="*60)
    print("示例4: 自定义提示词")
    print("="*60 + "\n")
    
    # 自定义提示词模板
    custom_prompt = """你是一个专业的技术文档助手。请基于以下上下文回答用户问题。

上下文信息:
{context}

用户问题: {question}

要求:
1. 回答要准确、简洁
2. 如果上下文中没有相关信息，请明确说明
3. 可以适当添加代码示例

回答:"""
    
    # 创建助手并使用自定义提示词
    assistant = RAGAssistant()
    assistant.setup_qa_chain(prompt_template=custom_prompt)
    
    # 查询
    answer = assistant.simple_query("如何使用 Python 读取 CSV 文件？")
    print(f"回答:\n{answer}")


def example_5_retrieval_only():
    """示例5: 只检索不生成"""
    print("\n" + "="*60)
    print("示例5: 只检索文档（不生成回答）")
    print("="*60 + "\n")
    
    # 创建助手
    assistant = RAGAssistant()
    
    # 只检索相关文档
    query = "神经网络"
    docs = assistant.retrieve_documents(query, k=3)
    
    print(f"查询: {query}")
    print(f"找到 {len(docs)} 个相关文档:\n")
    
    for i, doc in enumerate(docs, 1):
        source = doc.metadata.get("source", "未知")
        content = doc.page_content[:150].replace("\n", " ")
        print(f"[{i}] {source}")
        print(f"    {content}...\n")


def example_6_interactive_chat():
    """示例6: 交互式对话"""
    print("\n" + "="*60)
    print("示例6: 交互式对话")
    print("="*60 + "\n")
    
    # 创建助手
    assistant = RAGAssistant()
    
    # 启动交互式对话
    assistant.chat()


def example_7_batch_queries():
    """示例7: 批量查询"""
    print("\n" + "="*60)
    print("示例7: 批量查询")
    print("="*60 + "\n")
    
    # 创建助手
    assistant = RAGAssistant()
    
    # 准备问题列表
    questions = [
        "什么是监督学习？",
        "什么是无监督学习？",
        "什么是强化学习？",
    ]
    
    # 批量查询
    for i, question in enumerate(questions, 1):
        print(f"\n问题 {i}: {question}")
        answer = assistant.simple_query(question)
        print(f"回答: {answer}")
        print("-" * 60)


def main():
    """运行所有示例"""
    print("\n" + "="*60)
    print("RAG 知识库助手 - 使用示例")
    print("="*60)
    
    examples = {
        "1": ("构建知识库", example_1_build_knowledge_base),
        "2": ("简单查询", example_2_simple_query),
        "3": ("详细查询", example_3_detailed_query),
        "4": ("自定义提示词", example_4_custom_prompt),
        "5": ("只检索不生成", example_5_retrieval_only),
        "6": ("交互式对话", example_6_interactive_chat),
        "7": ("批量查询", example_7_batch_queries),
    }
    
    print("\n可用示例:")
    for key, (name, _) in examples.items():
        print(f"  {key}. {name}")
    print("  0. 退出")
    
    while True:
        choice = input("\n请选择要运行的示例 (输入数字): ").strip()
        
        if choice == "0":
            print("再见！")
            break
        
        if choice in examples:
            try:
                _, example_func = examples[choice]
                example_func()
            except Exception as e:
                print(f"\n错误: {str(e)}")
        else:
            print("无效选择，请重新输入")


if __name__ == "__main__":
    main()
