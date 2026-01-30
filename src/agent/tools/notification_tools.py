"""通知工具 - 支持多种通知方式

本模块提供了跨平台的通知功能，包括：
1. 系统级通知（macOS/Linux/Windows）
2. 声音提醒
3. 任务完成综合通知

主要应用场景：
- Agent 长时间任务完成后提醒用户
- 重要操作结果的即时通知
- 错误或警告的可视化提醒
"""

# === 标准库导入 ===
import os           # 操作系统接口（本文件中未直接使用，但保留以备扩展）
import subprocess   # 用于执行系统命令，如 osascript、notify-send 等
import platform     # 用于检测当前操作系统类型（macOS/Linux/Windows）

# === 类型提示导入 ===
from typing import List, Dict, Any, Optional  # 用于类型标注，提高代码可读性和 IDE 支持

# === 数据结构导入 ===
from dataclasses import dataclass  # 装饰器，用于快速创建数据类
from enum import Enum              # 枚举类型，用于定义固定的选项集合

# === 内部模块导入 ===
from src.agent.tools.base import BaseTool, ToolResult, ToolCategory  # 工具基类和相关类型


class NotificationType(Enum):
    """通知类型枚举
    
    使用枚举而不是字符串的好处：
    1. 类型安全：IDE 可以提供自动补全
    2. 防止拼写错误：只能使用预定义的值
    3. 代码可读性更好
    
    用法示例：
        notification_type = NotificationType.SYSTEM
        if notification_type == NotificationType.SYSTEM:
            # 处理系统通知
            pass
    """
    SYSTEM = "system"      # 系统级通知（弹窗横幅）- 用于重要提醒
    SOUND = "sound"        # 纯声音提醒 - 用于轻量级提示
    LOG = "log"            # 日志记录 - 用于后台静默记录
    TERMINAL = "terminal"  # 终端文字输出 - 用于开发调试


@dataclass
class NotificationConfig:
    """通知配置数据类
    
    @dataclass 装饰器的作用：
    - 自动生成 __init__、__repr__、__eq__ 等方法
    - 减少样板代码，使类定义更简洁
    
    用法示例：
        # 使用默认配置
        config = NotificationConfig()
        
        # 自定义配置
        config = NotificationConfig(
            enable_system=True,
            enable_sound=False,
            default_sound="hero"
        )
        
        # 访问属性
        if config.enable_system:
            send_system_notification()
    """
    enable_system: bool = True     # 是否启用系统通知（默认开启）
    enable_sound: bool = True      # 是否启用声音提醒（默认开启）
    default_sound: str = "default" # 默认提示音名称


