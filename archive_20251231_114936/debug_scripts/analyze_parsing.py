#!/usr/bin/env python
"""分析 API 日志中的 Ollama 解析问题"""
import re
import sys
from collections import defaultdict

def analyze_logs(log_file='/tmp/api.log'):
    """分析日志文件中的 Ollama 解析情况"""
    
    try:
        with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
    except FileNotFoundError:
        print(f"❌ 找不到日志文件: {log_file}")
        return
    
    print("📊 Ollama 解析日志分析")
    print("=" * 70)
    
    # 统计各种解析结果
    stats = defaultdict(int)
    parsing_details = []
    
    for line in lines:
        if '[DEBUG /api/query]' in line:
            # 提取调试信息
            if '成功从 JSON 解析' in line:
                stats['success_direct'] += 1
                parsing_details.append(('✅ 直接JSON解析', line.strip()))
            elif '从文本中提取 JSON 成功' in line:
                stats['success_extract'] += 1
                parsing_details.append(('✅ 提取JSON成功', line.strip()))
            elif 'JSON 格式但无' in line:
                stats['json_no_answer'] += 1
                parsing_details.append(('⚠️ JSON无answer字段', line.strip()))
            elif 'JSON 解析失败' in line:
                stats['json_parse_fail'] += 1
                parsing_details.append(('⚠️ JSON解析失败', line.strip()))
            elif 'JSON 提取也失败' in line:
                stats['json_extract_fail'] += 1
                parsing_details.append(('⚠️ JSON提取失败', line.strip()))
            elif '未找到 JSON 结构' in line:
                stats['no_json_structure'] += 1
                parsing_details.append(('⚠️ 未找到JSON结构', line.strip()))
            elif '最终答案为空' in line:
                stats['empty_answer'] += 1
                parsing_details.append(('❌ 答案为空', line.strip()))
            elif '最终答案长度' in line:
                stats['final_answer_ok'] += 1
                # 提取答案长度
                match = re.search(r'(\d+)\s*字符', line)
                if match:
                    length = int(match.group(1))
                    parsing_details.append(('✅ 最终答案', f"长度: {length} 字符"))
            elif '解析异常' in line:
                stats['parse_exception'] += 1
                parsing_details.append(('❌ 解析异常', line.strip()))
            elif '使用原始文本' in line:
                stats['use_raw_text'] += 1
                parsing_details.append(('⚠️ 使用原始文本', line.strip()))
    
    # 输出统计信息
    print("\n📈 解析统计:\n")
    print(f"✅ 直接 JSON 解析: {stats['success_direct']} 次")
    print(f"✅ 提取 JSON 成功: {stats['success_extract']} 次")
    print(f"✅ 最终答案有效: {stats['final_answer_ok']} 次")
    print(f"\n⚠️ JSON 无 answer 字段: {stats['json_no_answer']} 次")
    print(f"⚠️ JSON 解析失败: {stats['json_parse_fail']} 次")
    print(f"⚠️ JSON 提取失败: {stats['json_extract_fail']} 次")
    print(f"⚠️ 未找到 JSON 结构: {stats['no_json_structure']} 次")
    print(f"⚠️ 使用原始文本: {stats['use_raw_text']} 次")
    print(f"\n❌ 答案为空: {stats['empty_answer']} 次")
    print(f"❌ 解析异常: {stats['parse_exception']} 次")
    
    # 计算成功率
    total_parses = sum([
        stats['success_direct'],
        stats['success_extract'],
        stats['json_no_answer'],
        stats['json_parse_fail'],
        stats['json_extract_fail'],
        stats['no_json_structure'],
        stats['empty_answer'],
        stats['parse_exception'],
        stats['use_raw_text']
    ])
    
    successes = stats['success_direct'] + stats['success_extract'] + stats['final_answer_ok']
    
    if total_parses > 0:
        success_rate = 100 * successes / total_parses
        print(f"\n{'='*70}")
        print(f"总解析次数: {total_parses}")
        print(f"成功次数: {successes}")
        print(f"成功率: {success_rate:.1f}%")
        print(f"{'='*70}")
    
    # 显示最近的解析细节
    print("\n📋 最近的解析细节 (最后20条):\n")
    for status, detail in parsing_details[-20:]:
        # 简化输出
        if '[DEBUG' in detail:
            msg = detail.split('[DEBUG /api/query]')[-1].strip()
            print(f"{status}: {msg[:80]}")
        else:
            print(f"{status}: {detail[:80]}")

if __name__ == '__main__':
    analyze_logs()
