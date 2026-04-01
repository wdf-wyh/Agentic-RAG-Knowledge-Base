"""系统信息工具 - 系统状态、进程管理、磁盘使用等"""

import os
import platform
import logging
from typing import List, Dict, Any
from pathlib import Path

from src.agent.tools.base import BaseTool, ToolResult, ToolCategory

logger = logging.getLogger(__name__)


class SystemInfoTool(BaseTool):
    """系统信息查询工具"""

    @property
    def name(self) -> str:
        return "system_info"

    @property
    def description(self) -> str:
        return "获取当前系统信息，包括操作系统、CPU、内存、磁盘使用率、Python版本等。"

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.UTILITY

    @property
    def parameters(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": "category",
                "type": "string",
                "description": "查询类别: 'all'(全部), 'os'(操作系统), 'memory'(内存), 'disk'(磁盘), 'python'(Python环境)。默认 'all'。",
                "required": False,
            }
        ]

    def execute(self, **kwargs) -> ToolResult:
        category = kwargs.get("category", "all")
        info = {}
        sections = []

        if category in ("all", "os"):
            os_info = {
                "system": platform.system(),
                "release": platform.release(),
                "version": platform.version(),
                "machine": platform.machine(),
                "processor": platform.processor(),
                "hostname": platform.node(),
            }
            info["os"] = os_info
            sections.append(
                f"💻 操作系统\n"
                f"  系统: {os_info['system']} {os_info['release']}\n"
                f"  架构: {os_info['machine']}\n"
                f"  处理器: {os_info['processor']}\n"
                f"  主机名: {os_info['hostname']}"
            )

        if category in ("all", "memory"):
            try:
                import psutil
                mem = psutil.virtual_memory()
                mem_info = {
                    "total_gb": round(mem.total / (1024**3), 2),
                    "used_gb": round(mem.used / (1024**3), 2),
                    "available_gb": round(mem.available / (1024**3), 2),
                    "percent": mem.percent,
                }
                info["memory"] = mem_info
                sections.append(
                    f"🧠 内存\n"
                    f"  总计: {mem_info['total_gb']} GB\n"
                    f"  已用: {mem_info['used_gb']} GB ({mem_info['percent']}%)\n"
                    f"  可用: {mem_info['available_gb']} GB"
                )
            except ImportError:
                sections.append("🧠 内存: 需要安装 psutil 库来查询内存信息")

        if category in ("all", "disk"):
            try:
                import shutil
                total, used, free = shutil.disk_usage("/")
                disk_info = {
                    "total_gb": round(total / (1024**3), 2),
                    "used_gb": round(used / (1024**3), 2),
                    "free_gb": round(free / (1024**3), 2),
                    "percent": round(used / total * 100, 1),
                }
                info["disk"] = disk_info
                sections.append(
                    f"💾 磁盘 (/)\n"
                    f"  总计: {disk_info['total_gb']} GB\n"
                    f"  已用: {disk_info['used_gb']} GB ({disk_info['percent']}%)\n"
                    f"  可用: {disk_info['free_gb']} GB"
                )
            except Exception as e:
                sections.append(f"💾 磁盘: 查询失败 ({e})")

        if category in ("all", "python"):
            import sys
            py_info = {
                "version": sys.version,
                "executable": sys.executable,
                "prefix": sys.prefix,
                "platform": sys.platform,
            }
            info["python"] = py_info
            sections.append(
                f"🐍 Python\n"
                f"  版本: {sys.version.split()[0]}\n"
                f"  路径: {sys.executable}\n"
                f"  环境: {sys.prefix}"
            )

        output = "🖥️ 系统信息\n\n" + "\n\n".join(sections)
        return ToolResult(success=True, output=output, data=info)


