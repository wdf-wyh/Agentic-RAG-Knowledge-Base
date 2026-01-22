#!/usr/bin/env python3
"""
日志查看工具 - 实时查看系统日志

用法:
    python view_logs.py              # 查看所有日志
    python view_logs.py backend      # 查看后端日志
    python view_logs.py follow       # 实时跟踪日志（类似 tail -f）
"""
import os
import sys
import time
import subprocess
from pathlib import Path


def view_logs(log_type="all", follow=False):
    """查看日志文件"""
    log_dir = Path(__file__).parent / "logs"
    
    if not log_dir.exists():
        print(f"❌ 日志目录不存在: {log_dir}")
        return
    
    # 确定日志文件
    if log_type == "backend":
        log_file = log_dir / "backend.log"
    elif log_type == "frontend":
        log_file = log_dir / "frontend.log"
    elif log_type == "all":
        # 显示两个日志文件
        log_file = None
    else:
        print(f"❌ 未知的日志类型: {log_type}")
        return
    
    if log_type == "all":
        # 显示后端日志
        backend_log = log_dir / "backend.log"
        frontend_log = log_dir / "frontend.log"
        
        print(f"\n{'='*80}")
        print(f"📋 后端日志: {backend_log}")
        print(f"{'='*80}")
        
        if backend_log.exists():
            lines = backend_log.read_text(encoding='utf-8').split('\n')
            # 显示最后100行
            for line in lines[-100:]:
                if line.strip():
                    print(line)
        else:
            print(f"⚠️ 后端日志文件为空或不存在")
        
        print(f"\n{'='*80}")
        print(f"📋 前端日志: {frontend_log}")
        print(f"{'='*80}")
        
        if frontend_log.exists():
            lines = frontend_log.read_text(encoding='utf-8').split('\n')
            # 显示最后100行
            for line in lines[-100:]:
                if line.strip():
                    print(line)
        else:
            print(f"⚠️ 前端日志文件为空或不存在")
    else:
        if not log_file.exists():
            print(f"⚠️ 日志文件不存在或为空: {log_file}")
            return
        
        print(f"\n{'='*80}")
        print(f"📋 日志文件: {log_file}")
        print(f"{'='*80}\n")
        
        if follow:
            # 实时跟踪模式（类似 tail -f）
            print("🔄 实时跟踪日志（按 Ctrl+C 停止）...\n")
            
            # 获取文件当前大小，从末尾开始读取
            last_size = log_file.stat().st_size
            
            while True:
                try:
                    current_size = log_file.stat().st_size
                    
                    if current_size > last_size:
                        # 文件有新内容
                        with open(log_file, 'r', encoding='utf-8') as f:
                            f.seek(last_size)
                            new_content = f.read()
                            if new_content:
                                print(new_content, end='', flush=True)
                        last_size = current_size
                    
                    time.sleep(0.1)
                except KeyboardInterrupt:
                    print("\n\n✓ 停止跟踪")
                    break
                except Exception as e:
                    print(f"❌ 错误: {e}")
                    break
        else:
            # 一次性显示日志
            content = log_file.read_text(encoding='utf-8')
            if content.strip():
                print(content)
            else:
                print("⚠️ 日志文件为空")


def print_help():
    """打印帮助信息"""
    print("""
📚 RAG 知识库日志查看工具
===========================

用法:
  python view_logs.py              # 查看所有日志（最后100行）
  python view_logs.py backend      # 查看后端日志
  python view_logs.py frontend     # 查看前端日志
  python view_logs.py follow       # 实时跟踪后端日志（tail -f 模式）

日志位置:
  📄 后端日志: logs/backend.log
  📄 前端日志: logs/frontend.log

🔍 查看完整日志:
  cat logs/backend.log
  tail -f logs/backend.log         # 实时跟踪

清空日志:
  echo "" > logs/backend.log
  """)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        arg = sys.argv[1]
        if arg in ["--help", "-h", "help"]:
            print_help()
        elif arg == "follow":
            view_logs("backend", follow=True)
        elif arg in ["backend", "frontend"]:
            view_logs(arg)
        else:
            print(f"❌ 未知参数: {arg}")
            print_help()
    else:
        view_logs("all")
