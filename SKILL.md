---
name: alimama-cli
version: "1.1.6"
description: alimama-cli 是一款查询万相台 AI 无界（one.alimama.com / 阿里妈妈 onebp）广告数据的只读命令行工具，可帮助 AI 助手用一行命令拉取自家店铺的广告推广数据，涵盖报表（11 种历史复盘）、推广（当前在投计划）、单元和商品的开关状态查询、场景大盘、账户余额和营销活动。全部只读，没有任何改动广告的功能。触发场景：用户提到「万相台」「阿里妈妈」「广告投放」「推广复盘」「推广计划」「onebp」「alimama」「广告效果」「广告花费」「ROI」「计划报表」「关键词推广」「人群推广」「货品全站推广」「营销场景报表」「广告数据」「广告诊断」等。
author: Rakel
homepage: https://rakel.top
tags:
  - taobao
  - alimama
  - advertising
  - ecommerce
  - cli
---

# 万相台 alimama-cli

alimama-cli 是一款查询万相台 AI 无界广告数据的只读命令行工具（CLI），供阿里妈妈广告主拉取自家店铺的广告数据。工具在用户的电脑上运行，使用用户在 Chrome 中已登录的万相台账号。工具**全部只读**：不新建计划、不调价、不切换投放开关、不删除，没有任何改动广告的功能。

> 本 Skill 作者：Rakel · 个人网站：https://rakel.top

## 快速开始

运行以下命令，检查登录状态并查看昨天的广告花费：

```bash
scripts/alimama.sh doctor            # 验证 cookie
scripts/alimama.sh charge-summary    # 看昨天广告花了多少
```

## 前提条件

- **Chrome 已登录万相台**：已在 Chrome 中登录 https://one.alimama.com，子账号需要有万相台权限。
- **取数方式（先看系统）**：Mac 不需要插件，工具直接读取 Chrome 中的登录状态；读不到登录且装了「taobao-cli 取数桥」插件时，自动改用插件。Windows 必须安装插件。无论哪个系统，取数都只用本工具的命令：不要用 AI 助手自带的浏览器（例如 Codex 内置浏览器）打开后台，也不要另写脚本抓取。
- **Codex 沙箱**：在 Codex 中一律用 MCP 工具取数，不要在终端里运行脚本——Codex 的沙箱默认不让联网、不让开本机端口，脚本会报「依赖下载失败」或「当前环境不允许在本机开端口」。MCP 还没接入时，请用户在自己打开的终端里运行 `mcp install`，再完全退出并重开 Codex。不要把「改成完全访问」当作解决办法（在 Windows 上有时不生效），不要自己另找运行环境，也不要改用你自带的浏览器取数。
- **已安装运行环境**：已安装 `uv`（推荐）或 Python 3.10 及以上版本。

## 首次使用

首次使用本 Skill 时，先按以下步骤完成检查。

1. **检查 MCP**：如果你的工具列表中已有 `shopdata-alimama` 的 doctor、commands、run、guide，说明 MCP 已接好，直接用这几个工具取数，不需要再运行下面的脚本。
   **注意**：在 Codex 中运行脚本时，如果提示「没有连上浏览器插件」，且原因是沙箱拦截了本机端口，请用户在终端运行 `scripts/alimama.sh mcp install`（Windows：`scripts\alimama.cmd mcp install`），重新打开 Codex 后改用 MCP 工具。不要改用你自带的浏览器取数。
2. **运行自检**：运行 `scripts/alimama.sh doctor`（Windows：`scripts\alimama.cmd doctor`）。看到 `checkAccess 通过` 即表示安装完成，跳到下一节。
3. **安装插件（Windows 必做；Mac 一般不用）**：如果提示「没有连上浏览器插件」或插件「太旧」，带用户按照 `extension/README.md` 安装插件：在 `chrome://extensions` 中打开「开发者模式」，点击「加载已解压的扩展程序」，选择本目录的 `extension/unpacked`，并把这个文件夹的完整路径告诉用户。如果其他工具已安装过插件且版本够新，无需重复安装。
4. **登录万相台**：如果提示未登录，或提示「子账号需要有权限」「用于会话的 cookie 异常」，请用户在同一个 Chrome 中用有万相台权限的账号登录 one.alimama.com，然后再运行一次 doctor。看到 `checkAccess 通过` 即表示检查完成。
   **重要**：账号密码由用户自己输入，你不要代填。

