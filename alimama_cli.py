#!/usr/bin/env python3
"""alimama-cli — 万相台 AI 无界 (one.alimama.com) 只读数据查询 CLI

参考 sycm-cli 的纯本地认证模型：
- browser_cookie3 从 Chrome 直接读 alimama.com cookies（无需重新登录）
- curl_cffi 伪 TLS 指纹直调万相台 onebp API
- 不开新 profile、不接管浏览器、不需要用户手动操作

接口完全反向工程自万相台 onebp 客户端 JS（onebp/merge bundle）。
所有命令均为只读 — 永远不调用 add/update/delete/save/close 类接口。

子命令：
    doctor               检查 cookie 与登录态
    api <path>           通用 POST 接口探测
    account-balance      账户余额（无日期）
    activity-list        活动列表（日期范围）
    campaign-list        计划列表（日期范围）
    keyword-effect       关键词效果（日期范围）
    daily-report         日维度花费汇总
"""
from __future__ import annotations

import argparse
import json
import os
import random
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import browser_cookie3
from curl_cffi import requests

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/148.0.0.0 Safari/537.36"
)

API_HOST = "https://one.alimama.com"
REFERER_DETAIL_PAGE = "https://one.alimama.com/index.html"

RISK_KEYWORDS = ("滑块", "验证码", "操作过于频繁", "请重新登录", "异常请求", "风控", "需要登录")

# 安全护栏
MIN_DELAY_SEC = 1.8
MAX_DELAY_SEC = 3.5
MAX_REQUESTS_PER_RUN = 80
MAX_CONSECUTIVE_FAILS = 2


class RiskTriggered(RuntimeError):
    pass


def _sleep_humanlike() -> None:
    time.sleep(random.uniform(MIN_DELAY_SEC, MAX_DELAY_SEC))


def load_alimama_cookies() -> dict[str, str]:
    """从 Chrome 读取 alimama.com 域所有 cookies。

    万相台和淘宝共享阿里通用登录 cookie，但鉴权域是 alimama.com。
    常见登录态 cookie：cookie2 / _tb_token_ / unb / cna / sgcookie。
    """
    jar = browser_cookie3.chrome(domain_name="alimama.com")
    cookies: dict[str, str] = {}
    # 优先级：one.alimama.com > .alimama.com > 其他子域
    # 通过两遍写入：先非 one，再 one，让 one 覆盖
    for c in jar:
        if c.domain and ("alimama.com" in c.domain or "taobao.com" in c.domain):
            if "one.alimama.com" not in c.domain:
                cookies[c.name] = c.value
    for c in jar:
        if c.domain and "one.alimama.com" in c.domain:
            cookies[c.name] = c.value
    if "cookie2" not in cookies and "unb" not in cookies:
        raise RuntimeError(
            "未找到阿里妈妈登录态。请在 Chrome 里打开并登录 https://one.alimama.com 后重试。"
        )
    return cookies


def _check_risk(text: str) -> None:
    for kw in RISK_KEYWORDS:
        if kw in text:
            raise RiskTriggered(f"响应含 '{kw}'，立即停止")


_request_count = 0
_consecutive_fails = 0
_csrf_id: str | None = None  # 由 ensure_csrf() 注入


def ensure_csrf(cookies: dict[str, str]) -> str:
    """首次调用：POST /member/checkAccess.json 拿到 csrfId 并缓存。

    万相台所有数据接口要求 URL 带 ?csrfId=xxx，否则 "bizLogin csrf检查未通过"。
    csrfId 在本进程内只取一次。
    """
    global _csrf_id
    if _csrf_id:
        return _csrf_id
    data = _api_call(
        "/member/checkAccess.json",
        body={"bizCode": "universalBP"},
        method="POST",
        cookies=cookies,
        skip_csrf=True,
    )
    csrf = (data.get("data") or {}).get("accessInfo", {}).get("csrfId")
    if not csrf:
        raise RuntimeError(f"无法从 checkAccess 拿到 csrfId: {json.dumps(data, ensure_ascii=False)[:200]}")
    _csrf_id = csrf
    return csrf


