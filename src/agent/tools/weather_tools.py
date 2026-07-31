"""天气工具 - 通过免费 API 获取天气信息"""

import logging
from typing import List, Dict, Any

from src.agent.tools.base import BaseTool, ToolResult, ToolCategory

logger = logging.getLogger(__name__)


class WeatherTool(BaseTool):
    """天气查询工具（使用 wttr.in 免费服务）"""

    @property
    def name(self) -> str:
        return "weather"

    @property
    def description(self) -> str:
        return (
            "查询指定城市的天气信息，包括温度、湿度、风速、天气描述等。"
            "city 必须来自用户原话或历史对话中已出现的地点；用户未说明地点时禁止调用，"
            "应直接追问要查哪个城市/地区。支持中文城市名。无需API密钥。禁止默认或猜测城市。"
        )

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.UTILITY

    @property
    def parameters(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": "city",
                "type": "string",
                "description": (
                    "必填。只能填用户明确说过的城市/地区名，例如用户说「广州天气」则填「广州」。"
                    "禁止填用户未提及的城市，禁止用示例城市或首都作为默认值。"
                ),
                "required": True,
            },
            {
                "name": "days",
                "type": "integer",
                "description": "预报天数(1-3)，默认1(仅当天)",
                "required": False,
            },
        ]

    @classmethod
    def city_aliases(cls, city: str) -> List[str]:
        """返回城市名的中英文别名，用于上下文校验。"""
        city = (city or "").strip()
        if not city:
            return []
        aliases = {city, city.lower()}
        for zh, en in cls.CITY_MAP.items():
            if city == zh or city.lower() == en.lower():
                aliases.add(zh)
                aliases.add(en)
                aliases.add(en.lower())
        return list(aliases)

    @classmethod
    def is_city_in_context(cls, city: str, context: str) -> bool:
        """判断城市是否出现在用户问题或历史对话中。"""
        if not city or not context:
            return False
        context_lower = context.lower()
        for alias in cls.city_aliases(city):
            if not alias:
                continue
            if alias.lower() == alias:
                if alias in context_lower:
                    return True
            elif alias in context:
                return True
        return False

    # 城市名中英文映射
    CITY_MAP = {
        "北京": "Beijing", "上海": "Shanghai", "广州": "Guangzhou",
        "深圳": "Shenzhen", "杭州": "Hangzhou", "南京": "Nanjing",
        "成都": "Chengdu", "武汉": "Wuhan", "西安": "Xian",
        "重庆": "Chongqing", "天津": "Tianjin", "苏州": "Suzhou",
        "长沙": "Changsha", "青岛": "Qingdao", "大连": "Dalian",
        "厦门": "Xiamen", "昆明": "Kunming", "三亚": "Sanya",
        "香港": "Hong Kong", "台北": "Taipei", "东京": "Tokyo",
        "首尔": "Seoul", "纽约": "New York", "伦敦": "London",
        "巴黎": "Paris", "悉尼": "Sydney", "新加坡": "Singapore",
    }

    # 天气描述中英文映射
    WEATHER_DESC = {
        "Sunny": "晴天 ☀️",
        "Clear": "晴朗 🌙",
        "Partly cloudy": "多云 ⛅",
        "Cloudy": "阴天 ☁️",
        "Overcast": "阴 ☁️",
        "Mist": "薄雾 🌫️",
        "Fog": "雾 🌫️",
        "Light rain": "小雨 🌦️",
        "Moderate rain": "中雨 🌧️",
        "Heavy rain": "大雨 🌧️",
        "Light snow": "小雪 🌨️",
        "Moderate snow": "中雪 ❄️",
        "Heavy snow": "大雪 ❄️",
        "Thunderstorm": "雷暴 ⛈️",
        "Patchy rain possible": "可能有零星小雨 🌦️",
        "Light drizzle": "毛毛雨 🌦️",
    }

    def execute(self, **kwargs) -> ToolResult:
        import requests

        city = (kwargs.get("city") or "").strip()
        if not city:
            return ToolResult(
                success=False,
                output="",
                error="缺少城市参数。请先询问用户要查询哪个城市/地区的天气，不要默认任何城市。",
            )
        days = min(int(kwargs.get("days", 1)), 3)

        # 映射中文城市名
        city_en = self.CITY_MAP.get(city, city)

        try:
            # 使用 wttr.in 的 JSON API
            url = f"https://wttr.in/{city_en}"
            response = requests.get(
                url,
                params={"format": "j1"},
                headers={"Accept-Language": "zh"},
                timeout=15,
            )
            response.raise_for_status()
            data = response.json()
        except requests.exceptions.Timeout:
            return ToolResult(success=False, output="", error="天气查询超时，请稍后重试")
        except requests.exceptions.ConnectionError:
            return ToolResult(success=False, output="", error="无法连接天气服务，请检查网络")
        except Exception as e:
            return ToolResult(success=False, output="", error=f"天气查询失败: {e}")

        try:
            current = data["current_condition"][0]
            area = data.get("nearest_area", [{}])[0]
            area_name = area.get("areaName", [{}])[0].get("value", city)
            country = area.get("country", [{}])[0].get("value", "")

            # 当前天气
            desc_en = current.get("weatherDesc", [{}])[0].get("value", "")
            desc = self.WEATHER_DESC.get(desc_en, desc_en)

            lines = [
                f"🌤️ 天气查询 - {area_name}, {country}\n",
                f"📍 当前天气:",
                f"  天气: {desc}",
                f"  温度: {current.get('temp_C', '?')}°C (体感 {current.get('FeelsLikeC', '?')}°C)",
                f"  湿度: {current.get('humidity', '?')}%",
                f"  风速: {current.get('windspeedKmph', '?')} km/h ({current.get('winddir16Point', '')})",
                f"  能见度: {current.get('visibility', '?')} km",
                f"  紫外线指数: {current.get('uvIndex', '?')}",
            ]

            # 天气预报
            forecasts = data.get("weather", [])[:days]
            if forecasts:
                lines.append(f"\n📅 天气预报:")
                for day in forecasts:
                    date = day.get("date", "")
                    max_temp = day.get("maxtempC", "?")
                    min_temp = day.get("mintempC", "?")
                    hourly = day.get("hourly", [])
                    # 取中午的天气描述
                    noon = hourly[4] if len(hourly) > 4 else hourly[0] if hourly else {}
                    day_desc_en = noon.get("weatherDesc", [{}])[0].get("value", "")
                    day_desc = self.WEATHER_DESC.get(day_desc_en, day_desc_en)
                    sunrise = day.get("astronomy", [{}])[0].get("sunrise", "") if day.get("astronomy") else ""
                    sunset = day.get("astronomy", [{}])[0].get("sunset", "") if day.get("astronomy") else ""
                    
                    lines.append(
                        f"  {date}: {day_desc}  {min_temp}°C ~ {max_temp}°C"
                        f"  🌅{sunrise} 🌇{sunset}"
                    )

            result_data = {
                "city": area_name,
                "country": country,
                "temperature": current.get("temp_C"),
                "feels_like": current.get("FeelsLikeC"),
                "humidity": current.get("humidity"),
                "description": desc,
            }

            return ToolResult(success=True, output="\n".join(lines), data=result_data)

        except (KeyError, IndexError) as e:
            return ToolResult(success=False, output="", error=f"解析天气数据失败: {e}")
