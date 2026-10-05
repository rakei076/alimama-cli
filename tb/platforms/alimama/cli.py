"""万相台 AI 无界 (one.alimama.com) 只读数据查询命令：tb alimama <命令>。

取数方式与其他平台一样（见 tb/core/transport.py）：浏览器插件优先；Mac 上没装插件就读 Chrome 的 cookie。
读取接口全是 POST，插件只放行 Platform.bridge_posts 里登记的查询接口。
请求、登录判断、风控词、护栏（请求数提醒 / 间隔）都在 tb.core 里，这里只放接口清单、参数拼装和输出。
接口完全反向工程自万相台 onebp 客户端 JS（onebp/merge bundle）。
查询类命令全部只读。唯一的写操作（按宝贝关停单元）单独放在 promo_off.py，只有私人版带这个文件。

子命令：
    doctor               检查登录态
    api <path>           通用 POST 接口探测（拒绝写操作）
    account-balance      账户余额（无日期）
    activity-list        活动列表（日期范围）
    campaign-list        计划列表（日期范围）
    keyword-effect       关键词效果（日期范围）
    daily-report         日维度花费汇总
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl

from ...core import transport
from ...core.auth import NotLoggedIn
from ...core.client import Client
from ...core.errors import TbError
from .platform import ALIMAMA

API_HOST = ALIMAMA.hosts["main"]
REFERER_DETAIL_PAGE = ALIMAMA.referer


class ClientCookies:
    """cookie 的「凭据句柄」：命令函数里一路传的 `cookies` 其实是它，真正的连接在 .client 里。
    像 dict 一样能 .get / in / len，读取走 client.cookie()。"""

    def __init__(self, client: Client):
        self.client = client

    def get(self, name: str, default: str | None = None) -> str | None:
        return self.client.cookie(name) or default

    def __contains__(self, name: str) -> bool:
        return bool(self.get(name))

    def __len__(self) -> int:
        return len(self.client.cookies)


_CLIENT: Client | None = None


def load_alimama_cookies() -> ClientCookies:
    """取当前应使用的登录态（一次运行只建一个连接）。"""
    global _CLIENT
    if _CLIENT is None:
        _CLIENT = transport.make_client(ALIMAMA)
    return ClientCookies(_CLIENT)


def ensure_csrf(cookies: ClientCookies) -> str:
    """csrfId：首次调用时 POST /member/checkAccess.json 取得并缓存（底座的 prepare 钩子做）。

    万相台所有数据接口要求 URL 带 ?csrfId=xxx，否则 "bizLogin csrf检查未通过"。
    """
    cookies.client.whoami()
    return cookies.client.state["csrf"]


def _api_call(
    path: str,
    body: dict[str, Any] | None = None,
    method: str = "POST",
    cookies: ClientCookies | None = None,
    referer: str | None = None,
    biz_code: str = "universalBP",
    write: bool = False,
) -> dict[str, Any]:
    """对万相台 API 做一次 POST/GET，返回完整响应。

    path 必须以 `/` 开头（拼到 https://one.alimama.com 后），可以自带查询串（如 ?bizCode=xxx）。
    所有请求 URL 自动带 bizCode=universalBP 和 csrfId（底座的 build_request 钩子做）。
    write=True 只给 Platform.write_allow 里登记的写接口用，不自动重试。
    """
    client = (cookies or load_alimama_cookies()).client
    bare, _, query = path.partition("?")
    params = dict(parse_qsl(query))
    params.setdefault("bizCode", biz_code)
    headers = {"Referer": referer or REFERER_DETAIL_PAGE}
    if method.upper() == "POST":
        return client.post("main", bare, body or {}, params=params, raw=True, headers=headers, write=write)
    return client.get("main", bare, {**params, **(body or {})}, raw=True, headers=headers)


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
    print("== tb alimama doctor ==")
    try:
        cookies = load_alimama_cookies()
        print(f"✓ 读到 {len(cookies)} 个 alimama/taobao 域 cookie" if len(cookies)
              else "✓ 通过浏览器插件取数（登录态在浏览器里，不读 cookie 文件）")
        for k in ("cookie2", "unb", "_tb_token_", "cna", "sgcookie", "_l_g_", "t", "sg") if len(cookies) else ():
            if k in cookies:
                print(f"✓ {k} = <present>")
        ensure_csrf(cookies)
        print("✓ checkAccess 通过，拿到 csrfId（登录态有效）")
        print(f"\nAPI host: {API_HOST}")
        print(f"Referer:  {REFERER_DETAIL_PAGE}")
    except Exception as e:
        print(f"✗ {e}")
        sys.exit(1)


def cmd_api(args: argparse.Namespace) -> None:
    """通用 API 探测命令：tb alimama api <path> [--method POST] [--body '{"k":"v"}']"""
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


# ---------- 字段字典 ----------
#
# fields.json：机器可读字段字典（字段码 -> 中文名/适用范围/展示格式/核验状态/备注）。
# 启动时加载一次；文件缺失或损坏不崩，退回空字典并在 stderr 提醒。
FIELDS_PATH = Path(__file__).resolve().parent / "fields.json"


def load_fields_dict() -> dict[str, dict]:
    """字段字典；缺失/损坏不崩，退回空字典并提醒。"""
    try:
        return json.loads(FIELDS_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        print(f"⚠️ fields.json 不可用({e}),退回内置字段表", file=sys.stderr)
        return {}


FIELDS_DICT = load_fields_dict()

FIELD_FMT_MAP = {
    "amt": "{:,.2f}",
    "int": "{:,.0f}",
    "pct": "{:.2%}",
    "num": "{:.2f}",
}


def _scope_matches(field_scopes: list[str] | None, cmd_name: str) -> bool:
    """scope 条目支持通配前缀："report-*" 匹配所有以 report- 开头的命令名。"""
    for pat in field_scopes or []:
        if pat == cmd_name:
            return True
        if pat.endswith("*") and cmd_name.startswith(pat[:-1]):
            return True
    return False


def all_fields_for_scope(cmd_name: str) -> list[str]:
    """FIELDS_DICT 中 scope 匹配 cmd_name 的全部字段码。"""
    return [k for k, v in FIELDS_DICT.items() if _scope_matches(v.get("scope"), cmd_name)]


def resolve_field_list(args: argparse.Namespace, cmd_name: str) -> list[str] | None:
    """由 --fields / --all-fields 算出本次请求要用的字段列表；都不传返回 None（=默认白名单不变）。"""
    fields_arg = getattr(args, "fields", None)
    if fields_arg:
        return [f.strip() for f in fields_arg.split(",") if f.strip()]
    if getattr(args, "all_fields", False):
        return all_fields_for_scope(cmd_name)
    return None


def field_label(field: str) -> str:
    """verified 字段用字典中文名；未知/candidate 字段用码原名 + '?' 后缀。"""
    entry = FIELDS_DICT.get(field)
    if entry and entry.get("status") == "verified":
        return entry["cn"]
    return f"{field}?"


def format_field_value(field: str, value: Any) -> str:
    """按字典 fmt 格式化；字典无该字段/无 fmt 时直接 str()；None 显示 '-'。"""
    if value is None:
        return "-"
    entry = FIELDS_DICT.get(field)
    fmt = FIELD_FMT_MAP.get(entry.get("fmt")) if entry else None
    if fmt:
        try:
            return fmt.format(value)
        except (TypeError, ValueError):
            return str(value)
    return str(value)


def fetch_with_field_fallback(custom_call, default_call, field_list, default_fields):
    """自定义字段(--fields/--all-fields)请求整体报错时，用默认白名单重发一次兜底。

    重发成功 → 说明默认白名单没问题，问题出在自定义字段这批里；报出本次新增字段
    （即自定义集合与默认白名单的差集）后抛错退出，不做逐字段二分定位(YAGNI)。
    重发也失败 → 大概率是接口/网络本身的问题，原样抛出原始异常。
    field_list 为 None（没传 --fields/--all-fields）时不做任何兜底，直接透传异常。
    """
    try:
        return custom_call()
    except Exception as original_err:
        if field_list is None:
            raise
        try:
            default_call()
        except Exception:
            raise original_err
        diff = sorted(set(field_list) - set(default_fields))
        raise RuntimeError(f"字段不被接口接受: {diff}") from original_err


# ---------- 通用报表接口 /report/query.json ----------
#
# 从 HAR 实测发现：万相台 11 个侧栏报表里有 10 个走同一个 /report/query.json，
# 仅靠 rptType + queryDomains 两个参数切换。
#
# 完整 17 个指标（queryFieldIn）：
REPORT_METRICS = {
    "adPv": "展现量",
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
                  offset: int | None = None,
                  item_search: str | None = None,
                  effect_window: int = 15,
                  field_list: list[str] | None = None,
                  cookies: dict[str, str] | None = None) -> dict[str, Any]:
    """通用报表查询。

    rpt_type:   campaign / adgroup / bidword / crowd / item_promotion / creative / area / coupon / real_time
    dimension:  account (总览) / date (按天) / campaign / adgroup / word / crowd / promotion / province / creative
    field_list: 传了就原样替换默认指标白名单塞进 queryFieldIn（未知码原样透传=试探入口）；
                None（默认）走原来的 REPORT_METRICS 白名单，行为不变。
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
        "queryFieldIn": field_list if field_list is not None else list(REPORT_METRICS.keys()),
        "startTime": start_date,
        "endTime": end_date,
        "splitType": "hour" if is_realtime else "day",
        "effectEqual": effect_window,
        "havingList": [],
        "pageSize": page_size,
        "pageNo": page_no,
        "orderField": "charge",
        "orderBy": "desc",
        "unifyType": "zhai",
    }
    # 网页报表使用 offset 分页；pageNo 会被服务端忽略。
    # 默认按花费降序，避免关键词第一页落到大量零消耗历史词。
    body["offset"] = offset if offset is not None else (page_no - 1) * page_size
    # 商品搜索:顶层 itemIdOrName,传完整 item_id 服务端精确返回该商品,传文字按名搜
    # (2026-07-08 HAR 实测:itemIdOrName=完整ID → count=1;残缺ID → count=0)
    if item_search is not None:
        body["itemIdOrName"] = item_search
    return _api_call("/report/query.json", body, method="POST", cookies=cookies)