def _api_call(
    path: str,
    body: dict[str, Any] | None = None,
    method: str = "POST",
    cookies: dict[str, str] | None = None,
    referer: str | None = None,
    biz_code: str = "universalBP",
    skip_csrf: bool = False,
) -> dict[str, Any]:
    """对万相台 API 做一次 POST/GET，带安全护栏。

    path 必须以 `/` 开头（拼到 https://one.alimama.com 后）。
    POST 默认 application/json，body 自动 JSON 序列化。
    所有请求 URL 自动带 ?bizCode=universalBP（onebp 全局必填参数）。
    """
    global _request_count, _consecutive_fails
    if _request_count >= MAX_REQUESTS_PER_RUN:
        raise RuntimeError(f"单次运行已达 {MAX_REQUESTS_PER_RUN} 次请求上限，自动停止")

    hour = datetime.now().hour
    if 1 <= hour < 6 and not os.environ.get("ALIMAMA_BYPASS_CURFEW"):
        raise RuntimeError(
            f"夜间禁跑时段 (1:00–6:00)，当前 {hour} 点。"
            f"如需强制运行：ALIMAMA_BYPASS_CURFEW=1 ..."
        )

    if not path.startswith("/"):
        path = "/" + path
    # 自动注入 bizCode（除非 path 已含）
    sep = "&" if "?" in path else "?"
    if "bizCode=" not in path:
        path = f"{path}{sep}bizCode={biz_code}"
        sep = "&"
    # 自动注入 csrfId（万相台 onebp 全局 CSRF 校验）
    if not skip_csrf and "csrfId=" not in path:
        csrf = ensure_csrf(cookies or {})
        path = f"{path}{sep}csrfId={csrf}"
    url = f"{API_HOST}{path}"

    headers = {
        "User-Agent": USER_AGENT,
        "Referer": referer or REFERER_DETAIL_PAGE,
        "Origin": API_HOST,
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "zh-CN,zh;q=0.9,ja;q=0.8,en;q=0.7",
    }
    if cookies and "XSRF-TOKEN" in cookies:
        headers["X-XSRF-TOKEN"] = cookies["XSRF-TOKEN"]
    # 浏览器 same-origin 标识 — 让服务端识别为浏览器同源 XHR
    headers["Sec-Fetch-Site"] = "same-origin"
    headers["Sec-Fetch-Mode"] = "cors"
    headers["Sec-Fetch-Dest"] = "empty"
    headers["X-Requested-With"] = "XMLHttpRequest"

    try:
        if method.upper() == "POST":
            headers["Content-Type"] = "application/json"
            resp = requests.post(
                url, json=body or {}, cookies=cookies, headers=headers,
                impersonate="chrome120", timeout=15,
            )
        else:
            resp = requests.get(
                url, params=body or {}, cookies=cookies, headers=headers,
                impersonate="chrome120", timeout=15,
            )
        _request_count += 1
        if resp.status_code != 200:
            _consecutive_fails += 1
            if _consecutive_fails >= MAX_CONSECUTIVE_FAILS:
                raise RuntimeError(
                    f"连续 {MAX_CONSECUTIVE_FAILS} 次失败 (最后 HTTP {resp.status_code})，自动停止"
                )
            raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:300]}")
        _check_risk(resp.text)
        _consecutive_fails = 0
        try:
            return resp.json()
        except Exception:
            raise RuntimeError(f"响应非 JSON: {resp.text[:300]}")
    except RiskTriggered:
        raise
    except Exception as e:
        _consecutive_fails += 1
        if _consecutive_fails >= MAX_CONSECUTIVE_FAILS:
            raise RuntimeError(f"连续 {MAX_CONSECUTIVE_FAILS} 次失败，自动停止，最后错误: {e}") from e
        raise


# ---------- 高频只读预设注册表 ----------
#
# 每个 preset 对应万相台的一个标准查询接口（已确认为 POST 只读）。

