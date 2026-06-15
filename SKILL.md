---
name: alimama-cli
description: 万相台 AI 无界（one.alimama.com / 阿里妈妈 onebp）数据查询 + 单元关停 CLI。给 AI 代理一行命令拉取自家店铺的广告推广数据 — 涵盖"报表"(11 种历史复盘) + "推广"(3 种当前在投计划) + 单元/商品开关查询 + 账户余额 / 营销活动。查询类全只读；唯一写操作 promo-off（按宝贝ID关停在投单元）默认 dry-run，必须 --execute 才执行。触发场景：用户提到"万相台/阿里妈妈/广告投放/推广复盘/推广计划/onebp/alimama/广告效果/广告花费/ROI/计划报表/关键词推广/人群推广/货品全站推广/营销场景报表/广告数据/广告诊断/关停广告/关掉某商品"等。
author: rakel
version: "0.9.0"
tags:
  - taobao
  - alimama
  - advertising
  - ecommerce
  - cli
  - readonly
---

# alimama-cli — 万相台 AI 无界 只读数据查询 CLI

## 一句话上手

```bash
~/.claude/skills/alimama-cli/scripts/alimama.sh doctor            # 验证 cookie
~/.claude/skills/alimama-cli/scripts/alimama.sh charge-summary    # 看昨天广告花了多少
```

## 适用人群

阿里妈妈广告主自己拉取自家店铺数据 + 关停广告。**查询类全只读**；**唯一的写操作是 `promo-off`（按宝贝ID关停在投单元），默认只列清单不执行，必须显式 `--execute` 才动**，且不调价/不删除/不新建。

## 前置条件

- macOS（已测试），Linux/Windows 理论可用
- 本地 Chrome **已登录** https://one.alimama.com
- 已装 `uv`（推荐）或 `pip install browser-cookie3 curl-cffi`

---

## 重要：模块结构（**别再搞混 "报表" vs "推广"**）

```
万相台 AI 无界
├─ 📊 报表（看历史数据复盘）   → report-* 子命令 + charge-summary
└─ 🚀 推广（看当前在投的计划） → promo-* 子命令
```

| 维度 | 📊 报表 | 🚀 推广 |
|---|---|---|
| 时间 | **历史区间** | **当前快照** |
| 关心 | "昨天/上周花了多少、ROI 多少、谁转化好" | "现在哪些计划在跑、出价多少、日预算多少" |
| 接口 | `/report/query.json`（带 startTime/endTime）| `/campaign/horizontal/findPage.json`（无日期） |
| 用户问"昨天花了多少" | ✅ 用这个 | ❌ |
| 用户问"现在在投哪些关键词" | ❌ | ✅ 用这个 |

---

## 全部子命令（23 个，含 1 个写操作）

### 🔧 工具/账户类（5 个）

| 子命令 | 用途 |
|---|---|
| `doctor` | 检查 cookie / 登录态 |
| `account-balance` | 账户余额（实时） |
| `activity-list` | 营销活动列表 |
| `campaign-list` | 推广计划清单（仅 ID + 名字，无业务数据） |
| `api <path>` | 通用接口探测（debug 用，AI 代理一般不调） |

### 📊 报表类（11 个）—— 看历史数据

每个都接受：`--date YYYY-MM-DD --end-date YYYY-MM-DD --limit N --window 1|7|15 --raw --out file`

| 子命令 | 对应万相台页面 | 干嘛用 |
|---|---|---|
| `charge-summary` | 营销场景报表 | **总览**：各推广场景（关键词推广/人群推广）各花了多少 |
| `report-campaign` | 计划报表 | 按"每个推广计划"看花费 + ROI |
| `report-adgroup` | 单元报表 | 按"计划下的单元"看 |
| `report-keyword` | 关键词报表 | 按"每个关键词"看，找高 ROI 词加价/低 ROI 词砍 |
| `report-crowd` | 人群报表 | 按"每个定向人群"看转化率 |
| `report-item` | 商品报表 | 按"每个被推广的商品"看 |
| `report-creative` | 创意报表 | 按"每个广告图/视频/标题"看点击率 |
| `report-area` | 地域报表 | 按"客户城市"看 |
| `report-coupon` | 权益报表 | 优惠券效果 |
| `report-realtime` | 实时报表 | 今天到现在的实时数据（按小时） |
| `report-other` | 其他推广报表 | 杂项 |

### 🚀 推广类（3 个）—— 看当前在投

每个接受：`--limit N --page N --status start pause --raw --out file`（**不需要日期**）

| 子命令 | bizCode | 干嘛用 |
|---|---|---|
| `promo-wholesite` | onebpSite | 货品全站推广 - 当前在跑哪些计划 |
| `promo-keyword` | onebpSearch | 关键词推广 - 当前在跑哪些计划 |
| `promo-crowd` | onebpDisplay | 人群推广 - 当前在跑哪些计划 |