## 区分报表与推广

万相台 AI 无界分为「报表」和「推广」两个模块。查询前先判断用户要的是历史数据还是当前在投状态，不要混淆两者。

```
万相台 AI 无界
├─ 📊 报表（看历史数据复盘）   → report-* 子命令 + charge-summary
└─ 🚀 推广（看当前在投的计划） → promo-* 子命令
```

| 对比项 | 报表 | 推广 |
|---|---|---|
| 时间范围 | **历史区间** | **当前快照** |
| 回答的问题 | 昨天或上周花了多少、ROI 多少、哪些转化好 | 现在哪些计划在跑、出价多少、日预算多少 |
| 接口 | `/report/query.json`（带 startTime/endTime） | `/campaign/horizontal/findPage.json`（无日期） |
| 用户问「昨天花了多少」 | 使用 | 不使用 |
| 用户问「现在在投哪些关键词」 | 不使用 | 使用 |

## 命令列表

以下命令全部只读。

### 工具与账户类

| 命令 | 用途 |
|---|---|
| `doctor` | 检查 cookie 和登录状态 |
| `account-balance` | 账户余额（实时） |
| `activity-list` | 营销活动列表 |
| `campaign-list` | 推广计划清单（仅含 ID 和名称，无业务数据） |
| `api <path>` | 通用接口探测，用于调试，AI 助手一般不调用 |

### 报表类

报表类命令用于查看历史数据。每个命令都接受以下参数：`--date YYYY-MM-DD --end-date YYYY-MM-DD --limit N --window 1|7|15 --raw --out file`。

| 命令 | 对应万相台页面 | 用途 |
|---|---|---|
| `charge-summary` | 营销场景报表 | **总览**：各推广场景（关键词推广、人群推广）分别花了多少 |
| `scene-summary` | 场景大盘（大屏） | **某个场景的大盘汇总**：展现量（adPv）、点击、花费、成交、ROI、加购、转化，默认过去 14 天，用 `--biz` 选择场景 |
| `scene-daily` | 营销场景报表 → 分日详情 | **某个场景按天**的展现、点击、花费、点击率、成交额、笔数、转化率、ROI 时序（含合计行），默认过去 14 天，用 `--biz` 选择场景，用 `--window 1\|7\|15` 指定转化窗口 |
| `report-campaign` | 计划报表 | 按每个推广计划查看花费和 ROI |
| `report-adgroup` | 单元报表 | 按计划下的单元查看 |
| `report-keyword` | 关键词报表 | 按每个关键词查看，找出高 ROI 的词加价、低 ROI 的词削减 |
| `report-crowd` | 人群报表 | 按每个定向人群查看转化率 |
| `report-item` | 商品报表 | 按每个被推广的商品查看 |
| `report-creative` | 创意报表 | 按每个广告图、视频或标题查看点击率 |
| `report-area` | 地域报表 | 按客户所在城市查看 |
| `report-coupon` | 权益报表 | 查看优惠券效果 |
| `report-realtime` | 实时报表 | 查看今天截至目前的实时数据（按小时） |
| `report-other` | 其他推广报表 | 其他杂项 |

### 推广类

推广类命令用于查看当前在投的计划，**不需要日期**。每个命令都接受以下参数：`--limit N --page N --status start pause --raw --out file`。

| 命令 | bizCode | 用途 |
|---|---|---|
| `promo-wholesite` | onebpSite | 货品全站推广：当前在跑的计划 |
| `promo-keyword` | onebpSearch | 关键词推广：当前在跑的计划 |
| `promo-crowd` | onebpDisplay | 人群推广：当前在跑的计划 |

`promo-*` 还支持用 `--item <宝贝ID>` 反查这个宝贝在哪个计划里推广。

**`promo-items --campaign <计划ID>`**：列出一个计划中的**全部商品及每个商品的开关状态**。测款计划这类一个计划包含多个商品的场景必须使用。可用 `--biz` 限定玩法，默认自动搜索全部玩法。开关状态取自单元的 `onlineStatus`（1=开，0=关）。标题显示为「商品已删除/下架」时，表示广告开着但宝贝已不存在，应清理。