LIST_PRESETS: dict[str, dict[str, Any]] = {
    "account-balance": {
        "path": "/account/checkRealBalance.json",
        "method": "POST",
        "body": {},
        "desc": "账户余额（实时）",
        "show": [],
        "needs_date": False,
    },
    "activity-list": {
        "path": "/activity/getActivityList.json",
        "method": "POST",
        "body": {},
        "desc": "营销活动列表",
        "show": ["activityId", "activityName", "startDate", "endDate", "status"],
        "needs_date": False,
    },
    "campaign-list": {
        "path": "/report/campaign/findPage.json",
        "method": "POST",
        "body": {"pageNo": 1, "pageSize": 10},
        "desc": "推广计划列表（已确认可用，返回 campaignId / strategySceneName）",
        "show": ["campaignId", "strategySceneName", "campaignName", "productLineId"],
        "needs_date": True,
    },
    "keyword-effect": {
        "path": "/report/adgroup/findPage.json",
        "method": "POST",
        "body": {"pageNo": 1, "pageSize": 10},
        "desc": "推广单元列表（未实测，字段名以实际响应为准）",
        "show": ["adgroupId", "adgroupName", "campaignId"],
        "needs_date": True,
    },
    "daily-report": {
        "path": "/report/chargeSum.json",
        "method": "POST",
        "body": {},
        "desc": "日维度花费汇总（未实测，可能需要额外参数）",
        "show": ["date", "chargeFee", "impression", "click"],
        "needs_date": True,
    },
}


def _build_preset_body(preset: dict[str, Any], start_date: str | None, end_date: str | None,
                       page_no: int, page_size: int) -> dict[str, Any]:
    body = dict(preset.get("body") or {})
    if preset.get("needs_date") and start_date:
        sd = start_date.replace("-", "")
        ed = (end_date or start_date).replace("-", "")
        body.setdefault("startDate", sd)
        body.setdefault("endDate", ed)
        body.setdefault("dateType", "day")
    body["pageNo"] = page_no
    body["pageSize"] = page_size
    return body


def fetch_preset(preset_name: str, *, start_date: str | None = None, end_date: str | None = None,
                  page_no: int = 1, page_size: int = 10,
                  cookies: dict[str, str] | None = None) -> dict[str, Any]:
    preset = LIST_PRESETS[preset_name]
    cookies = cookies or load_alimama_cookies()
    body = _build_preset_body(preset, start_date, end_date, page_no, page_size)
    return _api_call(preset["path"], body, method=preset["method"], cookies=cookies)


# ---------- 命令 ----------

def cmd_doctor(args: argparse.Namespace) -> None:
    print("== alimama-cli doctor ==")
    try:
        cookies = load_alimama_cookies()
        print(f"✓ 读到 {len(cookies)} 个 alimama/taobao 域 cookie")
        for k in ("cookie2", "unb", "_tb_token_", "cna", "sgcookie", "_l_g_", "t", "sg"):
            if k in cookies:
                v = cookies[k]
                print(f"✓ {k} = {v[:24]}{'...' if len(v) > 24 else ''}")
        print(f"\nAPI host: {API_HOST}")
        print(f"Referer:  {REFERER_DETAIL_PAGE}")
    except Exception as e:
        print(f"✗ {e}")
        sys.exit(1)


def cmd_api(args: argparse.Namespace) -> None:
    """通用 API 探测命令：alimama-cli api <path> [--method POST] [--body '{"k":"v"}']"""
    cookies = load_alimama_cookies()
    body: dict[str, Any] = {}
    if args.body:
        body = json.loads(args.body)
    for kv in args.param or []:
        if "=" not in kv:
            continue
        k, v = kv.split("=", 1)
        body[k] = v
    data = _api_call(args.path, body, method=args.method, cookies=cookies, referer=args.referer)
    print(json.dumps(data, ensure_ascii=False, indent=2))


