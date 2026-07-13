# alimama-cli

![License](https://img.shields.io/github/license/rakei076/alimama-cli)
![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![Stars](https://img.shields.io/github/stars/rakei076/alimama-cli?style=social)
![Last Commit](https://img.shields.io/github/last-commit/rakei076/alimama-cli)

万相台 AI 无界（`one.alimama.com` / 阿里妈妈 onebp）**数据查询 + 单元关停** CLI。

给 AI 代理一行命令拉取自家店铺的广告推广数据。**查询类全只读**；唯一写操作 `promo-off`（按宝贝ID关停在投单元）默认只列清单，必须 `--execute` 才执行，不调价/不删除/不新建。

---

> 💡 推荐：自己做了一个电商模特图生成站 [paitumao.com](https://paitumao.com)，
> 用的是目前最强的模特图生成模型，image-2 定价 ¥0.5/张，专门服务预算有限的小商家。
> 有需要的话加我微信聊，备注一下来意。

---

## 数据结构：每个推广场景都是「大盘 → 计划 → 商品」三层

三个推广场景（人群 / 关键词 / 货品全站）**结构完全一样**，只是 bizCode 不同。纵向看是三层，每层对应一个命令：

```
万相台 · 推广
│
├─ 👥 人群推广 (onebpDisplay)
│   ├─ 📊 大盘汇总(大屏) ───────► scene-summary --biz crowd
│   │      展现量·点击·点击率·花费·成交·ROI·加购·转化   (默认过去7天)
│   ├─ 📋 计划层 (campaign) ────► promo-crowd        (+ --item 反查宝贝在哪些计划)
│   │      每条计划: 预算·出价·状态·计划名
│   │      └─ 🔹 商品/单元层 (adgroup) ──► promo-items --campaign <计划ID>
│   │             每个商品: 宝贝ID·标题·开关(onlineStatus)   promo-units [--item <宝贝ID> | --unit <单元ID>]
│   │             （一计划多商品；同商品又散在多条计划）
│   │             └─ ⚙️ 关停 ──► promo-off --item <宝贝ID> [--execute]   ← 唯一写操作
│   └─ 📈 历史报表(按维度复盘) ─► report-crowd / report-campaign / report-item ...
│
├─ 🔑 关键词推广 (onebpSearch) ── 同三层：scene-summary/promo-keyword/promo-units/report-keyword
├─ 🛒 货品全站推广 (onebpSite) ── 同三层（特点：一计划=一商品）
└─ （店铺直选 / 内容营销 / 活动专属：暂未支持）
```

> **大盘对应场景总账，计划管理预算出价，商品层管理开关，最底层为单个商品的关停操作。**
> 三个场景的大盘数据之和等于全账户合计（已验证一致）。

### 📊 报表模块

接口 `POST /report/query.json`（一个接口，`rptType` 区分维度）。每个报表含**展现量/花费/成交/ROI/点击/CTR**等：

| 报表 | 命令 | rptType |
|---|---|---|
| 营销场景花费 | `charge-summary` | (chargeSum) |
| 计划 / 单元 / 关键词 / 人群 / 商品 / 创意 / 地域 / 权益 / 实时 / 其他 | `report-campaign` … `report-other` | campaign/adgroup/bidword/crowd/item_promotion/creative/area/coupon/real_time/other |

### 🔧 账户/工具

`doctor`(cookie自检) · `account-balance`(余额) · `activity-list` · `campaign-list` · `api`(通用探测)

---

## "报表" 与 "推广" 的区别

| 维度 | 📊 报表 | 🚀 推广 |
|---|---|---|
| 时间范围 | **历史数据** | **当前快照** |
| 关注点 | 昨天/上周花费、ROI、关键词转化情况 | 当前在跑的计划、出价、日预算 |
| 示例 | "上周关键词推广花了 ¥X,XXX" | "当前关键词推广有 N 个计划在跑，最大日预算 ¥XXX" |
| 接口 | `/report/query.json`（含时间窗口参数） | `/campaign/horizontal/findPage.json`（无日期，查当前状态） |
| 操作类型 | 查看数据 | 查看配置 |

**典型使用场景**：
1. 查看昨日报表，了解花费与 ROI
2. 查看当前推广列表，判断计划是否需要调整

---

## 装机

```bash
git clone git@github.com:rakei076/alimama-cli.git ~/.claude/skills/alimama-cli
# 装 uv（如未装）：
curl -LsSf https://astral.sh/uv/install.sh | sh
# 验证：
~/.claude/skills/alimama-cli/scripts/alimama.sh doctor
```

前置条件：macOS 本机 Chrome 已登录 one.alimama.com；Windows 首次运行会自动打开一个专用 Chrome/Edge 窗口，只需登录一次，后续自动复用。

Windows 可直接运行：

```bat
scripts\alimama.cmd doctor
```

启动脚本会优先使用 `uv`；否则使用 Python 3，并在首次运行时自动安装缺少的依赖。Windows 下 Python、依赖缓存和专用浏览器 Profile 都保存在项目内的隐藏目录，因此也能在只允许访问工作区的 Codex/AI 沙箱中运行。

> `.runtime/` 含登录后的专用浏览器 Profile。它已加入 `.gitignore`，请勿提交、打包或分享该目录。

如果旧版本在受限环境中报 `AppData\Roaming\uv\python: 拒绝访问`，更新后重新运行 `scripts\alimama.cmd doctor` 即可。

---

## 典型用法

### 1. 查看广告花费

```bash
~/.claude/skills/alimama-cli/scripts/alimama.sh charge-summary
```

输出：
```
# 万相台 推广花费汇总
# 区间: YYYY-MM-DD ~ YYYY-MM-DD
场景             花费(元)    占比
关键词推广     XX,XXX.XX  5X.X%
人群推广       XX,XXX.XX  4X.X%
总花费         XX,XXX.XX 100.0%
```

### 2. 查看各计划的投入产出比

```bash
~/.claude/skills/alimama-cli/scripts/alimama.sh report-campaign --limit 20
```

输出（按花费降序，含 ROI）：
```
#  名称                            花费    成交     ROI    点击    CTR
1  <计划 A 名字>              ¥XXX   ¥X,XXX  XX.XX   XXX   X.X%   🟢
2  <计划 B 名字>              ¥XXX   ¥X,XXX  XX.XX   XXX   X.X%   🟢
10 <计划 J 名字>              ¥XX    ¥0       0.00    XX   X.X%   🔴
```

### 3. 查看当前在投的关键词推广计划

```bash
~/.claude/skills/alimama-cli/scripts/alimama.sh promo-keyword --limit 10
```

输出：
```
[ 1] ⭐🟢 在投  campaignId=<示例 ID>
     计划名: <你的计划名>
     日预算: ¥XXX  出价: 平均点击成本X.XX元  类型: smart_bid
     投放时段: HH:MM-HH:MM    推广类型: item   创建: YYYY-MM-DD
...
```

### 4. 筛选高花费无转化的关键词

```bash
~/.claude/skills/alimama-cli/scripts/alimama.sh report-keyword --limit 50 --raw \
  | jq '[.data.list[] | select(.charge > 5 and .alipayInshopAmt == 0)]'
```

### 5. 查看货品全站推广在投商品

```bash
~/.claude/skills/alimama-cli/scripts/alimama.sh promo-wholesite --limit 20
```

---

## 全部子命令

| 子命令 | 类别 | 说明 |
|---|---|---|
| `doctor` | 工具 | 检查 cookie / 登录态 |
| `account-balance` | 账户 | 实时余额 |
| `activity-list` | 账户 | 营销活动列表 |
| `campaign-list` | 账户 | 全部计划名单（无业务数据，仅 ID+名字）|
| `api <path>` | 工具 | 通用接口探测 |
| `charge-summary` | 📊 报表 | 营销场景花费汇总 |
| `report-campaign` | 📊 报表 | 计划报表 |
| `report-adgroup` | 📊 报表 | 单元报表 |
| `report-keyword` | 📊 报表 | 关键词报表 |
| `report-crowd` | 📊 报表 | 人群报表 |
| `report-item` | 📊 报表 | 商品报表 |
| `report-creative` | 📊 报表 | 创意报表 |
| `report-area` | 📊 报表 | 地域报表 |
| `report-coupon` | 📊 报表 | 权益报表 |
| `report-realtime` | 📊 报表 | 实时报表 |
| `report-other` | 📊 报表 | 其他推广报表 |
| `scene-summary` | 📊 报表 | **场景大盘汇总**：展现量/点击/花费/成交/ROI（`--biz crowd/keyword/wholesite`，默认过去7天）|
| `promo-wholesite` | 🚀 推广 | 货品全站推广 - 当前计划（+ `--item` 反查）|
| `promo-keyword` | 🚀 推广 | 关键词推广 - 当前计划（+ `--item` 反查）|
| `promo-crowd` | 🚀 推广 | 人群推广 - 当前计划（+ `--item` 反查）|
| `promo-items` | 🚀 推广 | **单计划全部商品 + 各自开关**（`--campaign <计划ID>`）|
| `promo-units` | 🚀 推广 | **单元拉平表 / 按商品反查 / 按单元ID定位**（`--item <宝贝ID>`、`--unit <单元ID>`，均服务端过滤）|
| `promo-off` | ⚙️ **写** | **按宝贝ID关停在投单元**（默认 dry-run，`--execute` 才执行）|

**通用参数**：
- 报表类：`--date YYYY-MM-DD --end-date YYYY-MM-DD --limit N --window 1|7|15 --raw --out file`
- 推广类：`--limit N --page N --status start pause --raw --out file`；`promo-units` 支持 `--item`(宝贝ID) / `--unit`(单元ID)，`promo-items` 支持 `--campaign`（这些 ID 过滤都走服务端，不全量拉）
- `scene-summary`：`--biz` `--date` `--end-date` `--no-realtime`

---

## 安全护栏

**硬约束**（确认是风险信号才停）：
| 项 | 行为 |
|---|---|
| 风控关键词检测 | 响应含 `滑块 / 验证码 / 操作过于频繁 / 请重新登录` → 立即终止 |
| 连续失败立停 | 连续 2 次 HTTP 失败 → 立即终止 |
| 夜间禁跑 | 1:00 – 6:00 默认禁跑（调试设 `ALIMAMA_BYPASS_CURFEW=1`）|

**软建议**（不停止，只 stderr 提示）：
| 项 | 默认 |
|---|---|
| 请求间隔（随机抖动）| 1.8 ~ 3.5 秒 |
| 累计请求软警告点 | 200 次（只是提示点，不是上限）|
| 可选硬上限 | 设 `ALIMAMA_REQUEST_LIMIT=N` 启用（默认无上限）|

**风控按"短时高频"判定，不按"总量"**，日常批量拉数据没问题。

**读写边界**：
- ✅ 查询全只读：findPage / findList / report / query / chargeSum / checkRealBalance
- ⚙️ **唯一写操作 `promo-off`**：只调 `/adgroup/updatePart.json` 把单元设 `pause`（关）。默认 dry-run 只列清单；必须 `--execute` 才真发；执行前应把清单给用户确认。
- ❌ 不调价 / 不删除 / 不新建 / 不批量改预算出价

---

## 鉴权机制

- macOS：用 `browser_cookie3` 从本机 Chrome SQLite 直读 alimama.com 域 cookie
- Windows：自动启动独立 Profile 的 Chrome/Edge，通过本机 CDP 读取由浏览器解密后的 cookie，兼容新版 Chrome App-Bound Encryption
- Windows 首次登录后保存专用 Profile；以后命令自动连接现有浏览器，或在浏览器关闭后自动重新启动
- 不导出、不粘贴 cookie，不关闭 Chrome 安全保护，也不接管用户的默认浏览器 Profile
- 用 `curl_cffi` 伪 TLS 指纹（impersonate=chrome120）
- 万相台需要 CSRF：CLI 启动时自动 POST `/member/checkAccess.json` 拿 csrfId 缓存
- 所有 POST 自动注入 `?bizCode=universalBP&csrfId=xxx`

---

## License

MIT — © 2026


---

## 联系作者

有想法、有需求，欢迎加微信找我，并注明来意。

- 微信：扫下方二维码加好友
- X / Twitter：[@LuJia32473](https://x.com/LuJia32473)

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
