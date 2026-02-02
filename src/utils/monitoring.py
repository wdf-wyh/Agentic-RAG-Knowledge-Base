"""性能监控 - 追踪工具执行时间和成功率"""

import time
import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import defaultdict
from threading import Lock
import json
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class ToolMetrics:
    """工具度量"""
    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    total_duration: float = 0.0
    min_duration: float = float('inf')
    max_duration: float = 0.0
    last_error: Optional[str] = None
    last_call_time: Optional[str] = None
    
    @property
    def success_rate(self) -> float:
        if self.total_calls == 0:
            return 0.0
        return self.successful_calls / self.total_calls
    
    @property
    def avg_duration(self) -> float:
        if self.successful_calls == 0:
            return 0.0
        return self.total_duration / self.successful_calls
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_calls": self.total_calls,
            "successful_calls": self.successful_calls,
            "failed_calls": self.failed_calls,
            "success_rate": f"{self.success_rate:.2%}",
            "avg_duration": f"{self.avg_duration:.2f}s",
            "min_duration": f"{self.min_duration:.2f}s" if self.min_duration != float('inf') else "N/A",
            "max_duration": f"{self.max_duration:.2f}s",
            "last_error": self.last_error,
            "last_call_time": self.last_call_time
        }


@dataclass
class QueryMetrics:
    """查询度量"""
    total_queries: int = 0
    avg_iterations: float = 0.0
    avg_response_time: float = 0.0
    tools_usage: Dict[str, int] = field(default_factory=dict)
    

