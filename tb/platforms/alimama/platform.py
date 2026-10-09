"""万相台 AI 无界（one.alimama.com）平台描述。读取接口全是 POST：走插件时只放行 bridge_posts 里逐个登记的查询接口；唯一写接口精确登记，且永不走插件。"""
import re

from ...core.platform import Platform
from . import session

try:
    from .promo_off import WRITE_PATHS   # 私人版才有；开源版导出时不带这个文件
except ImportError:
    WRITE_PATHS = ()

ALIMAMA = Platform(
    name="alimama",
    display="万相台",
    hosts={"main": "https://one.alimama.com"},
    login_page="https://one.alimama.com/index.html",
    launch_url="https://one.alimama.com/index.html",   # 用首页：robots.txt 经登录中转会被拦成 referer_forbidden；首页中转后回来，插件按域名确认落地
    # 登录态 cookie2/unb 住在 .taobao.com（阿里通用登录），.alimama.com 下只有 wk_ 前缀的同义版本，所以必须连 taobao 域一起读。
    login_cookies=("cookie2", "unb"),
    cookie_domains=("taobao.com", "tmall.com", "alimama.com", "one.alimama.com"),
    referer="https://one.alimama.com/index.html",
    expired_hints=(),
    # 读取通道拒绝的「动词前缀」：路径段以这些词开头（后接大写字母 / 下划线 / 点 / 斜杠 / 结尾）就是写操作，如 updatePart、deleteAll
    write_re=re.compile(r"(^|/)(add|create|update|delete|modify|save|remove|pause|start|stop|submit|set|cancel|batch|copy|upload|apply|bind|unbind)([A-Z_./]|$)"),
    env_prefix="ALIMAMA",
    risk_words=("滑块", "验证码", "操作过于频繁", "请重新登录", "异常请求", "风控", "需要登录"),
    delay=(1.8, 3.5),
    warn_after=200,
    allow_post=True,
    # 走插件时允许的只读查询接口（精确路径）；和插件 SITES 里万相台的 POSTS 一一对应，tests/test_extension_release.py 会核对
    bridge_posts=(
        "/member/checkAccess.json", "/account/checkRealBalance.json", "/activity/getActivityList.json",
        "/report/query.json", "/report/chargeSum.json", "/report/campaign/findPage.json", "/report/adgroup/findPage.json",
        "/campaign/horizontal/findPage.json", "/adgroup/horizontal/findPage.json",
    ),
    write_allow=WRITE_PATHS,   # 私人版：关停单元的写接口；不带 promo_off.py 时为空
    prepare=session.prepare,
    build_request=session.build_request,
    check_payload=session.check_payload,
)
