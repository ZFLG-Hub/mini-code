#!/usr/bin/env python3
import sys
import os

# 强制 UTF-8 输出，解决 Windows 控制台 GBK 乱码问题
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.app import App


def main():
    try:
        app = App()
        app.run()
    except Exception as e:
        print(f"\n程序启动失败: {e}")
        input("\n按 Enter 键退出...")
        sys.exit(1)


if __name__ == "__main__":
    main()