class SystemNotifyTool(BaseTool):
    """系统通知工具 - 发送系统级通知
    
    这是一个跨平台的系统通知工具，可以：
    - 在 macOS 上调用 AppleScript 显示通知横幅
    - 在 Linux 上调用 notify-send 命令
    - 在 Windows 上调用 PowerShell 的 Toast 通知
    - 自动回退到终端输出（当系统通知不可用时）
    
    继承关系：
        BaseTool -> SystemNotifyTool
        
    使用示例：
        # 方式1: 直接创建并使用
        tool = SystemNotifyTool()
        result = tool.execute(
            title="下载完成",
            message="文件已成功下载到 Downloads 文件夹"
        )
        
        # 方式2: 使用自定义配置
        config = NotificationConfig(enable_sound=False)
        tool = SystemNotifyTool(config)
        result = tool.execute(title="静默通知", message="这是一个无声通知")
        
        # 方式3: 通过便捷函数
        from notification_tools import notify
        notify("任务完成", "数据处理已完成")
    """
    
    def __init__(self, config: Optional[NotificationConfig] = None):
        """初始化系统通知工具
        
        Args:
            config: 可选的通知配置对象
                   如果不提供，将使用默认配置（启用系统通知和声音）
        
        实现细节：
            1. 使用 config or NotificationConfig() 模式确保总有配置可用
            2. 通过 platform.system() 检测操作系统类型：
               - "Darwin" = macOS
               - "Linux" = Linux
               - "Windows" = Windows
            3. super().__init__() 调用父类 BaseTool 的初始化
        """
        self.config = config or NotificationConfig()  # 配置对象，提供默认值
        self._system = platform.system()              # 操作系统类型（Darwin/Linux/Windows）
        super().__init__()                            # 调用父类初始化方法
    
    @property
    def name(self) -> str:
        """工具名称
        
        @property 装饰器的作用：
        - 将方法转换为只读属性
        - 可以像访问属性一样调用：tool.name 而不是 tool.name()
        - 符合工具系统的统一接口规范
        
        Returns:
            工具的唯一标识符，用于 Agent 调用时识别工具
        """
        return "system_notify"
    
    @property
    def description(self) -> str:
        """工具描述
        
        这个描述会被：
        1. 显示在工具列表中，帮助用户理解工具功能
        2. 传递给 LLM，让 AI 理解何时使用这个工具
        3. 用于生成 API 文档
        
        编写技巧：
        - 第一句话简明扼要说明功能
        - 列出典型使用场景
        - 说明平台兼容性
        """
        return """发送系统通知。在 macOS 上会显示系统通知横幅，在其他系统上会尝试使用相应的通知机制。
适用场景：
- 长时间任务完成后提醒用户
- 重要操作结果通知
- 错误或警告提醒"""
    
    @property
    def category(self) -> ToolCategory:
        """工具分类
        
        用于：
        - 在工具列表中分组显示
        - Agent 根据任务类型筛选合适的工具
        - 统计和管理不同类别的工具
        
        Returns:
            ToolCategory.NOTIFICATION 表示这是一个通知类工具
        """
        return ToolCategory.NOTIFICATION
    
    @property
    def parameters(self) -> List[Dict[str, Any]]:
        """参数定义
        
        这个方法定义了工具接受的参数列表，每个参数是一个字典，包含：
        - name: 参数名称（用于调用时的关键字参数）
        - type: 参数类型（string/integer/boolean/object/array）
        - description: 参数说明（告诉用户/AI 这个参数的作用）
        - required: 是否必需（True=必须提供，False=可选）
        
        这些定义会被用于：
        1. 生成 API 文档
        2. 参数验证（检查类型和必填项）
        3. LLM 理解如何调用工具
        4. IDE 自动补全和类型检查
        
        Returns:
            参数定义列表，每个参数一个字典
        """
        return [
            {
                "name": "title",                      # 参数名
                "type": "string",                    # 数据类型
                "description": "通知标题",            # 参数说明
                "required": True                     # 必需参数
            },
            {
                "name": "message",
                "type": "string", 
                "description": "通知内容",           # 通知的主要文字内容
                "required": True
            },
            {
                "name": "subtitle",
                "type": "string",
                "description": "通知副标题（可选）",  # 仅 macOS 支持副标题
                "required": False                    # 可选参数
            },
            {
                "name": "sound",
                "type": "boolean",                   # 布尔类型：True 或 False
                "description": "是否播放提示音，默认为 True",
                "required": False
            }
        ]
    
    def execute(self, **kwargs) -> ToolResult:
        """执行工具 - 发送系统通知
        
        这是工具的核心方法，执行实际的通知发送操作。
        
        Args:
            **kwargs: 可变关键字参数，包含：
                - title (str): 通知标题
                - message (str): 通知内容
                - subtitle (str, optional): 副标题
                - sound (bool, optional): 是否播放声音
        
        Returns:
            ToolResult: 工具执行结果对象，包含：
                - success (bool): 是否成功
                - output (str): 输出信息（显示给用户）
                - error (str): 错误信息（如果失败）
                - data (dict): 结构化数据（可选）
        
        工作流程：
            1. 从 kwargs 中提取参数，提供默认值
            2. 验证参数（如：message 不能为空）
            3. 根据操作系统类型调用对应的通知方法
            4. 返回执行结果
        """
        # 参数提取与默认值设置
        title = kwargs.get("title", "RAG Agent 通知")  # get() 方法：如果键不存在返回默认值
        message = kwargs.get("message", "")             # 空字符串作为默认值，后续会验证
        subtitle = kwargs.get("subtitle", "")           # 副标题，可选
        play_sound = kwargs.get("sound", True)          # 默认播放声音
        
        # 参数验证：message 是必需的
        if not message:
            return ToolResult(
                success=False,
                output="",
                error="通知内容不能为空"
            )
        
        # try-except 块：捕获所有可能的异常，确保不会崩溃
        try:
            # 根据操作系统类型分发到不同的实现方法
            if self._system == "Darwin":  # macOS 系统
                return self._notify_macos(title, message, subtitle, play_sound)
            elif self._system == "Linux":  # Linux 系统
                return self._notify_linux(title, message)
            elif self._system == "Windows":  # Windows 系统
                return self._notify_windows(title, message)
            else:
                # 未知系统或不支持的系统，回退到终端输出
                return self._notify_terminal(title, message)
        except Exception as e:
            # 捕获所有异常，返回失败结果而不是崩溃
            return ToolResult(
                success=False,
                output="",
                error=f"发送通知失败: {str(e)}"
            )
    
    def _notify_macos(self, title: str, message: str, subtitle: str, play_sound: bool) -> ToolResult:
        """macOS 系统通知实现
        
        技术细节：
            使用 AppleScript 的 'display notification' 命令发送通知
            AppleScript 是 macOS 的自动化脚本语言
        
        Args:
            title: 通知标题（显示在通知横幅顶部）
            message: 通知正文（主要内容）
            subtitle: 通知副标题（显示在标题和正文之间）
            play_sound: 是否播放系统提示音
        
        Returns:
            ToolResult: 包含执行结果的对象
        
        AppleScript 语法说明：
            display notification "内容" with title "标题" subtitle "副标题" sound name "声音"
        """
        # 构建 AppleScript 命令
        # 使用列表逐步添加命令片段，最后用空格连接
        script_parts = [f'display notification "{message}"']  # 基础命令 + 消息内容
        script_parts.append(f'with title "{title}"')          # 添加标题
        
        # 副标题是可选的，只有提供时才添加
        if subtitle:
            script_parts.append(f'subtitle "{subtitle}"')
        
        # 声音是可选的
        if play_sound:
            script_parts.append('sound name "default"')  # "default" 是系统默认提示音
        
        script = " ".join(script_parts)  # 将所有部分用空格连接成完整的脚本
        
        # 执行 AppleScript
        # osascript 是 macOS 的 AppleScript 执行器
        result = subprocess.run(
            ["osascript", "-e", script],  # -e 参数表示执行后面的脚本字符串
            capture_output=True,          # 捕获标准输出和标准错误
            text=True                     # 以文本模式（而非字节）返回输出
        )
        
        # 检查执行结果
        if result.returncode == 0:  # returncode 为 0 表示成功
            return ToolResult(
                success=True,
                output=f"✅ 通知已发送: {title}",  # 友好的成功消息
                data={
                    "title": title,
                    "message": message,
                    "platform": "macOS"  # 记录使用的平台
                }
            )
        else:
            # 命令执行失败，返回错误信息
            return ToolResult(
                success=False,
                output="",
                error=f"发送通知失败: {result.stderr}"  # stderr 包含错误详情
            )
    
    def _notify_linux(self, title: str, message: str) -> ToolResult:
        """Linux 系统通知实现
        
        技术细节：
            使用 notify-send 命令，这是 Linux 桌面环境的标准通知工具
            需要安装 libnotify-bin 包（大多数 Linux 发行版预装）
        
        Args:
            title: 通知标题
            message: 通知内容
        
        Returns:
            ToolResult: 执行结果
            如果 notify-send 不可用，会回退到终端输出
        """
        try:
            # 执行 notify-send 命令
            # 格式：notify-send "标题" "内容"
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
            # notify-send 命令不存在（未安装或不在 PATH 中）
            # 回退到终端通知
            return self._notify_terminal(title, message)
    
    def _notify_windows(self, title: str, message: str) -> ToolResult:
        """Windows 系统通知实现
        
        技术细节：
            使用 PowerShell 调用 Windows.UI.Notifications API
            发送 Windows 10/11 风格的 Toast 通知
        
        Args:
            title: 通知标题
            message: 通知内容
        
        Returns:
            ToolResult: 执行结果
            如果失败，会回退到终端输出
        
        PowerShell 脚本说明：
            1. 加载 Windows Runtime 的通知 API
            2. 创建 XML 格式的通知模板
            3. 使用 ToastNotificationManager 显示通知
        """
        # PowerShell 脚本（使用 f-string 插入变量）
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
            # 执行 PowerShell 脚本
            result = subprocess.run(
                ["powershell", "-Command", script],  # -Command 参数执行脚本
                capture_output=True,
                text=True
            )
            
            # 注意：Toast 通知可能没有明显的错误返回，所以这里简单认为成功
            return ToolResult(
                success=True,
                output=f"✅ 通知已发送: {title}",
                data={"title": title, "message": message, "platform": "Windows"}
            )
        except Exception as e:
            # 如果 PowerShell 执行失败，回退到终端通知
            return self._notify_terminal(title, message)
    
    def _notify_terminal(self, title: str, message: str) -> ToolResult:
        """终端通知实现（通用回退方案）
        
        当系统通知不可用时的回退方案：
        - 在终端中打印格式化的通知框
        - 使用 Unicode 字符绘制边框
        - 适用于无桌面环境的服务器或不支持的系统
        
        Args:
            title: 通知标题
            message: 通知内容
        
        Returns:
            ToolResult: 总是返回成功（因为终端输出不会失败）
        
        设计思路：
            使用 ╔═╗║╚╝ 等字符绘制边框，使输出更美观
            即使没有图形界面，也能提供视觉上的提醒效果
        """
        # 使用三引号字符串和 f-string 创建格式化的通知框
        # ║ 是垂直线，═ 是水平线，╔╗╚╝ 是四个角
        output = f"""
╔══════════════════════════════════════════════════════════════╗
║  📢 通知: {title}
╠══════════════════════════════════════════════════════════════╣
║  {message}
╚══════════════════════════════════════════════════════════════╝
"""
        print(output)  # 直接打印到终端
        return ToolResult(
            success=True,
            output=output,
            data={"title": title, "message": message, "platform": "terminal"}
        )


