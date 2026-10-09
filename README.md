# 万相台 alimama-cli

![License](https://img.shields.io/github/license/rakei076/alimama-cli)
![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![Stars](https://img.shields.io/github/stars/rakei076/alimama-cli?style=social)
![Last Commit](https://img.shields.io/github/last-commit/rakei076/alimama-cli)

alimama-cli 是一款读取万相台（阿里妈妈）广告数据的工具，可帮助你和 AI 助手查看花费、投产，以及计划、单元、关键词、人群和商品报表，看清广告费用花在哪里、哪些花费在浪费。工具在你的电脑上运行，使用你在 Chrome 中已登录的万相台账号。

> 本 Skill 作者：Rakel · 个人网站：https://rakel.top

## 使用须知

- **仅读取本店数据**：工具使用你的登录状态，只能读取当前登录店铺的数据，无法也不应读取其他店铺的数据。
- **只读访问**：工具不会新建计划、调价、切换投放开关或删除任何内容，没有任何改动广告的功能。名称像写操作的接口一律拒绝调用。

## 安装

安装约需 5 分钟，只需进行一次。

**在 Codex 里使用**：请用 MCP 接入（见下面「接入 AI 助手」一步），让 Codex 通过 MCP 取数，不要让它在终端里直接运行脚本。Codex 的沙箱默认不让联网、也不让在本机开端口，在终端里跑脚本，第一次装依赖和连插件都会被拦下；MCP 服务由 Codex 单独启动，不受这个限制。接入命令（`mcp install`）请在你自己打开的终端里运行一次（Windows 用 PowerShell 或命令提示符），然后完全退出 Codex 再打开。Codex 的「完全访问」在 Windows 上有时不生效，不要依赖它。

1. **安装 Python 运行环境**：推荐安装 [uv](https://docs.astral.sh/uv/)。Mac 运行 `brew install uv`；Windows 在 PowerShell 中运行 `powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"`，然后重新打开终端。也可以直接使用 Python 3.10 或更高版本。
2. **安装取数桥插件（只有 Windows 需要）**：
   - **Mac**：跳过这一步。工具直接读取你在 Chrome 中的登录状态，Chrome 里登录着就能用。
   - **Windows**：必须安装。Windows 版 Chrome 会加密登录状态，工具读不到，只能通过「taobao-cli 取数桥」插件取数。安装方法见 [extension/README.md](extension/README.md)，约需 2 分钟。插件由各店铺数据工具共用，为其他工具装过的不用再装。
3. **登录万相台**：在 Chrome 中打开 <https://one.alimama.com> 并登录，保持登录状态。使用子账号时，子账号需要有万相台权限。
4. **运行自检**：运行 `scripts/alimama.sh doctor`（Windows：`scripts\alimama.cmd doctor`）。看到 `checkAccess 通过` 即表示安装完成。
5. **接入 AI 助手**：运行 `scripts/alimama.sh mcp install`（Windows：`scripts\alimama.cmd mcp install`），将本工具通过 MCP 接入电脑上的 AI 助手（Claude Code、Codex、Cursor、Claude Desktop）。MCP 是让 AI 助手直接调用本工具的接口。重新打开 AI 助手后，对它说「看下昨天广告花了多少、哪些计划在亏」，看到 AI 助手返回广告数据即表示接入完成。

**提示**：也可以将整个文件夹放入 AI 助手的 Skill 目录（Claude Code 为 `~/.claude/skills/alimama-cli`）。

### Mac 和 Windows 的区别

| | Mac | Windows |
|---|---|---|
| 取数桥插件 | 不需要 | 必须安装 |
| 怎么读取数据 | 直接读取 Chrome 中的登录状态。读不到时（例如刚重启过 Chrome），如果装了插件，自动改用插件 | 只通过插件，在你已登录的 Chrome 中读取 |
| 命令 | `scripts/alimama.sh` | `scripts\alimama.cmd` |

两个系统都一样：在 Chrome 中登录要用的后台。工具读不到 AI 助手自带浏览器（例如 Codex 内置浏览器）里的登录，取数时也不要让 AI 助手改用它。

## 功能

你可以直接向 AI 助手提问，工具支持以下场景：

| 场景 | 说明 |
|---|---|
| 昨日花费 | 查看各推广场景（关键词、人群、全站等）的花费和投产 |
| 亏损计划排查 | 按计划、单元、关键词、人群和商品拆分数据，找出花费多、成交少的部分 |
| 在投计划 | 查看当前在投的计划、预算和出价 |
| 商品投放位置 | 查看一个商品分布在哪些计划中，以及在各计划中是否开启 |
| 场景趋势 | 查看某个推广场景按天的展现、点击、花费、成交和投产 |

## 命令参考

在本文件夹中运行命令。Windows 将 `scripts/alimama.sh` 替换为 `scripts\alimama.cmd`。常用参数如下：

| 参数 | 说明 |
|---|---|
| `--help` | 查看每个命令的参数 |
| `--raw` | 输出原始 JSON |
| `--out 文件` | 将结果写入文件 |
| `--date --end-date` | 指定日期，报表类命令均支持，默认查询昨天 |

命令按类别列出如下：

| 类别 | 命令 |
|---|---|
| 花费总览 | `charge-summary` `scene-summary` `scene-daily` |
| 报表（历史数据） | `report-campaign` `report-adgroup` `report-keyword` `report-crowd` `report-item` `report-creative` `report-area` `report-coupon` `report-realtime` `report-other` |
| 在投（当前状态） | `promo-wholesite` `promo-keyword` `promo-crowd` `promo-items` `promo-units` `campaign-list` |
| 账户 | `account-balance` `activity-list` |
| 工具 | `doctor` `api` |

**注意**：`keyword-effect` 和 `daily-report` 两个命令尚未在真实账号上验证，结果仅供参考。

字段中文名和口径统一取自 `tb/platforms/alimama/fields.json`。转化数据受归因窗口影响，用 `--window 1|7|15` 指定，默认 15 天。

## 安全与风控

作者的店铺每天都在使用本工具。在正常查询范围内，基本不会触发风控；即使触发，淘宝也只会弹出验证提醒，在浏览器中完成验证即可。

| 项目 | 说明 |
|---|---|
| 请求间隔 | 每两次请求之间随机等待 1.8～3.5 秒 |
| 请求数提醒 | 单次运行达到 200 个请求时提醒一次，不会停止。如需硬上限，可设置 `ALIMAMA_REQUEST_LIMIT` |
| 风控词 | 返回内容中出现「滑块」「验证码」「操作过于频繁」「请重新登录」「异常请求」「风控」「需要登录」时立即停止 |
| 写操作 | 工具没有任何写功能；插件也只放行逐个登记的查询接口 |

## 常见问题

| 现象 | 原因和处理方法 |
|---|---|
| 提示没有登录或登录已失效（退出码 2） | 在 Chrome 中打开 one.alimama.com 重新登录，然后再次运行 |
| 提示「子账号需要有权限」或「用于会话的 cookie 异常」 | 当前登录的子账号没有万相台权限，请换用有权限的账号登录 |
| 提示「没有连上浏览器插件」 | 确认 Chrome 和插件都已开启。插件每 30 秒检查一次，请稍等后再试。详见 [extension/README.md](extension/README.md) |
| 提示插件「太旧」或「文件夹不见了」 | 在 `chrome://extensions` 中移除旧版取数桥插件，再加载本工具自带的 `extension/unpacked` |
| 提示触发风控（退出码 3） | 工具会先停止运行。在浏览器中正常打开万相台，按提示完成验证，再重新运行 |
| 昨天的数据为空 | 万相台在凌晨尚未生成完昨天的数据，请稍后再查，或用 `scene-summary` 查看过去几天的数据 |

## 相关工具

作者还提供生意参谋、千牛、达摩盘、1688 订单统计、竞品评价洞察、广告诊断报告等店铺数据工具。这些工具共用同一个取数桥插件，安装一次即可。

工具介绍和获取方式见 <https://rakel.top/tools/>。

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