**`promo-units`**：把所有计划的**全部单元（即商品广告位）展平成一张表**，相当于网页上的「单元 Tab」。参数如下：

- **`--biz`**：限定玩法，默认扫描全部 3 种。
- **`--item <宝贝ID>`**：反查**某个商品分布在哪些计划中，以及各自的开关状态**。一个商品常被加入多个计划，在每个计划中都算一个独立的单元，各有开关。
- **`--unit <单元ID>`**：按单元 ID 精确定位一个单元。

**`--item` 和 `--unit` 都使用服务端过滤，不会全量拉回后再筛选，命中即停。**

## 按问题选择命令

根据用户的问题选择要调用的命令：

| 用户的问题 | 调用 |
|---|---|
| 「看昨天广告花了多少」「昨天的 ROI」 | `charge-summary --date YYYY-MM-DD` |
| 「哪些计划最赚钱」「ROI 最高的计划」 | `report-campaign --date X --end-date Y --limit 10` |
| 「哪些关键词在浪费钱」 | `report-keyword --date X --raw`，然后用 jq 过滤 `charge>5 and alipayInshopAmt==0` |
| 「现在关键词推广有多少计划在跑」 | `promo-keyword` |
| 「看货品全站推广现在的状况」 | `promo-wholesite` |
| 「宝贝 XXX 现在在哪个全站/关键词/人群计划里推」 | `promo-wholesite --item XXX`（自动翻遍全部页面反查，命中时显示计划 ID、预算、出价和状态） |
| 「计划 XXX 里有哪些商品」「哪个开哪个关」 | `promo-items --campaign XXX` |
| 「宝贝 XXX 散在哪些计划里」「各自开关」 | `promo-units --item XXX`（服务端过滤；三种玩法的结果都准确，包括关键词推广） |
| 「单元 XXX 是什么」「看某个单元 ID 的信息」 | `promo-units --unit XXX`（服务端精确定位，命中即停） |
| 「把所有计划的单元拉平成一张表看」 | `promo-units`（相当于网页上的「单元 Tab」） |
| 「人群/关键词推广的展现量/点击/花费/ROI 大盘」 | `scene-summary [--biz crowd]`（默认过去 14 天，展现量即 adPv） |
| 「关键词推广这几天每天花费/ROI 怎么走的」「某场景分日趋势」 | `scene-daily --biz keyword --date X --end-date Y`（按天时序，含合计行） |
| 「看哪个人群转化好」 | `report-crowd --date X --end-date Y` |
| 「看每个商品的广告效果」 | `report-item` |
| 「看哪个城市出单多」 | `report-area` |
| 「看实时数据」 | `report-realtime` |
| 「账户还剩多少钱」 | `account-balance` |
| 报错或验证环境 | `doctor` |

**`--date` 默认为昨天**，以免今天的数据不完整。

## 报表类输出格式

将报表输出交给 LLM 分析时，参考以下格式。

`charge-summary` 输出格式化文本，加 `--raw` 输出 JSON：

```json
{
  "data": {
    "totalCharge": 12345.67,
    "searchCharge": 6789.01,
    "displayCharge": 5556.66,
    "contentSceneCharge": 0,
    "activitySceneCharge": 0,
    "crowdSceneCharge": 0,
    "shopSceneCharge": 0,
    "itemSceneCharge": 0,
    "siteSceneCharge": 0,
    "agencySceneCharge": 0
  }
}
```

`report-*` 的输出格式：

```json
{
  "data": {
    "count": 57,
    "totalData": {"charge": 1234.56, "alipayInshopAmt": 8888.88, "roi": 7.20},
    "list": [
      {
        "campaignId": 0,
        "promotionName": "<计划名>",
        "charge": 100.00,
        "alipayInshopAmt": 1000.00,
        "roi": 10.00,
        "click": 200,
        "ctr": 0.040,
        "ecpc": 0.50,
        "cvr": 0.010,
        "cartRate": 0.05,
        "alipayInshopNum": 5
      }
    ]
  }
}
```

**完整指标（queryFieldIn）**：从 v0.10 起包含 `adPv`（展现量），报表输出已带「展现」列。