class SoundAlertTool(BaseTool):
    """声音提醒工具 - 播放系统提示音
    
    功能说明：
        播放系统内置的提示音，用于声音提醒
        不同的声音类型对应不同的事件类型
    
    平台支持：
        - macOS: 使用 afplay 播放系统声音文件
        - Linux: 使用 paplay 播放系统声音
        - Windows/其他: 使用终端响铃（\a 字符）
    
    应用场景：
        - 需要声音提示但不需要可视化通知
        - 后台任务完成提醒
        - 错误或警告的声音提示
        - 倒计时或定时提醒
    
    使用示例：
        tool = SoundAlertTool()
        
        # 播放成功提示音
        tool.execute(sound_type="success")
        
        # 播放错误提示音，重复3次
        tool.execute(sound_type="error", repeat=3)
        
        # 使用便捷函数
        from notification_tools import alert
        alert("warning")
    """
    
    def __init__(self):
        """初始化声音提醒工具
        
        检测操作系统类型，以便选择合适的播放方法
        """
        self._system = platform.system()  # 检测操作系统
        super().__init__()                # 调用父类初始化
    
    @property
    def name(self) -> str:
        """工具名称：sound_alert"""
        return "sound_alert"
    
    @property
    def description(self) -> str:
        """工具描述
        
        详细说明可用的声音类型和使用场景
        帮助 AI 理解何时选择合适的提示音
        """
        return """播放系统提示音。适用于需要声音提醒的场景。
可选的声音类型：
- success: 成功提示音
- error: 错误提示音  
- warning: 警告提示音
- info: 信息提示音
- complete: 完成提示音"""
    
    @property
    def category(self) -> ToolCategory:
        """工具分类：通知类"""
        return ToolCategory.NOTIFICATION
    
    @property
    def parameters(self) -> List[Dict[str, Any]]:
        """参数定义
        
        sound_type: 声音类型，决定播放哪种提示音
        repeat: 重复次数，用于强调重要通知
        """
        return [
            {
                "name": "sound_type",
                "type": "string",
                "description": "声音类型: success/error/warning/info/complete",
                "required": False  # 可选，默认为 info
            },
            {
                "name": "repeat",
                "type": "integer",
                "description": "重复次数，默认为 1",
                "required": False
            }
        ]
    
    def execute(self, **kwargs) -> ToolResult:
        """执行工具 - 播放提示音
        
        Args:
            **kwargs: 可变关键字参数
                - sound_type (str): 声音类型，默认 "info"
                - repeat (int): 重复次数，默认 1
        
        Returns:
            ToolResult: 执行结果
        
        实现逻辑：
            1. 提取参数（sound_type 和 repeat）
            2. 根据操作系统选择播放方法
            3. 循环播放指定次数
            4. 返回执行结果
        """
        sound_type = kwargs.get("sound_type", "info")  # 默认信息提示音
        repeat = kwargs.get("repeat", 1)               # 默认播放一次
        
        # macOS 声音名称映射表
        # 将通用的声音类型映射到 macOS 系统声音文件名
        macos_sounds = {
            "success": "Glass",    # 清脆的玻璃声 - 适合成功提示
            "error": "Basso",      # 低沉的声音 - 适合错误提示
            "warning": "Sosumi",   # 引人注意的声音 - 适合警告
            "info": "Pop",         # 轻快的爆破音 - 适合信息提示
            "complete": "Hero"     # 胜利的声音 - 适合完成提示
        }
        
        try:
            if self._system == "Darwin":  # macOS 系统
                # 从映射表中获取声音文件名，如果类型不存在则使用 "Pop"
                sound_name = macos_sounds.get(sound_type, "Pop")
                
                # 循环播放指定次数
                for _ in range(repeat):
                    # afplay 是 macOS 的音频播放命令
                    # /System/Library/Sounds/ 是系统声音文件夹
                    subprocess.run(
                        ["afplay", f"/System/Library/Sounds/{sound_name}.aiff"],
                        capture_output=True  # 捕获输出，避免干扰终端
                    )
                    
                return ToolResult(
                    success=True,
                    output=f"🔔 已播放 {sound_type} 提示音",
                    data={"sound_type": sound_type, "repeat": repeat}
                )
                
            elif self._system == "Linux":  # Linux 系统
                # 使用 paplay 播放 FreeDesktop 标准声音
                for _ in range(repeat):
                    subprocess.run(
                        ["paplay", "/usr/share/sounds/freedesktop/stereo/complete.oga"],
                        capture_output=True
                    )
                    
                return ToolResult(
                    success=True,
                    output=f"🔔 已播放提示音",
                    data={"sound_type": sound_type}
                )
                
            else:  # Windows 或其他系统
                # 使用终端响铃（ASCII 响铃字符 \a）
                # 这是最通用的方法，几乎所有系统都支持
                for _ in range(repeat):
                    print("\a", end="", flush=True)  # \a 是响铃字符
                    # end="" 表示不换行
                    # flush=True 立即输出，不缓冲
                    
                return ToolResult(
                    success=True,
                    output=f"🔔 已播放终端提示音",
                    data={"sound_type": "terminal_bell"}
                )
                
        except Exception as e:
            # 捕获所有异常，确保不会崩溃
            return ToolResult(
                success=False,
                output="",
                error=f"播放提示音失败: {str(e)}"
            )


