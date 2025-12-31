#!/usr/bin/env python3
"""
RAG 知识库系统 - 命令行工具入口

使用方式:
    python run_cli.py build --documents ./documents
    python run_cli.py query --question "什么是机器学习？"
    python run_cli.py chat
    python run_cli.py chat --provider ollama
"""
import os
import sys
import argparse
import re

# 确保项目根目录在 Python 路径中
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.config.settings import Config
from src.core.document_processor import DocumentProcessor
from src.core.vector_store import VectorStore
from src.services.rag_assistant import RAGAssistant
from src.services.ollama_client import generate as ollama_generate


def build_knowledge_base(documents_path: str):
    """构建知识库
    
    Args:
        documents_path: 文档目录路径
    """
    print("\n" + "="*60)
    print("开始构建知识库")
    print("="*60)
    
    # 验证配置
    Config.validate()
    
    # 处理文档
    processor = DocumentProcessor()
    chunks = processor.process_documents(documents_path)
    
    if not chunks:
        print("没有文档需要处理")
        return
    
    # 创建向量数据库
    vector_store = VectorStore()
    vector_store.create_vectorstore(chunks)
    
    print("\n" + "="*60)
    print("知识库构建完成！")
    print("="*60)


def query_knowledge_base(question: str, provider: str = None, ollama_model: str = None, ollama_api_url: str = None):
    """查询知识库
    
    Args:
        question: 问题
        provider: 模型提供者
        ollama_model: Ollama 模型名称
        ollama_api_url: Ollama API URL
    """
    Config.validate()

    final_provider = provider or Config.MODEL_PROVIDER

    assistant = RAGAssistant()

    if final_provider and final_provider.lower() == "ollama":
        try:
            docs = assistant.retrieve_documents(question, k=Config.TOP_K)

            contexts = []
            for doc in docs:
                if hasattr(doc, "page_content"):
                    contexts.append(doc.page_content)
                elif isinstance(doc, dict):
                    contexts.append(doc.get("page_content") or doc.get("content") or str(doc))
                else:
                    contexts.append(str(doc))

            context_text = "\n\n".join(contexts)
            prompt = (
                "请基于下面的上下文，用完整、连贯的中文回答用户的问题。只输出回答的纯文本，不要包含任何 JSON 对象、代码块、注释或额外说明。\n"
                + f"基于以下上下文回答问题:\n{context_text}\n\n问题: {question}\n\n"
                + "回答示例：这是示例答案\n"
            )

            model_name = ollama_model or "gemma3:4b"
            api_url = ollama_api_url or None

            ollama_text = ollama_generate(
                model=model_name,
                prompt=prompt,
                max_tokens=Config.MAX_TOKENS,
                temperature=Config.TEMPERATURE,
                api_url=api_url,
            )

            result = {
                "question": question,
                "answer": ollama_text,
                "sources": docs,
            }
        except Exception as e:
            print(f"调用本地 Ollama 失败: {e}")
            result = assistant.query(question)
    else:
        result = assistant.query(question)

    print(f"\n回答:\n{result['answer']}")

    if "sources" in result and result["sources"]:
        print(f"\n参考来源:")
        seen_sources = set()
        source_count = 1
        for doc in result["sources"]:
            source = getattr(doc, "metadata", {}).get("source", "未知") if hasattr(doc, "metadata") else "未知"
            if source not in seen_sources:
                seen_sources.add(source)
                print(f"  [{source_count}] {source}")
                source_count += 1


