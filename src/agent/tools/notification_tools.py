"""通知工具 - 支持多种通知方式"""

import os
import subprocess
import platform
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum

from src.agent.tools.base import BaseTool, ToolResult, ToolCategory


class NotificationType(Enum):
    """通知类型"""
    SYSTEM = "system"      # 系统通知
    SOUND = "sound"        # 声音提醒
    LOG = "log"            # 日志记录
    TERMINAL = "terminal"  # 终端输出


@dataclass
class NotificationConfig:
    """通知配置"""
    enable_system: bool = True
    enable_sound: bool = True
    default_sound: str = "default"


class SystemNotifyTool(BaseTool):
    """系统通知工具 - 发送系统级通知"""
    
    def __init__(self, config: Optional[NotificationConfig] = None):
        self.config = config or NotificationConfig()
        self._system = platform.system()
        super().__init__()
    
    @property
    def name(self) -> str:
        return "system_notify"
    
    @property
    def description(self) -> str:
        return """发送系统通知。在 macOS 上会显示系统通知横幅，在其他系统上会尝试使用相应的通知机制。
适用场景：
- 长时间任务完成后提醒用户
- 重要操作结果通知
- 错误或警告提醒"""
    
    @property
    def category(self) -> ToolCategory:
        return ToolCategory.NOTIFICATION
    
    @property
    def parameters(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": "title",
                "type": "string",
                "description": "通知标题",
                "required": True
            },
            {
                "name": "message",
                "type": "string", 
                "description": "通知内容",
                "required": True
            },
            {
                "name": "subtitle",
                "type": "string",
                "description": "通知副标题（可选）",
                "required": False
            },
            {
                "name": "sound",
                "type": "boolean",
                "description": "是否播放提示音，默认为 True",
                "required": False
            }
        ]
    
    def execute(self, **kwargs) -> ToolResult:
        """发送系统通知"""
        title = kwargs.get("title", "RAG Agent 通知")
        message = kwargs.get("message", "")
        subtitle = kwargs.get("subtitle", "")
        play_sound = kwargs.get("sound", True)
        
        if not message:
            return ToolResult(
                success=False,
                output="",
                error="通知内容不能为空"
            )
        
        try:
            if self._system == "Darwin":  # macOS
                return self._notify_macos(title, message, subtitle, play_sound)
            elif self._system == "Linux":
                return self._notify_linux(title, message)
            elif self._system == "Windows":
                return self._notify_windows(title, message)
            else:
                # 回退到终端输出
                return self._notify_terminal(title, message)
        except Exception as e:
            return ToolResult(
                success=False,
                output="",
                error=f"发送通知失败: {str(e)}"
            )
    
    def _notify_macos(self, title: str, message: str, subtitle: str, play_sound: bool) -> ToolResult:
        """macOS 系统通知"""
        # 构建 AppleScript
        script_parts = [f'display notification "{message}"']
        script_parts.append(f'with title "{title}"')
        
        if subtitle:
            script_parts.append(f'subtitle "{subtitle}"')
        
        if play_sound:
            script_parts.append('sound name "default"')
        
        script = " ".join(script_parts)
        
        # 执行 AppleScript
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            return ToolResult(
                success=True,
                output=f"✅ 通知已发送: {title}",
                data={
                    "title": title,
                    "message": message,
                    "platform": "macOS"
                }
            )
        else:
            return ToolResult(
                success=False,
                output="",
                error=f"发送通知失败: {result.stderr}"
            )
    
    def _notify_linux(self, title: str, message: str) -> ToolResult:
        """Linux 系统通知（使用 notify-send）"""
        try:
            result = subprocess.run(
                ["notify-send", title, message],
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                return ToolResult(
                    success=True,
                    output=f"✅ 通知已发送: {title}",
                    data={"title": title, "message": message, "platform": "Linux"}
                )
            else:
                return ToolResult(
                    success=False,
                    output="",
                    error=f"发送通知失败: {result.stderr}"
                )
        except FileNotFoundError:
            return self._notify_terminal(title, message)
    
    def _notify_windows(self, title: str, message: str) -> ToolResult:
        """Windows 系统通知（使用 PowerShell）"""
        script = f'''
        [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
        [Windows.UI.Notifications.ToastNotification, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
        [Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime] | Out-Null

        $template = @"
        <toast>
            <visual>
                <binding template="ToastText02">
                    <text id="1">{title}</text>
                    <text id="2">{message}</text>
                </binding>
            </visual>
        </toast>
"@

        $xml = New-Object Windows.Data.Xml.Dom.XmlDocument
        $xml.LoadXml($template)
        $toast = New-Object Windows.UI.Notifications.ToastNotification $xml
        [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("RAG Agent").Show($toast)
        '''
        
        try:
            result = subprocess.run(
                ["powershell", "-Command", script],
                capture_output=True,
                text=True
            )
            
            return ToolResult(
                success=True,
                output=f"✅ 通知已发送: {title}",
                data={"title": title, "message": message, "platform": "Windows"}
            )
        except Exception as e:
            return self._notify_terminal(title, message)
    
    def _notify_terminal(self, title: str, message: str) -> ToolResult:
        """终端通知（回退方案）"""
        output = f"""
╔══════════════════════════════════════════════════════════════╗
║  📢 通知: {title}
╠══════════════════════════════════════════════════════════════╣
║  {message}
╚══════════════════════════════════════════════════════════════╝
"""
        print(output)
        return ToolResult(
            success=True,
            output=output,
            data={"title": title, "message": message, "platform": "terminal"}
        )


class SoundAlertTool(BaseTool):
    """声音提醒工具 - 播放提示音"""
    
    def __init__(self):
        self._system = platform.system()
        super().__init__()
    
    @property
    def name(self) -> str:
        return "sound_alert"
    
    @property
    def description(self) -> str:
        return """播放系统提示音。适用于需要声音提醒的场景。
可选的声音类型：
- success: 成功提示音
- error: 错误提示音  
- warning: 警告提示音
- info: 信息提示音
- complete: 完成提示音"""
    
    @property
    def category(self) -> ToolCategory:
        return ToolCategory.NOTIFICATION
    
    @property
    def parameters(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": "sound_type",
                "type": "string",
                "description": "声音类型: success/error/warning/info/complete",
                "required": False
            },
            {
                "name": "repeat",
                "type": "integer",
                "description": "重复次数，默认为 1",
                "required": False
            }
        ]
    
    def execute(self, **kwargs) -> ToolResult:
        """播放提示音"""
        sound_type = kwargs.get("sound_type", "info")
        repeat = kwargs.get("repeat", 1)
        
        # macOS 声音映射
        macos_sounds = {
            "success": "Glass",
            "error": "Basso",
            "warning": "Sosumi",
            "info": "Pop",
            "complete": "Hero"
        }
        
        try:
            if self._system == "Darwin":
                sound_name = macos_sounds.get(sound_type, "Pop")
                for _ in range(repeat):
                    subprocess.run(
                        ["afplay", f"/System/Library/Sounds/{sound_name}.aiff"],
                        capture_output=True
                    )
                return ToolResult(
                    success=True,
                    output=f"🔔 已播放 {sound_type} 提示音",
                    data={"sound_type": sound_type, "repeat": repeat}
                )
            elif self._system == "Linux":
                # 使用 paplay 或 aplay
                for _ in range(repeat):
                    subprocess.run(["paplay", "/usr/share/sounds/freedesktop/stereo/complete.oga"],
                                 capture_output=True)
                return ToolResult(
                    success=True,
                    output=f"🔔 已播放提示音",
                    data={"sound_type": sound_type}
                )
            else:
                # Windows 或其他系统 - 使用终端响铃
                for _ in range(repeat):
                    print("\a", end="", flush=True)
                return ToolResult(
                    success=True,
                    output=f"🔔 已播放终端提示音",
                    data={"sound_type": "terminal_bell"}
                )
        except Exception as e:
            return ToolResult(
                success=False,
                output="",
                error=f"播放提示音失败: {str(e)}"
            )


