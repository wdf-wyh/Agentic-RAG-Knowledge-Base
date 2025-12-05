"""Streamlit Web 界面"""
import streamlit as st
import os
from pathlib import Path

from config import Config
from document_processor import DocumentProcessor
from vector_store import VectorStore
from rag_assistant import RAGAssistant


# 页面配置
st.set_page_config(
    page_title="RAG 知识库助手",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded"
)


def init_session_state():
    """初始化 session state"""
    if "assistant" not in st.session_state:
        st.session_state.assistant = None
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "vector_store_loaded" not in st.session_state:
        st.session_state.vector_store_loaded = False


def load_assistant():
    """加载助手"""
    try:
        Config.validate()
        
        if st.session_state.assistant is None:
            vector_store = VectorStore()
            vector_store.load_vectorstore()
            
            if vector_store.vectorstore is not None:
                st.session_state.assistant = RAGAssistant(vector_store=vector_store)
                st.session_state.assistant.setup_qa_chain()
                st.session_state.vector_store_loaded = True
                return True
            else:
                st.error("未找到向量数据库，请先构建知识库")
                return False
        return True
    except Exception as e:
        st.error(f"加载失败: {str(e)}")
        return False


def sidebar():
    """侧边栏"""
    with st.sidebar:
        st.title("📚 RAG 知识库助手")
        st.markdown("---")
        
        # 配置信息
        st.subheader("⚙️ 配置")
        st.text(f"模型: {Config.LLM_MODEL}")
        st.text(f"Embedding: {Config.EMBEDDING_MODEL}")
        st.text(f"检索数量: {Config.TOP_K}")
        
        st.markdown("---")
        
        # 构建知识库
        st.subheader("🔨 构建知识库")
        
        documents_path = st.text_input(
            "文档目录",
            value=Config.DOCUMENTS_PATH
        )
        
        if st.button("开始构建", type="primary"):
            if not os.path.exists(documents_path):
                st.error(f"目录不存在: {documents_path}")
            else:
                with st.spinner("正在处理文档..."):
                    try:
                        processor = DocumentProcessor()
                        chunks = processor.process_documents(documents_path)
                        
                        if chunks:
                            vector_store = VectorStore()
                            vector_store.create_vectorstore(chunks)
                            st.success(f"✓ 知识库构建成功！共处理 {len(chunks)} 个文本块")
                            
                            # 重新加载
                            st.session_state.assistant = None
                            st.session_state.vector_store_loaded = False
                            st.rerun()
                        else:
                            st.warning("未找到可处理的文档")
                    except Exception as e:
                        st.error(f"构建失败: {str(e)}")
        
        st.markdown("---")
        
        # 状态显示
        st.subheader("📊 状态")
        if st.session_state.vector_store_loaded:
            st.success("✓ 知识库已加载")
        else:
            st.warning("⚠ 知识库未加载")
        
        st.text(f"对话轮次: {len(st.session_state.messages)}")
        
        if st.button("清空对话"):
            st.session_state.messages = []
            st.rerun()


def main_area():
    """主区域"""
    st.title("💬 知识库问答")
    
    # 检查并加载助手
    if not st.session_state.vector_store_loaded:
        if not load_assistant():
            st.info("👈 请先在侧边栏构建知识库")
            return
    
    # 显示历史消息
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            
            # 显示来源
            if message["role"] == "assistant" and "sources" in message:
                with st.expander("📖 参考来源"):
                    for i, source in enumerate(message["sources"], 1):
                        st.text(f"[{i}] {source}")
    
    # 输入框
    if prompt := st.chat_input("请输入你的问题..."):
        # 显示用户消息
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
        
        # 生成回答
        with st.chat_message("assistant"):
            with st.spinner("思考中..."):
                try:
                    result = st.session_state.assistant.query(prompt)
                    answer = result["answer"]
                    sources = []
                    
                    if "sources" in result and result["sources"]:
                        sources = [
                            doc.metadata.get("source", "未知来源")
                            for doc in result["sources"]
                        ]
                    
                    st.markdown(answer)
                    
                    # 显示来源
                    if sources:
                        with st.expander("📖 参考来源"):
                            for i, source in enumerate(sources, 1):
                                st.text(f"[{i}] {source}")
                    
                    # 保存消息
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": answer,
                        "sources": sources
                    })
                    
                except Exception as e:
                    error_msg = f"生成回答时出错: {str(e)}"
                    st.error(error_msg)
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": error_msg
                    })


def main():
    """主函数"""
    init_session_state()
    sidebar()
    main_area()


if __name__ == "__main__":
    main()
