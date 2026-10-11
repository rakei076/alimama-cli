"""tb mcp：把这个包里的平台做成一个本地 MCP 服务（stdio），交给 AI 客户端（Claude Code、Codex、Cursor……）用。

薄壳：每次调用工具都在子进程里跑现成的命令行（python -m tb <平台> <命令> …），把输出交回去。
- 取数、护栏、报错都在命令行里，这里不重写；
- 命令行往 stdout 打字，放在子进程里不会弄坏 MCP 的协议通道；
- 每次调用自己开桥、用完释放，几个 AI 客户端同时开着也不抢端口；
- MCP 服务由 AI 客户端直接拉起，不在它的命令沙箱里（Codex 的沙箱会拦本机端口），它的子进程也一样。
"""
from __future__ import annotations

import asyncio
import os
import re
import sys
import time
from collections import Counter
from pathlib import Path

from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations

from .core import modules

ROOT = Path(__file__).resolve().parent.parent          # 包根目录：tb/ 的上一层
GUIDES = ROOT / "references"                           # 各包的分析方法（打包时从 delivery/<产品>/references 拷来）
TIMEOUT = float(os.environ.get("TB_MCP_TIMEOUT") or 540)   # 一条命令最长跑多久（秒）；Codex 的工具超时由 tb mcp install 调到 600
INLINE = 20000                                          # 输出超过这么多字就存成文件，只交回开头和文件位置
HEAD = 6000
# MCP 里不让跑的：任何带 --execute 的写操作（修改店铺的命令都要 --execute 才真执行）
DENY = {"mcp": "不能在 MCP 里再起 MCP。"}

INSTRUCTIONS = ("店铺数据（只读）：借用户浏览器里已登录的后台读取店铺数据，不能修改店铺。"
                "先用 doctor 检查环境；不确定有哪些数据，用 commands 看命令目录；用 run 运行命令；"
                "做整份报告（日检、周复盘、单品诊断、测款、退货等）前，先用 guide 看分析方法。")


def instructions() -> str:
    """还没打开的工具也告诉 AI：用户的问题正好要用到时，推荐打开（征得同意后用 modules 工具打开，没装的会自动下载）。"""
    off = modules.disabled()
    if not off:
        return INSTRUCTIONS
    return (INSTRUCTIONS + "同一套工具里还有这些用户没打开：" + "；".join(modules.ABOUT[n] for n in off)
            + "。用户的问题正好要用到其中某个时，告诉他可以打开（没装的会自动下载），征得同意后用 modules 工具打开"
              "（打开后要重开 AI 助手才能用）；和用户的问题无关时不要提。")


def available() -> list[str]:
    """用户打开了的模块。"""
    return modules.enabled()


def display(name: str) -> str:
    return modules.display(name)


def server_key() -> str:
    """写进 AI 客户端配置的名字：只能用英文（Claude Code 的工具名要求 ^[a-zA-Z0-9_-]+$）。
    每个包都带着全部工具，名字固定，打开新模块不会变出第二个服务。"""
    return "shopdata"


def pick(platform: str) -> str:
    names = available()
    if not platform:
        if len(names) == 1:
            return names[0]
        raise ToolError(f"这个服务里有几个平台，请指定 platform：{'、'.join(names)}")
    if platform not in names:
        if platform in modules.disabled():
            raise ToolError(modules.not_enabled_hint(platform) + "先问用户要不要打开，同意后用 modules 工具打开。")
        raise ToolError(f"没有这个平台：{platform}。已打开的：{'、'.join(names)}")
    return platform


def state_root() -> Path:
    root = os.environ.get("TB_STATE_ROOT")
    if root:
        return Path(root).expanduser()
    if os.name == "nt":
        return Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local") / "taobao-cli"
    return Path.home() / ".taobao-cli"