class TaskCompletionNotifyTool(BaseTool):
    """任务完成通知工具 - 综合通知（系统通知 + 声音）"""
    
    def __init__(self):
        self._system_notify = SystemNotifyTool()
        self._sound_alert = SoundAlertTool()
        super().__init__()
    
    @property
    def name(self) -> str:
        return "task_complete_notify"
    
    @property
    def description(self) -> str:
        return """发送任务完成通知，同时播放提示音和显示系统通知。
适用于：
- Agent 完成复杂任务后通知用户
- 长时间运行的操作完成
- 需要用户注意的重要结果"""
    
    @property
    def category(self) -> ToolCategory:
        return ToolCategory.NOTIFICATION
    
    @property
    def parameters(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": "task_name",
                "type": "string",
                "description": "任务名称",
                "required": True
            },
            {
                "name": "status",
                "type": "string",
                "description": "任务状态: success/error/warning",
                "required": False
            },
            {
                "name": "details",
                "type": "string",
                "description": "详细信息",
                "required": False
            }
        ]
    
    def execute(self, **kwargs) -> ToolResult:
        """发送任务完成通知"""
        task_name = kwargs.get("task_name", "任务")
        status = kwargs.get("status", "success")
        details = kwargs.get("details", "")
        
        # 状态图标和文字
        status_info = {
            "success": ("✅", "成功完成"),
            "error": ("❌", "执行失败"),
            "warning": ("⚠️", "完成但有警告")
        }
        
        icon, status_text = status_info.get(status, ("ℹ️", "已完成"))
        
        # 构建消息
        title = f"{icon} {task_name} {status_text}"
        message = details if details else f"{task_name} 已{status_text}"
        
        # 发送系统通知
        notify_result = self._system_notify.execute(
            title=title,
            message=message,
            sound=True
        )
        
        # 播放声音（如果系统通知没有声音）
        sound_result = self._sound_alert.execute(sound_type=status)
        
        return ToolResult(
            success=notify_result.success,
            output=f"{title}\n{message}",
            data={
                "task_name": task_name,
                "status": status,
                "details": details,
                "notification_sent": notify_result.success,
                "sound_played": sound_result.success
            }
        )


# 便捷函数
def notify(title: str, message: str, sound: bool = True) -> ToolResult:
    """发送通知的便捷函数"""
    tool = SystemNotifyTool()
    return tool.execute(title=title, message=message, sound=sound)


def alert(sound_type: str = "info") -> ToolResult:
    """播放提示音的便捷函数"""
    tool = SoundAlertTool()
    return tool.execute(sound_type=sound_type)


def task_complete(task_name: str, status: str = "success", details: str = "") -> ToolResult:
    """任务完成通知的便捷函数"""
    tool = TaskCompletionNotifyTool()
    return tool.execute(task_name=task_name, status=status, details=details)
