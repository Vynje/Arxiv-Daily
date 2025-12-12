#!/usr/bin/env python3
"""
启动 ARXIV-DAILY GUI 应用程序的入口点。
"""
import sys
import os

# 确保当前目录在路径中
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from gui_main import main

if __name__ == "__main__":
    main()