| 字段 | 含义 |
|---|---|
| `adPv` | 展现量 |
| `charge` | 花费 |
| `click` | 点击量 |
| `ctr` | 点击率 |
| `ecpc` | 平均点击花费 |
| `alipayInshopAmt` | 成交金额 |
| `alipayInshopNum` | 成交笔数 |
| `alipayDirNum` | 直接成交单数 |
| `cartInshopNum` | 加购数 |
| `cvr` | 转化率 |
| `roi` | 投产比 |
| `cartRate` | 加购率 |
| `cartCost` | 加购成本 |
| `colCartCost` | 收藏加购成本 |
| `itemColCartCost` | 商品收藏加购成本 |
| `inshopPotentialUvRate` | 潜客率 |
| `newAlipayInshopUvRate` | 新成交客户率 |

不同 `report-X` 命令返回的每行数据中，**名称字段不同**：

| 命令 | 名称字段 |
|---|---|
| `report-campaign` | `promotionName` |
| `report-adgroup` | `adgroupName` |
| `report-keyword` | `originalWord` |
| `report-crowd` | `crowdName` |
| `report-item` | `itemTitle` |
| `report-creative` | `creativeName` |
| `report-area` | `provinceName` / `province` |

## 推广类输出格式

`promo-*` 的输出格式：

```json
{
  "data": {
    "count": 33,
    "list": [
      {
        "campaignId": 0,
        "campaignName": "<计划名>",
        "bizCode": "onebpSearch",
        "displayStatus": "start",
        "dayBudget": 260.0,
        "bidUnit": "平均点击成本${constraintValue}元",
        "constraintValue": 0.27,
        "bidTypeV2": "smart_bid",
        "launchPeriodDisplayTime": "18:30-19:00",
        "promotionType": "item",
        "topStatus": true,
        "gmtCreate": "2026-03-09 15:42:30"
      }
    ]
  }
}
```

**判断状态**：`displayStatus == "start"` 表示在投，`"pause"` 表示暂停。

## 接口说明

### 宝贝 ID 与计划的对应关系

以下是反查商品所在计划的关键信息。`findPage` 返回的顶层字段 `itemId` / `itemIdList` / `scopeItems` **恒为 null**。网页上能看到宝贝 ID，是因为请求体带了 `adgroupRequired:true`，服务端才会回填单元：

```
计划行.adgroupList[]              → 该计划下的所有单元（一计划可含多个单元）
计划行.adgroupList[i].material.materialId  → 宝贝 ID（lastAdgroup.material 兜底）
计划行.adgroupList[i].material.title       → 商品标题（被删/下架时为 null）
计划行.adgroupList[i].onlineStatus         → 单元开关：1=投放中 / 0=未投放
```

`_promo_item()` 取计划里的第一个商品，用于在投计划列表和 `--item` 反查。CLI 已默认带 `adgroupRequired:true`。`promo-items`、`promo-units` 使用下面的单元级接口。

### 单元级接口

查询单元和商品时，推荐使用单元级接口。

**`POST /adgroup/horizontal/findPage.json?bizCode=<X>`** 返回扁平的单元列表，每行是一个商品广告位。**三种玩法都直接返回 `material.materialId`（宝贝 ID）、`material.title`、`onlineStatus` 和 `campaignId/campaignName`**。

请求体为 `{bizCode, offset, pageSize, statusList:[start,pause,end], campaignId?, itemId?, adgroupId?}`。代码见 `fetch_all_adgroups()` 和 `_adgroup_unit()`，`promo-units`/`promo-items` 都使用这个接口。

请求体支持以下三个服务端过滤参数，默认优先使用，不要全量拉回客户端再筛选：

| body 参数 | 作用 | 实测 |
|---|---|---|
| `campaignId` | 只取某个计划下的单元 | `promo-items` 使用 |
| `itemId`（数字） | 只取某个宝贝 ID 的单元 | **返回该商品分布在各计划中的全部单元**（验证过 1 个商品命中 15 个单元）；`promo-units --item` 使用 |
| `adgroupId`（数字） | 精确定位某个单元 ID | count=1，命中即停；`promo-units --unit` 使用 |

**重要**：有 ID（计划、宝贝或单元）时一律使用服务端过滤，命中即停。不要把全量数据（关键词单元可能上千个）拉回客户端再过滤，这样慢且容易超时。只有用户要查看全表时才不带过滤参数。