class TaskCompletionNotifyTool(BaseTool):
    """任务完成通知工具 - 综合通知（系统通知 + 声音）
    
    设计模式：组合模式（Composition Pattern）
        组合 SystemNotifyTool 和 SoundAlertTool 两个工具
        提供一体化的任务完成通知体验
    
    功能特点：
        1. 同时发送系统通知和播放提示音
        2. 根据任务状态自动选择合适的图标和声音
        3. 提供友好的成功/失败/警告消息
    
    应用场景：
        - Agent 完成复杂任务后的综合通知
        - 长时间运行的批处理完成
        - 需要多感官提醒的重要事件
        - 自动化脚本执行结果通知
    
    使用示例：
        tool = TaskCompletionNotifyTool()
        
        # 成功通知
        tool.execute(
            task_name="数据导出",
            status="success",
            details="成功导出 1000 条记录到 output.csv"
        )
        
        # 错误通知
        tool.execute(
            task_name="文件上传",
            status="error",
            details="网络连接失败"
        )
        
        # 使用便捷函数
        from notification_tools import task_complete
        task_complete("模型训练", "success", "准确率: 95.2%")
    """
    
    def __init__(self):
        """初始化任务完成通知工具
        
        组合模式实现：
            创建两个内部工具实例，作为组件使用
            这样可以复用已有的通知功能，避免代码重复
        """
        self._system_notify = SystemNotifyTool()  # 系统通知组件
        self._sound_alert = SoundAlertTool()      # 声音提醒组件
        super().__init__()
    
    @property
    def name(self) -> str:
        """工具名称：task_complete_notify"""
        return "task_complete_notify"
    
    @property
    def description(self) -> str:
        """工具描述
        
        强调这是一个高级工具，组合了多种通知方式
        """
        return """发送任务完成通知，同时播放提示音和显示系统通知。
适用于：
- Agent 完成复杂任务后通知用户
- 长时间运行的操作完成
- 需要用户注意的重要结果"""
    
    @property
    def category(self) -> ToolCategory:
        """工具分类：通知类"""
        return ToolCategory.NOTIFICATION
    
    @property
    def parameters(self) -> List[Dict[str, Any]]:
        """参数定义
        
        参数设计：
            - task_name: 任务名称，简洁描述任务
            - status: 任务状态，决定通知样式和声音
            - details: 详细信息，提供更多上下文
        """
        return [
            {
                "name": "task_name",
                "type": "string",
                "description": "任务名称",
                "required": True  # 必需，用于标识任务
            },
            {
                "name": "status",
                "type": "string",
                "description": "任务状态: success/error/warning",
                "required": False  # 可选，默认为 success
            },
            {
                "name": "details",
                "type": "string",
                "description": "详细信息",
                "required": False  # 可选，提供额外的上下文
            }
        ]
    
    def execute(self, **kwargs) -> ToolResult:
        """执行工具 - 发送任务完成通知
        
        Args:
            **kwargs: 可变关键字参数
                - task_name (str): 任务名称
                - status (str): 任务状态 (success/error/warning)
                - details (str): 详细信息
        
        Returns:
            ToolResult: 综合执行结果
        
        工作流程：
            1. 提取参数并设置默认值
            2. 根据状态选择合适的图标和文字
            3. 构建通知标题和消息
            4. 发送系统通知
            5. 播放对应的提示音
            6. 返回综合结果
        """
        # 参数提取
        task_name = kwargs.get("task_name", "任务")
        status = kwargs.get("status", "success")      # 默认成功状态
        details = kwargs.get("details", "")
        
        # 状态信息映射表
        # 字典的值是元组：(图标, 状态文字)
        # 这种设计使得添加新状态类型很容易
        status_info = {
            "success": ("✅", "成功完成"),      # 绿色勾 - 成功
            "error": ("❌", "执行失败"),        # 红叉 - 错误
            "warning": ("⚠️", "完成但有警告")  # 警告标志 - 警告
        }
        
        # 从映射表获取状态信息，如果状态类型未知则使用默认值
        icon, status_text = status_info.get(status, ("ℹ️", "已完成"))
        
        # 构建通知消息
        title = f"{icon} {task_name} {status_text}"                          # 标题包含图标
        message = details if details else f"{task_name} 已{status_text}"    # 有详情用详情，否则用简单描述
        
        # 发送系统通知（带声音）
        notify_result = self._system_notify.execute(
            title=title,
            message=message,
            sound=True  # 启用系统通知的声音
        )
        
        # 播放额外的提示音（基于状态）
        # 即使系统通知有声音，也播放额外的提示音以加强提醒效果
        sound_result = self._sound_alert.execute(sound_type=status)
        
        # 返回综合结果
        # 只要系统通知成功就认为整体成功
        # data 中记录两个组件的执行状态
        return ToolResult(
            success=notify_result.success,
            output=f"{title}\n{message}",  # 输出包含完整的通知信息
            data={
                "task_name": task_name,
                "status": status,
                "details": details,
                "notification_sent": notify_result.success,  # 系统通知是否成功
                "sound_played": sound_result.success         # 提示音是否成功
            }
        )


