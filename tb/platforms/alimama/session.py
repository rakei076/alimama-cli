"""万相台（one.alimama.com）的会话钩子：csrfId、每个请求的公共参数与浏览器同源头、业务检查。"""
from __future__ import annotations

from ...core.errors import ApiFailed, LoginExpired

BIZ_CODE = "universalBP"


def _headers(client) -> dict[str, str]:
    """伪装成浏览器同源 XHR，让服务端识别为页面自己的请求。"""
    h = {
        "Origin": client.platform.hosts["main"],
        "Sec-Fetch-Site": "same-origin", "Sec-Fetch-Mode": "cors", "Sec-Fetch-Dest": "empty",
        "X-Requested-With": "XMLHttpRequest",
    }
    xsrf = client.cookies.get("XSRF-TOKEN")
    if xsrf:
        h["X-XSRF-TOKEN"] = xsrf
    return h


def prepare(client) -> dict:
    """首次调用：POST /member/checkAccess.json 拿到 csrfId 并缓存（一次运行只取一次）。"""
    url = f"{client.platform.hosts['main']}/member/checkAccess.json"
    payload = client.send(url, {"bizCode": BIZ_CODE}, "main /member/checkAccess.json", _headers(client),
                          body={"bizCode": BIZ_CODE}, method="POST")
    csrf = ((payload.get("data") or {}).get("accessInfo") or {}).get("csrfId") if isinstance(payload, dict) else None
    if not csrf:
        raise LoginExpired("无法从 checkAccess 拿到 csrfId，登录状态不完整。", endpoint="main /member/checkAccess.json",
                           stage="登录检查", hint=client.login_hint)
    client.state["csrf"] = csrf
    return payload.get("data") or {}


def build_request(client, host: str, path: str, params: dict):
    query = dict(params)
    query.setdefault("bizCode", BIZ_CODE)
    query.setdefault("csrfId", client.state["csrf"])
    return client.platform.hosts[host] + path, query, _headers(client)


def check_payload(client, payload, resp, label: str) -> None:
    info = payload.get("info") if isinstance(payload, dict) else None
    if not isinstance(info, dict):
        return
    if info.get("ok") is False or info.get("errorCode"):
        raise ApiFailed(f"万相台业务失败 errorCode={info.get('errorCode')}: {info.get('message') or ''}",
                        endpoint=label, stage="平台返回")