def cmd_preset(args: argparse.Namespace) -> None:
    preset = LIST_PRESETS[args.preset_name]
    data = fetch_preset(
        args.preset_name,
        start_date=getattr(args, "date", None),
        end_date=getattr(args, "end_date", None),
        page_no=getattr(args, "page", 1),
        page_size=getattr(args, "limit", 10),
    )
    if args.out:
        Path(args.out).write_text(json.dumps(data, ensure_ascii=False, indent=2))
        print(f"已写入 {args.out}", file=sys.stderr)
        return
    if args.raw:
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return

    print(f"# {preset['desc']}")
    if preset.get("needs_date") and getattr(args, "date", None):
        end = args.end_date or args.date
        print(f"# {args.date}{' ~ ' + end if end != args.date else ''}")

    d = data.get("data", data) if isinstance(data, dict) else {}
    if not isinstance(d, dict):
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return

    rows = None
    for key in ("dataList", "dataSource", "list", "rows", "items", "result"):
        if isinstance(d.get(key), list):
            rows = d[key]
            print(f"# 共 {d.get('totalCount', d.get('count', d.get('total', '?')))} 条，本页 {len(rows)}")
            break

    if rows is None:
        print(json.dumps(d, ensure_ascii=False, indent=2))
        return

    print()
    show = preset["show"]
    if not show:
        for i, r in enumerate(rows, 1):
            print(f"[{i:2}] {json.dumps(r, ensure_ascii=False)}")
        return
    for i, r in enumerate(rows, 1):
        if not isinstance(r, dict):
            print(f"[{i:2}] {r}")
            continue
        vals = " | ".join(f"{k}={r.get(k, '?')}" for k in show)
        print(f"[{i:2}] {vals}")


# ---------- 高频专用命令：花费汇总 ----------
#
# 接口：POST /report/chargeSum.json
# 已验证参数（来自浏览器 DevTools 实际请求）：
#   queryDomains: ["scene"]           — 维度（"scene"=营销场景, "campaign"=计划, "adgroup"=单元, "keyword"=关键词）
#   queryFieldIn: [指标 ID 列表]       — 见 CHARGE_METRICS 字典
#   startTime/endTime: YYYY-MM-DD     — 注意是带 - 的格式，不是 YYYYMMDD
#   splitType: "day"                  — 时间拆分
#   rptType: "account"                — 报表类型
#   bizCode: "universalBP"            — 业务码
#   source: "baseReport"              — 基础报表
#   effectEqual: 15                   — 转化窗口天数（15/7/1）

CHARGE_METRICS = {
    "adPv": "展现量",
    "click": "点击量",
    "charge": "花费(元)",
    "ctr": "点击率",
    "ecpc": "平均点击花费",
    "alipayInshopAmt": "成交金额",
    "alipayInshopNum": "成交笔数",
    "cvr": "转化率",
}

CHARGE_SCENE_FIELDS = {
    "searchCharge": "关键词推广",
    "displayCharge": "人群推广",
    "contentSceneCharge": "内容场景",
    "siteSceneCharge": "站点场景",
    "activitySceneCharge": "活动场景",
    "agencySceneCharge": "代运营场景",
    "crowdSceneCharge": "人群场景",
    "shopSceneCharge": "店铺场景",
    "itemSceneCharge": "商品场景",
}


def fetch_charge_summary(*, start_date: str, end_date: str,
                          effect_window: int = 15,
                          cookies: dict[str, str] | None = None) -> dict[str, Any]:
    """拉取「营销场景报表」总览：每个推广场景花了多少钱。"""
    cookies = cookies or load_alimama_cookies()
    body = {
        "fromRealTime": False,
        "source": "baseReport",
        "byPage": True,
        "byPageWithoutCount": False,
        "totalTag": True,
        "needCountAccelerate": True,
        "bizCode": "universalBP",
        "effectEqual": effect_window,
        "startTime": start_date,
        "endTime": end_date,
        "havingList": [],
        "pageSize": 20,
        "queryDomains": ["scene"],
        "queryFieldIn": list(CHARGE_METRICS.keys()),
        "rptType": "account",
        "splitType": "day",
        "unifyType": "zhai",
    }
    return _api_call("/report/chargeSum.json", body, method="POST", cookies=cookies)


