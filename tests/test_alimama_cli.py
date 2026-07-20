import sys
from datetime import date, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import alimama_cli

NEW_SCENE_FIELDS = [
    "alipayInshopUv", "alipayInshopCost", "colCartNum",
    "naturalPayAmt", "orgNaturalPv",
]


def test_fields_dict_loads_and_has_verified_entries():
    d = alimama_cli.load_fields_dict()
    assert d["alipayInshopUv"]["cn"] == "成交人数"
    assert d["alipayInshopUv"]["status"] == "verified"
    assert "T-2" in d["naturalPayAmt"]["note"]


def test_fields_dict_missing_file_returns_empty(monkeypatch, tmp_path):
    monkeypatch.setattr(alimama_cli, "FIELDS_PATH", tmp_path / "no.json")
    assert alimama_cli.load_fields_dict() == {}


class Response:
    status_code = 200
    text = '{"info":{"ok":true},"data":{}}'

    def json(self):
        return {"info": {"ok": True}, "data": {}}


def test_business_error_raises():
    with pytest.raises(RuntimeError, match="业务失败"):
        alimama_cli._validate_business_response({
            "info": {"ok": False, "errorCode": "LOGIN", "message": "请登录"},
            "data": None,
        })


def test_scene_daily_builds_day_split_scene_request(monkeypatch):
    seen = {}

    def fake_api_call(path, body, method="POST", cookies=None):
        seen["path"] = path
        seen["body"] = body
        return {"data": {"list": [{"thedate": "2026-07-17", "charge": 1.0}],
                         "totalData": [{"charge": 1.0}]}}

    monkeypatch.setattr(alimama_cli, "_api_call", fake_api_call)
    payload = alimama_cli.fetch_scene_daily(
        "onebpSearch", "2026-07-11", "2026-07-17", cookies={"x": "y"},
    )
    # 场景过滤靠 URL ?bizCode=
    assert seen["path"] == "/report/query.json?bizCode=onebpSearch"
    b = seen["body"]
    assert b["rptType"] == "account"
    assert b["queryDomains"] == ["date"]      # 按天拆
    assert b["splitType"] == "day"
    assert b["fromRealTime"] is False          # 分日用历史归因
    assert b["startTime"] == "2026-07-11" and b["endTime"] == "2026-07-17"
    assert payload["data"]["list"][0]["thedate"] == "2026-07-17"


def test_scene_daily_computes_ecpc_from_charge_and_click():
    # 服务端不返回 ecpc(平均点击花费)，用 花费/点击 现算
    assert alimama_cli._scene_daily_value({"charge": 100.0, "click": 500}, "ecpc") == 0.2
    # 点击为 0 不能除，返回 None（表格显示 —）
    assert alimama_cli._scene_daily_value({"charge": 5.0, "click": 0}, "ecpc") is None
    # 有原生字段则直接用
    assert alimama_cli._scene_daily_value({"charge": 100.0, "click": 500, "roi": 3.1}, "roi") == 3.1


def test_report_uses_offset_and_charge_sort(monkeypatch):
    seen = {}

    def fake_api_call(path, body, method="POST", cookies=None):
        seen["body"] = body
        return {"data": {}}

    monkeypatch.setattr(alimama_cli, "_api_call", fake_api_call)
    alimama_cli.fetch_report(
        rpt_type="bidword", dimension="word",
        start_date="2026-07-11", end_date="2026-07-17",
        page_no=3, page_size=50, cookies={"cookie2": "test"},
    )
    assert seen["body"]["offset"] == 100
    assert seen["body"]["orderField"] == "charge"
    assert seen["body"]["orderBy"] == "desc"


def test_transient_network_error_is_retried(monkeypatch):
    calls = []

    def post(*args, **kwargs):
        calls.append(1)
        if len(calls) == 1:
            raise alimama_cli.requests.exceptions.Timeout("timeout")
        return Response()

    monkeypatch.setattr(alimama_cli.requests, "post", post)
    monkeypatch.setattr(alimama_cli.time, "sleep", lambda _: None)
    monkeypatch.setattr(alimama_cli, "MAX_RETRIES", 2)
    payload = alimama_cli._api_call(
        "/test.json", {}, cookies={}, skip_csrf=True
    )
    assert payload["info"]["ok"] is True
    assert len(calls) == 2


