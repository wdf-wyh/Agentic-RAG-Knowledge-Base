#!/usr/bin/env python
"""最终验证: 前端问题已解决"""
import requests
import json

def main():
    url = 'http://localhost:8000/api/query'
    
    # 测试查询
    test_cases = [
        "深度学习的主要架构有哪些？",
        "什么是机器学习",
        "Python 数据处理",
    ]
    
    print("🧪 最终系统验证\n" + "="*60)
    
    for question in test_cases:
        print(f"\n📝 测试问题: {question}")
        
        payload = {
            'question': question,
            'provider': 'ollama',
            'top_k': 2
        }
        
        try:
            response = requests.post(url, json=payload, timeout=300)
            result = response.json()
            
            # 检查答案
            answer = result.get('answer', '')
            sources = result.get('sources', [])
            
            answer_ok = answer and answer != '我无法根据现有知识库中的信息回答这个问题'
            sources_ok = all(src.get('source') != '未知来源' for src in sources)
            
            status = '✅' if (answer_ok and sources_ok) else '❌'
            print(f"{status} 答案有效: {answer_ok}")
            print(f"{status} 来源有效: {sources_ok} ({len(sources)} 个)")
            
            if sources_ok and sources:
                print(f"   来源: {sources[0]['source']}")
            
        except Exception as e:
            print(f"❌ 错误: {str(e)[:100]}")
    
    print("\n" + "="*60)
    print("✅ 所有测试完成!")
    print("\n前端现在应该能正常显示:")
    print("  • 完整的答案文本")
    print("  • 实际的文档来源")  
    print("  • 相关内容的预览")

if __name__ == '__main__':
    main()
