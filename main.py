"""命令行主程序"""
import argparse
import re
import os

from config import Config
from document_processor import DocumentProcessor
from vector_store import VectorStore
from rag_assistant import RAGAssistant
from ollama_client import generate as ollama_generate

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
    """
    Config.validate()

    # 决定最终使用的 provider（CLI 参数优先）
    final_provider = provider or Config.MODEL_PROVIDER

    assistant = RAGAssistant()

    # 当使用本地 Ollama 时，避免调用远程 LLM。仅检索文档并把上下文发给 Ollama 本地模型。
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
            # 要求模型以纯文本回答（不要输出 JSON、代码块或额外注释）
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
            # 若 Ollama 调用失败，回退到默认 RAGAssistant
            result = assistant.query(question)
    else:
        # 默认使用 RAGAssistant（LangChain LLM）生成答案
        result = assistant.query(question)

    print(f"\n回答:\n{result['answer']}")

    if "sources" in result and result["sources"]:
        print(f"\n参考来源:")
        # 去重来源文件，避免显示重复的文档
        seen_sources = set()
        source_count = 1
        for doc in result["sources"]:
            source = getattr(doc, "metadata", {}).get("source", "未知") if hasattr(doc, "metadata") else (doc.get("metadata", {}).get("source") if isinstance(doc, dict) and doc.get("metadata") else "未知")
            if source not in seen_sources:
                seen_sources.add(source)
                print(f"  [{source_count}] {source}")
                source_count += 1

    # 简单后处理：若 Ollama 返回的答案明显碎片化或包含残留格式标记，尝试请求 Ollama 对该答案进行改写为完整中文句子
    if final_provider and final_provider.lower() == "ollama":
        ans = result.get("answer", "")
        if ans:
            fragile = False
            # 判定条件：过短、包含代码块/json标记或包含非自然结束符号
            if len(ans) < 20:
                fragile = True
            if any(token in ans.lower() for token in ['```', 'json', '{"answer"', '``']):
                fragile = True
            if re.search(r'[，,。.!?]$', ans) is None:
                # 若末尾无常见句末标点，也视为可能残缺
                fragile = True

            if fragile:
                # 尝试最多 2 次，请模型把碎片化或不完整的回答改写为完整的纯文本回答
                success = False
                for attempt in range(2):
                    try:
                        rewrite_prompt = (
                            "请将下面的文本改写为一段完整、连贯的中文回答。只输出纯文本，不要包含 JSON、代码块或额外注释：\n"
                            + ans
                        )

                        rewritten = ollama_generate(
                            model=model_name,
                            prompt=rewrite_prompt,
                            max_tokens=200,
                            temperature=0.0,
                            api_url=api_url,
                        )

                        if rewritten and len(rewritten.strip()) > 0:
                            # 直接采用改写后的纯文本作为答案
                            result['answer'] = rewritten.strip()
                            success = True
                            print('\n（已对模型输出进行了后处理改写，采用纯文本结果）')
                            break

                    except Exception as e:
                        print(f"后处理改写尝试失败: {e}")
                        continue

                if not success:
                    print('\n（后处理未能得到更好结果，保留原始输出）')


def start_chat(provider: str = None, ollama_model: str = None, ollama_api_url: str = None):
    """启动交互式对话
    
    Args:
        provider: 模型提供者
        ollama_model: Ollama 模型名称
        ollama_api_url: Ollama API URL
    """
    Config.validate()
    
    final_provider = provider if provider is not None else Config.MODEL_PROVIDER
    
    if final_provider and final_provider.lower() == "ollama":
        # 使用 Ollama 模式
        print("\n" + "="*50)
        print("知识库助手已启动（Ollama 模式，输入 'quit' 或 'exit' 退出）")
        print("="*50 + "\n")
        
        assistant = RAGAssistant()
        # 预加载向量数据库，避免在聊天时打印加载信息
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
                
                # 使用 Ollama 直接处理
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
                    from ollama_client import generate as ollama_generate
                    answer = ollama_generate(
                        model=model_name,
                        prompt=prompt,
                        max_tokens=Config.MAX_TOKENS,
                        temperature=Config.TEMPERATURE,
                        api_url=api_url,
                    )
                    
                    print(f"\n回答: {answer}")
                    
                    # 显示去重的参考来源
                    if docs:
                        print(f"\n参考来源:")
                        seen_sources = set()
                        source_count = 1
                        for doc in docs:
                            source = getattr(doc, "metadata", {}).get("source", "未知") if hasattr(doc, "metadata") else (doc.get("metadata", {}).get("source") if isinstance(doc, dict) and doc.get("metadata") else "未知")
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
        # 使用 LangChain LLM 模式
        print("\n" + "="*50)
        print("知识库助手已启动（输入 'quit' 或 'exit' 退出）")
        print("="*50 + "\n")
        
        assistant = RAGAssistant()
        assistant.chat()


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="RAG 知识库助手",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  # 构建知识库
  python main.py build --documents ./documents
  
  # 查询知识库
  python main.py query --question "什么是机器学习？"
  
  # 启动交互式对话
  python main.py chat
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
    query_parser.add_argument(
        "--question",
        type=str,
        required=True,
        help="要查询的问题"
    )
    query_parser.add_argument(
        "--provider",
        type=str,
        default=None,
        help="模型提供者: openai|gemini|ollama (默认使用配置中的 MODEL_PROVIDER)"
    )
    query_parser.add_argument(
        "--ollama-model",
        type=str,
        default="gemma3:4b",
        help="当 provider=ollama 时使用的本地模型名 (默认: gemma3:4b)"
    )
    query_parser.add_argument(
        "--ollama-api-url",
        type=str,
        default=None,
        help="可选 Ollama 服务地址，例如 http://localhost:11434"
    )
    
    # chat 命令
    chat_parser = subparsers.add_parser("chat", help="启动交互式对话")
    chat_parser.add_argument(
        "--provider",
        type=str,
        default=None,
        help="模型提供者: openai|gemini|ollama (默认使用配置中的 MODEL_PROVIDER)"
    )
    chat_parser.add_argument(
        "--ollama-model",
        type=str,
        default="gemma3:4b",
        help="当 provider=ollama 时使用的本地模型名 (默认: gemma3:4b)"
    )
    chat_parser.add_argument(
        "--ollama-api-url",
        type=str,
        default=None,
        help="可选 Ollama 服务地址，例如 http://localhost:11434"
    )
    # ollama 命令用于直接调用本地 Ollama 模型
    ollama_parser = subparsers.add_parser("ollama", help="调用本地 Ollama 模型进行演示")
    ollama_parser.add_argument("--model", type=str, default="gemma3:4b", help="模型名 (默认: gemma3:4b)")
    ollama_parser.add_argument("--prompt", type=str, required=True, help="输入提示文本")
    ollama_parser.add_argument("--max_tokens", type=int, default=256, help="最大生成 token 数")
    ollama_parser.add_argument("--temperature", type=float, default=0.7, help="温度")
    ollama_parser.add_argument("--api_url", type=str, default=None, help="可选 Ollama 服务地址，例如 http://localhost:11434")
    
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
        # 简单演示本地 Ollama 调用
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

    os.environ["http_proxy"] = "http://127.0.0.1:7897"
    os.environ["https_proxy"] = "http://127.0.0.1:7897"

    main()