**不使用「计划级 findPage + adgroupRequired」取单元的原因**：

| 玩法 | 计划级接口嵌套单元的 material | 单元级接口的 material | 备注 |
|---|---|---|---|
| 货品全站 onebpSite | 有宝贝 ID | 有宝贝 ID | 一个计划对应一个商品 |
| 人群推广 onebpDisplay | 有宝贝 ID | 有宝贝 ID | 一个计划包含多个商品；同一商品常被加入多个计划 |
| 关键词 onebpSearch | **恒为 null** | 有宝贝 ID | 计划级接口认不出商品，**必须使用单元级接口** |

- 计划级接口带 `adgroupRequired:true` 时，关键词推广的 **material 恒为 null**，而且单元数量很多（见过单个计划 266 个单元，总计 1848 个），响应体大，容易超时。因此**单元和商品查询一律使用单元级接口**，不要再用 adgroupRequired 取单元。
- 单个请求的超时时间默认为 30 秒，可用 `ALIMAMA_TIMEOUT` 覆盖。onebpSearch 服务端响应偏慢，`fetch_all_adgroups` 使用 pageSize=50。
- `_promo_item()`（计划级取单元）仅保留用于货品全站和人群推广快速取首图的场景。

### 场景大盘汇总

`scene-summary` 用于查询展现量等大盘指标。**展现量字段为 `adPv`**。各推广场景的大盘汇总使用 `POST /report/query.json`。**场景过滤依靠 URL 中的 `?bizCode=<scene>`；body 里的 bizCode 不生效，会返回全账户合计。**

```
URL : /report/query.json?bizCode=onebpDisplay&csrfId=<X>
body: {bizCode, byPage:false, fromRealTime:true, startTime, endTime,
       splitType:"sum", computeType:"sum", sourceList:["scene","adgroup_list"],
       queryDomains:[], queryFieldIn:[adPv,click,charge,ctr,ecpm,cvr,roi,...]}
```

- **实测结果**：人群推广（onebpDisplay）与关键词推广（onebpSearch）两个场景之和**等于全账户合计**（该店的货品全站推广大多处于暂停，约为 0）。
- **实时归因**：`fromRealTime:true` 表示实时归因，与网页一致；`false` 表示历史数据。**昨天的数据在凌晨可能尚未生成，因此默认查询过去 7 天**。
- **货品全站超时**：`onebpSite`（货品全站）的 sum 查询服务端偏慢，常在 30 秒时超时；命令已做优雅降级处理，此时显示 ⚠️。
- **代码与命令**：代码见 `fetch_scene_summary()` / `cmd_scene_summary`；命令格式为 `scene-summary [--biz] [--date --end-date] [--no-realtime]`。

## 字段字典与取数方法

从 v0.12 起，AI 助手取数以查字段字典为主，不必记忆命令。`tb/platforms/alimama/fields.json` 是机器可读的字段字典，每个条目为 `字段码 → {cn 中文名, scope 适用命令, fmt 格式, status, note 口径备注}`。

**标准取数流程**：

1. **读取字段字典**：先读 `fields.json`，找到需要的字段码及其 `note`（口径警告）。
2. **选列取数**：用 `--fields` 选择列，例如 `report-keyword --fields charge,roi,alipayInshopUv --date X --end-date Y`。需要字典中某个命令的全部字段时，使用 `--all-fields`。
3. **按需使用预设命令**：预设命令（`charge-summary`/`scene-summary` 等）是常用查询的快捷方式，并非唯一入口。

`status: candidate` 表示该字段的中文名尚未破译，使用前先验证。`note` 中的口径警告**必须遵守**，见下方「口径警告」。

### 口径警告

在结论中写入数据前，先阅读以下规则。

- **自然流量两列**（`naturalPayAmt`/`orgNaturalPv`）：**仅 T-2 之前的日期可信**，最新 1～2 天恒为 0，因为归因尚未完成。
- **单日成交和 ROI 在归因未完成时会偏低**：复盘时查询 7 天以上的区间（`scene-summary`/`scene-daily` 默认已是 14 天）。