def test_scene_summary_request_fields_include_new_fields(monkeypatch):
    seen = {}

    def fake_api_call(path, body, method="POST", cookies=None):
        seen["body"] = body
        return {"data": {"list": [{}]}}

    monkeypatch.setattr(alimama_cli, "_api_call", fake_api_call)
    alimama_cli.fetch_scene_summary(
        "onebpSearch", "2026-07-06", "2026-07-19", cookies={"x": "y"},
    )
    for f in NEW_SCENE_FIELDS:
        assert f in seen["body"]["queryFieldIn"]


def test_scene_daily_query_field_in_includes_new_fields(monkeypatch):
    seen = {}

    def fake_api_call(path, body, method="POST", cookies=None):
        seen["body"] = body
        return {"data": {"list": [], "totalData": []}}

    monkeypatch.setattr(alimama_cli, "_api_call", fake_api_call)
    alimama_cli.fetch_scene_daily(
        "onebpSearch", "2026-07-06", "2026-07-19", cookies={"x": "y"},
    )
    query_fields = seen["body"]["queryFieldIn"]
    for f in NEW_SCENE_FIELDS:
        assert f in query_fields
    # 不能改动 REPORT_METRICS 本身，也不能重复追加同一字段
    for f in alimama_cli.REPORT_METRICS.keys():
        assert f in query_fields
    assert len(query_fields) == len(set(query_fields))


def test_scene_summary_and_daily_default_to_past_14_days():
    parser = alimama_cli.build_parser()
    expected_start = (date.today() - timedelta(days=14)).isoformat()
    expected_end = (date.today() - timedelta(days=1)).isoformat()

    ss_args = parser.parse_args(["scene-summary"])
    assert ss_args.date == expected_start
    assert ss_args.end_date == expected_end

    sd_args = parser.parse_args(["scene-daily"])
    assert sd_args.date == expected_start
    assert sd_args.end_date == expected_end


def test_scene_summary_and_daily_default_body_uses_past_14_days(monkeypatch, capsys):
    # 光验证 argparse 解析结果不够：确认默认日期真的被传进了请求 body。
    expected_start = (date.today() - timedelta(days=14)).isoformat()
    expected_end = (date.today() - timedelta(days=1)).isoformat()

    monkeypatch.setattr(alimama_cli, "load_alimama_cookies", lambda: {"x": "y"})

    seen = {}

    def fake_api_call(path, body, method="POST", cookies=None):
        seen["body"] = body
        return {"data": {"list": [{}], "totalData": [{}]}}

    monkeypatch.setattr(alimama_cli, "_api_call", fake_api_call)

    ss_args = alimama_cli.build_parser().parse_args(["scene-summary", "--biz", "keyword"])
    alimama_cli.cmd_scene_summary(ss_args)
    assert seen["body"]["startTime"] == expected_start
    assert seen["body"]["endTime"] == expected_end

    seen.clear()
    sd_args = alimama_cli.build_parser().parse_args(["scene-daily", "--biz", "keyword"])
    alimama_cli.cmd_scene_daily(sd_args)
    assert seen["body"]["startTime"] == expected_start
    assert seen["body"]["endTime"] == expected_end


def test_scene_summary_warns_when_recent_days_not_settled(monkeypatch, capsys):
    def fake_fetch_scene_summary(biz_code, start, end, *, realtime=True, cookies=None):
        return {"data": {"list": [{"adPv": 1}]}}

    monkeypatch.setattr(alimama_cli, "fetch_scene_summary", fake_fetch_scene_summary)
    monkeypatch.setattr(alimama_cli, "load_alimama_cookies", lambda: {})

    end_date = (date.today() - timedelta(days=1)).isoformat()  # 距今 1 天，未出数
    args = alimama_cli.build_parser().parse_args(
        ["scene-summary", "--biz", "keyword", "--date", end_date, "--end-date", end_date]
    )
    alimama_cli.cmd_scene_summary(args)
    out = capsys.readouterr().out
    assert "⚠️ 最近2天自然流量列尚未出数（归因未完成）" in out


def test_report_fields_flag_replaces_default_query_field_in(monkeypatch):
    seen = {}

    def fake_api_call(path, body, method="POST", cookies=None):
        seen["body"] = body
        return {"data": {"list": [], "totalData": []}}

    monkeypatch.setattr(alimama_cli, "_api_call", fake_api_call)
    monkeypatch.setattr(alimama_cli, "load_alimama_cookies", lambda: {"x": "y"})

    args = alimama_cli.build_parser().parse_args(
        ["report-campaign", "--date", "2026-07-11", "--fields", "foo,charge"]
    )
    alimama_cli.cmd_report(args)
    assert seen["body"]["queryFieldIn"] == ["foo", "charge"]