class ProcessListTool(BaseTool):
    """进程查询工具"""

    @property
    def name(self) -> str:
        return "process_list"

    @property
    def description(self) -> str:
        return "查看系统中正在运行的进程，按CPU或内存排序。可以搜索特定进程。"

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.UTILITY

    @property
    def parameters(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": "filter",
                "type": "string",
                "description": "过滤进程名称（可选），如 'python'、'node'",
                "required": False,
            },
            {
                "name": "sort_by",
                "type": "string",
                "description": "排序方式: 'cpu'(CPU使用率), 'memory'(内存使用率)。默认 'memory'。",
                "required": False,
            },
            {
                "name": "limit",
                "type": "integer",
                "description": "显示前N个进程，默认15",
                "required": False,
            },
        ]

    def execute(self, **kwargs) -> ToolResult:
        try:
            import psutil
        except ImportError:
            return ToolResult(success=False, output="", error="需要安装 psutil 库: pip install psutil")

        filter_name = kwargs.get("filter", "")
        sort_by = kwargs.get("sort_by", "memory")
        limit = int(kwargs.get("limit", 15))

        processes = []
        for proc in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent", "status"]):
            try:
                info = proc.info
                if filter_name and filter_name.lower() not in info["name"].lower():
                    continue
                processes.append(info)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        # 排序
        sort_key = "memory_percent" if sort_by == "memory" else "cpu_percent"
        processes.sort(key=lambda p: p.get(sort_key, 0) or 0, reverse=True)
        processes = processes[:limit]

        if not processes:
            return ToolResult(success=True, output="未找到匹配的进程", data={"processes": []})

        lines = [f"📊 进程列表 (按{('内存' if sort_by == 'memory' else 'CPU')}排序)\n"]
        lines.append(f"{'PID':>7} | {'进程名':<25} | {'CPU%':>6} | {'内存%':>6} | 状态")
        lines.append("-" * 70)
        for p in processes:
            lines.append(
                f"{p['pid']:>7} | {p['name'][:25]:<25} | "
                f"{(p['cpu_percent'] or 0):>5.1f}% | "
                f"{(p['memory_percent'] or 0):>5.1f}% | "
                f"{p['status']}"
            )

        return ToolResult(success=True, output="\n".join(lines), data={"processes": processes})


class NetworkInfoTool(BaseTool):
    """网络信息工具"""

    @property
    def name(self) -> str:
        return "network_info"

    @property
    def description(self) -> str:
        return "获取网络连接信息，包括本机IP地址、网络接口、端口监听等。"

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.UTILITY

    @property
    def parameters(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": "info_type",
                "type": "string",
                "description": "信息类型: 'ip'(IP地址), 'interfaces'(网络接口), 'ports'(监听端口)。默认 'ip'。",
                "required": False,
            }
        ]

    def execute(self, **kwargs) -> ToolResult:
        info_type = kwargs.get("info_type", "ip")

        if info_type == "ip":
            import socket
            hostname = socket.gethostname()
            try:
                local_ip = socket.gethostbyname(hostname)
            except socket.gaierror:
                local_ip = "无法获取"

            output = (
                f"🌐 网络信息\n"
                f"  主机名: {hostname}\n"
                f"  本地IP: {local_ip}"
            )

            # 尝试获取更多网络接口信息
            try:
                import psutil
                interfaces = psutil.net_if_addrs()
                for name, addrs in interfaces.items():
                    for addr in addrs:
                        if addr.family == socket.AF_INET:
                            output += f"\n  {name}: {addr.address}"
            except ImportError:
                pass

            return ToolResult(success=True, output=output, data={"hostname": hostname, "local_ip": local_ip})

        elif info_type == "ports":
            try:
                import psutil
                connections = psutil.net_connections(kind="inet")
                listening = [
                    c for c in connections
                    if c.status == "LISTEN"
                ]
                listening.sort(key=lambda c: c.laddr.port)

                lines = ["🔌 监听端口\n"]
                lines.append(f"{'端口':>6} | {'地址':<20} | PID")
                lines.append("-" * 45)
                seen = set()
                for conn in listening[:30]:
                    port = conn.laddr.port
                    if port in seen:
                        continue
                    seen.add(port)
                    addr = f"{conn.laddr.ip}:{port}"
                    lines.append(f"{port:>6} | {addr:<20} | {conn.pid or '-'}")

                return ToolResult(success=True, output="\n".join(lines), data={"listening_ports": len(seen)})
            except ImportError:
                return ToolResult(success=False, output="", error="需要安装 psutil 库")
            except Exception as e:
                return ToolResult(success=False, output="", error=f"获取端口信息失败: {e}")

        else:
            return ToolResult(success=False, output="", error=f"不支持的信息类型: {info_type}")
