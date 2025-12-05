"""RAG 检索增强生成模块"""
from typing import List, Optional, Any

from langchain_classic.chains.retrieval_qa.base import RetrievalQA
from langchain.chat_models import init_chat_model
from langchain_core.prompts import PromptTemplate
from typing import Any

from config import Config
from vector_store import VectorStore


class RAGAssistant:
    """RAG 知识库助手"""
    
    # 默认提示词模板
    DEFAULT_PROMPT_TEMPLATE = """你是一个专业的知识库助手。请根据以下提供的上下文信息来回答用户的问题。

上下文信息:
{context}

用户问题: {question}

请基于上述上下文信息给出准确、详细的回答。如果上下文中没有相关信息，请明确告知用户你无法根据现有知识库回答该问题。

回答:"""
    
    def __init__(
        self,
        vector_store: VectorStore = None,
        model_name: str = None,
        temperature: float = None,
        max_tokens: int = None,
    ):
        """初始化 RAG 助手
        
        Args:
            vector_store: 向量数据库实例
            model_name: LLM 模型名称
            temperature: 温度参数
            max_tokens: 最大生成 token 数
        """
        self.vector_store = vector_store or VectorStore()
        
        # 初始化 LLM（使用 langchain 的 init_chat_model ）
        model = model_name or Config.LLM_MODEL
        self.llm = init_chat_model(
            model,
            temperature=temperature or Config.TEMPERATURE,
            max_tokens=max_tokens or Config.MAX_TOKENS,
        )
        
        self.qa_chain: Optional[RetrievalQA] = None
    
    def setup_qa_chain(self, prompt_template: str = None) -> RetrievalQA:
        """设置问答链
        
        Args:
            prompt_template: 自定义提示词模板
            
        Returns:
            问答链实例
        """
        # 确保向量数据库已加载
        if self.vector_store.vectorstore is None:
            self.vector_store.load_vectorstore()
        
        if self.vector_store.vectorstore is None:
            raise ValueError("向量数据库未初始化，请先创建或加载数据库")
        
        # 创建提示词模板
        template = prompt_template or self.DEFAULT_PROMPT_TEMPLATE
        prompt = PromptTemplate(
            template=template,
            input_variables=["context", "question"]
        )
        
        # 创建检索器
        retriever = self.vector_store.get_retriever()
        
        # 创建问答链
        self.qa_chain = RetrievalQA.from_chain_type(
            llm=self.llm,
            chain_type="stuff",
            retriever=retriever,
            return_source_documents=True,
            chain_type_kwargs={"prompt": prompt}
        )
        
        print("✓ 问答链初始化成功")
        return self.qa_chain
    
    def query(self, question: str, return_sources: bool = True) -> dict:
        """查询知识库
        
        Args:
            question: 用户问题
            return_sources: 是否返回来源文档
            
        Returns:
            包含答案和来源的字典
        """
        if self.qa_chain is None:
            self.setup_qa_chain()
        
        print(f"\n问题: {question}")
        print("检索中...")
        
        result = self.qa_chain({"query": question})
        
        response = {
            "question": question,
            "answer": result["result"],
        }
        
        if return_sources and "source_documents" in result:
            response["sources"] = result["source_documents"]
            print(f"\n找到 {len(result['source_documents'])} 个相关文档片段")
        
        return response
    
    def simple_query(self, question: str) -> str:
        """简单查询，只返回答案
        
        Args:
            question: 用户问题
            
        Returns:
            答案文本
        """
        result = self.query(question, return_sources=False)
        return result["answer"]
    
    def retrieve_documents(self, query: str, k: int = None) -> List[Any]:
        """检索相关文档（不生成答案）
        
        Args:
            query: 查询文本
            k: 返回文档数量
            
        Returns:
            相关文档列表
        """
        return self.vector_store.similarity_search(query, k=k)
    
    def chat(self):
        """交互式对话模式"""
        print("\n" + "="*50)
        print("知识库助手已启动（输入 'quit' 或 'exit' 退出）")
        print("="*50 + "\n")
        
        if self.qa_chain is None:
            self.setup_qa_chain()
        
        while True:
            try:
                question = input("\n你的问题: ").strip()
                
                if question.lower() in ["quit", "exit", "退出"]:
                    print("再见！")
                    break
                
                if not question:
                    continue
                
                result = self.query(question)
                
                print(f"\n回答: {result['answer']}")
                
                if "sources" in result and result["sources"]:
                    print(f"\n参考来源 ({len(result['sources'])} 个文档片段):")
                    for i, doc in enumerate(result["sources"], 1):
                        source = doc.metadata.get("source", "未知来源")
                        preview = doc.page_content[:100].replace("\n", " ")
                        print(f"  [{i}] {source}")
                        print(f"      {preview}...")
                
            except KeyboardInterrupt:
                print("\n\n再见！")
                break
            except Exception as e:
                print(f"\n错误: {str(e)}")
