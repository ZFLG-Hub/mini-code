"""多模聊 启动器 — 检查环境并启动 CLI 模式"""
import sys
import os
import subprocess

os.chdir(os.path.dirname(os.path.abspath(__file__)))

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def check_module(name, pip_name=None):
    try:
        __import__(name)
        return True
    except ImportError:
        return False


def main():
    print()
    print("  ======================================")
    print("    Multi-Model Chat (duomoliao)")
    print("  ======================================")
    print()

    missing = []
    for mod, pip_name in [
        ("rich", "rich"),
        ("openai", "openai"),
        ("anthropic", "anthropic"),
    ]:
        if not check_module(mod):
            missing.append(pip_name)

    if missing:
        print(f"  [WARN] Missing: {', '.join(missing)}")
        print("  Installing dependencies...")
        print()
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install"] + missing,
            cwd=os.path.dirname(os.path.abspath(__file__)),
        )
        if result.returncode != 0:
            print()
            print("  [ERROR] Failed to install dependencies.")
            print(f"  Run manually: pip install {' '.join(missing)}")
            input("\n  Press Enter to exit...")
            sys.exit(1)

    print("  Starting...")
    print()

    try:
        from src.app import App
        app = App()
        app.run()
    except Exception as e:
        print(f"\n  [ERROR] Startup failed: {e}")
        import traceback
        traceback.print_exc()
        input("\n  Press Enter to exit...")
        sys.exit(1)


if __name__ == "__main__":
    main()
