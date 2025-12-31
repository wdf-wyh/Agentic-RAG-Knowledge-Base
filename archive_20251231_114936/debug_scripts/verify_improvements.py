#!/usr/bin/env python
"""快速验证 Ollama 解析改进"""
import sys
import time

def verify_ollama_improvements():
    """验证 app_api.py 中的改进"""
    
    print("🔍 验证 Ollama 解析改进")
    print("=" * 60)
    
    try:
        # 读取 app_api.py
        with open('app_api.py', 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 检查项
        checks = [
            ("改进的提示词", "你是一个专业的信息提取助手"),
            ("详细的日志", "✅ 成功从 JSON 解析"),
            ("降级策略1", "尝试从文本中提取 JSON"),
            ("降级策略2", "未找到 JSON 结构，使用原始文本"),
            ("空值保护", "最终答案为空，使用默认拒绝消息"),
            ("最终长度检查", "最终答案长度:"),
        ]
        
        print("\n✅ 检查改进项:\n")
        all_ok = True
        for name, keyword in checks:
            if keyword in content:
                print(f"✅ {name}")
            else:
                print(f"❌ {name} - 未找到: '{keyword}'")
                all_ok = False
        
        print("\n" + "=" * 60)
        
        if all_ok:
            print("✅ 所有改进都已实施!")
            print("\n📋 下一步:")
            print("1. 启动 API: python app_api.py")
            print("2. 运行测试: python test_ollama_parsing.py")
            print("3. 分析日志: python analyze_parsing.py")
            return True
        else:
            print("❌ 部分改进未找到，请检查代码")
            return False
            
    except Exception as e:
        print(f"❌ 验证失败: {e}")
        return False

if __name__ == '__main__':
    success = verify_ollama_improvements()
    sys.exit(0 if success else 1)
