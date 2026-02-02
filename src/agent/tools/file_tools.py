"""文件操作工具 - 让 Agent 具备读写文件的能力"""

import os
import shutil
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime

from src.agent.tools.base import BaseTool, ToolResult, ToolCategory


class PathSecurityMixin:
    """路径安全检查混入类 - 提供符号链接安全验证"""
    
    _allowed_paths: List[str] = []
    
    def _is_path_allowed(self, path: Path) -> bool:
        """检查路径是否在允许范围内（包含符号链接安全检查）
        
        安全检查包括：
        1. 路径必须在允许的目录内
        2. 如果是符号链接，目标路径也必须在允许范围内
        """
        # 首先检查是否是符号链接，如果是，验证目标路径
        if path.is_symlink():
            try:
                # 获取符号链接的真实目标路径
                real_path = path.resolve()
                # 如果目标路径不在允许范围内，拒绝访问
                if not self._check_path_in_allowed(real_path):
                    return False
            except (OSError, ValueError):
                # 符号链接解析失败，拒绝访问
                return False
        
        return self._check_path_in_allowed(path.resolve())
    
    def _check_path_in_allowed(self, abs_path: Path) -> bool:
        """检查绝对路径是否在允许的目录列表中"""
        for allowed in self._allowed_paths:
            allowed_abs = Path(allowed).resolve()
            try:
                abs_path.relative_to(allowed_abs)
                return True
            except ValueError:
                continue
        return False


class ReadFileTool(PathSecurityMixin, BaseTool):
    """读取文件工具"""
    
    def __init__(self, allowed_paths: List[str] = None):
        """
        Args:
            allowed_paths: 允许访问的路径列表（安全限制）
        """
        self._allowed_paths = allowed_paths or ["./documents", "./uploads"]
        super().__init__()
    
    @property
    def name(self) -> str:
        return "read_file"
    
    @property
    def description(self) -> str:
        return "读取指定文件的内容。支持文本文件（.txt, .md, .py, .json 等）。"
    
    @property
    def category(self) -> ToolCategory:
        return ToolCategory.FILE_OPERATION
    
    @property
    def parameters(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": "file_path",
                "type": "string",
                "description": "文件路径（相对于项目根目录）",
                "required": True
            },
            {
                "name": "max_lines",
                "type": "integer",
                "description": "最大读取行数，默认 100",
                "required": False
            }
        ]
    
    def execute(self, **kwargs) -> ToolResult:
        """读取文件"""
        file_path = kwargs.get("file_path", "")
        max_lines = kwargs.get("max_lines", 100)
        
        if not file_path:
            return ToolResult(success=False, output="", error="文件路径不能为空")
        
        try:
            path = Path(file_path)
            
            # 安全检查
            if not self._is_path_allowed(path):
                return ToolResult(
                    success=False,
                    output="",
                    error=f"安全限制：不允许访问该路径。允许的路径: {self._allowed_paths}"
                )
            
            if not path.exists():
                return ToolResult(success=False, output="", error=f"文件不存在: {file_path}")
            
            if not path.is_file():
                return ToolResult(success=False, output="", error=f"不是文件: {file_path}")
            
            # 读取文件
            with open(path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            total_lines = len(lines)
            if max_lines and total_lines > max_lines:
                content = "".join(lines[:max_lines])
                note = f"\n\n[注: 文件共 {total_lines} 行，仅显示前 {max_lines} 行]"
            else:
                content = "".join(lines)
                note = ""
            
            return ToolResult(
                success=True,
                output=f"文件内容 ({path.name}):\n\n{content}{note}",
                data={"content": content, "total_lines": total_lines},
                metadata={"file_path": str(path), "lines_read": min(max_lines, total_lines)}
            )
            
        except UnicodeDecodeError:
            return ToolResult(success=False, output="", error="文件编码错误，不是有效的文本文件")
        except Exception as e:
            return ToolResult(success=False, output="", error=f"读取文件失败: {str(e)}")


class WriteFileTool(PathSecurityMixin, BaseTool):
    """写入文件工具"""
    
    def __init__(self, allowed_paths: List[str] = None):
        self._allowed_paths = allowed_paths or ["./documents", "./uploads", "./output"]
        super().__init__()
    
    @property
    def name(self) -> str:
        return "write_file"
    
    @property
    def description(self) -> str:
        return "将内容写入文件。如果文件存在会覆盖，不存在则创建。⚠️ 请谨慎使用，仅限允许路径。"
    
    @property
    def category(self) -> ToolCategory:
        return ToolCategory.FILE_OPERATION
    
    @property
    def parameters(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": "file_path",
                "type": "string",
                "description": "文件路径（相对于项目根目录）",
                "required": True
            },
            {
                "name": "content",
                "type": "string",
                "description": "要写入的内容",
                "required": True
            },
            {
                "name": "append",
                "type": "boolean",
                "description": "是否追加模式，默认 False（覆盖）",
                "required": False
            }
        ]
    
    def execute(self, **kwargs) -> ToolResult:
        """写入文件"""
        file_path = kwargs.get("file_path", "")
        content = kwargs.get("content", "")
        append = kwargs.get("append", False)
        
        if not file_path:
            return ToolResult(success=False, output="", error="文件路径不能为空")
        
        try:
            path = Path(file_path)
            
            # 安全检查
            if not self._is_path_allowed(path):
                return ToolResult(
                    success=False,
                    output="",
                    error=f"安全限制：不允许写入该路径。允许的路径: {self._allowed_paths}"
                )
            
            # 确保目录存在
            path.parent.mkdir(parents=True, exist_ok=True)
            
            # 写入文件
            mode = 'a' if append else 'w'
            with open(path, mode, encoding='utf-8') as f:
                f.write(content)
            
            action = "追加" if append else "写入"
            return ToolResult(
                success=True,
                output=f"成功{action}文件: {path}\n内容长度: {len(content)} 字符",
                metadata={"file_path": str(path), "bytes_written": len(content.encode('utf-8'))}
            )
            
        except Exception as e:
            return ToolResult(success=False, output="", error=f"写入文件失败: {str(e)}")


