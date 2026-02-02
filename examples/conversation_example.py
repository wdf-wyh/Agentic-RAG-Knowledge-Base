"""对话历史功能使用示例"""

import asyncio
from src.services.conversation_manager import ConversationManager
from src.services.rag_assistant import RAGAssistant
from src.core.vector_store import VectorStore
from src.models.schemas import ConversationMessage


async def example_continuous_conversation():
    """示例：使用对话历史进行连续对话"""
    
    print("=" * 70)
    print("示例：连续对话功能")
    print("=" * 70)
    
    # 1. 初始化组件
    print("\n1. 初始化RAG助手...")
    vector_store = VectorStore()
    vector_store.load_vectorstore()
    assistant = RAGAssistant(vector_store=vector_store)
    assistant.setup_qa_chain()
    print("   ✓ RAG助手已就绪")
    
    # 2. 创建对话管理器
    print("\n2. 创建对话管理器...")
    conv_manager = ConversationManager()
    conv_id = conv_manager.create_conversation()
    print(f"   ✓ 会话ID: {conv_id}")
    
    # 3. 第一轮对话
    print("\n3. 第一轮对话")
    print("-" * 70)
    question1 = "什么是深度学习？"
    print(f"👤 用户: {question1}")
    
    # 添加用户消息
    conv_manager.add_message(conv_id, "user", question1)
    
    # 查询（不带历史）
    result1 = assistant.query(question1, return_sources=False)
    answer1 = result1.get("answer", "")
    print(f"🤖 助手: {answer1[:200]}...")
    
    # 保存助手回复
    conv_manager.add_message(conv_id, "assistant", answer1)
    
    # 4. 第二轮对话 - 使用指代词
    print("\n4. 第二轮对话（使用指代词）")
    print("-" * 70)
    question2 = "它有哪些主要应用？"  # "它"指代"深度学习"
    print(f"👤 用户: {question2}")
    
    # 添加用户消息
    conv_manager.add_message(conv_id, "user", question2)
    
    # 获取历史并查询
    history = conv_manager.get_history(conv_id, max_messages=4)  # 排除刚添加的用户消息
    print(f"   [系统] 使用历史消息数: {len(history) - 1}")
    
    result2 = assistant.query(
        question2, 
        return_sources=False,
        conversation_history=history[:-1]  # 传入历史（排除当前问题）
    )
    answer2 = result2.get("answer", "")
    print(f"🤖 助手: {answer2[:200]}...")
    
    # 保存助手回复
    conv_manager.add_message(conv_id, "assistant", answer2)
    
    # 5. 第三轮对话 - 继续追问
    print("\n5. 第三轮对话（继续追问）")
    print("-" * 70)
    question3 = "请详细解释第一个应用"
    print(f"👤 用户: {question3}")
    
    conv_manager.add_message(conv_id, "user", question3)
    
    # 获取更新的历史
    history = conv_manager.get_history(conv_id, max_messages=6)
    print(f"   [系统] 使用历史消息数: {len(history) - 1}")
    
    result3 = assistant.query(
        question3,
        return_sources=False,
        conversation_history=history[:-1]
    )
    answer3 = result3.get("answer", "")
    print(f"🤖 助手: {answer3[:200]}...")
    
    conv_manager.add_message(conv_id, "assistant", answer3)
    
    # 6. 查看完整对话历史
    print("\n6. 完整对话历史")
    print("-" * 70)
    full_history = conv_manager.get_history(conv_id)
    for i, msg in enumerate(full_history, 1):
        role_icon = "👤" if msg.role == "user" else "🤖"
        role_name = "用户" if msg.role == "user" else "助手"
        content_preview = msg.content[:100] + "..." if len(msg.content) > 100 else msg.content
        print(f"[{i}] {role_icon} {role_name}: {content_preview}")
    
    # 7. 保存对话
    print("\n7. 保存对话到磁盘...")
    conv_manager.save_conversation(conv_id)
    print(f"   ✓ 已保存到 conversations/{conv_id}.json")
    
    # 8. 格式化历史用于展示
    print("\n8. 格式化的LLM上下文（最近2轮）")
    print("-" * 70)
    formatted = conv_manager.format_history_for_llm(conv_id, max_turns=2)
    print(formatted)
    
    print("\n" + "=" * 70)
    print("示例完成！")
    print("=" * 70)


def example_without_history():
    """对比示例：不使用历史的对话"""
    
    print("\n\n" + "=" * 70)
    print("对比示例：不使用历史的对话")
    print("=" * 70)
    
    vector_store = VectorStore()
    vector_store.load_vectorstore()
    assistant = RAGAssistant(vector_store=vector_store)
    assistant.setup_qa_chain()
    
    print("\n场景：用户使用指代词但系统没有历史上下文")
    print("-" * 70)
    
    # 第一个问题
    question1 = "什么是CNN？"
    print(f"👤 用户: {question1}")
    result1 = assistant.query(question1, return_sources=False)
    print(f"🤖 助手: {result1.get('answer', '')[:150]}...")
    
    # 第二个问题 - 使用指代词但没有历史
    print()
    question2 = "它的优势是什么？"  # "它"指代不明
    print(f"👤 用户: {question2}")
    result2 = assistant.query(question2, return_sources=False)
    print(f"🤖 助手: {result2.get('answer', '')[:150]}...")
    print("\n⚠️  注意：助手无法理解'它'指代什么，因为没有历史上下文")
    
    print("\n" + "=" * 70)


if __name__ == "__main__":
    try:
        # 运行带历史的示例
        asyncio.run(example_continuous_conversation())
        
        # 运行不带历史的对比示例
        # example_without_history()
        
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        import traceback
        traceback.print_exc()
