#!/usr/bin/env python3
"""alimama-cli — 万相台 AI 无界 (one.alimama.com) 只读数据查询 CLI

参考 sycm-cli 的纯本地认证模型：
- browser_cookie3 从 Chrome 直接读 alimama.com cookies（无需重新登录）
- curl_cffi 伪 TLS 指纹直调万相台 onebp API
- 不开新 profile、不接管浏览器、不需要用户手动操作

接口完全反向工程自万相台 onebp 客户端 JS（onebp/merge bundle）。
查询类命令全部只读；唯一写操作 promo-off（按宝贝ID关停在投单元）默认 dry-run，
必须 --execute 才执行，且只关单元(pause)，不调价/不删除/不新建。

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
MAX_CONSECUTIVE_FAILS = 2
# 单请求超时（秒）。万相台 onebpSearch 等接口服务端响应偏慢，默认 30，可用 env 覆盖。
REQUEST_TIMEOUT = int(os.environ.get("ALIMAMA_TIMEOUT", "30"))
# 请求数策略（建议性，不硬停）：
#   达到 SOFT_WARN_AT 在 stderr 打一次温和提醒；不停止运行。
#   如果要兜底（脚本跑飞），设环境变量 ALIMAMA_REQUEST_LIMIT=数字。
REQUEST_SOFT_WARN_AT = 200


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

    # 软警告：达到阈值在 stderr 提醒一次，不停止
    if _request_count == REQUEST_SOFT_WARN_AT:
        print(
            f"⚠️  已发出 {REQUEST_SOFT_WARN_AT} 次请求 — 大批量正常，但建议留意：风控通常按"
            f"\"短时高频\"判断而不是\"总量\"，每个请求间隔 1.8~3.5 秒已经足够。继续运行。",
            file=sys.stderr,
        )
    # 可选硬上限（环境变量），默认无
    hard_limit_env = os.environ.get("ALIMAMA_REQUEST_LIMIT")
    if hard_limit_env and hard_limit_env.isdigit():
        hard_limit = int(hard_limit_env)
        if _request_count >= hard_limit:
            raise RuntimeError(
                f"达到自定义硬上限 ALIMAMA_REQUEST_LIMIT={hard_limit}，停止。"
                f"如要继续：unset ALIMAMA_REQUEST_LIMIT 或调大它。"
            )

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
                impersonate="chrome120", timeout=REQUEST_TIMEOUT,
            )
        else:
            resp = requests.get(
                url, params=body or {}, cookies=cookies, headers=headers,
                impersonate="chrome120", timeout=REQUEST_TIMEOUT,
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


# ---------- 通用报表接口 /report/query.json ----------
#
# 从 HAR 实测发现：万相台 11 个侧栏报表里有 10 个走同一个 /report/query.json，
# 仅靠 rptType + queryDomains 两个参数切换。
#
# 完整 17 个指标（queryFieldIn）：
REPORT_METRICS = {
    "charge": "花费(元)",
    "click": "点击量",
    "ctr": "点击率",
    "ecpc": "平均点击花费",
    "alipayInshopAmt": "成交金额",
    "alipayInshopNum": "成交笔数",
    "alipayDirNum": "直接成交单数",
    "cartInshopNum": "加购数",
    "cvr": "转化率",
    "roi": "投产比",
    "cartRate": "加购率",
    "cartCost": "加购成本",
    "colCartCost": "收藏加购成本",
    "itemColCartCost": "商品收藏加购成本",
    "inshopPotentialUvRate": "潜客率",
    "newAlipayInshopUvRate": "新成交客户率",
}

# rptType 对应的中文名 + 默认 queryDomains（明细列表用）
REPORT_TYPES = {
    "campaign":        {"name": "计划报表",    "list_domain": "campaign"},
    "adgroup":         {"name": "单元报表",    "list_domain": "adgroup"},
    "bidword":         {"name": "关键词报表",  "list_domain": "word"},
    "crowd":           {"name": "人群报表",    "list_domain": "crowd"},
    "item_promotion":  {"name": "商品报表",    "list_domain": "promotion"},
    "creative":        {"name": "创意报表",    "list_domain": "creative"},
    "area":            {"name": "地域报表",    "list_domain": "province"},
    "coupon":          {"name": "权益报表",    "list_domain": "adgroup"},
    "real_time":       {"name": "实时报表",    "list_domain": "date"},
    "other_promotion": {"name": "其他推广报表","list_domain": "promotion"},
}


def fetch_report(*, rpt_type: str, dimension: str,
                  start_date: str, end_date: str,
                  page_no: int = 1, page_size: int = 20,
                  effect_window: int = 15,
                  cookies: dict[str, str] | None = None) -> dict[str, Any]:
    """通用报表查询。

    rpt_type:   campaign / adgroup / bidword / crowd / item_promotion / creative / area / coupon / real_time
    dimension:  account (总览) / date (按天) / campaign / adgroup / word / crowd / promotion / province / creative
    """
    cookies = cookies or load_alimama_cookies()
    is_realtime = rpt_type == "real_time"
    body = {
        "bizCode": "universalBP",
        "fromRealTime": is_realtime,
        "source": "baseReport",
        "from": "pcBaseReport",
        "byPage": True,
        "byPageWithoutCount": False,
        "totalTag": True,
        "needCountAccelerate": True,
        "rptType": rpt_type,
        "queryDomains": [dimension],
        "queryFieldIn": list(REPORT_METRICS.keys()),
        "startTime": start_date,
        "endTime": end_date,
        "splitType": "hour" if is_realtime else "day",
        "effectEqual": effect_window,
        "havingList": [],
        "pageSize": page_size,
        "pageNo": page_no,
        "unifyType": "zhai",
    }
    return _api_call("/report/query.json", body, method="POST", cookies=cookies)


def cmd_report(args: argparse.Namespace) -> None:
    rpt_info = REPORT_TYPES[args.rpt_type]
    dim = args.dim or rpt_info["list_domain"]
    end = args.end_date or args.date
    data = fetch_report(
        rpt_type=args.rpt_type, dimension=dim,
        start_date=args.date, end_date=end,
        page_no=args.page, page_size=args.limit,
        effect_window=args.window,
    )
    if args.raw or args.out:
        out = json.dumps(data, ensure_ascii=False, indent=2)
        if args.out:
            Path(args.out).write_text(out)
            print(f"已写入 {args.out}", file=sys.stderr)
        else:
            print(out)
        return

    d = data.get("data") or {}
    raw_total = d.get("totalData")
    # totalData 可能是 list 或 dict，规范化
    if isinstance(raw_total, list):
        total_data = raw_total[0] if raw_total else {}
    elif isinstance(raw_total, dict):
        total_data = raw_total
    else:
        total_data = {}
    rows = d.get("list") or []
    count = d.get("count", 0)

    print(f"# 万相台 - {rpt_info['name']}（维度: {dim}）")
    print(f"# {args.date} ~ {end}  转化窗口 {args.window} 天  共 {count} 条，本页 {len(rows)}")

    # 总计
    if total_data:
        charge = float(total_data.get("charge") or 0)
        amt = float(total_data.get("alipayInshopAmt") or 0)
        roi = float(total_data.get("roi") or 0)
        click = total_data.get("click") or 0
        print(f"\n  总计: 花费 ¥{charge:,.2f} | 成交 ¥{amt:,.2f} | ROI {roi:.2f} | 点击 {click:,}")

    if not rows:
        print("\n（无明细数据）")
        return

    # 明细按 charge 降序
    rows_sorted = sorted(rows, key=lambda r: -float(r.get("charge") or 0))
    print()
    # 不同报表的 name 字段不一样，按 rptType 优先级查找
    name_candidates = {
        "campaign":        ["promotionName", "campaignName", "name"],
        "adgroup":         ["adgroupName", "promotionName", "name"],
        "bidword":         ["originalWord", "word", "bidword", "name"],
        "crowd":           ["crowdName", "targetCrowd", "promotionName", "name"],
        "item_promotion":  ["itemTitle", "promotionName", "name"],
        "creative":        ["creativeTitle", "creativeName", "promotionName", "name"],
        "area":            ["provinceName", "province", "areaName", "name"],
        "coupon":          ["couponName", "promotionName", "name"],
        "real_time":       ["dateStr", "date", "hour", "promotionName"],
        "other_promotion": ["promotionName", "name"],
    }
    name_field = None
    for cand in name_candidates.get(args.rpt_type, ["promotionName", "name"]):
        if rows_sorted[0].get(cand):
            name_field = cand
            break

    print(f"{'#':<4} {'名称':<28} {'花费':>9} {'成交':>10} {'ROI':>6} {'点击':>6} {'CTR':>6}")
    print("-" * 80)
    for i, r in enumerate(rows_sorted[:args.limit], 1):
        name = str(r.get(name_field, '?'))[:26] if name_field else '?'
        charge = float(r.get("charge") or 0)
        amt = float(r.get("alipayInshopAmt") or 0)
        roi = float(r.get("roi") or 0)
        click = r.get("click") or 0
        ctr = float(r.get("ctr") or 0)
        print(f"{i:<4} {name:<28} {charge:>9,.2f} {amt:>10,.2f} {roi:>6.2f} {click:>6} {ctr*100:>5.1f}%")


# ---------- "推广"模块（不是"报表"！）—— 当前在投的计划列表 ----------
#
# 接口：POST /campaign/horizontal/findPage.json
# 区分参数：bizCode (映射到不同推广玩法)
# 不需要日期 — 这是"当前在投"快照，不是历史

PROMO_BIZ_CODES = {
    "wholesite": ("onebpSite",    "货品全站推广"),
    "keyword":   ("onebpSearch",  "关键词推广"),
    "crowd":     ("onebpDisplay", "人群推广"),
}

# 场景大盘汇总（scene-summary）：/report/query.json + splitType=sum，按 URL ?bizCode= 区分场景。
# 请求全字段（HAR 实测有效），展示挑核心。展现量字段 = adPv。
SCENE_SUMMARY_REQUEST_FIELDS = [
    "click", "charge", "ctr", "ecpc", "ecpm", "cvr", "roi",
    "adPv", "alipayInshopNum", "alipayDirNum", "alipayInshopAmt",
    "cartInshopNum", "cartRate", "cartCost", "colCartCost",
    "clickUv", "clickUvCost", "shopVisitUv", "shopVisitUvRate",
    "firstPurchaseUv", "newAlipayInshopUvRate",
]
SCENE_SUMMARY_SHOW = [
    ("adPv", "展现量", "{:,.0f}"),
    ("click", "点击量", "{:,.0f}"),
    ("ctr", "点击率", "{:.2%}"),
    ("ecpc", "平均点击花费", "¥{:.2f}"),
    ("ecpm", "千次展现成本", "¥{:.2f}"),
    ("charge", "花费", "¥{:,.2f}"),
    ("alipayInshopAmt", "成交金额", "¥{:,.2f}"),
    ("alipayInshopNum", "成交笔数", "{:,.0f}"),
    ("roi", "投产比(ROI)", "{:.2f}"),
    ("cvr", "转化率", "{:.2%}"),
    ("cartInshopNum", "加购数", "{:,.0f}"),
    ("cartRate", "加购率", "{:.2%}"),
    ("clickUv", "点击人数", "{:,.0f}"),
]


def _promo_item(row: dict[str, Any]) -> tuple[str | None, str | None]:
    """从一个计划行里取出 (宝贝ID, 商品标题)。

    货品全站/关键词/人群推广都是"一计划推一个商品"，宝贝 ID 落在
    adgroupList[0].material.materialId（lastAdgroup.material 兜底）。
    """
    for ag_field in ("adgroupList", "lastAdgroup"):
        ag = row.get(ag_field)
        if isinstance(ag, dict):
            ag = [ag]
        if isinstance(ag, list) and ag:
            mat = (ag[0] or {}).get("material") or {}
            mid = mat.get("materialId")
            if mid:
                title = mat.get("title") or mat.get("itemTitle")
                return str(mid), title
    return None, None


def _promo_all_items(row: dict[str, Any]) -> list[dict[str, Any]]:
    """列出一个计划下的所有商品（单元）及其开关状态。

    每个单元 (adgroup) = 一个商品：
      material.materialId → 宝贝 ID
      material.title      → 标题（商品被删除/下架时取不到）
      onlineStatus        → 开关：1=投放中 / 0=未投放
    """
    out: list[dict[str, Any]] = []
    for ag in (row.get("adgroupList") or []):
        ag = ag or {}
        mat = ag.get("material") or {}
        mid = mat.get("materialId")
        if not mid:
            continue
        online = ag.get("onlineStatus")
        out.append({
            "itemId": str(mid),
            "title": mat.get("title") or mat.get("itemTitle"),
            "onlineStatus": online,
            "on": online == 1,
            "adgroupId": ag.get("adgroupId"),
        })
    return out


def find_promo_campaign(campaign_id: int, *, biz_code: str | None = None,
                        cookies: dict[str, str] | None = None) -> tuple[dict[str, Any] | None, str | None]:
    """按计划 ID 在推广列表里定位某个计划（带单元）。

    biz_code 给定则只搜该玩法，否则依次搜 wholesite/keyword/crowd。
    返回 (计划行, 命中的 bizCode)；找不到返回 (None, None)。
    """
    cookies = cookies or load_alimama_cookies()
    biz_codes = [biz_code] if biz_code else [b for b, _ in PROMO_BIZ_CODES.values()]
    for bc in biz_codes:
        offset, page_size, total = 0, 100, None
        while True:
            # 只为定位计划拿头部信息，不需要单元（adgroup_required=False 更轻，避免关键词推广超时）
            page = fetch_promo_campaigns(biz_code=bc, page_size=page_size, offset=offset,
                                         status_list=["start", "pause", "end"],
                                         adgroup_required=False, cookies=cookies)
            pd = page.get("data") or {}
            rows = pd.get("list") or []
            total = pd.get("count", 0) if total is None else total
            for r in rows:
                if r.get("campaignId") == campaign_id:
                    return r, bc
            offset += page_size
            if not rows or offset >= (total or 0):
                break
    return None, None


def fetch_all_promo_campaigns(biz_code: str, *, status_list: list[str] | None = None,
                              cookies: dict[str, str] | None = None) -> list[dict[str, Any]]:
    """翻完所有页，返回某玩法下的全部计划行（带单元）。"""
    cookies = cookies or load_alimama_cookies()
    rows_all: list[dict[str, Any]] = []
    # 每页 20 而非 100：关键词推广单计划可含数百单元，adgroupRequired 响应体大，
    # 大 pageSize 会把多条重计划塞进一个响应导致 15s 超时。小页更稳。
    offset, page_size, total = 0, 20, None
    while True:
        page = fetch_promo_campaigns(biz_code=biz_code, page_size=page_size, offset=offset,
                                     status_list=status_list, cookies=cookies)
        pd = page.get("data") or {}
        rows = pd.get("list") or []
        total = pd.get("count", 0) if total is None else total
        rows_all.extend(rows)
        offset += page_size
        if not rows or offset >= (total or 0):
            break
    return rows_all


# 接口：POST /adgroup/horizontal/findPage.json —— 单元级（扁平），三种玩法都直接带 material.materialId
# 比"计划级 findPage + adgroupRequired"更可靠：关键词推广在计划级里 material 恒为 null，
# 但单元级接口能正常返回宝贝 ID；且行扁平不嵌套，单元再多也不会超时。
def fetch_all_adgroups(biz_code: str, *, status_list: list[str] | None = None,
                       campaign_id: int | None = None,
                       cookies: dict[str, str] | None = None) -> list[dict[str, Any]]:
    """翻完所有页，返回某玩法下的全部单元行（每行一个商品广告位）。"""
    cookies = cookies or load_alimama_cookies()
    rows_all: list[dict[str, Any]] = []
    offset, page_size, total = 0, 50, None
    while True:
        body: dict[str, Any] = {
            "bizCode": biz_code,
            "offset": offset,
            "pageSize": page_size,
            "statusList": status_list or ["start", "pause"],
        }
        if campaign_id is not None:
            body["campaignId"] = campaign_id
        page = _api_call(f"/adgroup/horizontal/findPage.json?bizCode={biz_code}",
                         body, method="POST", cookies=cookies)
        pd = page.get("data") or {}
        rows = pd.get("list") or []
        total = pd.get("count", 0) if total is None else total
        rows_all.extend(rows)
        offset += page_size
        if not rows or offset >= (total or 0):
            break
    return rows_all


def _adgroup_unit(ag: dict[str, Any]) -> dict[str, Any]:
    """从单元级行里抽出统一结构。"""
    mat = ag.get("material") or {}
    online = ag.get("onlineStatus")
    return {
        "itemId": str(mat.get("materialId")) if mat.get("materialId") else None,
        "title": mat.get("title") or mat.get("itemTitle") or ag.get("adgroupName"),
        "on": online == 1,
        "onlineStatus": online,
        "campaignId": ag.get("campaignId"),
        "campaignName": ag.get("campaignName"),
        "adgroupId": ag.get("adgroupId"),
    }


# ============================ 写操作（需确认后执行） ============================
# 接口：POST /adgroup/updatePart.json?csrfId=<X>&bizCode=<biz>
#   body: {"bizCode","adgroupList":[{"campaignId","adgroupId","displayStatus":"pause"|"start"}],"csrfId"}
#   pause→响应 onlineStatus:0（关）；start→1（开）；成功标志 errorCount:0
#   (HAR 实测 loginPointId/bx-v 为可选埋点；同一读接口不带也成，故省略)

def set_adgroups_status(biz_code: str, units: list[dict[str, Any]], status: str,
                        cookies: dict[str, str]) -> dict[str, Any]:
    """把若干单元(adgroup)批量设为 pause / start。写操作。

    units: 每项含 campaignId / adgroupId。status: "pause" 关 / "start" 开。
    """
    if status not in ("pause", "start"):
        raise ValueError("status 只能是 pause 或 start")
    csrf = ensure_csrf(cookies)
    body = {
        "bizCode": biz_code,
        "adgroupList": [
            {"campaignId": u["campaignId"], "adgroupId": u["adgroupId"], "displayStatus": status}
            for u in units
        ],
        "csrfId": csrf,
    }
    return _api_call(f"/adgroup/updatePart.json?bizCode={biz_code}",
                     body, method="POST", cookies=cookies)


def fetch_promo_campaigns(*, biz_code: str, page_size: int = 20, offset: int = 0,
                           status_list: list[str] | None = None,
                           adgroup_required: bool = True,
                           cookies: dict[str, str] | None = None) -> dict[str, Any]:
    """拉某种推广玩法 (bizCode) 下当前的所有计划。

    adgroup_required=True 时服务端会回填每个计划的单元 (adgroupList)，
    其中 material.materialId 即被推广的宝贝 ID、material.title 即商品标题。
    这是把"宝贝 ID ↔ 计划"对应起来的唯一来源（findPage 顶层 itemId 恒为 null）。
    """
    cookies = cookies or load_alimama_cookies()
    body = {
        "bizCode": biz_code,
        "adgroupRequired": adgroup_required,
        "offset": offset,
        "pageSize": page_size,
        "statusList": status_list or ["start", "pause"],
    }
    # 关键：bizCode 必须同时放在 URL 上（HAR 实测），否则服务端不过滤
    path = f"/campaign/horizontal/findPage.json?bizCode={biz_code}"
    return _api_call(path, body, method="POST", cookies=cookies)


def cmd_promo(args: argparse.Namespace) -> None:
    biz_code, label = PROMO_BIZ_CODES[args.promo_key]
    item_filter = getattr(args, "item", None)

    if item_filter:
        # 反查模式：宝贝可能在任意一页，自动翻页扫全部计划再过滤
        cookies = load_alimama_cookies()
        all_rows: list[dict[str, Any]] = []
        total = None
        offset, page_size = 0, 100
        while True:
            page = fetch_promo_campaigns(
                biz_code=biz_code, page_size=page_size, offset=offset,
                status_list=args.status, cookies=cookies,
            )
            pd = page.get("data") or {}
            batch = pd.get("list") or []
            total = pd.get("count", 0) if total is None else total
            all_rows.extend(batch)
            offset += page_size
            if not batch or offset >= (total or 0):
                break
        data = {"data": {"count": total or len(all_rows), "list": all_rows}}
    else:
        data = fetch_promo_campaigns(
            biz_code=biz_code, page_size=args.limit,
            offset=(args.page - 1) * args.limit,
            status_list=args.status,
        )
    if args.raw or args.out:
        out = json.dumps(data, ensure_ascii=False, indent=2)
        if args.out:
            Path(args.out).write_text(out)
            print(f"已写入 {args.out}", file=sys.stderr)
        else:
            print(out)
        return

    d = data.get("data") or {}
    rows = d.get("list") or []
    count = d.get("count", 0)

    # 按宝贝 ID 过滤（反查"这个宝贝在哪个计划里推"）
    item_filter = getattr(args, "item", None)
    if item_filter:
        item_filter = str(item_filter)
        rows = [r for r in rows if _promo_item(r)[0] == item_filter]

    print(f"# 万相台 - {label}（bizCode={biz_code}）")
    print(f"# 当前共 {count} 个计划，本页 {len(rows)}")
    if item_filter:
        print(f"# 按宝贝ID过滤: {item_filter}（命中 {len(rows)} 个计划）")
    if args.status != ["start", "pause"]:
        print(f"# 过滤状态: {args.status}")
    print()

    # 按日预算降序
    rows_sorted = sorted(rows, key=lambda r: -float(r.get("dayBudget") or 0))
    for i, r in enumerate(rows_sorted, 1):
        cid = r.get("campaignId", "?")
        name = (r.get("campaignName") or "?")[:35]
        status = r.get("displayStatus", "?")
        status_label = {"start": "🟢 在投", "pause": "⏸  暂停", "end": "⏹  结束"}.get(status, status)
        is_top = "⭐" if r.get("topStatus") else "  "
        budget = float(r.get("dayBudget") or 0)
        bid_v = float(r.get("constraintValue") or 0)
        bid_unit = (r.get("bidUnit") or "—").replace("${constraintValue}", str(bid_v))
        bid_type = r.get("bidTypeV2") or "—"
        period = r.get("launchPeriodDisplayTime") or "全天"
        ptype = r.get("promotionType") or "—"
        ctime = (r.get("gmtCreate") or "—")[:10]
        item_id, item_title = _promo_item(r)

        print(f"[{i:>2}] {is_top}{status_label}  campaignId={cid}")
        print(f"     计划名: {name}")
        if item_id:
            print(f"     宝贝ID: {item_id}  {(item_title or '')[:30]}")
        print(f"     日预算: ¥{budget:<8,.0f}  出价: {bid_unit:<25}  类型: {bid_type}")
        print(f"     投放时段: {period:<15}  推广类型: {ptype:<6}  创建: {ctime}")
        print()


def cmd_promo_items(args: argparse.Namespace) -> None:
    """列出某个计划里的所有商品 + 每个商品的开关状态。

    直接走单元级接口 + campaignId 过滤（三种玩法都准，且绕开偏慢的计划级 findPage）。
    """
    cid = int(args.campaign)
    biz_keys = [args.biz] if getattr(args, "biz", None) else list(PROMO_BIZ_CODES)
    cookies = load_alimama_cookies()

    ags: list[dict[str, Any]] = []
    hit_biz: str | None = None
    for key in biz_keys:
        biz_code = PROMO_BIZ_CODES[key][0]
        rows = fetch_all_adgroups(biz_code, campaign_id=cid,
                                  status_list=["start", "pause", "end"], cookies=cookies)
        if rows:
            ags, hit_biz = rows, key
            break

    if not ags:
        print(f"# 未找到计划 {cid} 的单元"
              + (f"（在 {args.biz} 里）" if getattr(args, "biz", None) else "（已搜全部推广玩法）"),
              file=sys.stderr)
        sys.exit(1)

    items = [u for u in (_adgroup_unit(a) for a in ags) if u["itemId"]]
    label = PROMO_BIZ_CODES[hit_biz][1]
    cname = ags[0].get("campaignName") or "?"

    if args.raw or args.out:
        payload = {
            "campaignId": cid,
            "campaignName": cname,
            "bizCode": PROMO_BIZ_CODES[hit_biz][0],
            "itemCount": len(items),
            "items": items,
        }
        out = json.dumps(payload, ensure_ascii=False, indent=2)
        if args.out:
            Path(args.out).write_text(out)
            print(f"已写入 {args.out}", file=sys.stderr)
        else:
            print(out)
        return

    print(f"# {label}  计划 {cid}「{cname}」")
    on = sum(1 for it in items if it["on"])
    print(f"# 共 {len(items)} 个商品，开 {on} / 关 {len(items) - on}\n")
    print(f"{'开关':<6}{'宝贝ID':<16}标题")
    print("-" * 56)
    for it in sorted(items, key=lambda x: (not x["on"])):
        lab = "🟢 开" if it["on"] else "🔴 关"
        title = it["title"] or "(商品已删除/下架)"
        print(f"{lab:<6}{str(it['itemId']):<16}{title[:26]}")
    print("-" * 56)


def cmd_promo_units(args: argparse.Namespace) -> None:
    """把某玩法（或全部玩法）下所有计划的单元拉平成一张表。

    相当于网页"单元 Tab"。--item 反查某商品散落在哪些计划里、各自开关。
    """
    biz_keys = [args.biz] if getattr(args, "biz", None) else list(PROMO_BIZ_CODES)
    cookies = load_alimama_cookies()
    item_filter = str(args.item) if getattr(args, "item", None) else None

    units: list[dict[str, Any]] = []
    for key in biz_keys:
        biz_code, _ = PROMO_BIZ_CODES[key]
        # 单元级接口：三种玩法都直接带 material.materialId（关键词推广也准）
        for ag in fetch_all_adgroups(biz_code, status_list=args.status, cookies=cookies):
            u = _adgroup_unit(ag)
            if item_filter and u["itemId"] != item_filter:
                continue
            u["biz"] = key
            units.append(u)

    if args.raw or args.out:
        out = json.dumps({"unitCount": len(units), "units": units}, ensure_ascii=False, indent=2)
        if args.out:
            Path(args.out).write_text(out)
            print(f"已写入 {args.out}", file=sys.stderr)
        else:
            print(out)
        return

    on = sum(1 for u in units if u["on"])
    uniq = len({u["itemId"] for u in units if u["itemId"]})
    scope = PROMO_BIZ_CODES[args.biz][1] if getattr(args, "biz", None) else "全部推广玩法"
    print(f"# 单元拉平表（{scope}，来源 /adgroup/horizontal/findPage）")
    if item_filter:
        print(f"# 按宝贝ID过滤: {item_filter}")
    print(f"# 单元 {len(units)} 个 | 开 {on} / 关 {len(units) - on} | 不同商品 {uniq} 个\n")
    print(f"{'开关':<6}{'宝贝ID':<16}{'计划ID':<14}计划名")
    print("-" * 70)
    for u in sorted(units, key=lambda x: (x["itemId"] or "", not x["on"])):
        lab = "🟢开" if u["on"] else "🔴关"
        print(f"{lab:<6}{str(u['itemId'] or '—'):<16}{str(u['campaignId']):<14}{(u['campaignName'] or '')[:22]}")
    print("-" * 70)


def cmd_promo_off(args: argparse.Namespace) -> None:
    """按宝贝ID关停：把该商品散落在各计划里、当前【在投】的单元全部 pause。

    ⚠️ 写操作。默认 dry-run（只列清单不执行）；加 --execute 才真正关。
    """
    item = str(args.item)
    biz_keys = [args.biz] if getattr(args, "biz", None) else list(PROMO_BIZ_CODES)
    cookies = load_alimama_cookies()

    # 收集该商品当前在投(onlineStatus==1)的单元，按玩法分组
    targets: dict[str, list[dict[str, Any]]] = {}
    for key in biz_keys:
        biz_code = PROMO_BIZ_CODES[key][0]
        for ag in fetch_all_adgroups(biz_code, status_list=["start", "pause"], cookies=cookies):
            u = _adgroup_unit(ag)
            if u["itemId"] == item and u["on"]:
                targets.setdefault(biz_code, []).append(u)

    total = sum(len(v) for v in targets.values())
    label_of = {b: lbl for b, lbl in PROMO_BIZ_CODES.values()}

    print(f"# 按宝贝ID关停  宝贝 {item}")
    print(f"# 当前在投(将被关闭)的单元: {total} 个\n")
    if total == 0:
        print("没有「在投」状态的单元，无需操作。")
        return

    print(f"{'玩法':<10}{'计划ID':<14}{'单元ID':<14}计划名")
    print("-" * 64)
    for biz_code, units in targets.items():
        for u in units:
            print(f"{label_of.get(biz_code, biz_code):<10}{str(u['campaignId']):<14}{str(u['adgroupId']):<14}{(u['campaignName'] or '')[:20]}")
    print("-" * 64)

    if not args.execute:
        print(f"\n🔒 DRY-RUN（未执行任何操作）。以上 {total} 个单元将被 pause。")
        print("   确认无误后，加 --execute 重新运行才会真正关闭。")
        return

    # ---- 执行（仅在 --execute 时） ----
    print(f"\n⚡ 执行关停 {total} 个单元 ...")
    ok = fail = 0
    for biz_code, units in targets.items():
        try:
            resp = set_adgroups_status(biz_code, units, "pause", cookies)
            err = (resp.get("data") or {}).get("errorCount", -1)
            if err == 0:
                ok += len(units)
                print(f"  ✅ {label_of.get(biz_code)}: {len(units)} 个已关")
            else:
                fail += len(units)
                print(f"  ⚠️ {label_of.get(biz_code)}: errorCount={err}  {json.dumps((resp.get('data') or {}).get('errorDetails'), ensure_ascii=False)[:200]}")
        except Exception as e:
            fail += len(units)
            print(f"  ❌ {label_of.get(biz_code)}: {e}")
    print(f"\n完成：成功 {ok} / 失败 {fail}")


def fetch_scene_summary(biz_code: str, start_date: str, end_date: str, *,
                        realtime: bool = True, cookies: dict[str, str] | None = None) -> dict[str, Any]:
    """某推广场景的大盘汇总（展现/点击/花费/成交/ROI…）。

    关键：场景过滤靠 URL 的 ?bizCode=<scene>（body 里的 bizCode 不生效）。
    splitType=sum 求区间合计。三场景之和 = 全账户合计（实测对得上）。
    """
    cookies = cookies or load_alimama_cookies()
    body = {
        "bizCode": biz_code, "byPage": False, "fromRealTime": realtime,
        "startTime": start_date, "endTime": end_date,
        "splitType": "sum", "computeType": "sum",
        "sourceList": ["scene", "adgroup_list"], "queryDomains": [],
        "queryFieldIn": SCENE_SUMMARY_REQUEST_FIELDS,
    }
    return _api_call(f"/report/query.json?bizCode={biz_code}", body, method="POST", cookies=cookies)


def cmd_scene_summary(args: argparse.Namespace) -> None:
    """各推广场景大盘汇总（展现量/点击/花费/成交/ROI/加购…）。

    默认看过去 7 天（昨天数据凌晨可能未出，单看昨天易为空）。
    """
    biz_keys = [args.biz] if getattr(args, "biz", None) else list(PROMO_BIZ_CODES)
    cookies = load_alimama_cookies()
    start, end = args.date, (args.end_date or args.date)
    realtime = not args.no_realtime

    results = []
    for key in biz_keys:
        biz_code, label = PROMO_BIZ_CODES[key]
        try:
            d = fetch_scene_summary(biz_code, start, end, realtime=realtime, cookies=cookies)
        except Exception as e:
            results.append((key, label, None, str(e)))
            continue
        pd = d.get("data") or {}
        lst = pd.get("list") or []
        row = lst[0] if lst else {}
        results.append((key, label, row, None))

    if args.raw or args.out:
        payload = {"startTime": start, "endTime": end, "realtime": realtime,
                   "scenes": {k: r for k, _, r, _ in results}}
        out = json.dumps(payload, ensure_ascii=False, indent=2)
        if args.out:
            Path(args.out).write_text(out)
            print(f"已写入 {args.out}", file=sys.stderr)
        else:
            print(out)
        return

    print(f"# 万相台 推广场景大盘汇总  {start} ~ {end}"
          + ("（实时归因）" if realtime else "（历史归因）"))
    print(f"# 展现量=adPv；三场景之和≈全账户\n")
    for key, label, row, err in results:
        print(f"━━ {label} ━━")
        if err:
            print(f"   ⚠️ {err[:80]}\n"); continue
        if not row:
            print("   （该区间无投放数据）\n"); continue
        for field, name, fmt in SCENE_SUMMARY_SHOW:
            v = row.get(field)
            shown = fmt.format(v) if isinstance(v, (int, float)) else "—"
            print(f"   {name:<8}: {shown}")
        print()


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
    week_ago = (date.today() - timedelta(days=7)).isoformat()

    ap = sp.add_parser("api", help="通用接口探测：alimama-cli api /xxx.json [--body JSON] [-p k=v]")
    ap.add_argument("path", help='接口路径，如 "/account/checkRealBalance.json"')
    ap.add_argument("--method", default="POST", choices=["POST", "GET"])
    ap.add_argument("--body", help="POST body (JSON 字符串)")
    ap.add_argument("--param", "-p", action="append", help="附加 body 字段 key=value，可重复")
    ap.add_argument("--referer", help="自定义 Referer 头")
    ap.set_defaults(func=cmd_api)

    # "推广" 模块子命令：看当前在投的计划列表（不是历史报表）
    for key in PROMO_BIZ_CODES:
        biz, label = PROMO_BIZ_CODES[key]
        psub = sp.add_parser(f"promo-{key}", help=f"{label}：当前在投计划列表（bizCode={biz}）")
        psub.add_argument("--limit", type=int, default=10, help="拉多少条 (默认 10)")
        psub.add_argument("--page", type=int, default=1)
        psub.add_argument("--status", nargs="+", default=["start", "pause"],
                          help="过滤状态：start/pause/end (默认 start+pause)")
        psub.add_argument("--item", help="按宝贝ID反查：只显示推广该商品的计划（自动翻全部页）")
        psub.add_argument("--raw", action="store_true")
        psub.add_argument("--out", help="输出到文件")
        psub.set_defaults(func=cmd_promo, promo_key=key)

    # 单个计划里的所有商品 + 开关状态（测款计划这类一计划多商品时用）
    pi = sp.add_parser("promo-items", help="列出某计划里的全部商品及开/关状态：promo-items --campaign <计划ID>")
    pi.add_argument("--campaign", required=True, help="计划 ID (campaignId)")
    pi.add_argument("--biz", choices=list(PROMO_BIZ_CODES.keys()),
                    help="限定推广玩法 wholesite/keyword/crowd（默认自动搜全部）")
    pi.add_argument("--raw", action="store_true")
    pi.add_argument("--out", help="输出到文件")
    pi.set_defaults(func=cmd_promo_items)

    # 单元拉平表（网页"单元 Tab"）：所有计划的全部单元一张表
    pu = sp.add_parser("promo-units", help="单元拉平表：所有计划的全部单元(=商品广告位)一张表；--item 反查某商品在哪些计划")
    pu.add_argument("--biz", choices=list(PROMO_BIZ_CODES.keys()),
                    help="限定玩法 wholesite/keyword/crowd（默认扫全部 3 种）")
    pu.add_argument("--item", help="按宝贝ID过滤：只看这个商品散落在哪些计划、各自开关")
    pu.add_argument("--status", nargs="+", default=["start", "pause"],
                    help="计划状态过滤 start/pause/end（默认 start+pause）")
    pu.add_argument("--raw", action="store_true")
    pu.add_argument("--out", help="输出到文件")
    pu.set_defaults(func=cmd_promo_units)

    # ⚠️ 写操作：按宝贝ID关停。默认 dry-run，必须 --execute 才真正关。
    po = sp.add_parser("promo-off", help="⚠️写：按宝贝ID关停该商品所有在投单元（默认dry-run，--execute才执行）")
    po.add_argument("--item", required=True, help="宝贝ID：关掉这个商品散落在各计划里的全部在投单元")
    po.add_argument("--biz", choices=list(PROMO_BIZ_CODES.keys()),
                    help="限定玩法（默认扫全部 3 种）")
    po.add_argument("--execute", action="store_true",
                    help="真正执行关停（不加=只列清单不动）")
    po.set_defaults(func=cmd_promo_off)

    # 推广场景大盘汇总：展现量/点击/花费/成交/ROI/加购…
    ss = sp.add_parser("scene-summary", help="各推广场景大盘汇总（展现量/点击/花费/成交/ROI），默认过去7天")
    ss.add_argument("--biz", choices=list(PROMO_BIZ_CODES.keys()),
                    help="限定场景 wholesite/keyword/crowd（默认三个都出）")
    ss.add_argument("--date", default=week_ago, help=f"开始日期 (默认过去7天起 {week_ago})")
    ss.add_argument("--end-date", default=yesterday, help=f"结束日期 (默认昨天 {yesterday})")
    ss.add_argument("--no-realtime", action="store_true",
                    help="用历史归因(默认实时归因，与网页一致)")
    ss.add_argument("--raw", action="store_true")
    ss.add_argument("--out", help="输出到文件")
    ss.set_defaults(func=cmd_scene_summary)

    cs = sp.add_parser("charge-summary", help="花费汇总：各营销场景花了多少（关键词推广/人群推广/...）")
    cs.add_argument("--date", default=yesterday, help=f"开始日期 YYYY-MM-DD (默认 {yesterday})")
    cs.add_argument("--end-date", help="结束日期 (默认 = --date)")
    cs.add_argument("--window", type=int, default=15, choices=[1, 7, 15],
                    help="转化窗口天数 1/7/15 (默认 15)")
    cs.add_argument("--raw", action="store_true", help="输出原始 JSON")
    cs.add_argument("--out", help="输出到文件")
    cs.set_defaults(func=cmd_charge_summary)

    # 通用报表子命令家族：report-campaign / report-keyword / report-crowd / ...
    REPORT_ALIASES = {
        "report-campaign": "campaign",
        "report-adgroup":  "adgroup",
        "report-keyword":  "bidword",
        "report-crowd":    "crowd",
        "report-item":     "item_promotion",
        "report-creative": "creative",
        "report-area":     "area",
        "report-coupon":   "coupon",
        "report-realtime": "real_time",
        "report-other":    "other_promotion",
    }
    for cmd_name, rpt in REPORT_ALIASES.items():
        info = REPORT_TYPES[rpt]
        sub = sp.add_parser(cmd_name, help=f"{info['name']}（按 {info['list_domain']} 维度，按花费降序）")
        sub.add_argument("--date", default=yesterday, help=f"开始日期 YYYY-MM-DD (默认 {yesterday})")
        sub.add_argument("--end-date", help="结束日期 (默认 = --date)")
        sub.add_argument("--dim", help=f"维度 (默认 {info['list_domain']}；可选 account/date/...)")
        sub.add_argument("--window", type=int, default=15, choices=[1, 7, 15], help="转化窗口 1/7/15 天")
        sub.add_argument("--limit", type=int, default=10, help="拉多少条 (默认 10)")
        sub.add_argument("--page", type=int, default=1)
        sub.add_argument("--raw", action="store_true")
        sub.add_argument("--out", help="输出到文件")
        sub.set_defaults(func=cmd_report, rpt_type=rpt)

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
