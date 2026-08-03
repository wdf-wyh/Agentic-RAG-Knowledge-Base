# Agentic RAG 系统架构

Agentic RAG 将 Agent 自主决策能力与 RAG 检索相结合，实现更复杂的多步骤知识问答。

## 架构组件

### ReAct 推理框架
Agent 按照 Thought（思考）→ Action（行动）→ Observation（观察）循环推理，直到得出最终答案。

### 工具层
- **rag_search**：查询本地知识库
- **web_search**：联网获取实时信息
- **file_tools**：读写本地文件
- **analysis_tools**：文档分析与摘要

### 意图路由
根据用户问题自动判断使用 RAG 检索、联网搜索还是直接回答，避免不必要的工具调用。

## 与纯 RAG 的区别

| 特性 | 纯 RAG | Agentic RAG |
|------|--------|-------------|
| 推理步骤 | 单步检索+生成 | 多步规划与工具调用 |
| 外部信息 | 仅知识库 | 知识库 + 联网 + 文件 |
| 复杂任务 | 受限 | 支持分析、报告生成 |
| 可观测性 | 基础来源展示 | 完整推理链路追踪 |

## GraphRAG 扩展

通过实体关系抽取构建知识图谱，支持多跳推理查询，例如"A 部门与 B 项目的关系"。

## 部署建议

- 本地部署：Ollama + bge-small-zh 嵌入模型
- 云端部署：DeepSeek API + Docker Compose
- 生产环境：启用 JWT 鉴权、Agent Tracing、RAG 评测回测