def start_chat(provider: str = None, ollama_model: str = None, ollama_api_url: str = None):
    """启动交互式对话"""
    Config.validate()
    
    final_provider = provider if provider is not None else Config.MODEL_PROVIDER
    
    if final_provider and final_provider.lower() == "ollama":
        print("\n" + "="*50)
        print("知识库助手已启动（Ollama 模式，输入 'quit' 或 'exit' 退出）")
        print("="*50 + "\n")
        
        assistant = RAGAssistant()
        assistant.vector_store.load_vectorstore()
        model_name = ollama_model or "gemma3:4b"
        api_url = ollama_api_url or None
        
        while True:
            try:
                question = input("\n你的问题: ").strip()
                
                if question.lower() in ["quit", "exit", "退出"]:
                    print("再见！")
                    break
                
                if not question:
                    continue
                
                docs = assistant.retrieve_documents(question, k=Config.TOP_K)
                
                contexts = []
                for doc in docs:
                    if hasattr(doc, "page_content"):
                        contexts.append(doc.page_content)
                    elif isinstance(doc, dict):
                        contexts.append(doc.get("page_content") or doc.get("content") or str(doc))
                    else:
                        contexts.append(str(doc))
                
                context_text = "\n\n".join(contexts)
                prompt = (
                    "请基于以下上下文信息回答用户的问题。\n\n"
                    f"上下文信息:\n{context_text}\n\n"
                    f"用户问题: {question}\n\n"
                    "请给出准确、详细的回答。如果上下文中没有相关信息，请明确告知用户。"
                )
                
                try:
                    answer = ollama_generate(
                        model=model_name,
                        prompt=prompt,
                        max_tokens=Config.MAX_TOKENS,
                        temperature=Config.TEMPERATURE,
                        api_url=api_url,
                    )
                    
                    print(f"\n回答: {answer}")
                    
                    if docs:
                        print(f"\n参考来源:")
                        seen_sources = set()
                        source_count = 1
                        for doc in docs:
                            source = getattr(doc, "metadata", {}).get("source", "未知") if hasattr(doc, "metadata") else "未知"
                            if source not in seen_sources:
                                seen_sources.add(source)
                                print(f"  [{source_count}] {source}")
                                source_count += 1
                
                except Exception as e:
                    print(f"\n调用 Ollama 失败: {e}")
                    
            except KeyboardInterrupt:
                print("\n\n再见！")
                break
            except Exception as e:
                print(f"\n错误: {str(e)}")
    else:
        print("\n" + "="*50)
        print("知识库助手已启动（输入 'quit' 或 'exit' 退出）")
        print("="*50 + "\n")
        
        assistant = RAGAssistant()
        assistant.chat()


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="RAG 知识库助手 - 命令行工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  # 构建知识库
  python run_cli.py build --documents ./documents
  
  # 查询知识库
  python run_cli.py query --question "什么是机器学习？"
  
  # 启动交互式对话
  python run_cli.py chat
  
  # 使用 Ollama 模式
  python run_cli.py chat --provider ollama
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="可用命令")
    
    # build 命令
    build_parser = subparsers.add_parser("build", help="构建知识库")
    build_parser.add_argument(
        "--documents",
        type=str,
        default=Config.DOCUMENTS_PATH,
        help=f"文档目录路径 (默认: {Config.DOCUMENTS_PATH})"
    )
    
    # query 命令
    query_parser = subparsers.add_parser("query", help="查询知识库")
    query_parser.add_argument("--question", type=str, required=True, help="要查询的问题")
    query_parser.add_argument("--provider", type=str, default=None, help="模型提供者: openai|gemini|ollama")
    query_parser.add_argument("--ollama-model", type=str, default="gemma3:4b", help="Ollama 模型名称")
    query_parser.add_argument("--ollama-api-url", type=str, default=None, help="Ollama API URL")
    
    # chat 命令
    chat_parser = subparsers.add_parser("chat", help="启动交互式对话")
    chat_parser.add_argument("--provider", type=str, default=None, help="模型提供者: openai|gemini|ollama")
    chat_parser.add_argument("--ollama-model", type=str, default="gemma3:4b", help="Ollama 模型名称")
    chat_parser.add_argument("--ollama-api-url", type=str, default=None, help="Ollama API URL")
    
    # ollama 命令
    ollama_parser = subparsers.add_parser("ollama", help="直接调用 Ollama 模型")
    ollama_parser.add_argument("--model", type=str, default="gemma3:4b", help="模型名称")
    ollama_parser.add_argument("--prompt", type=str, required=True, help="输入提示")
    ollama_parser.add_argument("--max_tokens", type=int, default=256, help="最大生成 token 数")
    ollama_parser.add_argument("--temperature", type=float, default=0.7, help="温度参数")
    ollama_parser.add_argument("--api_url", type=str, default=None, help="Ollama API URL")
    
    args = parser.parse_args()
    
    if args.command == "build":
        build_knowledge_base(args.documents)
    elif args.command == "query":
        query_knowledge_base(args.question, provider=args.provider, ollama_model=args.ollama_model, ollama_api_url=args.ollama_api_url)
    elif args.command == "chat":
        start_chat(provider=getattr(args, 'provider', None), 
                  ollama_model=getattr(args, 'ollama_model', None), 
                  ollama_api_url=getattr(args, 'ollama_api_url', None))
    elif args.command == "ollama":
        try:
            text = ollama_generate(
                model=args.model,
                prompt=args.prompt,
                max_tokens=args.max_tokens,
                temperature=args.temperature,
                api_url=args.api_url,
            )
            print("\nOllama 生成:")
            print(text)
        except Exception as e:
            print(f"调用 Ollama 出错: {e}")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