class PerformanceMonitor:
    """性能监控器"""
    
    def __init__(self, metrics_dir: str = "./logs"):
        self.metrics_dir = Path(metrics_dir)
        self.metrics_dir.mkdir(exist_ok=True)
        
        self._tool_metrics: Dict[str, ToolMetrics] = defaultdict(ToolMetrics)
        self._query_history: List[Dict] = []
        self._lock = Lock()
        
        # 加载历史数据
        self._load_metrics()
    
    def _load_metrics(self):
        """加载历史度量数据"""
        metrics_file = self.metrics_dir / "tool_metrics.json"
        if metrics_file.exists():
            try:
                with open(metrics_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                for name, metrics_data in data.get("tools", {}).items():
                    m = ToolMetrics()
                    m.total_calls = metrics_data.get("total_calls", 0)
                    m.successful_calls = metrics_data.get("successful_calls", 0)
                    m.failed_calls = metrics_data.get("failed_calls", 0)
                    m.total_duration = metrics_data.get("total_duration", 0)
                    self._tool_metrics[name] = m
            except Exception as e:
                logger.warning(f"加载度量数据失败: {e}")
    
    def _save_metrics(self):
        """保存度量数据"""
        metrics_file = self.metrics_dir / "tool_metrics.json"
        try:
            data = {
                "updated_at": datetime.now().isoformat(),
                "tools": {name: m.to_dict() for name, m in self._tool_metrics.items()}
            }
            with open(metrics_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存度量数据失败: {e}")
    
    def record_tool_call(
        self, 
        tool_name: str, 
        success: bool, 
        duration: float,
        error: str = None
    ):
        """记录工具调用"""
        with self._lock:
            metrics = self._tool_metrics[tool_name]
            metrics.total_calls += 1
            metrics.last_call_time = datetime.now().isoformat()
            
            if success:
                metrics.successful_calls += 1
                metrics.total_duration += duration
                metrics.min_duration = min(metrics.min_duration, duration)
                metrics.max_duration = max(metrics.max_duration, duration)
            else:
                metrics.failed_calls += 1
                metrics.last_error = error
            
            # 每 10 次调用保存一次
            if metrics.total_calls % 10 == 0:
                self._save_metrics()
    
    def record_query(
        self,
        query: str,
        response_time: float,
        iterations: int,
        tools_used: List[str],
        success: bool
    ):
        """记录查询"""
        with self._lock:
            self._query_history.append({
                "query": query[:100],
                "response_time": response_time,
                "iterations": iterations,
                "tools_used": tools_used,
                "success": success,
                "timestamp": datetime.now().isoformat()
            })
            
            # 保留最近 1000 条
            if len(self._query_history) > 1000:
                self._query_history = self._query_history[-1000:]
    
    def get_tool_stats(self, tool_name: str = None) -> Dict[str, Any]:
        """获取工具统计"""
        with self._lock:
            if tool_name:
                if tool_name in self._tool_metrics:
                    return {tool_name: self._tool_metrics[tool_name].to_dict()}
                return {}
            return {name: m.to_dict() for name, m in self._tool_metrics.items()}
    
    def get_summary(self) -> Dict[str, Any]:
        """获取总体摘要"""
        with self._lock:
            total_calls = sum(m.total_calls for m in self._tool_metrics.values())
            total_success = sum(m.successful_calls for m in self._tool_metrics.values())
            
            # 最近 1 小时的查询统计
            one_hour_ago = (datetime.now() - timedelta(hours=1)).isoformat()
            recent_queries = [q for q in self._query_history if q["timestamp"] > one_hour_ago]
            
            return {
                "total_tool_calls": total_calls,
                "overall_success_rate": f"{total_success / total_calls:.2%}" if total_calls > 0 else "N/A",
                "total_queries_recorded": len(self._query_history),
                "queries_last_hour": len(recent_queries),
                "avg_response_time_last_hour": (
                    f"{sum(q['response_time'] for q in recent_queries) / len(recent_queries):.2f}s"
                    if recent_queries else "N/A"
                ),
                "most_used_tools": self._get_most_used_tools(5),
                "slowest_tools": self._get_slowest_tools(3),
                "error_prone_tools": self._get_error_prone_tools(3)
            }
    
    def _get_most_used_tools(self, n: int) -> List[Dict]:
        """获取使用最多的工具"""
        sorted_tools = sorted(
            self._tool_metrics.items(),
            key=lambda x: x[1].total_calls,
            reverse=True
        )
        return [
            {"name": name, "calls": m.total_calls}
            for name, m in sorted_tools[:n]
        ]
    
    def _get_slowest_tools(self, n: int) -> List[Dict]:
        """获取最慢的工具"""
        sorted_tools = sorted(
            [(name, m) for name, m in self._tool_metrics.items() if m.avg_duration > 0],
            key=lambda x: x[1].avg_duration,
            reverse=True
        )
        return [
            {"name": name, "avg_duration": f"{m.avg_duration:.2f}s"}
            for name, m in sorted_tools[:n]
        ]
    
    def _get_error_prone_tools(self, n: int) -> List[Dict]:
        """获取错误率最高的工具"""
        sorted_tools = sorted(
            [(name, m) for name, m in self._tool_metrics.items() if m.total_calls > 0],
            key=lambda x: 1 - x[1].success_rate
        )
        return [
            {"name": name, "error_rate": f"{(1 - m.success_rate):.2%}", "last_error": m.last_error}
            for name, m in sorted_tools[:n]
            if m.success_rate < 1.0
        ]


# 全局监控器实例
monitor = PerformanceMonitor()


def track_tool(func):
    """工具执行追踪装饰器"""
    from functools import wraps
    
    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        error_msg = None
        success = False
        
        try:
            result = func(*args, **kwargs)
            success = getattr(result, 'success', True)
            error_msg = getattr(result, 'error', None)
            return result
        except Exception as e:
            error_msg = str(e)
            raise
        finally:
            duration = time.time() - start_time
            # 获取工具名称（从 self.name 或函数名）
            tool_name = "unknown"
            if args and hasattr(args[0], 'name'):
                tool_name = args[0].name
            else:
                tool_name = func.__name__
            
            monitor.record_tool_call(tool_name, success, duration, error_msg)
    
    return wrapper
