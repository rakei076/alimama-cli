"""分析方法：通用的随包发（references/*.md），每家公司自己的要求（月报、周报、汇报格式……）放在整台电脑共用的「分析要求」文件夹。

为什么分开：公司的要求写进 references/ 或 SKILL.md，就和工具本身搅在一起——工具一升级就被冲掉，公司改过的文件也没法
干净地把代码修改交回来。公司的要求放在工具文件夹外面（paths.machine_root()/分析要求/），升级、换新版本、装了几份工具
（几个 AI 助手各带一份）都读同一份，工具永远不碰它。

主题怎么切（两边一样）：带「## 通用规则」的是工作流合集，除「目录」「通用规则」外每个二级标题是一个主题（「模块 N：」前缀去掉），
通用规则每个主题都带上；别的文件整份是一个主题，名字取一级标题。公司要求里和通用方法同名的主题，以公司的为准，
通用的那份改名「<主题>（通用版）」留着备查。
"""
from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

from .paths import machine_root

PACKAGE = Path(__file__).resolve().parents[2] / "references"   # 打包时从 delivery/<产品>/references 拷来
COMPANY_DIRNAME = "分析要求"
NOTE_FILE = "使用说明.txt"
NOTE = """这里放你们公司自己的分析要求，AI 助手做报告前会先看这里，有就照它做，没有才用工具自带的通用分析方法。

怎么写：
- 一份要求一个 .md 文件，文件名随意，比如「月报要求.md」「周报要求.md」。
- 第一行写「# 主题名」，比如「# 月报」。AI 按这个名字找；和工具自带的主题同名时，以这里的为准。
- 下面照你们的要求写：要看哪些数据、怎么算、报告分几部分、每部分写什么、交给谁、什么格式。写得越具体，AI 做得越像。
- 一个文件里想放好几个主题：加一个「## 通用规则」小节（每个主题都会带上），其余每个「## 标题」就是一个主题。

这个文件夹在工具文件夹外面：工具升级、换新版本都不会动它；电脑上装了几份工具（几个 AI 助手各带一份）也都读这一份。
"""


def company_folder(create: bool = False) -> Path:
    folder = machine_root() / COMPANY_DIRNAME
    if create:
        folder.mkdir(parents=True, exist_ok=True)
        note = folder / NOTE_FILE
        if not note.exists():
            note.write_text(NOTE, encoding="utf-8")
    return folder


def _split(folder: Path) -> list[tuple[str, str, tuple[str, str]]]:
    """(主题名, 所在文件的标题, (通用规则, 正文))"""
    found: list[tuple[str, str, tuple[str, str]]] = []
    if not folder.is_dir():
        return found
    for md in sorted(folder.glob("*.md")):
        text = md.read_text(encoding="utf-8", errors="replace")
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
    return found


def _named(found: list[tuple[str, str, tuple[str, str]]]) -> dict[str, tuple[str, str]]:
    """几份文件里主题重名时（比如两个工具都有「周复盘」），名字后面带上所在文件的标题。"""
    seen = Counter(name for name, _, _ in found)
    return {(f"{name}（{title}）" if seen[name] > 1 else name): body for name, title, body in found}


def company_topics() -> dict[str, tuple[str, str]]:
    return _named(_split(company_folder()))


def package_topics() -> dict[str, tuple[str, str]]:
    return _named(_split(PACKAGE))


def topics() -> dict[str, tuple[str, str]]:
    """全部主题：公司的在前；通用的和公司的同名时，通用的改叫「<主题>（通用版）」。"""
    mine = company_topics()
    out = dict(mine)
    for name, body in package_topics().items():
        out[f"{name}（通用版）" if name in mine else name] = body
    return out


def find(topic: str) -> tuple[str, tuple[str, str]] | None:
    """按名字找主题：先找完全一样的，再找名字里包含它的（公司的优先）。"""
    all_topics = topics()
    if topic in all_topics:
        return topic, all_topics[topic]
    hit = next((k for k in all_topics if topic in k), None)
    return (hit, all_topics[hit]) if hit else None


def listing() -> str:
    mine, ours = company_topics(), package_topics()
    lines = []
    if mine:
        lines.append("本公司的分析要求（优先照这些做）：")
        lines += [f"· {t}" for t in mine]
    lines.append("通用分析方法：" if ours else "这个包没有附带通用分析方法。")
    lines += [f"· {t}（通用版）" if t in mine else f"· {t}" for t in ours]
    lines.append(f"\n本公司的要求放在：{company_folder()}"
                 + ("" if mine else "（还没有。公司有自己的月报、周报等要求时，写成 .md 放进去，里面的「使用说明.txt」写了格式）"))
    return "\n".join(lines)


def show(topic: str) -> str:
    hit = find(topic)
    if not hit:
        raise KeyError(topic)
    name, body = hit
    origin = "本公司的分析要求" if name in company_topics() else "通用分析方法"
    return f"【{origin}：{name}】\n\n" + "\n\n".join(x for x in body if x)


def main(argv: list[str]) -> int:
    """tb guide：看分析方法。tb guide <主题> 看全文；tb guide --where 打开（没有就建好）本公司要求的文件夹位置。"""
    import argparse
    import sys
    ap = argparse.ArgumentParser(prog="tb guide", description="分析方法：通用的随包发，本公司的要求放在整台电脑共用的文件夹，优先照它。")
    ap.add_argument("topic", nargs="?", help="主题名（写一部分也行）；不写就列出全部")
    ap.add_argument("--where", action="store_true", help="打印本公司要求的文件夹位置（没有就建好，并放一份使用说明）")
    args = ap.parse_args(argv)
    if args.where:
        print(company_folder(create=True))
        return 0
    if not args.topic:
        print(listing())
        return 0
    try:
        print(show(args.topic))
    except KeyError:
        print(f"❌ 没有这个主题：{args.topic}\n\n{listing()}", file=sys.stderr)
        return 1
    return 0
