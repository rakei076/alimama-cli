# 万相台 alimama-cli

![License](https://img.shields.io/github/license/rakei076/alimama-cli)
![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![Stars](https://img.shields.io/github/stars/rakei076/alimama-cli?style=social)
![Last Commit](https://img.shields.io/github/last-commit/rakei076/alimama-cli)

> 本 Skill 作者：Rakel · 个人网站：https://rakel.top

让你的 AI 直接读自家店铺的万相台（阿里妈妈）广告数据：花费、投产、计划、单元、关键词、人群、商品报表，看清广告钱花在哪、哪些在浪费。全部只读，在你自己的电脑上运行，用你浏览器里已经登录的账号。

## 两条规矩

- **只查你自己的店。** 用的是你自己的登录，拿不到也不该拿别人家的数据。
- **全程只读。** 不建计划、不调价、不开关、不删除；本工具没有任何改动广告的功能，名字像写操作的接口一律拒绝调用。

## 安装（约 5 分钟，只需一次）

1. **装 Python 运行环境。** 推荐装 [uv](https://docs.astral.sh/uv/)：Mac 运行 `brew install uv`；Windows 在 PowerShell 里运行 `powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"`，然后重开终端。也可以直接用 Python 3.10 以上。
2. **装取数桥插件。** 见 [extension/README.md](extension/README.md)，约 2 分钟。插件是共用的，别的店铺数据工具装过就不用再装。Windows 必须装；Mac 可以不装，不装就直接读 Chrome 里的登录。
3. **登录。** 用 Chrome 打开 <https://one.alimama.com> 登录，保持登录。子账号要有万相台的权限。
4. **自检。** 运行 `scripts/alimama.sh doctor`（Windows：`scripts\alimama.cmd doctor`），看到 `checkAccess 通过` 就装好了。
5. **交给 AI。** 把整个文件夹放进 AI 助手的 Skill 目录（Claude Code 是 `~/.claude/skills/alimama-cli`），然后直接对它说「看下昨天广告花了多少、哪些计划在亏」。

## 能让 AI 做什么

| 场景 | 它回答什么 |
|---|---|
| 昨天花了多少 | 各推广场景（关键词、人群、全站…）的花费和投产 |
| 哪些计划在亏 | 按计划、单元、关键词、人群、商品拆开，找出花钱多、成交少的 |
| 现在在投什么 | 当前在跑的计划、预算和出价 |
| 某个商品在哪推 | 一个宝贝散落在哪些计划里、各自开没开 |
| 大盘走势 | 某个推广场景按天的展现、点击、花费、成交、投产 |

## 命令

在本文件夹里运行（Windows 把 `scripts/alimama.sh` 换成 `scripts\alimama.cmd`）。加 `--help` 看每个命令的参数，加 `--raw` 拿原始 JSON，加 `--out 文件` 写进文件。报表类命令都能用 `--date --end-date` 指定日期，默认查昨天。

| 场景 | 命令 |
|---|---|
| 花费总览 | `charge-summary` `scene-summary` `scene-daily` |
| 报表（看历史） | `report-campaign` `report-adgroup` `report-keyword` `report-crowd` `report-item` `report-creative` `report-area` `report-coupon` `report-realtime` `report-other` |
| 在投（看现在） | `promo-wholesite` `promo-keyword` `promo-crowd` `promo-items` `promo-units` `campaign-list` |
| 账户 | `account-balance` `activity-list` |
| 工具 | `doctor` `api` |

还有 `keyword-effect` 和 `daily-report` 两个命令没有在真实账号上核实过，结果仅供参考。

字段中文名和口径统一取自 `tb/platforms/alimama/fields.json`。转化数据受归因窗口影响，用 `--window 1|7|15` 指定，默认 15 天。

## 安全护栏

**关于风控**：作者自己的店每天都在用。只要是正常范围内的查询，基本没遇到过风控；就算碰上，淘宝也只是弹一个验证提醒，在浏览器里过一下就好。

| 护栏 | 值 |
|---|---|
| 请求间隔 | 每两次请求之间随机停 1.8～3.5 秒 |
| 请求数提醒 | 一次跑到 200 个请求时提醒一次（不停）；要硬上限可设 `ALIMAMA_REQUEST_LIMIT` |
| 风控词 | 返回里出现「滑块 / 验证码 / 操作过于频繁 / 请重新登录 / 异常请求 / 风控 / 需要登录」立即停 |
| 写操作 | 没有任何写功能；插件也只放行逐个登记的查询接口 |

## 故障排查

| 现象 | 处理 |
|---|---|
| 提示没有登录、登录已失效（退出码 2） | 在 Chrome 里打开 one.alimama.com 重新登录，再运行 |
| 提示「子账号需要有权限」或「用于会话的 cookie 异常」 | 当前登录的子账号没有万相台权限，换有权限的账号登录 |
| 提示「没有连上浏览器插件」 | Chrome 要开着、插件要开着；插件每 30 秒检查一次，等一会儿再试。详见 [extension/README.md](extension/README.md) |
| 提示插件「太旧」或「文件夹不见了」 | 在 `chrome://extensions` 移除旧的取数桥，再加载本工具自带的 `extension/unpacked` |
| 提示触发风控（退出码 3） | 工具会先停下。在浏览器里正常打开万相台，按提示过一下验证，再运行就行 |
| 昨天的数据是空的 | 万相台凌晨还没出完昨天的数据，晚点再查，或用 `scene-summary` 看过去几天 |

## 更多工具

同一个作者还做了生意参谋、千牛、达摩盘、1688 订单统计、竞品评价洞察、广告诊断报告等店铺数据工具，都共用这一个取数插件，装一次就够。

介绍和获取方式：<https://rakel.top/tools/>

## 协议

MIT。仅供店铺经营者查询自家数据，请遵守平台规则。


## 联系作者

有想法、有需求，欢迎加微信找我，并注明来意。想要帮你装好、按你的需求定制，或者想用千牛、达摩盘等更多工具，也可以直接问。

- 微信：扫下方二维码加好友
- X / Twitter：[@Rakel076](https://x.com/Rakel076)

<p align="center">
  <img src="assets/wechat-qr.jpg" alt="WeChat QR" width="240">
</p>

如果这个工具帮到了你，欢迎给个 ⭐️。

---

## Star History

<a href="https://www.star-history.com/?repos=rakei076%2Fsycm-cli%2Crakei076%2Falimama-cli&type=date&legend=top-left">
 <picture>
   <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/chart?repos=rakei076/sycm-cli%2Crakei076/alimama-cli&type=date&theme=dark&legend=top-left&sealed_token=1C-YpKaGC2R31lIvkjjJxJ5-Nic1CJuUI18K8ttteBZoy0ktTZ7ZtH4Das9FbfclXR8d63D7McC7DbIABoPlfFEPPVjrG29Nvo56crqx6KT53wxcUbu8e8qMMgoYWjZC7fTkPi4X5H4u7liA8fp2zUmmQ-c4CABvtjksi6k69cEhKOTppTM48U7VLkac" />
   <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/chart?repos=rakei076/sycm-cli%2Crakei076/alimama-cli&type=date&legend=top-left&sealed_token=1C-YpKaGC2R31lIvkjjJxJ5-Nic1CJuUI18K8ttteBZoy0ktTZ7ZtH4Das9FbfclXR8d63D7McC7DbIABoPlfFEPPVjrG29Nvo56crqx6KT53wxcUbu8e8qMMgoYWjZC7fTkPi4X5H4u7liA8fp2zUmmQ-c4CABvtjksi6k69cEhKOTppTM48U7VLkac" />
   <img alt="Star History Chart" src="https://api.star-history.com/chart?repos=rakei076/sycm-cli%2Crakei076/alimama-cli&type=date&legend=top-left&sealed_token=1C-YpKaGC2R31lIvkjjJxJ5-Nic1CJuUI18K8ttteBZoy0ktTZ7ZtH4Das9FbfclXR8d63D7McC7DbIABoPlfFEPPVjrG29Nvo56crqx6KT53wxcUbu8e8qMMgoYWjZC7fTkPi4X5H4u7liA8fp2zUmmQ-c4CABvtjksi6k69cEhKOTppTM48U7VLkac" />
 </picture>
</a>
