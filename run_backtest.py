#!/usr/bin/env python3
"""RAG 回测 CLI 工具

用法:
    python run_backtest.py                    # 使用默认数据集
    python run_backtest.py --build            # 先构建知识库再回测
    python run_backtest.py --methods hybrid   # 指定检索方法
"""
import argparse
import json
import sys
from pathlib import Path

# 确保项目根目录在 path 中
sys.path.insert(0, str(Path(__file__).parent))


def build_kb():
  """构建知识库"""
  from src.core.document_processor import DocumentProcessor
  from src.core.vector_store import VectorStore
  from src.core.graph_rag import KnowledgeGraph
  from src.config.settings import Config

  print("[BUILD] 构建知识库...")
  processor = DocumentProcessor()
  chunks = processor.process_documents("./documents")
  if not chunks:
    print("[ERROR] 未找到文档，请确保 documents/ 目录有文件")
    sys.exit(1)

  vs = VectorStore()
  vs.create_vectorstore(chunks)
  print(f"[OK] 已索引 {len(chunks)} 个文本块")

  if Config.ENABLE_GRAPH_RAG:
    kg = KnowledgeGraph()
    stats = kg.build_from_chunks(chunks)
    print(f"[OK] 知识图谱: {stats['entities']} 实体, {stats['relations']} 关系")


def run_backtest(dataset: str, methods: list, rerank_options: list, top_k: int):
  from src.evaluation.rag_evaluator import RAGEvaluator
  from src.api.routes import load_assistant, get_assistant

  if not load_assistant():
    print("[ERROR] 向量库未加载，请先运行 --build")
    sys.exit(1)

  evaluator = RAGEvaluator(assistant=get_assistant())
  print(f"\n[EVAL] 开始回测: {dataset}")
  print(f"   方法: {methods}")
  print(f"   Rerank: {rerank_options}")
  print("-" * 60)

  report = evaluator.run_backtest(
    dataset_path=dataset,
    methods=methods,
    rerank_options=rerank_options,
    k=top_k,
  )

  # 保存报告
  output = Path("data/eval_reports/latest.json")
  evaluator.save_report(report, str(output))
  print(f"\n[REPORT] 回测报告已保存: {output}")

  # 打印摘要
  print("\n" + "=" * 60)
  print("回测摘要")
  print("=" * 60)
  for strategy, stats in report["summary"].items():
    print(f"\n  [{strategy}]")
    print(f"    Hit Rate:    {stats['hit_rate']:.1%}")
    print(f"    Recall@K:    {stats['avg_recall_at_k']:.1%}")
    print(f"    MRR:         {stats['avg_mrr']:.3f}")
    print(f"    Latency:     {stats['avg_latency_ms']:.0f} ms")

  print(f"\n[BEST] 最佳策略: {report['best_strategy']}")
  print("=" * 60)
  return report


def main():
  parser = argparse.ArgumentParser(description="RAG 检索回测工具")
  parser.add_argument("--build", action="store_true", help="先构建知识库")
  parser.add_argument("--dataset", default="data/demo_dataset/qa_pairs.json")
  parser.add_argument("--methods", nargs="+", default=["vector", "bm25", "hybrid"])
  parser.add_argument("--no-rerank", action="store_true", help="跳过 rerank 对比")
  parser.add_argument("--offline", action="store_true", help="离线 BM25 回测（无需向量库）")
  parser.add_argument("--top-k", type=int, default=3)
  args = parser.parse_args()

  if args.build and not args.offline:
    build_kb()

  rerank_options = [False] if (args.no_rerank or args.offline) else [False, True]
  methods = ["bm25"] if args.offline else args.methods

  if args.offline:
    from src.evaluation.rag_evaluator import RAGEvaluator
    evaluator = RAGEvaluator()
    print(f"\n[EVAL] 离线回测模式: {args.dataset}")
    report = evaluator.run_backtest(
      args.dataset, methods=methods, rerank_options=rerank_options,
      k=args.top_k, offline=True,
    )
    output = Path("data/eval_reports/latest.json")
    evaluator.save_report(report, str(output))
    print(f"\n[REPORT] 回测报告已保存: {output}")
    for strategy, stats in report["summary"].items():
      print(f"  [{strategy}] Hit Rate: {stats['hit_rate']:.1%}, MRR: {stats['avg_mrr']:.3f}")
    print(f"\n[BEST] 最佳策略: {report['best_strategy']}")
    sys.exit(0 if report["summary"].get(report["best_strategy"], {}).get("hit_rate", 0) >= 0.5 else 1)

  report = run_backtest(args.dataset, methods, rerank_options, args.top_k)

  # 退出码：最佳策略 hit_rate > 0.5 为成功
  best = report.get("best_strategy")
  if best and report["summary"].get(best, {}).get("hit_rate", 0) >= 0.5:
    sys.exit(0)
  sys.exit(1)


if __name__ == "__main__":
  main()
