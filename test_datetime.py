#!/usr/bin/env python3
"""测试脚本 - 验证日期时间是否正确"""

from datetime import datetime
import pytz
import os

# 测试1: 检查系统时区设置
print("=" * 60)
print("测试1: 系统时区设置")
print("=" * 60)
print(f"系统时区环境变量 (TZ): {os.environ.get('TZ', '未设置')}")

# 测试2: 检查当前时间
print("\n" + "=" * 60)
print("测试2: 当前时间")
print("=" * 60)

# 不带时区的本地时间
local_time = datetime.now()
print(f"本地时间 (无时区): {local_time}")
print(f"本地时间 (格式化): {local_time.strftime('%Y年%m月%d日 %H:%M:%S')}")

# 带中国时区的时间
tz = pytz.timezone('Asia/Shanghai')
shanghai_time = datetime.now(tz)
print(f"上海时间 (有时区): {shanghai_time}")
print(f"上海时间 (格式化): {shanghai_time.strftime('%Y年%m月%d日 %H:%M:%S')}")

# 测试3: 验证配置模块
print("\n" + "=" * 60)
print("测试3: 配置模块导入")
print("=" * 60)

try:
    from src.config.settings import Config
    print("✓ 配置模块导入成功")
except Exception as e:
    print(f"✗ 配置模块导入失败: {e}")

# 测试4: 验证 Agent 模块
print("\n" + "=" * 60)
print("测试4: Agent 模块导入")
print("=" * 60)

try:
    from src.agent.base import BaseAgent
    print("✓ Agent 模块导入成功")
except Exception as e:
    print(f"✗ Agent 模块导入失败: {e}")

print("\n" + "=" * 60)
print("✅ 所有测试完成")
print("=" * 60)
print("\n预期结果:")
print("- 系统时区应该是 Asia/Shanghai")
print("- 上海时间应该显示正确的当前日期（2026年1月19日）")
print("- 所有模块应该导入成功")
