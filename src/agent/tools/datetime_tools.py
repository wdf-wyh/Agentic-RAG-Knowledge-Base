"""日期时间工具 - 提供时间查询、日期计算、倒计时等功能"""

import logging
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any, Optional
from zoneinfo import ZoneInfo

from src.agent.tools.base import BaseTool, ToolResult, ToolCategory

logger = logging.getLogger(__name__)


# 常用时区别名映射
TIMEZONE_ALIASES = {
    "北京": "Asia/Shanghai",
    "上海": "Asia/Shanghai",
    "中国": "Asia/Shanghai",
    "东京": "Asia/Tokyo",
    "日本": "Asia/Tokyo",
    "首尔": "Asia/Seoul",
    "韩国": "Asia/Seoul",
    "纽约": "America/New_York",
    "美东": "America/New_York",
    "洛杉矶": "America/Los_Angeles",
    "美西": "America/Los_Angeles",
    "伦敦": "Europe/London",
    "英国": "Europe/London",
    "巴黎": "Europe/Paris",
    "法国": "Europe/Paris",
    "柏林": "Europe/Berlin",
    "德国": "Europe/Berlin",
    "莫斯科": "Europe/Moscow",
    "俄罗斯": "Europe/Moscow",
    "悉尼": "Australia/Sydney",
    "澳大利亚": "Australia/Sydney",
    "新加坡": "Asia/Singapore",
    "印度": "Asia/Kolkata",
    "迪拜": "Asia/Dubai",
    "UTC": "UTC",
}

# 中国节假日/纪念日（部分常见的）
CHINESE_HOLIDAYS = {
    (1, 1): "元旦",
    (2, 14): "情人节",
    (3, 8): "妇女节",
    (3, 12): "植树节",
    (4, 1): "愚人节",
    (5, 1): "劳动节",
    (5, 4): "青年节",
    (6, 1): "儿童节",
    (7, 1): "建党节",
    (8, 1): "建军节",
    (9, 10): "教师节",
    (10, 1): "国庆节",
    (12, 25): "圣诞节",
}

WEEKDAY_NAMES = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]


class CurrentTimeTool(BaseTool):
    """获取当前日期时间"""

    @property
    def name(self) -> str:
        return "current_time"

    @property
    def description(self) -> str:
        return "获取当前日期和时间，支持不同时区。可用于回答'现在几点'、'今天星期几'等问题。"

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.UTILITY

    @property
    def parameters(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": "timezone",
                "type": "string",
                "description": "时区名称，如 'Asia/Shanghai'、'America/New_York'，也支持中文如 '北京'、'纽约'。默认为北京时间。",
                "required": False,
            }
        ]

    def execute(self, **kwargs) -> ToolResult:
        tz_input = kwargs.get("timezone", "Asia/Shanghai")

        # 解析时区
        tz_name = TIMEZONE_ALIASES.get(tz_input, tz_input)
        try:
            tz = ZoneInfo(tz_name)
        except Exception:
            return ToolResult(
                success=False,
                output="",
                error=f"无法识别时区: {tz_input}。请使用标准时区名如 'Asia/Shanghai' 或中文如 '北京'。",
            )

        now = datetime.now(tz)
        weekday = WEEKDAY_NAMES[now.weekday()]

        # 检查今天是否是节假日
        holiday = CHINESE_HOLIDAYS.get((now.month, now.day), "")
        holiday_info = f"  🎉 今天是{holiday}！" if holiday else ""

        # 获取年份信息
        day_of_year = now.timetuple().tm_yday
        total_days = 366 if (now.year % 4 == 0 and (now.year % 100 != 0 or now.year % 400 == 0)) else 365
        year_progress = round(day_of_year / total_days * 100, 1)

        output = (
            f"📅 当前时间 ({tz_name})\n"
            f"日期: {now.strftime('%Y年%m月%d日')} {weekday}\n"
            f"时间: {now.strftime('%H:%M:%S')}\n"
            f"时区: {tz_name} (UTC{now.strftime('%z')})\n"
            f"本年第 {day_of_year} 天，年度进度 {year_progress}%"
            f"{holiday_info}"
        )

        return ToolResult(
            success=True,
            output=output,
            data={
                "datetime": now.isoformat(),
                "date": now.strftime("%Y-%m-%d"),
                "time": now.strftime("%H:%M:%S"),
                "weekday": weekday,
                "timezone": tz_name,
                "day_of_year": day_of_year,
                "year_progress": year_progress,
                "holiday": holiday or None,
            },
        )


