#!/usr/bin/env python3
"""Agent CLI - 命令行交互入口"""

import argparse
import sys
from typing import Optional

from src.agent.rag_agent import RAGAgent, AgentBuilder
from src.agent.base import AgentConfig


def print_banner():
    """打印欢迎横幅"""
    print("""
╔══════════════════════════════════════════════════════════════╗
║                                                              ║
║     🤖 Agentic RAG System - 智能知识库助手                    ║
║                                                              ║
║     具备自主决策、多工具协调、自省反思能力的 AI Agent          ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
    """)


def print_tools(agent: RAGAgent):
    """打印可用工具"""
    print("\n📦 可用工具:")
    print("-" * 50)
    for name, tool in agent.tools.items():
        print(f"  • {name}: {tool.description}")
    print("-" * 50)


def run_interactive(agent: RAGAgent):
    """交互式对话模式"""
    print_banner()
    print_tools(agent)
    
    print("\n💬 进入交互模式 (输入 'quit' 或 'exit' 退出, 'tools' 查看工具)")
    print("=" * 60)
    
    chat_history = ""
    
    while True:
        try:
            user_input = input("\n🧑 你: ").strip()
            
            if not user_input:
                continue
            
            if user_input.lower() in ['quit', 'exit', 'q']:
                print("\n👋 再见!")
                break
            
            if user_input.lower() == 'tools':
                print_tools(agent)
                continue
            
            if user_input.lower() == 'clear':
                chat_history = ""
                print("✓ 对话历史已清除")
                continue
            
            print("\n🤖 Agent 正在思考...")
            
            # 执行查询
            result = agent.run(user_input, chat_history)
            
            # 显示思考过程
            if result.thought_process:
                print("\n📝 思考过程:")
                for step in result.thought_process:
                    print(f"  Step {step.step}: {step.thought[:100]}...")
                    if step.action:
                        print(f"    → 使用工具: {step.action}")
            
            # 显示答案
            print(f"\n🤖 Agent: {result.answer}")
            
            # 显示元信息
            if result.tools_used:
                print(f"\n📊 使用的工具: {', '.join(result.tools_used)}")
            print(f"📊 推理迭代: {result.iterations} 次")
            
            # 更新对话历史
            chat_history += f"\nUser: {user_input}\nAssistant: {result.answer}\n"
            
        except KeyboardInterrupt:
            print("\n\n👋 再见!")
            break
        except Exception as e:
            print(f"\n❌ 错误: {e}")


def run_single_query(agent: RAGAgent, question: str, verbose: bool = True):
    """执行单次查询"""
    if verbose:
        print(f"\n🔍 问题: {question}")
        print("=" * 60)
        print("🤖 Agent 正在处理...")
    
    result = agent.run(question)
    
    if verbose:
        print(f"\n📝 答案:\n{result.answer}")
        print(f"\n📊 统计: 使用工具 {result.tools_used}, 迭代 {result.iterations} 次")
    else:
        print(result.answer)
    
    return result


def run_analyze(agent: RAGAgent):
    """运行知识库分析"""
    print("\n🔍 开始分析知识库...")
    result = agent.analyze_knowledge_base()
    print(f"\n{result.answer}")


def run_research(agent: RAGAgent, topic: str, use_web: bool = True):
    """运行主题研究"""
    print(f"\n🔍 研究主题: {topic}")
    print(f"   使用网络搜索: {'是' if use_web else '否'}")
    result = agent.research_topic(topic, use_web)
    print(f"\n{result.answer}")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="Agentic RAG System - 智能知识库助手",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例用法:
  # 交互模式
  python run_agent.py chat
  
  # 单次查询
  python run_agent.py query "什么是深度学习？"
  
  # 分析知识库
  python run_agent.py analyze
  
  # 研究主题
  python run_agent.py research "大语言模型的最新进展"
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="可用命令")
    
    # chat 命令
    chat_parser = subparsers.add_parser("chat", help="进入交互对话模式")
    chat_parser.add_argument("--type", choices=["simple", "full", "research", "manager"],
                            default="full", help="Agent 类型")
    
    # query 命令
    query_parser = subparsers.add_parser("query", help="执行单次查询")
    query_parser.add_argument("question", help="查询问题")
    query_parser.add_argument("--type", choices=["simple", "full", "research", "manager"],
                             default="full", help="Agent 类型")
    query_parser.add_argument("-q", "--quiet", action="store_true", help="简洁输出")
    
    # analyze 命令
    analyze_parser = subparsers.add_parser("analyze", help="分析知识库结构")
    
    # research 命令
    research_parser = subparsers.add_parser("research", help="研究某个主题")
    research_parser.add_argument("topic", help="研究主题")
    research_parser.add_argument("--no-web", action="store_true", help="不使用网络搜索")
    
    # tools 命令
    tools_parser = subparsers.add_parser("tools", help="列出所有可用工具")
    
    args = parser.parse_args()
    
    if args.command is None:
        parser.print_help()
        return
    
    # 创建 Agent
    if args.command == "chat":
        agent = getattr(AgentBuilder, f"create_{args.type}_agent")()
        run_interactive(agent)
    
    elif args.command == "query":
        agent = getattr(AgentBuilder, f"create_{args.type}_agent")()
        run_single_query(agent, args.question, verbose=not args.quiet)
    
    elif args.command == "analyze":
        agent = AgentBuilder.create_manager_agent()
        run_analyze(agent)
    
    elif args.command == "research":
        agent = AgentBuilder.create_research_agent()
        run_research(agent, args.topic, use_web=not args.no_web)
    
    elif args.command == "tools":
        agent = AgentBuilder.create_full_agent()
        print_tools(agent)


if __name__ == "__main__":
    main()
