import sys
import signal

from rich.console import Console
from rich.markdown import Markdown
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from . import config as cfg
from . import history
from .backends.openai import OpenAIBackend
from .backends.claude import ClaudeBackend
from .backends.gemini import GeminiBackend
from .backends.deepseek import DeepSeekBackend

console = Console()

BACKEND_CLASSES = {
    "openai": OpenAIBackend,
    "claude": ClaudeBackend,
    "gemini": GeminiBackend,
    "deepseek": DeepSeekBackend,
}


class App:
    def __init__(self):
        self.config = cfg.load_config()
        self.session = None
        self.backend = None
        self.current_model_key = None
        self._interrupted = False

    def run(self):
        self._print_banner()
        self.session = history.create_session(cfg.get_default_model(self.config))
        self._switch_model(cfg.get_default_model(self.config))

        while True:
            try:
                model_display = self.current_model_key or "none"
                prompt_text = Text.from_markup(f"\n[bold cyan]{model_display}[/] > ")
                user_input = console.input(prompt_text).strip()
            except (KeyboardInterrupt, EOFError):
                console.print("\n[dim]再见![/]")
                break

            if not user_input:
                continue

            if user_input.startswith("/"):
                self._handle_command(user_input)
                continue

            self._chat(user_input)

    def _chat(self, user_input):
        self.session["messages"].append({"role": "user", "content": user_input})

        console.print()
        try:
            self._interrupted = False
            original_handler = signal.signal(signal.SIGINT, self._sigint_handler)

            messages = self._prepare_messages(self.session["messages"])

            collected = []
            with Live(Text(""), console=console, refresh_per_second=20, transient=False) as live:
                try:
                    for chunk in self.backend.chat(messages, stream=True):
                        if self._interrupted:
                            break
                        collected.append(chunk)
                        md = Markdown("".join(collected))
                        live.update(md)
                finally:
                    signal.signal(signal.SIGINT, original_handler)

            full_response = "".join(collected)
            if self._interrupted:
                full_response += "\n\n[已中断]"
            console.print()

        except Exception as e:
            full_response = f"[错误] {e}"
            console.print(f"[red]{full_response}[/]")

        self.session["messages"].append({"role": "assistant", "content": full_response})
        history.save_session(self.session)

    def _sigint_handler(self, signum, frame):
        self._interrupted = True

    def _handle_command(self, raw):
        parts = raw.split(maxsplit=1)
        cmd = parts[0].lower()
        arg = parts[1] if len(parts) > 1 else ""

        handlers = {
            "/model": self._cmd_model,
            "/models": self._cmd_models,
            "/key": self._cmd_key,
            "/history": self._cmd_history,
            "/load": self._cmd_load,
            "/new": self._cmd_new,
            "/save": self._cmd_save,
            "/help": self._cmd_help,
            "/exit": self._cmd_exit,
            "/quit": self._cmd_exit,
        }

        handler = handlers.get(cmd)
        if handler:
            handler(arg)
        else:
            console.print(f"[red]未知命令: {cmd}[/] 输入 /help 查看帮助")

    def _cmd_model(self, arg):
        if not arg:
            self._cmd_models("")
            console.print(f"\n当前模型: [bold cyan]{self.current_model_key}[/]")
            console.print("用法: /model <模型名>  例如 /model claude/sonnet-4-6")
            return

        if arg not in self.config.get("models", {}):
            console.print(f"[red]未知模型: {arg}[/]")
            console.print("可用模型:")
            self._cmd_models("")
            return

        self._switch_model(arg)
        console.print(f"[green]已切换到: {arg}[/]")

    def _cmd_key(self, arg):
        """设置或查看 API Key: /key openai sk-xxx"""
        if not arg:
            keys = self.config.get("api_keys", {})
            if keys:
                console.print("[bold]已配置的 API Key:[/]")
                for name in keys:
                    masked = keys[name][:8] + "..." if len(keys[name]) > 8 else "***"
                    console.print(f"  {name}: {masked}")
            else:
                console.print("[dim]未配置任何 API Key[/]")
            console.print("用法: /key <后端名> <api-key>  例如 /key openai sk-xxx")
            console.print("后端名: openai, claude, gemini")
            return

        parts = arg.split(maxsplit=1)
        backend_name = parts[0].lower()
        if backend_name not in ("openai", "claude", "gemini", "deepseek"):
            console.print("[red]后端名必须是: openai, claude, gemini, deepseek[/]")
            return

        if len(parts) < 2:
            existing = self.config.get("api_keys", {}).get(backend_name)
            if existing:
                console.print(f"{backend_name}: {existing[:8]}...")
            else:
                console.print(f"[dim]{backend_name}: 未设置[/]")
            return

        cfg.set_api_key(self.config, backend_name, parts[1])
        console.print(f"[green]已保存 {backend_name} 的 API Key[/]")
        self._switch_model(self.current_model_key)

    def _cmd_models(self, _):
        table = Table(title="可用模型")
        table.add_column("名称", style="cyan")
        table.add_column("后端", style="green")
        table.add_column("实际模型", style="dim")

        for key, info in self.config.get("models", {}).items():
            marker = " *" if key == self.current_model_key else ""
            table.add_row(key + marker, info["backend"], info["model"])

        console.print(table)

    def _cmd_history(self, _):
        sessions = history.list_sessions()
        if not sessions:
            console.print("[dim]暂无历史会话[/]")
            return

        table = Table(title="历史会话")
        table.add_column("ID", style="cyan")
        table.add_column("模型", style="green")
        table.add_column("消息数")
        table.add_column("预览")
        table.add_column("更新时间")

        for s in sessions:
            marker = " *" if self.session and s["id"] == self.session["session_id"] else ""
            table.add_row(
                s["id"] + marker,
                s["model"],
                str(s["messages"]),
                s["preview"][:40],
                s["updated"][:19],
            )

        console.print(table)
        console.print("[dim]使用 /load <id> 加载会话，* 表示当前会话[/]")

    def _cmd_load(self, arg):
        if not arg:
            console.print("[red]用法: /load <会话ID>[/]")
            return

        session = history.load_session(arg)
        if not session:
            console.print(f"[red]会话不存在: {arg}[/]")
            return

        history.save_session(self.session)
        self.session = session
        self._switch_model(session.get("model", cfg.get_default_model(self.config)))
        console.print(f"[green]已加载会话 {arg} ({len(session['messages'])} 条消息)[/]")

    def _cmd_new(self, _):
        history.save_session(self.session)
        self.session = history.create_session(self.current_model_key)
        console.print(f"[green]新会话已创建: {self.session['session_id']}[/]")

    def _cmd_save(self, _):
        history.save_session(self.session)
        console.print(f"[green]会话已保存: {self.session['session_id']}[/]")

    def _cmd_help(self, _):
        help_text = """
[bold]命令列表[/]

/model [name]  切换模型（不带参数列出可用模型）
/models        列出所有支持的模型
/key [后端 key]  设置或查看 API Key（/key openai sk-xxx）
/history       查看历史会话列表
/load <id>     加载历史会话
/new           开始新会话
/save          手动保存当前会话
/help          显示此帮助
/exit          退出

[bold]快速开始[/]
  /key deepseek sk-xxx           设置 DeepSeek Key
  /key openai sk-your-key-here   设置 OpenAI Key
  /key claude sk-ant-...         设置 Claude Key
  /key gemini ...                设置 Gemini Key
  /model deepseek/v4             切换到 DeepSeek V4
  /model openai/gpt-4o           切换到 GPT-4o
"""
        console.print(help_text)

    def _cmd_exit(self, _):
        history.save_session(self.session)
        console.print("[dim]再见![/]")
        sys.exit(0)

    def _prepare_messages(self, messages):
        max_history = self.config.get("max_history_messages", 20)
        if len(messages) <= max_history:
            return messages

        system_msgs = [m for m in messages if m["role"] == "system"]
        other_msgs = [m for m in messages if m["role"] != "system"]
        trimmed = other_msgs[-max_history:]
        return system_msgs + trimmed

    def _switch_model(self, model_key):
        info = cfg.get_model_info(self.config, model_key)
        if not info:
            console.print(f"[red]模型配置不存在: {model_key}[/]")
            return

        api_key = cfg.get_api_key(self.config, info["backend"])
        if not api_key:
            console.print(
                f"[yellow]警告: 未设置 {info['backend']} 的 API Key，使用 /key 设置[/]"
            )

        max_tokens = self.config.get("max_output_tokens", 4096)
        backend_cls = BACKEND_CLASSES[info["backend"]]
        self.backend = backend_cls(info["model"], api_key, max_tokens)
        self.current_model_key = model_key

    def _print_banner(self):
        banner = """
+--------------------------------------+
|       多模聊 -- 多模型聊天工具        |
+--------------------------------------+
|  支持: OpenAI/Claude/Gemini/DeepSeek |
|  输入 /help 查看命令                 |
+--------------------------------------+
"""
        console.print(banner, style="bold cyan")