class DateCalculatorTool(BaseTool):
    """日期计算工具"""

    @property
    def name(self) -> str:
        return "date_calculator"

    @property
    def description(self) -> str:
        return "日期计算工具：计算两个日期之间的天数差、在某个日期上加减天数、计算距离某个节日或截止日期还有多少天。"

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.UTILITY

    @property
    def parameters(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": "operation",
                "type": "string",
                "description": "操作类型: 'diff'(计算两日期差), 'add'(日期加减天数), 'countdown'(距离目标日期的倒计时)",
                "required": True,
            },
            {
                "name": "date1",
                "type": "string",
                "description": "第一个日期，格式 YYYY-MM-DD，如 '2025-01-01'。对于 'add' 操作为起始日期，对于 'countdown' 为目标日期。",
                "required": True,
            },
            {
                "name": "date2",
                "type": "string",
                "description": "第二个日期，格式 YYYY-MM-DD。仅在 'diff' 操作时需要。",
                "required": False,
            },
            {
                "name": "days",
                "type": "integer",
                "description": "要加减的天数。仅在 'add' 操作时需要，正数向后，负数向前。",
                "required": False,
            },
        ]

    def _parse_date(self, date_str: str) -> Optional[datetime]:
        for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y年%m月%d日"):
            try:
                return datetime.strptime(date_str, fmt)
            except ValueError:
                continue
        return None

    def execute(self, **kwargs) -> ToolResult:
        operation = kwargs.get("operation", "diff")
        date1_str = kwargs.get("date1", "")
        date2_str = kwargs.get("date2", "")
        days = kwargs.get("days", 0)

        date1 = self._parse_date(str(date1_str))
        if not date1:
            return ToolResult(success=False, output="", error=f"无法解析日期: {date1_str}，请使用 YYYY-MM-DD 格式。")

        if operation == "diff":
            date2 = self._parse_date(str(date2_str))
            if not date2:
                return ToolResult(success=False, output="", error=f"无法解析第二个日期: {date2_str}")
            delta = (date2 - date1).days
            abs_delta = abs(delta)
            weeks = abs_delta // 7
            remaining_days = abs_delta % 7
            output = (
                f"📊 日期差计算\n"
                f"从 {date1.strftime('%Y-%m-%d')} 到 {date2.strftime('%Y-%m-%d')}\n"
                f"相差: {abs_delta} 天（约 {weeks} 周 {remaining_days} 天）\n"
                f"约 {abs_delta / 30.44:.1f} 个月，{abs_delta / 365.25:.2f} 年"
            )
            return ToolResult(success=True, output=output, data={"days": delta, "weeks": weeks})

        elif operation == "add":
            try:
                days = int(days)
            except (ValueError, TypeError):
                return ToolResult(success=False, output="", error="请提供有效的天数(整数)")
            result_date = date1 + timedelta(days=days)
            weekday = WEEKDAY_NAMES[result_date.weekday()]
            output = (
                f"📅 日期计算\n"
                f"{date1.strftime('%Y-%m-%d')} {'加上' if days >= 0 else '减去'} {abs(days)} 天\n"
                f"= {result_date.strftime('%Y年%m月%d日')} {weekday}"
            )
            return ToolResult(success=True, output=output, data={"result_date": result_date.strftime("%Y-%m-%d")})

        elif operation == "countdown":
            today = datetime.now()
            target = date1
            # 如果目标日期已过，检查今年/明年的同一日期
            if target < today:
                target = target.replace(year=today.year)
                if target < today:
                    target = target.replace(year=today.year + 1)
            delta = (target - today).days
            output = (
                f"⏳ 倒计时\n"
                f"目标日期: {target.strftime('%Y年%m月%d日')} {WEEKDAY_NAMES[target.weekday()]}\n"
                f"距今还有: {delta} 天"
            )
            return ToolResult(success=True, output=output, data={"days_remaining": delta, "target_date": target.strftime("%Y-%m-%d")})

        else:
            return ToolResult(success=False, output="", error=f"不支持的操作: {operation}，请使用 diff/add/countdown")


class WorldClockTool(BaseTool):
    """世界时钟 - 同时显示多个时区的时间"""

    @property
    def name(self) -> str:
        return "world_clock"

    @property
    def description(self) -> str:
        return "世界时钟，同时显示多个城市/时区的当前时间。用于比较不同地区的时间。"

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.UTILITY

    @property
    def parameters(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": "cities",
                "type": "string",
                "description": "城市列表，用逗号分隔，如 '北京,纽约,伦敦,东京'。不填则显示默认主要城市。",
                "required": False,
            }
        ]

    def execute(self, **kwargs) -> ToolResult:
        cities_str = kwargs.get("cities", "北京,纽约,伦敦,东京,悉尼")
        cities = [c.strip() for c in cities_str.split(",")]

        lines = ["🌍 世界时钟\n"]
        results = []
        for city in cities:
            tz_name = TIMEZONE_ALIASES.get(city, city)
            try:
                tz = ZoneInfo(tz_name)
                now = datetime.now(tz)
                weekday = WEEKDAY_NAMES[now.weekday()]
                lines.append(
                    f"  🕐 {city:8s} | {now.strftime('%Y-%m-%d %H:%M:%S')} {weekday} (UTC{now.strftime('%z')})"
                )
                results.append({"city": city, "timezone": tz_name, "time": now.isoformat()})
            except Exception:
                lines.append(f"  ❌ {city:8s} | 无法识别该时区")

        return ToolResult(success=True, output="\n".join(lines), data={"clocks": results})