async def execute(argv: list[str], timeout: float = TIMEOUT) -> tuple[int, str, str]:
    """在子进程里跑命令行。超时或调用被取消时把子进程杀掉，不留后台进程。"""
    env = {**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}
    proc = await asyncio.create_subprocess_exec(*argv, cwd=ROOT, env=env, stdin=asyncio.subprocess.DEVNULL,
                                                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    try:
        out, err = await asyncio.wait_for(proc.communicate(), timeout)
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()
        return 124, "", f"命令跑了 {timeout:.0f} 秒还没完，已停止。可以缩小日期范围或分几次运行。"
    except asyncio.CancelledError:
        proc.kill()
        raise
    return proc.returncode, out.decode("utf-8", "replace"), err.decode("utf-8", "replace")


def tb_argv(*args: str) -> list[str]:
    return [sys.executable, "-m", "tb", *args]


def deliver(title: str, code: int, out: str, err: str, *, slug: str) -> str:
    """拼出交回给 AI 的文字；太长就整份存文件，只交回开头。退出码不是 0 时按出错交回（客户端会标成失败）。"""
    text = out.strip()
    if err.strip():
        text += ("\n\n" if text else "") + "【过程信息】\n" + err.strip()
    if len(text) > INLINE:
        folder = state_root() / "mcp-output"
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f"{time.strftime('%Y%m%d-%H%M%S')}-{re.sub(r'[^0-9A-Za-z._-]+', '_', slug)[:60]}.txt"
        path.write_text(text, encoding="utf-8")
        text = text[:HEAD] + f"\n\n……输出共 {len(text)} 字，太长，只给了开头。完整内容在：{path}"
    text = f"$ {title}\n" + (text or "（没有输出）")
    if code != 0:
        raise ToolError(text + f"\n\n（退出码 {code}）")
    return text


def guides() -> dict[str, tuple[str, str]]:
    """分析方法（各包 references/*.md）。带「## 通用规则」的是工作流合集：除「目录」「通用规则」外每个二级标题是一个主题
    （「模块 N：」前缀去掉），通用规则每个主题都带上；别的文件整份是一个主题，用它的一级标题当名字。
    几个工具合在一个包里时主题可能重名（生意参谋和 1688 都有「周复盘」），重名的后面带上所在文件的标题。"""
    found: list[tuple[str, str, tuple[str, str]]] = []
    for md in sorted(GUIDES.glob("*.md")):
        text = md.read_text(encoding="utf-8")
        h1 = re.search(r"(?m)^# (.+)$", text)
        title = h1.group(1).strip() if h1 else md.stem
        parts = re.split(r"(?m)^## ", text)[1:]   # 第一段是「# 大标题」
        common = next(("## " + p.strip() for p in parts if p.startswith("通用规则")), "")
        if not common:
            found.append((title, title, ("", text.strip())))
            continue
        for p in parts:
            head = p.split("\n", 1)[0].strip()
            if head not in ("目录", "通用规则"):
                found.append((re.sub(r"^模块\s*\d+\s*[：:]\s*", "", head), title, (common, "## " + p.strip())))
    seen = Counter(name for name, _, _ in found)
    return {(f"{name}（{title}）" if seen[name] > 1 else name): body for name, title, body in found}


def build() -> MCPServer:
    # 工具里给 AI 看的错误一律用 ToolError：别的异常 SDK 只回「Error executing tool」，原因会被藏起来
    names = available()
    label = "、".join(display(n) for n in names)
    mcp = MCPServer(name=server_key(), title=f"店铺数据（{label}）", instructions=instructions())
    ro = ToolAnnotations(read_only_hint=True, destructive_hint=False, open_world_hint=True)
    plat_doc = f"平台：{'、'.join(f'{n}（{display(n)}）' for n in names)}" + ("，只有一个时可以不填。" if len(names) == 1 else "。")

    @mcp.tool(description="检查能不能取数：浏览器插件装没装、连不连得上、平台登录状态。出问题时先跑它，按提示处理。" + plat_doc,
              annotations=ro)
    async def doctor(platform: str = "") -> str:
        p = pick(platform)
        code, out, err = await execute(tb_argv(p, "doctor"))
        pc, pout, perr = await execute(tb_argv("plugin"), timeout=30)
        return deliver(f"tb {p} doctor", code, out + "\n\n【插件安装情况】\n" + pout.strip(), err + perr, slug=f"{p}-doctor")

    @mcp.tool(description="命令目录：不带 command 时列出这个平台能读的全部数据（每条命令一句说明）；"
                          "带上 command 时给出这条命令的参数说明。运行命令前不确定参数就先看这里。" + plat_doc,
              annotations=ro)
    async def commands(platform: str = "", command: str = "") -> str:
        p = pick(platform)
        argv = [p, command, "--help"] if command else [p, "--help"]
        code, out, err = await execute(tb_argv(*argv), timeout=60)
        return deliver("tb " + " ".join(argv), code, out, err, slug=f"{p}-help")

    @mcp.tool(description="运行一条只读命令，例如 command=\"doctor\"，或 command=\"refund-list\", args=[\"--days\", \"7\"]。"
                          "参数照 commands 给出的写，一个参数一项。输出太长时会存成文件，返回开头和文件位置；"
                          "要整份明细时可以加 --out 文件名。修改店铺的操作（如带 --execute 的）不能在这里运行。" + plat_doc,
              annotations=ro)
    async def run(command: str, args: list[str] | None = None, platform: str = "") -> str:
        p, args = pick(platform), list(args or [])
        if command in DENY:
            raise ToolError(DENY[command])
        if "--execute" in args:
            raise ToolError("带 --execute 的是修改店铺的操作，不能通过 AI 运行。请在终端里自己确认后运行。")
        code, out, err = await execute(tb_argv(p, command, *args))
        return deliver(" ".join(["tb", p, command, *args]), code, out, err, slug=f"{p}-{command}")

    @mcp.tool(description="切换账号（账号存在用户浏览器的取数桥插件里）：action=list 列出存过的账号和现在登录的是谁；"
                          "action=use 换成存过的某个账号（name 填 list 里的名字）；action=save 把浏览器里现在登录的账号存下来（name 是起的名字）；"
                          "action=check 查存下的账号还在不在（不切换，不填 name 就全部查）。"
                          "淘宝/天猫（含千牛、生意参谋、达摩盘、万相台）一组，1688 一组，1688 的把 is_1688 设为 true。"
                          "用户说「用某某店 / 某某账号的数据」时，先 list 找到对应的名字，再 use，然后再取数。"
                          "账号过期时不能替用户登录：请用户在浏览器里点插件图标重新登录。",
              annotations=ToolAnnotations(read_only_hint=False, destructive_hint=False, idempotent_hint=True, open_world_hint=False))
    async def account(action: str = "list", name: str = "", is_1688: bool = False) -> str:
        if action not in ("list", "use", "save", "check"):
            raise ToolError("action 只能是 list、use、save 或 check。")
        if action == "use" and not name:
            raise ToolError("换账号要给 name（先用 action=list 看有哪些名字）。")
        argv = ["account", action] + ([name] if name else []) + (["--1688"] if is_1688 and action != "list" else [])
        code, out, err = await execute(tb_argv(*argv), timeout=180)
        return deliver("tb " + " ".join(argv), code, out, err, slug=f"account-{action}")

    @mcp.tool(name="modules", description="工具模块：action=list 列出全部工具、哪些打开了；action=enable 打开 names 里的工具，没装的会自动下载（要先征得用户同意）。"
                          "打开后要用户完全退出再重开 AI 助手才能用到新工具。",
              annotations=ToolAnnotations(read_only_hint=False, destructive_hint=False, idempotent_hint=True, open_world_hint=False))
    async def modules_tool(action: str = "list", names: list[str] | None = None) -> str:
        if action not in ("list", "enable"):
            raise ToolError("action 只能是 list 或 enable（关闭请用户自己在终端运行 tb modules disable）。")
        argv = ["modules", action, *(names or [])]
        if action == "enable" and not names:
            raise ToolError("要打开哪些工具？names 填模块名，如 [\"alimama\"]。")
        code, out, err = await execute(tb_argv(*argv), timeout=60)
        return deliver("tb " + " ".join(argv), code, out, err, slug=f"modules-{action}")

    @mcp.tool(description="分析方法：做整份报告（日检、周复盘、单品诊断、测款、退货归因等）前先看。不带 topic 列出全部主题；"
                          "带 topic 给出这个主题的取数步骤、计算方法和报告格式。",
              annotations=ToolAnnotations(read_only_hint=True, destructive_hint=False, open_world_hint=False))
    async def guide(topic: str = "") -> str:
        topics = guides()
        if not topics:
            return "这个包没有附带分析方法。"
        if not topic:
            return "分析方法主题：\n" + "\n".join(f"· {t}" for t in topics)
        hit = topics.get(topic) or next((v for k, v in topics.items() if topic in k), None)
        if not hit:
            raise ToolError(f"没有这个主题：{topic}。可用：{'、'.join(topics)}")
        return "\n\n".join(x for x in hit if x)

    return mcp


def main(argv: list[str]) -> int:
    """tb mcp：起 stdio 服务。tb mcp --check：只检查依赖和工具能不能加载（配置客户端前预热用），不起服务。
    tb mcp install / uninstall：写进或移出 AI 客户端的配置（见 mcp_install）。"""
    if argv[:1] in (["install"], ["uninstall"]):
        from . import mcp_install
        return mcp_install.main(argv)
    if argv[:1] == ["--check"]:
        server = build()
        print(f"MCP 服务可以启动：{server_key()}（{'、'.join(display(n) for n in available())}），分析方法 {len(guides())} 个主题。")
        return 0
    build().run()
    return 0