`promo-*` 还支持 `--item <宝贝ID>` 反查（这宝贝在哪个计划里推）。

**`promo-items --campaign <计划ID>`**：列出**一个计划里的全部商品 + 每个商品的开/关状态**（测款计划这类"一计划多商品"必用）。`--biz` 可限定玩法，默认自动搜全部。开关取自单元的 `onlineStatus`（1=开/0=关）；标题为"商品已删除/下架"=广告开着但宝贝没了，该清理。

**`promo-units`**：把所有计划的**全部单元(=商品广告位)拉平成一张表**，相当于网页的"单元 Tab"。`--biz` 限定玩法（默认扫全部 3 种）；`--item <宝贝ID>` 反查**某商品散落在哪些计划、各自开关**（这是"关掉某商品全部投放"的前置视图——一个商品常进多条计划，每条算一个独立单元各有开关）。

---

## AI 代理决策指南（用户说什么 → 调用什么）

| 用户问 | 调用 |
|---|---|
| "看昨天广告花了多少" / "昨天的 ROI" | `charge-summary --date YYYY-MM-DD` |
| "哪些计划最赚钱" / "ROI 最高的计划" | `report-campaign --date X --end-date Y --limit 10` |
| "哪些关键词在浪费钱" | `report-keyword --date X --raw` 然后 jq 过滤 `charge>5 and alipayInshopAmt==0` |
| "现在关键词推广有多少计划在跑" | `promo-keyword` |
| "看货品全站推广现在的状况" | `promo-wholesite` |
| "宝贝 XXX 现在在哪个全站/关键词/人群计划里推" | `promo-wholesite --item XXX`（自动翻全部页反查，命中显示计划ID/预算/出价/状态） |
| "计划 XXX 里有哪些商品 / 哪个开哪个关" | `promo-items --campaign XXX` |
| "宝贝 XXX 散在哪些计划里 / 各自开关" | `promo-units --item XXX`（三种玩法都准，含关键词推广） |
| "把所有计划的单元拉平成一张表看" | `promo-units`（相当于网页"单元 Tab"） |
| "把宝贝 XXX 的广告全关了" | ⚠️写：`promo-off --item XXX`（先看 dry-run 清单），确认后 `promo-off --item XXX --execute` |
| "人群/关键词推广的展现量/点击/花费/ROI 大盘" | `scene-summary [--biz crowd]`（默认过去7天，展现量=adPv） |
| "看哪个人群转化好" | `report-crowd --date X --end-date Y` |
| "看每个商品的广告效果" | `report-item` |
| "看哪个城市出单多" | `report-area` |
| "看实时数据" | `report-realtime` |
| "账户还剩多少钱" | `account-balance` |
| 报错或验证环境 | `doctor` |

**默认 `--date` 是昨天**（避免今天数据不全）。

---

## 报表类输出 schema（喂给 LLM 分析时用）

`charge-summary` 输出格式化文本，加 `--raw` 拿 JSON：