def test_report_all_fields_flag_pulls_full_scope(monkeypatch):
    seen = {}

    def fake_api_call(path, body, method="POST", cookies=None):
        seen["body"] = body
        return {"data": {"list": [], "totalData": []}}

    monkeypatch.setattr(alimama_cli, "_api_call", fake_api_call)
    monkeypatch.setattr(alimama_cli, "load_alimama_cookies", lambda: {"x": "y"})

    args = alimama_cli.build_parser().parse_args(
        ["report-campaign", "--date", "2026-07-11", "--all-fields"]
    )
    alimama_cli.cmd_report(args)
    expected = {
        k for k, v in alimama_cli.FIELDS_DICT.items()
        if alimama_cli._scope_matches(v.get("scope"), "report-*")
    }
    assert expected  # 字典里确实有 report-* 字段
    assert expected <= set(seen["body"]["queryFieldIn"])


def test_report_fields_and_all_fields_are_mutually_exclusive():
    parser = alimama_cli.build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(
            ["report-campaign", "--date", "2026-07-11", "--fields", "foo",
             "--all-fields"]
        )


def test_report_unknown_field_prints_with_question_mark_suffix(monkeypatch, capsys):
    def fake_api_call(path, body, method="POST", cookies=None):
        return {"data": {"list": [{"foo": 1, "charge": 2.5}], "totalData": []}}

    monkeypatch.setattr(alimama_cli, "_api_call", fake_api_call)
    monkeypatch.setattr(alimama_cli, "load_alimama_cookies", lambda: {"x": "y"})

    args = alimama_cli.build_parser().parse_args(
        ["report-campaign", "--date", "2026-07-11", "--fields", "foo,charge"]
    )
    alimama_cli.cmd_report(args)
    out = capsys.readouterr().out
    assert "foo?" in out
    assert "花费" in out  # charge 是 verified 字段，用中文名


def test_report_without_fields_flags_behaves_unchanged(monkeypatch):
    seen = {}

    def fake_api_call(path, body, method="POST", cookies=None):
        seen["body"] = body
        return {"data": {"list": [], "totalData": []}}

    monkeypatch.setattr(alimama_cli, "_api_call", fake_api_call)
    monkeypatch.setattr(alimama_cli, "load_alimama_cookies", lambda: {"x": "y"})

    args = alimama_cli.build_parser().parse_args(
        ["report-campaign", "--date", "2026-07-11"]
    )
    alimama_cli.cmd_report(args)
    assert seen["body"]["queryFieldIn"] == list(alimama_cli.REPORT_METRICS.keys())


def test_report_custom_fields_error_falls_back_and_reports_rejected(monkeypatch):
    calls = []

    def fake_api_call(path, body, method="POST", cookies=None):
        calls.append(body["queryFieldIn"])
        if len(calls) == 1:
            raise RuntimeError("接口报错")
        return {"data": {"list": [], "totalData": []}}

    monkeypatch.setattr(alimama_cli, "_api_call", fake_api_call)
    monkeypatch.setattr(alimama_cli, "load_alimama_cookies", lambda: {"x": "y"})

    args = alimama_cli.build_parser().parse_args(
        ["report-campaign", "--date", "2026-07-11", "--fields", "notAField,charge"]
    )
    with pytest.raises(RuntimeError, match="字段不被接口接受"):
        alimama_cli.cmd_report(args)
    assert len(calls) == 2
    assert calls[1] == list(alimama_cli.REPORT_METRICS.keys())


def test_scene_summary_fields_flag_replaces_query_field_in(monkeypatch):
    seen = {}

    def fake_api_call(path, body, method="POST", cookies=None):
        seen["body"] = body
        return {"data": {"list": [{}]}}

    monkeypatch.setattr(alimama_cli, "_api_call", fake_api_call)
    monkeypatch.setattr(alimama_cli, "load_alimama_cookies", lambda: {"x": "y"})

    args = alimama_cli.build_parser().parse_args(
        ["scene-summary", "--biz", "keyword", "--fields", "foo,charge"]
    )
    alimama_cli.cmd_scene_summary(args)
    assert seen["body"]["queryFieldIn"] == ["foo", "charge"]


