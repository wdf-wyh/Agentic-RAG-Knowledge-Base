#!/usr/bin/env python3
"""MCP Server - 将知识库暴露为 MCP 工具

用法:
    python mcp_server.py

在 Cursor / Claude Desktop 的 MCP 配置中添加:
    {
      "mcpServers": {
        "agentic-rag": {
          "command": "python",
          "args": ["mcp_server.py"],
          "cwd": "/path/to/Agentic-RAG-Knowledge-Base"
        }
      }
    }
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))


def run_stdio_mcp():
    """简易 stdio MCP 协议实现"""
    from src.api.routes import load_assistant, get_assistant
    from src.config.settings import Config

    tools = [
        {
            "name": "rag_search",
            "description": "在本地知识库中检索相关文档",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "搜索查询"},
                    "top_k": {"type": "integer", "default": 3},
                },
                "required": ["query"],
            },
        },
        {
            "name": "list_documents",
            "description": "列出知识库中的所有文档",
            "inputSchema": {"type": "object", "properties": {}},
        },
        {
            "name": "graph_query",
            "description": "查询知识图谱中的实体关系",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "查询实体或关系"},
                },
                "required": ["query"],
            },
        },
    ]

    def handle_request(req: dict) -> dict:
        method = req.get("method", "")
        req_id = req.get("id")

        if method == "initialize":
            return {"jsonrpc": "2.0", "id": req_id, "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "agentic-rag", "version": "3.1.0"},
            }}

        if method == "tools/list":
            return {"jsonrpc": "2.0", "id": req_id, "result": {"tools": tools}}

        if method == "tools/call":
            params = req.get("params", {})
            tool_name = params.get("name", "")
            args = params.get("arguments", {})

            try:
                if tool_name == "rag_search":
                    if not load_assistant():
                        text = "知识库未加载，请先构建知识库"
                    else:
                        assistant = get_assistant()
                        docs = assistant.retrieve_documents(
                            args["query"],
                            k=args.get("top_k", 3),
                            method=Config.DEFAULT_RETRIEVAL_METHOD,
                            rerank=Config.ENABLE_RERANK,
                        )
                        parts = []
                        for i, doc in enumerate(docs, 1):
                            meta = getattr(doc, "metadata", {})
                            src = meta.get("source", "unknown") if isinstance(meta, dict) else "unknown"
                            content = getattr(doc, "page_content", "")[:500]
                            parts.append(f"[{i}] {src}\n{content}")
                        text = "\n\n".join(parts) if parts else "未找到相关文档"

                elif tool_name == "list_documents":
                    from src.core.vector_store import VectorStore
                    vs = VectorStore()
                    docs = vs.get_document_list()
                    text = json.dumps(docs, ensure_ascii=False, indent=2)

                elif tool_name == "graph_query":
                    from src.core.graph_rag import KnowledgeGraph
                    kg = KnowledgeGraph()
                    ctx = kg.search_context(args.get("query", ""))
                    text = ctx or "未找到相关图谱信息"

                else:
                    text = f"未知工具: {tool_name}"

                return {"jsonrpc": "2.0", "id": req_id, "result": {
                    "content": [{"type": "text", "text": text}],
                }}
            except Exception as e:
                return {"jsonrpc": "2.0", "id": req_id, "error": {
                    "code": -32000, "message": str(e),
                }}

        if method == "notifications/initialized":
            return None

        return {"jsonrpc": "2.0", "id": req_id, "error": {
            "code": -32601, "message": f"Method not found: {method}",
        }}

    # 主循环
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
            resp = handle_request(req)
            if resp is not None:
                sys.stdout.write(json.dumps(resp, ensure_ascii=False) + "\n")
                sys.stdout.flush()
        except Exception as e:
            err = {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": str(e)}}
            sys.stdout.write(json.dumps(err) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    run_stdio_mcp()