```json
{
  "data": {
    "totalCharge": 31634.39,
    "searchCharge": 16969.55,
    "displayCharge": 14664.84,
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

`report-*` 输出格式：

```json
{
  "data": {
    "count": 57,
    "totalData": {"charge": 1955.55, "alipayInshopAmt": 13923.89, "roi": 7.12},
    "list": [
      {
        "campaignId": 0,
        "promotionName": "<计划名>",
        "charge": 344.25,
        "alipayInshopAmt": 4107.33,
        "roi": 11.93,
        "click": 867,
        "ctr": 0.044,
        "ecpc": 0.40,
        "cvr": 0.012,
        "cartRate": 0.05,
        "alipayInshopNum": 8
      }
    ]
  }
}
```

**17 个完整指标 (queryFieldIn)**：
`charge`(花费) / `click`(点击量) / `ctr`(点击率) / `ecpc`(平均点击花费) / `alipayInshopAmt`(成交金额) / `alipayInshopNum`(成交笔数) / `alipayDirNum`(直接成交单数) / `cartInshopNum`(加购数) / `cvr`(转化率) / `roi`(投产比) / `cartRate`(加购率) / `cartCost`(加购成本) / `colCartCost`(收藏加购成本) / `itemColCartCost`(商品收藏加购成本) / `inshopPotentialUvRate`(潜客率) / `newAlipayInshopUvRate`(新成交客户率)

不同 `report-X` 子命令的 row 里**名称字段不同**：

| 子命令 | 名称字段 |
|---|---|
| `report-campaign` | `promotionName` |
| `report-adgroup` | `adgroupName` |
| `report-keyword` | `originalWord` |
| `report-crowd` | `crowdName` |
| `report-item` | `itemTitle` |
| `report-creative` | `creativeName` |
| `report-area` | `provinceName` / `province` |

## 推广类输出 schema

`promo-*` 输出：

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

判定状态：`displayStatus == "start"` 在投，`"pause"` 暂停。

### 宝贝 ID ↔ 计划 的对应（反查关键情报）

`findPage` 顶层的 `itemId` / `itemIdList` / `scopeItems` **恒为 null**，网页上能看到宝贝 ID 是因为请求体带了 `adgroupRequired:true`，服务端才回填单元：

```
计划行.adgroupList[]              → 该计划下的所有单元（一计划可含多个单元）
计划行.adgroupList[i].material.materialId  → 宝贝 ID（lastAdgroup.material 兜底）
计划行.adgroupList[i].material.title       → 商品标题（被删/下架时为 null）
计划行.adgroupList[i].onlineStatus         → 单元开关：1=投放中 / 0=未投放
```

`_promo_item()` 取第一个商品；`_promo_all_items()` 取全部单元 + 开关，供 `promo-items`/`promo-units` 用。CLI 已默认 `adgroupRequired:true`。

### 单元级接口（推荐用它做单元/商品查询）

**`POST /adgroup/horizontal/findPage.json?bizCode=<X>`** —— 扁平单元列表，每行一个商品广告位，**三种玩法都直接返回 `material.materialId`（宝贝ID）+ `material.title` + `onlineStatus` + `campaignId/campaignName`**。

请求体：`{bizCode, offset, pageSize, statusList:[start,pause,end], campaignId?}`。支持 `campaignId` 服务端过滤（拉单个计划的全部单元）。代码见 `fetch_all_adgroups()` + `_adgroup_unit()`，`promo-units`/`promo-items` 都走它。

**为什么不用"计划级 findPage + adgroupRequired"取单元**（踩过的坑）：

| 玩法 | 计划级嵌套单元 material | 单元级接口 material | 备注 |
|---|---|---|---|
| 货品全站 onebpSite | ✅ 有宝贝ID | ✅ | 一计划=一商品 |
| 人群推广 onebpDisplay | ✅ 有宝贝ID | ✅ | 一计划=多商品；同商品常进多计划 |
| 关键词 onebpSearch | **❌ 恒 null** | ✅ 有宝贝ID | 计划级认不出商品，**必须走单元级接口** |

- 计划级 `adgroupRequired:true` 对关键词推广 **material 恒 null**，且单元巨多（单计划见过 266/1848 总），响应体大易超时 → **单元/商品查询一律用单元级接口**，不要再用 adgroupRequired 取单元。
- 单请求超时默认 30s（`ALIMAMA_TIMEOUT` 可覆盖）；onebpSearch 服务端偏慢，`fetch_all_adgroups` 用 pageSize=50。
- `_promo_item()`/`_promo_all_items()`（计划级取单元）仅保留给货品全站/人群的快速取首图场景。

### 写接口：开关单元（`promo-off` 用）

**`POST /adgroup/updatePart.json?csrfId=<X>&bizCode=<biz>`** —— HAR 实测：
```
body: {"bizCode":"<biz>","adgroupList":[{"campaignId":<cid>,"adgroupId":<aid>,"displayStatus":"pause"}],"csrfId":"<X>"}
```
- `displayStatus`: `"pause"`=关（响应 `onlineStatus:0`） / `"start"`=开（`onlineStatus:1`）
- `adgroupList` 可一次传多个单元（同 bizCode 批量）
- 成功标志：响应 `data.errorCount == 0`
- `loginPointId` / `bx-v` 头：HAR 里有，但同源读接口不带也成 → **判定为可选埋点，CLI 省略**（首次实测确认）
- 代码：`set_adgroups_status()`；命令 `promo-off`（默认 dry-run，`--execute` 才真发）

**写操作铁律**：`promo-off` 默认只列清单不动；必须 `--execute` 才调写接口；AI 代理执行前必须把清单给用户确认。只关单元(pause)，不调价/不删/不新建。

### 场景大盘汇总（`scene-summary`）—— 展现量等大盘指标

**展现量字段 = `adPv`**。各推广场景的大盘汇总走 `POST /report/query.json`，**场景过滤靠 URL 的 `?bizCode=<scene>`（body 里的 bizCode 不生效，会返回全账户合计！）**：
```
URL : /report/query.json?bizCode=onebpDisplay&csrfId=<X>
body: {bizCode, byPage:false, fromRealTime:true, startTime, endTime,
       splitType:"sum", computeType:"sum", sourceList:["scene","adgroup_list"],
       queryDomains:[], queryFieldIn:[adPv,click,charge,ctr,ecpm,cvr,roi,...]}