# ============================================================
# 便捷函数 - 简化工具调用
# ============================================================
# 这些函数提供了更简单的 API，无需手动创建工具实例
# 适合在脚本中快速使用通知功能

def notify(title: str, message: str, sound: bool = True) -> ToolResult:
    """发送通知的便捷函数
    
    这是 SystemNotifyTool 的快捷方式，隐藏了工具实例化的细节
    
    Args:
        title (str): 通知标题
        message (str): 通知内容
        sound (bool): 是否播放提示音，默认 True
    
    Returns:
        ToolResult: 执行结果对象
    
    使用示例：
        # 基本用法
        notify("下载完成", "文件已保存到 Downloads 文件夹")
        
        # 静默通知（无声音）
        notify("后台更新", "系统已更新到最新版本", sound=False)
        
        # 在脚本中使用
        if download_success:
            result = notify("成功", "所有文件下载完成")
            if result.success:
                print("通知已发送")
    
    实现说明：
        每次调用都创建新的工具实例，这样可以保证线程安全
        虽然会有轻微的性能开销，但对于通知功能来说可以忽略
    """
    tool = SystemNotifyTool()  # 创建工具实例
    return tool.execute(title=title, message=message, sound=sound)  # 执行并返回结果


def alert(sound_type: str = "info") -> ToolResult:
    """播放提示音的便捷函数
    
    这是 SoundAlertTool 的快捷方式
    
    Args:
        sound_type (str): 声音类型
            可选值：success, error, warning, info, complete
            默认：info
    
    Returns:
        ToolResult: 执行结果对象
    
    使用示例：
        # 播放成功提示音
        alert("success")
        
        # 播放错误提示音
        alert("error")
        
        # 默认信息提示音
        alert()
        
        # 在条件判断中使用
        if error_occurred:
            alert("error")
        else:
            alert("success")
    
    提示：
        如果需要重复播放，请直接使用 SoundAlertTool：
        tool = SoundAlertTool()
        tool.execute(sound_type="warning", repeat=3)
    """
    tool = SoundAlertTool()  # 创建工具实例
    return tool.execute(sound_type=sound_type)  # 执行并返回结果