class ListDirectoryTool(PathSecurityMixin, BaseTool):
    """列出目录内容工具"""
    
    def __init__(self, allowed_paths: List[str] = None):
        self._allowed_paths = allowed_paths or ["./documents", "./uploads", "./output", "."]
        super().__init__()
        PathSecurityMixin.__init__(self)
    
    @property
    def name(self) -> str:
        return "list_directory"
    
    @property
    def description(self) -> str:
        return "列出指定目录中的文件和子目录。"
    
    @property
    def category(self) -> ToolCategory:
        return ToolCategory.FILE_OPERATION
    
    @property
    def parameters(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": "directory",
                "type": "string",
                "description": "目录路径，默认为 './documents'",
                "required": False
            },
            {
                "name": "recursive",
                "type": "boolean",
                "description": "是否递归列出子目录，默认 False",
                "required": False
            }
        ]
    
    def execute(self, **kwargs) -> ToolResult:
        """列出目录内容"""
        directory = kwargs.get("directory", "./documents")
        recursive = kwargs.get("recursive", False)
        
        try:
            path = Path(directory)
            
            # 安全检查
            error = self._check_path_in_allowed(path)
            if error:
                return error
            
            if not path.exists():
                return ToolResult(success=False, output="", error=f"目录不存在: {directory}")
            
            if not path.is_dir():
                return ToolResult(success=False, output="", error=f"不是目录: {directory}")
            
            items = []
            
            if recursive:
                for item in path.rglob("*"):
                    rel_path = item.relative_to(path)
                    item_type = "📁" if item.is_dir() else "📄"
                    size = item.stat().st_size if item.is_file() else 0
                    items.append({
                        "name": str(rel_path),
                        "type": "directory" if item.is_dir() else "file",
                        "size": size
                    })
            else:
                for item in path.iterdir():
                    item_type = "📁" if item.is_dir() else "📄"
                    size = item.stat().st_size if item.is_file() else 0
                    items.append({
                        "name": item.name,
                        "type": "directory" if item.is_dir() else "file",
                        "size": size
                    })
            
            # 排序：目录在前，文件在后
            items.sort(key=lambda x: (0 if x["type"] == "directory" else 1, x["name"]))
            
            output_parts = [f"目录 '{directory}' 内容 ({len(items)} 项):\n"]
            for item in items:
                icon = "📁" if item["type"] == "directory" else "📄"
                size_str = f" ({item['size']} bytes)" if item["type"] == "file" else ""
                output_parts.append(f"{icon} {item['name']}{size_str}")
            
            return ToolResult(
                success=True,
                output="\n".join(output_parts),
                data=items,
                metadata={"directory": directory, "item_count": len(items)}
            )
            
        except Exception as e:
            return ToolResult(success=False, output="", error=f"列出目录失败: {str(e)}")


class MoveFileTool(PathSecurityMixin, BaseTool):
    """移动/重命名文件工具"""
    
    def __init__(self, allowed_paths: List[str] = None):
        self._allowed_paths = allowed_paths or ["./documents", "./uploads", "./output"]
        super().__init__()
    
    @property
    def name(self) -> str:
        return "move_file"
    
    @property
    def description(self) -> str:
        return "移动或重命名文件/目录。可用于整理文档结构。⚠️ 请谨慎使用，仅限允许路径。"
    
    @property
    def category(self) -> ToolCategory:
        return ToolCategory.FILE_OPERATION
    
    @property
    def parameters(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": "source",
                "type": "string",
                "description": "源文件/目录路径",
                "required": True
            },
            {
                "name": "destination",
                "type": "string",
                "description": "目标路径",
                "required": True
            }
        ]
    
    def execute(self, **kwargs) -> ToolResult:
        """移动文件"""
        source = kwargs.get("source", "")
        destination = kwargs.get("destination", "")
        
        if not source or not destination:
            return ToolResult(success=False, output="", error="源路径和目标路径不能为空")
        
        try:
            src_path = Path(source)
            dst_path = Path(destination)
            
            # 安全检查
            if not self._is_path_allowed(src_path) or not self._is_path_allowed(dst_path):
                return ToolResult(
                    success=False,
                    output="",
                    error=f"安全限制：不允许在该路径操作。允许的路径: {self._allowed_paths}"
                )
            
            if not src_path.exists():
                return ToolResult(success=False, output="", error=f"源路径不存在: {source}")
            
            # 确保目标目录存在
            dst_path.parent.mkdir(parents=True, exist_ok=True)
            
            # 移动
            shutil.move(str(src_path), str(dst_path))
            
            return ToolResult(
                success=True,
                output=f"成功移动:\n  从: {source}\n  到: {destination}",
                metadata={"source": source, "destination": destination}
            )
            
        except Exception as e:
            return ToolResult(success=False, output="", error=f"移动失败: {str(e)}")