def test_scene_daily_fields_flag_replaces_query_field_in(monkeypatch):
    seen = {}

    def fake_api_call(path, body, method="POST", cookies=None):
        seen["body"] = body
        return {"data": {"list": [], "totalData": []}}

    monkeypatch.setattr(alimama_cli, "_api_call", fake_api_call)
    monkeypatch.setattr(alimama_cli, "load_alimama_cookies", lambda: {"x": "y"})

    args = alimama_cli.build_parser().parse_args(
        ["scene-daily", "--biz", "keyword", "--fields", "foo,charge"]
    )
    alimama_cli.cmd_scene_daily(args)
    assert seen["body"]["queryFieldIn"] == ["foo", "charge"]


def test_scene_summary_custom_fields_error_falls_back_and_reports_rejected(monkeypatch, capsys):
    """scene-summary 的字段拒绝 fallback 链路：自定义字段请求报错 → 默认白名单重发成功 →
    该场景的错误行里带"字段不被接口接受"提示，但不影响进程整体退出（逐场景 try/except）。

    cmd_scene_daily 复用同一个 fetch_with_field_fallback helper（见 alimama_cli.py 里
    cmd_scene_daily 的调用），行为与本测试一致，不再重复构造 Namespace 测一遍。
    """
    calls = []

    def fake_api_call(path, body, method="POST", cookies=None):
        calls.append(body["queryFieldIn"])
        if len(calls) == 1:
            raise RuntimeError("接口报错")
        return {"data": {"list": [{}]}}

    monkeypatch.setattr(alimama_cli, "_api_call", fake_api_call)
    monkeypatch.setattr(alimama_cli, "load_alimama_cookies", lambda: {"x": "y"})

    args = alimama_cli.build_parser().parse_args(
        ["scene-summary", "--biz", "keyword", "--fields", "foo,charge"]
    )
    alimama_cli.cmd_scene_summary(args)

    assert len(calls) == 2
    assert calls[1] == alimama_cli.SCENE_SUMMARY_REQUEST_FIELDS
    captured = capsys.readouterr()
    assert "字段不被接口接受" in (captured.out + captured.err)


def test_scene_daily_warns_when_recent_days_not_settled(monkeypatch, capsys):
    def fake_fetch_scene_daily(biz_code, start, end, *, effect_window=15, cookies=None):
        return {"data": {"list": [{"thedate": end, "charge": 1.0}], "totalData": [{"charge": 1.0}]}}

    monkeypatch.setattr(alimama_cli, "fetch_scene_daily", fake_fetch_scene_daily)
    monkeypatch.setattr(alimama_cli, "load_alimama_cookies", lambda: {})

    end_date = date.today().isoformat()  # 距今 0 天，未出数
    args = alimama_cli.build_parser().parse_args(
        ["scene-daily", "--biz", "keyword", "--date", end_date, "--end-date", end_date]
    )
    alimama_cli.cmd_scene_daily(args)
    out = capsys.readouterr().out
    assert "⚠️ 最近2天自然流量列尚未出数（归因未完成）" in out


def test_chrome_cookie_file_uses_env_profile(monkeypatch):
    monkeypatch.setenv("ALIMAMA_CHROME_PROFILE", "Profile 1")
    path = alimama_cli._chrome_cookie_file()
    assert path is not None
    assert "Profile 1/Cookies" in path


def test_chrome_cookie_file_none_when_unset(monkeypatch):
    monkeypatch.delenv("ALIMAMA_CHROME_PROFILE", raising=False)
    assert alimama_cli._chrome_cookie_file() is None


def test_load_alimama_cookies_passes_profile_cookie_file(monkeypatch):
    monkeypatch.setenv("ALIMAMA_CHROME_PROFILE", "Profile 1")
    seen = {}

    def fake_chrome(domain_name=None, cookie_file=None):
        seen["domain_name"] = domain_name
        seen["cookie_file"] = cookie_file
        return []

    monkeypatch.setattr(alimama_cli.browser_cookie3, "chrome", fake_chrome)
    with pytest.raises(RuntimeError, match="未找到阿里妈妈登录态"):
        alimama_cli.load_alimama_cookies()
    assert seen["cookie_file"] is not None
    assert "Profile 1/Cookies" in seen["cookie_file"]


def test_load_alimama_cookies_no_cookie_file_when_unset(monkeypatch):
    monkeypatch.delenv("ALIMAMA_CHROME_PROFILE", raising=False)
    seen = {}

    def fake_chrome(domain_name=None, cookie_file=None):
        seen["cookie_file"] = cookie_file
        return []

    monkeypatch.setattr(alimama_cli.browser_cookie3, "chrome", fake_chrome)
    with pytest.raises(RuntimeError):
        alimama_cli.load_alimama_cookies()
    assert seen["cookie_file"] is None