def task_complete(task_name: str, status: str = "success", details: str = "") -> ToolResult:
    """任务完成通知的便捷函数
    
    这是 TaskCompletionNotifyTool 的快捷方式
    提供最简单的方式发送任务完成通知
    
    Args:
        task_name (str): 任务名称（必需）
        status (str): 任务状态，默认 "success"
            可选值：success, error, warning
        details (str): 详细信息（可选）
    
    Returns:
        ToolResult: 执行结果对象
    
    使用示例：
        # 简单的成功通知
        task_complete("数据备份")
        
        # 带详细信息的成功通知
        task_complete("数据导出", "success", "成功导出 1000 条记录")
        
        # 错误通知
        task_complete("文件上传", "error", "网络连接超时")
        
        # 警告通知
        task_complete("代码检查", "warning", "发现 3 个潜在问题")
        
        # 在函数结束时通知
        def process_data():
            try:
                # ... 处理数据 ...
                task_complete("数据处理", "success", "处理完成")
            except Exception as e:
                task_complete("数据处理", "error", str(e))
    
    设计思路：
        这个函数特别适合在自动化脚本的关键节点使用
        可以让用户及时了解任务执行状态，而无需一直盯着屏幕
    """
    tool = TaskCompletionNotifyTool()  # 创建工具实例
    return tool.execute(task_name=task_name, status=status, details=details)  # 执行并返回结果