class CreateDirectoryTool(PathSecurityMixin, BaseTool):
    """创建目录工具"""
    
    def __init__(self, allowed_paths: List[str] = None):
        self._allowed_paths = allowed_paths or ["./documents", "./uploads", "./output"]
        super().__init__()
    
    @property
    def name(self) -> str:
        return "create_directory"
    
    @property
    def description(self) -> str:
        return "创建新目录，支持创建多级目录结构。"
    
    @property
    def category(self) -> ToolCategory:
        return ToolCategory.FILE_OPERATION
    
    @property
    def parameters(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": "directory",
                "type": "string",
                "description": "要创建的目录路径",
                "required": True
            }
        ]
    
    def execute(self, **kwargs) -> ToolResult:
        """创建目录"""
        directory = kwargs.get("directory", "")
        
        if not directory:
            return ToolResult(success=False, output="", error="目录路径不能为空")
        
        try:
            path = Path(directory)
            
            # 安全检查
            if not self._is_path_allowed(path):
                return ToolResult(
                    success=False,
                    output="",
                    error=f"安全限制：不允许在该路径创建目录。允许的路径: {self._allowed_paths}"
                )
            
            if path.exists():
                return ToolResult(
                    success=True,
                    output=f"目录已存在: {directory}",
                    metadata={"directory": directory, "created": False}
                )
            
            path.mkdir(parents=True, exist_ok=True)
            
            return ToolResult(
                success=True,
                output=f"成功创建目录: {directory}",
                metadata={"directory": directory, "created": True}
            )
            
        except Exception as e:
            return ToolResult(success=False, output="", error=f"创建目录失败: {str(e)}")


class DeleteFileTool(PathSecurityMixin, BaseTool):
    """查看文件信息工具（已禁用删除功能，出于安全考虑）"""
    
    def __init__(self, allowed_paths: List[str] = None, require_confirmation: bool = True):
        self._allowed_paths = allowed_paths or ["./documents", "./uploads", "./output"]
        self._require_confirmation = require_confirmation
        super().__init__()
    
    @property
    def name(self) -> str:
        return "view_file_info"
    
    @property
    def description(self) -> str:
        return "查看文件或目录的详细信息（大小、修改时间等）。注意：已禁用删除功能。"
    
    @property
    def category(self) -> ToolCategory:
        return ToolCategory.FILE_OPERATION
    
    @property
    def parameters(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": "file_path",
                "type": "string",
                "description": "要查看的文件或目录路径",
                "required": True
            }
        ]
    
    def execute(self, **kwargs) -> ToolResult:
        """查看文件信息（不执行删除）"""
        file_path = kwargs.get("file_path", "")
        
        if not file_path:
            return ToolResult(success=False, output="", error="文件路径不能为空")
        
        try:
            path = Path(file_path)
            
            # 安全检查
            if not self._is_path_allowed(path):
                return ToolResult(
                    success=False,
                    output="",
                    error=f"安全限制：不允许访问该路径"
                )
            
            if not path.exists():
                return ToolResult(success=False, output="", error=f"文件不存在: {file_path}")
            
            # 获取文件信息
            stat = path.stat()
            is_dir = path.is_dir()
            
            import datetime
            modified_time = datetime.datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S')
            
            dir_emoji = '📁 目录'
            file_emoji = '📄 文件'
            info_parts = [
                f"文件信息: {file_path}",
                f"类型: {dir_emoji if is_dir else file_emoji}",
                f"大小: {stat.st_size} 字节",
                f"修改时间: {modified_time}",
                "\n⚠️ 注意：删除功能已禁用，出于安全考虑。如需删除文件，请手动操作。"
            ]
            
            if is_dir:
                try:
                    items = list(path.iterdir())
                    info_parts.append(f"包含: {len(items)} 个项目")
                except Exception:
                    pass
            
            return ToolResult(
                success=True,
                output="\n".join(info_parts),
                data={"path": str(path), "size": stat.st_size, "modified": modified_time, "is_dir": is_dir},
                metadata={"type": "directory" if is_dir else "file"}
            )
            
        except Exception as e:
            return ToolResult(success=False, output="", error=f"获取文件信息失败: {str(e)}")