**提示**：配套工具 **sycm-cli**（生意参谋店铺数据体检）同样提供 `fields.json` 字典。做广告与自然流量交叉复盘时，可以两个工具配合使用。

## 安全与风控

作者的店铺每天都在使用本工具。在正常查询范围内，基本不会触发风控；即使触发，淘宝也只会弹出验证提醒。

| 项目 | 默认值 | 触发后 |
|---|---|---|
| 请求间隔（随机抖动） | 1.8～3.5 秒 | 自动等待 |
| 累计请求提醒 | 200 次 | 提醒一次，**继续运行** |
| 可选硬上限 | 无（默认不启用） | 设置 `ALIMAMA_REQUEST_LIMIT=N` 后启用，达到 N 次时停止 |
| 风控关键词 | 「滑块」「验证码」「操作过于频繁」「请重新登录」「异常请求」「风控」「需要登录」 | 停止运行，退出码 3；请用户在浏览器中完成验证后再继续 |
| 写操作 | 名称像写操作的接口一律拒绝；插件只放行逐个登记的查询接口 | 拒绝调用 |

**风控按「短时高频」判定，与请求总量无关**。日常批量拉取报表没有问题。

## 调用示例

### 查看昨天的广告效果

用户问「昨天广告效果怎么样」时：

```bash
DATE=$(date -v-1d +%Y-%m-%d)
scripts/alimama.sh charge-summary --date $DATE --out /tmp/wxt-$DATE.json
scripts/alimama.sh report-campaign --date $DATE --limit 10 --out /tmp/wxt-camp-$DATE.json
# 然后读两个 JSON，告诉用户：总花费 / ROI / Top 3 计划 / Bottom 3 计划
```

### 查看在跑的关键词推广计划

用户问「现在哪些关键词推广计划在跑」时：

```bash
scripts/alimama.sh promo-keyword --limit 30 --out /tmp/promo-kw.json
# 读 JSON，告诉用户：共 N 个计划，X 个在投，Y 个暂停，前 5 个按预算
```

### 找出 ROI 低于 1 的在投计划

用户问「找出在投但 ROI < 1 的计划（赔本货）」时：

```bash
DATE=$(date -v-1d +%Y-%m-%d)
scripts/alimama.sh report-campaign --date $DATE --limit 100 --raw \
  | jq '[.data.list[] | select(.charge > 50 and .roi < 1)]'
```

## 常见问题

| 现象 | 原因 | 处理方法 |
|---|---|---|
| `doctor` 报未登录或登录失效 | Chrome 没有登录 one.alimama.com | 请用户在 Chrome 中打开 one.alimama.com 登录 |
| 提示「子账号需要有权限」或「用于会话的 cookie 异常」 | 当前账号没有万相台权限 | 换用有权限的账号登录 |
| 提示「没有连上浏览器插件」 | 插件未安装、已停用，或 Chrome 没有打开 | 按照 `extension/README.md` 安装插件；插件每 30 秒检查一次，请稍等后再试 |
| 提示插件「太旧」或「文件夹不见了」 | 安装的是旧版，或当初加载的文件夹已被删除 | 在 `chrome://extensions` 中移除旧版取数桥插件，再加载本目录的 `extension/unpacked` |
| Windows 报 `AppData\Roaming\uv\python: 拒绝访问` | AI 助手的沙箱只允许访问工作区 | 运行 `scripts\alimama.cmd doctor`；Python、依赖和运行数据都放在本目录的 `.runtime/` 中 |
| 任意命令返回 list:[] 但 count > 0 | 缺少关键参数（如 orderBy） | CLI 已内置正确参数，正常情况下不会遇到 |
| 提示触发风控（退出码 3） | 万相台弹出了验证 | 停止操作，请用户在浏览器中打开万相台完成验证，再继续 |

## 限制

- **只读**：只覆盖读取接口，创建、调价、开关、删除一律不做，以免误操作造成广告费损失。
- **推广类范围**：只支持关键词推广、人群推广和货品全站推广 3 种，店铺直选、内容营销、智惠券尚未支持。
- **字段可能为空**：部分行字段（如 `bidUnit`）服务端可能返回 None。CLI 已做处理，但不保证完全正确。
- **转化窗口**：不同的 `--window`（1/7/15 天）会影响转化数据，默认为 15 天。