def cmd_report(args: argparse.Namespace) -> None:
    rpt_info = REPORT_TYPES[args.rpt_type]
    dim = args.dim or rpt_info["list_domain"]
    end = args.end_date or args.date
    default_fields = list(REPORT_METRICS.keys())
    field_list = resolve_field_list(args, "report-*")

    def _do(fl: list[str] | None) -> dict[str, Any]:
        return fetch_report(
            rpt_type=args.rpt_type, dimension=dim,
            start_date=args.date, end_date=end,
            page_no=args.page, page_size=args.limit,
            offset=getattr(args, "offset", None),
            item_search=getattr(args, "search", None),
            effect_window=args.window,
            field_list=fl,
        )

    data = fetch_with_field_fallback(
        lambda: _do(field_list), lambda: _do(None), field_list, default_fields,
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

    if field_list is not None:
        # --fields/--all-fields 给了自定义字段 → 按用户给的字段顺序渲染动态列，
        # 而不是原来那套固定 6 列（展现/花费/成交/ROI/点击/CTR）。
        if not rows:
            print("\n（无明细数据）")
            return
        rows_sorted = sorted(rows, key=lambda r: -float(r.get("charge") or 0))
        print()
        print(" | ".join(field_label(f) for f in field_list))
        print("-" * 90)
        for r in rows_sorted[:args.limit]:
            print(" | ".join(format_field_value(f, r.get(f)) for f in field_list))
        return

    # 总计
    if total_data:
        charge = float(total_data.get("charge") or 0)
        amt = float(total_data.get("alipayInshopAmt") or 0)
        roi = float(total_data.get("roi") or 0)
        click = total_data.get("click") or 0
        adpv = total_data.get("adPv") or 0
        print(f"\n  总计: 展现 {int(adpv):,} | 花费 ¥{charge:,.2f} | 成交 ¥{amt:,.2f} | ROI {roi:.2f} | 点击 {click:,}")

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

    print(f"{'#':<4} {'名称':<28} {'展现':>9} {'花费':>9} {'成交':>10} {'ROI':>6} {'点击':>6} {'CTR':>6}")
    print("-" * 90)
    for i, r in enumerate(rows_sorted[:args.limit], 1):
        name = str(r.get(name_field, '?'))[:26] if name_field else '?'
        adpv = int(r.get("adPv") or 0)
        charge = float(r.get("charge") or 0)
        amt = float(r.get("alipayInshopAmt") or 0)
        roi = float(r.get("roi") or 0)
        click = r.get("click") or 0
        ctr = float(r.get("ctr") or 0)
        print(f"{i:<4} {name:<28} {adpv:>9,} {charge:>9,.2f} {amt:>10,.2f} {roi:>6.2f} {click:>6} {ctr*100:>5.1f}%")


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

def _natural_flow_not_settled(end_date: str) -> bool:
    """区间结束日距今 ≤2 天时，自然流量相关字段（naturalPayAmt/orgNaturalPv 等）
    归因未跑完，数值还没出来——提醒用户别拿这两天的自然流量列当真。
    """
    try:
        end = datetime.strptime(end_date, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return False
    return (date.today() - end).days <= 2


# 场景大盘汇总（scene-summary）：/report/query.json + splitType=sum，按 URL ?bizCode= 区分场景。
# 请求全字段（HAR 实测有效），展示挑核心。展现量字段 = adPv。
SCENE_SUMMARY_REQUEST_FIELDS = [
    "click", "charge", "ctr", "ecpc", "ecpm", "cvr", "roi",
    "adPv", "alipayInshopNum", "alipayDirNum", "alipayInshopAmt",
    "cartInshopNum", "cartRate", "cartCost", "colCartCost",
    "clickUv", "clickUvCost", "shopVisitUv", "shopVisitUvRate",
    "firstPurchaseUv", "newAlipayInshopUvRate",
    "alipayInshopUv", "alipayInshopCost", "colCartNum",
    "naturalPayAmt", "orgNaturalPv",
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
    ("alipayInshopUv", "成交人数", "{:,.0f}"),
    ("alipayInshopCost", "总成交成本", "¥{:.2f}"),
    ("colCartNum", "总收藏加购数", "{:,.0f}"),
    ("naturalPayAmt", "自然流量转化金额", "¥{:,.2f}"),
    ("orgNaturalPv", "自然流量曝光量", "{:,.0f}"),
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
                       item_id: int | str | None = None,
                       adgroup_id: int | str | None = None,
                       cookies: dict[str, str] | None = None) -> list[dict[str, Any]]:
    """翻完所有页，返回某玩法下的全部单元行（每行一个商品广告位）。

    服务端过滤（强烈优先用，别再全量拉回客户端筛）：
    - campaign_id：只取某计划下的单元
    - item_id：只取某宝贝ID的单元（实测返回该商品散落各计划的全部单元，对关停安全）
    - adgroup_id：精确定位某个单元ID
    三者均为服务端过滤，命中后通常一页内返回完。
    """
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
        if item_id is not None:
            body["itemId"] = int(item_id)
        if adgroup_id is not None:
            body["adgroupId"] = int(adgroup_id)
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

    相当于网页"单元 Tab"。
    --item 反查某商品散落在哪些计划里、各自开关（服务端按 itemId 过滤，不全量拉）。
    --unit 精确定位某个单元ID（服务端按 adgroupId 过滤，命中即停）。
    """
    biz_keys = [args.biz] if getattr(args, "biz", None) else list(PROMO_BIZ_CODES)
    cookies = load_alimama_cookies()
    item_filter = str(args.item) if getattr(args, "item", None) else None
    unit_filter = str(args.unit) if getattr(args, "unit", None) else None
    # 精确按ID查时，状态放宽到含 end，避免漏掉已结束的单元
    status_list = args.status
    if (item_filter or unit_filter) and status_list == ["start", "pause"]:
        status_list = ["start", "pause", "end"]

    units: list[dict[str, Any]] = []
    for key in biz_keys:
        biz_code, _ = PROMO_BIZ_CODES[key]
        # 单元级接口：三种玩法都直接带 material.materialId（关键词推广也准）
        # itemId / adgroupId 走服务端过滤，命中即停，不再全量拉回客户端筛
        rows = fetch_all_adgroups(biz_code, status_list=status_list,
                                  item_id=item_filter, adgroup_id=unit_filter,
                                  cookies=cookies)
        for ag in rows:
            u = _adgroup_unit(ag)
            u["biz"] = key
            units.append(u)
        if unit_filter and units:
            break  # 单元ID全局唯一，命中后无需再扫其余玩法

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
    if unit_filter:
        print(f"# 按单元ID过滤(服务端): {unit_filter}")
    if item_filter:
        print(f"# 按宝贝ID过滤(服务端): {item_filter}")
    print(f"# 单元 {len(units)} 个 | 开 {on} / 关 {len(units) - on} | 不同商品 {uniq} 个\n")
    print(f"{'开关':<6}{'宝贝ID':<16}{'计划ID':<14}计划名")
    print("-" * 70)
    for u in sorted(units, key=lambda x: (x["itemId"] or "", not x["on"])):
        lab = "🟢开" if u["on"] else "🔴关"
        print(f"{lab:<6}{str(u['itemId'] or '—'):<16}{str(u['campaignId']):<14}{(u['campaignName'] or '')[:22]}")
    print("-" * 70)


def fetch_scene_summary(biz_code: str, start_date: str, end_date: str, *,
                        realtime: bool = True, field_list: list[str] | None = None,
                        cookies: dict[str, str] | None = None) -> dict[str, Any]:
    """某推广场景的大盘汇总（展现/点击/花费/成交/ROI…）。

    关键：场景过滤靠 URL 的 ?bizCode=<scene>（body 里的 bizCode 不生效）。
    splitType=sum 求区间合计。三场景之和 = 全账户合计（实测对得上）。
    field_list 传了就替换默认字段白名单（未知码原样透传）；None 行为不变。
    """
    cookies = cookies or load_alimama_cookies()
    body = {
        "bizCode": biz_code, "byPage": False, "fromRealTime": realtime,
        "startTime": start_date, "endTime": end_date,
        "splitType": "sum", "computeType": "sum",
        "sourceList": ["scene", "adgroup_list"], "queryDomains": [],
        "queryFieldIn": field_list if field_list is not None else SCENE_SUMMARY_REQUEST_FIELDS,
    }
    return _api_call(f"/report/query.json?bizCode={biz_code}", body, method="POST", cookies=cookies)


def cmd_scene_summary(args: argparse.Namespace) -> None:
    """各推广场景大盘汇总（展现量/点击/花费/成交/ROI/加购…）。

    默认看过去 14 天（昨天数据凌晨可能未出，单看昨天易为空）。
    """
    biz_keys = [args.biz] if getattr(args, "biz", None) else list(PROMO_BIZ_CODES)
    cookies = load_alimama_cookies()
    start, end = args.date, (args.end_date or args.date)
    realtime = not args.no_realtime
    field_list = resolve_field_list(args, "scene-summary")

    results = []
    for key in biz_keys:
        biz_code, label = PROMO_BIZ_CODES[key]
        try:
            d = fetch_with_field_fallback(
                lambda bc=biz_code: fetch_scene_summary(
                    bc, start, end, realtime=realtime, field_list=field_list, cookies=cookies),
                lambda bc=biz_code: fetch_scene_summary(
                    bc, start, end, realtime=realtime, field_list=None, cookies=cookies),
                field_list, SCENE_SUMMARY_REQUEST_FIELDS,
            )
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
        if field_list is not None:
            for f in field_list:
                print(f"   {field_label(f):<8}: {format_field_value(f, row.get(f))}")
        else:
            for field, name, fmt in SCENE_SUMMARY_SHOW:
                v = row.get(field)
                shown = fmt.format(v) if isinstance(v, (int, float)) else "—"
                print(f"   {name:<8}: {shown}")
        print()

    if _natural_flow_not_settled(end):
        print("⚠️ 最近2天自然流量列尚未出数（归因未完成）")


# 分日详情（scene-daily）：营销场景报表 → 某场景 → 分日详情。
# rptType=account + queryDomains=["date"] 按天拆；场景过滤靠 URL ?bizCode=（与 scene-summary 同）。
# 每行一天，含 thedate + 全指标；服务端返回 totalData 作为“合计数据”行。
# 默认表格列（对齐网页“分日数据明细”的可见列）。其余指标（加购数/加购率/潜客率/
# 新成交客户率/直接成交单数/各类成本…）已在响应里，用 --raw 全部拿得到。
# 新字段常量：与 SCENE_SUMMARY_REQUEST_FIELDS 追加的 5 个一致，供 fetch_scene_daily
# 的 queryFieldIn 复用（REPORT_METRICS 本身不动，其他 report-* 命令共用它）。
SCENE_NEW_FIELDS = [
    "alipayInshopUv", "alipayInshopCost", "colCartNum",
    "naturalPayAmt", "orgNaturalPv",
]

SCENE_DAILY_SHOW = [
    ("adPv", "展现", "{:,.0f}"),
    ("click", "点击", "{:,.0f}"),
    ("charge", "花费", "{:,.2f}"),
    ("ctr", "点击率", "{:.2%}"),
    ("ecpc", "平均点击花费", "{:.2f}"),
    ("alipayInshopAmt", "成交额", "{:,.2f}"),
    ("alipayInshopNum", "笔数", "{:,.0f}"),
    ("cvr", "转化率", "{:.2%}"),
    ("roi", "ROI", "{:.2f}"),
    ("alipayInshopUv", "成交人数", "{:,.0f}"),
    ("naturalPayAmt", "自然流量转化金额", "{:,.2f}"),
    ("orgNaturalPv", "自然流量曝光量", "{:,.0f}"),
]


SCENE_DAILY_REQUEST_FIELDS = list(dict.fromkeys(list(REPORT_METRICS.keys()) + SCENE_NEW_FIELDS))


def fetch_scene_daily(biz_code: str, start_date: str, end_date: str, *,
                      effect_window: int = 15,
                      field_list: list[str] | None = None,
                      cookies: dict[str, str] | None = None) -> dict[str, Any]:
    """某推广场景的分日详情（按天的展现/点击/花费/成交/ROI）。

    与 scene-summary 同一接口，区别：splitType=day + queryDomains=[date] 按天拆，
    走 pcBaseReport 源、rptType=account。场景过滤同样靠 URL ?bizCode=<scene>。
    field_list 传了就替换默认字段白名单（未知码原样透传）；None 行为不变。
    """
    cookies = cookies or load_alimama_cookies()
    body = {
        "bizCode": "universalBP", "fromRealTime": False,
        "source": "baseReport", "from": "pcBaseReport",
        "byPage": True, "byPageWithoutCount": False, "totalTag": True,
        "needCountAccelerate": True,
        "rptType": "account", "queryDomains": ["date"],
        "queryFieldIn": field_list if field_list is not None else SCENE_DAILY_REQUEST_FIELDS,
        "startTime": start_date, "endTime": end_date,
        "splitType": "day", "effectEqual": effect_window, "havingList": [],
        "pageSize": 100, "pageNo": 1, "unifyType": "zhai",
    }
    return _api_call(f"/report/query.json?bizCode={biz_code}", body, method="POST", cookies=cookies)


def _scene_daily_value(row: dict[str, Any], field: str) -> Any:
    """取指标；ecpc(平均点击花费) 服务端不返回，用 花费/点击 现算（与网页一致）。"""
    v = row.get(field)
    if v is None and field == "ecpc":
        charge, click = row.get("charge"), row.get("click")
        if isinstance(charge, (int, float)) and isinstance(click, (int, float)) and click:
            return charge / click
    return v


def _scene_daily_line(row: dict[str, Any]) -> str:
    cells = []
    for field, _, fmt in SCENE_DAILY_SHOW:
        v = _scene_daily_value(row, field)
        cells.append(fmt.format(v) if isinstance(v, (int, float)) else "—")
    return "  ".join(f"{c:>10}" for c in cells)


def cmd_scene_daily(args: argparse.Namespace) -> None:
    """某推广场景的分日详情（营销场景报表 → 场景 → 分日详情），默认过去14天。"""
    biz_keys = [args.biz] if getattr(args, "biz", None) else list(PROMO_BIZ_CODES)
    cookies = load_alimama_cookies()
    start, end = args.date, (args.end_date or args.date)
    field_list = resolve_field_list(args, "scene-daily")

    results = []
    for key in biz_keys:
        biz_code, label = PROMO_BIZ_CODES[key]
        try:
            d = fetch_with_field_fallback(
                lambda bc=biz_code: fetch_scene_daily(
                    bc, start, end, effect_window=args.window, field_list=field_list, cookies=cookies),
                lambda bc=biz_code: fetch_scene_daily(
                    bc, start, end, effect_window=args.window, field_list=None, cookies=cookies),
                field_list, SCENE_DAILY_REQUEST_FIELDS,
            )
        except Exception as e:
            results.append((key, label, None, None, str(e)))
            continue
        pd = d.get("data") or {}
        rows = pd.get("list") or []
        total = pd.get("totalData")
        if isinstance(total, list):
            total = total[0] if total else None
        results.append((key, label, rows, total, None))

    if args.raw or args.out:
        payload = {"startTime": start, "endTime": end,
                   "scenes": {k: {"list": r, "totalData": t} for k, _, r, t, _ in results}}
        out = json.dumps(payload, ensure_ascii=False, indent=2)
        if args.out:
            Path(args.out).write_text(out)
            print(f"已写入 {args.out}", file=sys.stderr)
        else:
            print(out)
        return

    if field_list is not None:
        header = "  ".join(f"{field_label(f):>10}" for f in field_list)
    else:
        header = "  ".join(f"{name:>10}" for _, name, _ in SCENE_DAILY_SHOW)
    print(f"# 万相台 分日详情  {start} ~ {end}（历史归因，转化窗口 {args.window} 天）\n")
    for key, label, rows, total, err in results:
        print(f"━━ {label} ━━")
        if err:
            print(f"   ⚠️ {err[:80]}\n"); continue
        if not rows:
            print("   （该区间无投放数据）\n"); continue
        print(f"  {'日期':>10}  {header}")
        if field_list is not None:
            def _line(row: dict[str, Any]) -> str:
                return "  ".join(f"{format_field_value(f, row.get(f)):>10}" for f in field_list)
        else:
            _line = _scene_daily_line
        for row in sorted(rows, key=lambda r: str(r.get("thedate"))):
            print(f"  {str(row.get('thedate')):>10}  {_line(row)}")
        if total:
            print(f"  {'合计':>10}  {_line(total)}")
        print()

    if _natural_flow_not_settled(end):
        print("⚠️ 最近2天自然流量列尚未出数（归因未完成）")


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

def _add_fields_group(sub: argparse.ArgumentParser) -> None:
    """给 report-*/scene-summary/scene-daily 加 --fields / --all-fields 万能选列（互斥）。"""
    g = sub.add_mutually_exclusive_group()
    g.add_argument("--fields",
                   help="逗号分隔字段码，替换默认字段白名单塞进请求(未知码原样透传=试探入口，如 --fields foo,charge)")
    g.add_argument("--all-fields", action="store_true",
                   help="拉取 fields.json 中该命令范围内的全部已知字段")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="tb alimama", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = p.add_subparsers(dest="cmd", required=True)

    d = sp.add_parser("doctor", help="检查 cookie / 登录态")
    d.set_defaults(func=cmd_doctor)

    yesterday = (date.today() - timedelta(days=1)).isoformat()
    two_weeks_ago = (date.today() - timedelta(days=14)).isoformat()

    ap = sp.add_parser("api", help="通用接口探测：tb alimama api /xxx.json [--body JSON] [-p k=v]")
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
    pu.add_argument("--item", help="按宝贝ID过滤(服务端)：只看这个商品散落在哪些计划、各自开关")
    pu.add_argument("--unit", help="按单元ID精确定位(服务端 adgroupId 过滤，命中即停)")
    pu.add_argument("--status", nargs="+", default=["start", "pause"],
                    help="计划状态过滤 start/pause/end（默认 start+pause）")
    pu.add_argument("--raw", action="store_true")
    pu.add_argument("--out", help="输出到文件")
    pu.set_defaults(func=cmd_promo_units)

    # ⚠️ 唯一的写操作（按宝贝关停单元）在 promo_off.py：只有私人版带这个文件，没有就不注册
    try:
        from . import promo_off
    except ImportError:
        promo_off = None
    if promo_off:
        promo_off.register(sp)

    # 推广场景大盘汇总：展现量/点击/花费/成交/ROI/加购…
    ss = sp.add_parser("scene-summary", help="各推广场景大盘汇总（展现量/点击/花费/成交/ROI），默认过去14天")
    ss.add_argument("--biz", choices=list(PROMO_BIZ_CODES.keys()),
                    help="限定场景 wholesite/keyword/crowd（默认三个都出）")
    ss.add_argument("--date", default=two_weeks_ago, help=f"开始日期 (默认过去14天起 {two_weeks_ago})")
    ss.add_argument("--end-date", default=yesterday, help=f"结束日期 (默认昨天 {yesterday})")
    ss.add_argument("--no-realtime", action="store_true",
                    help="用历史归因(默认实时归因，与网页一致)")
    ss.add_argument("--raw", action="store_true")
    ss.add_argument("--out", help="输出到文件")
    _add_fields_group(ss)
    ss.set_defaults(func=cmd_scene_summary)

    sd = sp.add_parser("scene-daily",
                       help="营销场景报表→分日详情：某场景按天的展现/点击/花费/成交/ROI，默认过去14天")
    sd.add_argument("--biz", choices=list(PROMO_BIZ_CODES.keys()),
                    help="限定场景 wholesite/keyword/crowd（默认三个都出）")
    sd.add_argument("--date", default=two_weeks_ago, help=f"开始日期 (默认过去14天起 {two_weeks_ago})")
    sd.add_argument("--end-date", default=yesterday, help=f"结束日期 (默认昨天 {yesterday})")
    sd.add_argument("--window", type=int, default=15, choices=[1, 7, 15],
                    help="转化窗口天数 1/7/15 (默认 15)")
    sd.add_argument("--raw", action="store_true")
    sd.add_argument("--out", help="输出到文件")
    _add_fields_group(sd)
    sd.set_defaults(func=cmd_scene_daily)

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
        sub.add_argument("--offset", type=int, default=None,
                         help="按 offset 分页(item_promotion 报表 pageNo 失效,须用 offset 全量翻页)")
        sub.add_argument("--search", default=None,
                         help="按商品搜索:传完整 item_id 精确返回该商品,传文字按商品名搜(itemIdOrName)")
        sub.add_argument("--raw", action="store_true")
        sub.add_argument("--out", help="输出到文件")
        _add_fields_group(sub)
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


def _force_utf8() -> None:
    """中文 Windows 的 cmd/SSH 常为 GBK；帮助文本里的 emoji 不应让 CLI 崩溃。统一用 UTF-8。"""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass


def main(argv: list[str] | None = None) -> int:
    global _CLIENT
    _force_utf8()
    args = build_parser().parse_args(argv)
    _CLIENT = None
    try:
        args.func(args)
        return 0
    except SystemExit as e:
        return int(e.code or 0)
    except NotLoggedIn as e:
        print(f"✗ {e}", file=sys.stderr)
        return 2
    except TbError as e:
        print(f"✗ {e}", file=sys.stderr)
        return e.exit_code
    except (RuntimeError, ValueError) as e:
        print(f"✗ {e}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\n中断", file=sys.stderr)
        return 130


if __name__ == "__main__":
    sys.exit(main())