def cmd_charge_summary(args: argparse.Namespace) -> None:
    end = args.end_date or args.date
    data = fetch_charge_summary(start_date=args.date, end_date=end, effect_window=args.window)
    if args.raw or args.out:
        out = json.dumps(data, ensure_ascii=False, indent=2)
        if args.out:
            Path(args.out).write_text(out)
            print(f"已写入 {args.out}", file=sys.stderr)
        else:
            print(out)
        return

    d = data.get("data") or {}
    if not d:
        print("（响应为空，可能时间窗口无投放）")
        return

    total = d.get("totalCharge", 0) or 0
    print(f"# 万相台 推广花费汇总")
    print(f"# 区间: {args.date} ~ {end}（{args.window} 天转化窗口）\n")

    # 各场景花费排序
    scenes = []
    for k, label in CHARGE_SCENE_FIELDS.items():
        v = d.get(k) or 0
        if v > 0 or k in ("searchCharge", "displayCharge"):
            scenes.append((label, v))
    scenes.sort(key=lambda x: -x[1])

    print(f"{'场景':<15} {'花费(元)':>12} {'占比':>8}")
    print("-" * 40)
    for label, v in scenes:
        pct = f"{v/total*100:.1f}%" if total else "—"
        print(f"{label:<15} {v:>12,.2f} {pct:>8}")
    print("-" * 40)
    print(f"{'总花费':<15} {total:>12,.2f} {'100.0%':>8}")


# ---------- main ----------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="alimama-cli", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = p.add_subparsers(dest="cmd", required=True)

    d = sp.add_parser("doctor", help="检查 cookie / 登录态")
    d.set_defaults(func=cmd_doctor)

    yesterday = (date.today() - timedelta(days=1)).isoformat()

    ap = sp.add_parser("api", help="通用接口探测：alimama-cli api /xxx.json [--body JSON] [-p k=v]")
    ap.add_argument("path", help='接口路径，如 "/account/checkRealBalance.json"')
    ap.add_argument("--method", default="POST", choices=["POST", "GET"])
    ap.add_argument("--body", help="POST body (JSON 字符串)")
    ap.add_argument("--param", "-p", action="append", help="附加 body 字段 key=value，可重复")
    ap.add_argument("--referer", help="自定义 Referer 头")
    ap.set_defaults(func=cmd_api)

    cs = sp.add_parser("charge-summary", help="花费汇总：各营销场景花了多少（关键词推广/人群推广/...）")
    cs.add_argument("--date", default=yesterday, help=f"开始日期 YYYY-MM-DD (默认 {yesterday})")
    cs.add_argument("--end-date", help="结束日期 (默认 = --date)")
    cs.add_argument("--window", type=int, default=15, choices=[1, 7, 15],
                    help="转化窗口天数 1/7/15 (默认 15)")
    cs.add_argument("--raw", action="store_true", help="输出原始 JSON")
    cs.add_argument("--out", help="输出到文件")
    cs.set_defaults(func=cmd_charge_summary)

    for name, preset in LIST_PRESETS.items():
        sub = sp.add_parser(name, help=preset["desc"])
        if preset.get("needs_date"):
            sub.add_argument("--date", default=yesterday, help=f"YYYY-MM-DD (默认昨天 {yesterday})")
            sub.add_argument("--end-date", help="结束日期 (默认 = --date)")
        sub.add_argument("--limit", type=int, default=10, help="拉多少条 (默认 10)")
        sub.add_argument("--page", type=int, default=1)
        sub.add_argument("--raw", action="store_true", help="输出原始 JSON")
        sub.add_argument("--out", help="输出到文件")
        sub.set_defaults(func=cmd_preset, preset_name=name)

    return p


def main() -> None:
    args = build_parser().parse_args()
    try:
        args.func(args)
    except RiskTriggered as e:
        print(f"\n⚠️  风险信号触发，已停止：{e}", file=sys.stderr)
        sys.exit(2)
    except KeyboardInterrupt:
        print("\n中断", file=sys.stderr)
        sys.exit(130)


if __name__ == "__main__":
    main()