```
- 实测：人群(onebpDisplay) + 关键词(onebpSearch) 两场景之和 **= 全账户合计**（货品全站该店多暂停≈0）。
- `fromRealTime:true`=实时归因(与网页一致)；`false`=历史。**昨天数据凌晨可能未出 → 默认查过去7天**。
- ⚠️ `onebpSite`(货品全站) 的 sum 查询服务端偏慢、常 30s 超时；命令已优雅降级显示 ⚠️。
- 代码 `fetch_scene_summary()` / `cmd_scene_summary`；命令 `scene-summary [--biz] [--date --end-date] [--no-realtime]`。

---

## 安全护栏

**硬约束**（真正的风险信号才停）：
| 项 | 默认值 | 触发后 |
|---|---|---|
| 连续失败次数上限 | 2 | 立即停，**不重试** |
| 风控关键词 | "滑块/验证码/操作过于频繁/请重新登录" | 抛 RiskTriggered 退出码 2 |
| 夜禁时段 | 1:00 – 6:00 | 阻止运行；`ALIMAMA_BYPASS_CURFEW=1` 可绕 |

**软建议**（不停止，只 stderr 提示）：
| 项 | 默认值 | 触发后 |
|---|---|---|
| 请求间隔（随机抖动） | 1.8 ~ 3.5 秒 | 自动等待 |
| 累计请求软警告点 | 200 次 | stderr 提醒一次，**继续运行** |
| 可选硬上限 | 无（默认不启用）| 设 `ALIMAMA_REQUEST_LIMIT=N` 启用，达到 N 次停 |

**风控按"短时高频"判定，不按总量** — 日常批量拉报表无问题。

**绝不调用任何含 add/create/modify/update/delete/save/batch 的接口**。

---

## 典型 AI 代理调用示例

### 场景 1：用户问"昨天广告效果怎么样"

```bash
DATE=$(date -v-1d +%Y-%m-%d)
~/.claude/skills/alimama-cli/scripts/alimama.sh charge-summary --date $DATE --out /tmp/wxt-$DATE.json
~/.claude/skills/alimama-cli/scripts/alimama.sh report-campaign --date $DATE --limit 10 --out /tmp/wxt-camp-$DATE.json
# 然后读两个 JSON，告诉用户：总花费 / ROI / Top 3 计划 / Bottom 3 计划
```

### 场景 2：用户问"现在哪些关键词推广计划在跑"

```bash
~/.claude/skills/alimama-cli/scripts/alimama.sh promo-keyword --limit 30 --out /tmp/promo-kw.json
# 读 JSON，告诉用户：共 N 个计划，X 个在投，Y 个暂停，前 5 个按预算
```

### 场景 3：用户问"找出在投但 ROI < 1 的计划（赔本货）"

```bash
DATE=$(date -v-1d +%Y-%m-%d)
~/.claude/skills/alimama-cli/scripts/alimama.sh report-campaign --date $DATE --limit 100 --raw \
  | jq '[.data.list[] | select(.charge > 50 and .roi < 1)]'
```

---

## 故障排查

| 现象 | 原因 | 处理 |
|---|---|---|
| `doctor` 报"未找到 alimama 登录态" | Chrome 没登录 one.alimama.com | 去 Chrome 打开 one.alimama.com 一次 |
| 任意子命令返回 list:[] 但 count > 0 | 缺关键参数（如 orderBy） | CLI 已内置正确参数，正常不会遇到 |
| `RiskTriggered: 滑块` | 触发风控 | **立即停 24 小时**，不要重试 |
| HTTP 5810 / "需要登录" | session 超时 | 去 Chrome 重新打开 one.alimama.com |
| 报错 "夜间禁跑" | 当前 1:00–6:00 | `ALIMAMA_BYPASS_CURFEW=1 alimama-cli ...` |

## 反编译笔记（接口情报）

来自 `https://g.alicdn.com/mm/onebp/<version>/onebp/merge.js` 和实际 HAR 抓包。

**统一鉴权**：
- Cookie 从本机 Chrome 直读
- 所有 POST 自动注入 URL `?bizCode=universalBP&csrfId=xxx`
- csrfId 启动时一次性 `POST /member/checkAccess.json` 拿，进程内缓存
- **无动态 sign，无 WASM 加密**（跟 sycm 同档简单）

**关键接口映射**：
- 报表通用入口：`POST /report/query.json` + `rptType` + `queryDomains`
- 营销场景汇总：`POST /report/chargeSum.json`
- 推广列表通用：`POST /campaign/horizontal/findPage.json?bizCode=X`

详细字段说明见 [README.md](README.md)（含完整模块树）。

---

## 局限性

- 只覆盖**读**接口；操作类（创建/调价/暂停）故意不做（避免误操作烧钱）
- 推广类只做了 3 种（关键词/人群/全站），其他（店铺直选/内容营销/智惠券）未做
- 部分 row 字段（如 `bidUnit`）服务端可能返回 None，CLI 已处理但不保证完美
- 不同 `--window`（1/7/15 天）会影响转化数据，默认 15
