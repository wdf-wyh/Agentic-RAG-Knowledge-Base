"""智能模式首轮不应把当前问题当成历史对话。"""

from src.agent.intent_router import IntentAnalysis, IntentType
from src.agent.rag_agent import RAGAgent
from src.services.conversation_manager import ConversationManager


def test_has_prior_conversation_empty_markers():
    assert RAGAgent._has_prior_conversation("") is False
    assert RAGAgent._has_prior_conversation("（无历史对话）") is False
    assert RAGAgent._has_prior_conversation("无历史对话") is False
    assert RAGAgent._has_prior_conversation("1. 👤 用户: hi") is True


def test_load_prior_history_excludes_current_user_turn(tmp_path):
    manager = ConversationManager(storage_path=str(tmp_path))
    agent = RAGAgent.__new__(RAGAgent)
    agent._conversation_manager = manager
    agent._current_conversation_id = manager.create_conversation()

    history = agent._load_prior_history_then_save_user("rewqrewqre", save_to_history=True)

    assert history == ""
    stored = manager.get_history(agent._current_conversation_id)
    assert len(stored) == 1
    assert stored[0].role == "user"
    assert stored[0].content == "rewqrewqre"


def test_load_prior_history_keeps_previous_turns(tmp_path):
    manager = ConversationManager(storage_path=str(tmp_path))
    agent = RAGAgent.__new__(RAGAgent)
    agent._conversation_manager = manager
    cid = manager.create_conversation()
    agent._current_conversation_id = cid
    manager.add_message(cid, "user", "什么是 RAG？")
    manager.add_message(cid, "assistant", "RAG 是检索增强生成。")

    history = agent._load_prior_history_then_save_user("刚才说的是什么", save_to_history=True)

    assert "什么是 RAG" in history
    assert "检索增强生成" in history
    assert history.count("刚才说的是什么") == 0


def test_coerce_conversation_intent_without_history():
    agent = RAGAgent.__new__(RAGAgent)
    analysis = IntentAnalysis(
        intent=IntentType.CONVERSATION,
        confidence=0.9,
        reasoning="误判",
        suggested_tools=[],
        sub_questions=[],
        needs_realtime=False,
        topic_keywords=[],
    )

    fixed = agent._coerce_conversation_intent(analysis, "")
    assert fixed.intent == IntentType.MULTI_STEP
