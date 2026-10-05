---
name: alimama-cli
description: 万相台 AI 无界（one.alimama.com / 阿里妈妈 onebp）只读数据查询 CLI。给 AI 代理一行命令拉取自家店铺的广告推广数据 — 涵盖"报表"(11 种历史复盘) + "推广"(当前在投计划) + 单元/商品开关查询 + 场景大盘 + 账户余额 / 营销活动。全部只读，没有任何改动广告的功能。触发场景：用户提到"万相台/阿里妈妈/广告投放/推广复盘/推广计划/onebp/alimama/广告效果/广告花费/ROI/计划报表/关键词推广/人群推广/货品全站推广/营销场景报表/广告数据/广告诊断"等。
author: Rakel
homepage: https://rakel.top
version: "0.12.0"
tags:
  - taobao
  - alimama
  - advertising
  - ecommerce
  - cli
---

# alimama-cli — 万相台 AI 无界 只读数据查询 CLI

> 本 Skill 作者：Rakel · 个人网站：https://rakel.top

## 一句话上手

```bash
scripts/alimama.sh doctor            # 验证 cookie
scripts/alimama.sh charge-summary    # 看昨天广告花了多少
```

## 适用人群

阿里妈妈广告主自己拉取自家店铺的广告数据。**全部只读**：不建计划、不调价、不开关、不删除，本工具没有任何改动广告的功能。

## 前置条件

- Chrome 已登录 https://one.alimama.com（子账号要有万相台权限）
- 已装取数桥插件（共用插件，别的店铺数据工具装过就不用再装）：Windows 必须；Mac 可选，不装就直接读 Chrome 的登录
- 已装 `uv`（推荐）或 Python 3.10+

## 首次使用（拿到这个 skill 后第一件事，AI 先做这个）

1. 运行 `scripts/alimama.sh doctor`（Windows：`scripts\alimama.cmd doctor`）。看到 `checkAccess 通过` 就装好了，跳到下一节。
2. 提示「没有连上浏览器插件」或插件「太旧」：带用户照 `extension/README.md` 装插件——`chrome://extensions` 打开开发者模式，「加载已解压的扩展程序」选本目录的 `extension/unpacked`（把这个文件夹的完整路径告诉用户）。别的工具装过、版本够新就不用再装。
3. 提示没登录，或「子账号需要有权限 / 用于会话的 cookie 异常」：请用户在同一个 Chrome 里用有万相台权限的账号登录 one.alimama.com（账号密码由用户自己输入，你不要代填），再运行一次 doctor。

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

## 全部子命令（全部只读）

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
| `scene-summary` | 场景大盘(大屏) | **某场景大盘汇总**：展现量(adPv)/点击/花费/成交/ROI/加购/转化，默认过去7天，`--biz` 选场景 |
| `scene-daily` | 营销场景报表→分日详情 | **某场景按天**的展现/点击/花费/点击率/成交额/笔数/转化率/ROI 时序（含合计行），默认过去7天，`--biz` 选场景，`--window 1\|7\|15` 转化窗口 |
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

**`promo-units`**：把所有计划的**全部单元(=商品广告位)拉平成一张表**，相当于网页的"单元 Tab"。`--biz` 限定玩法（默认扫全部 3 种）；`--item <宝贝ID>` 反查**某商品散落在哪些计划、各自开关**（一个商品常进多条计划，每条算一个独立单元各有开关）；`--unit <单元ID>` 按单元ID精确定位一条单元。**`--item` 和 `--unit` 都走服务端过滤（不全量拉回来再筛），命中即停。**

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
| "宝贝 XXX 散在哪些计划里 / 各自开关" | `promo-units --item XXX`（服务端过滤；三种玩法都准，含关键词推广） |
| "单元 XXX 是什么 / 看某个单元ID的信息" | `promo-units --unit XXX`（服务端精确定位，命中即停） |
| "把所有计划的单元拉平成一张表看" | `promo-units`（相当于网页"单元 Tab"） |
| "人群/关键词推广的展现量/点击/花费/ROI 大盘" | `scene-summary [--biz crowd]`（默认过去7天，展现量=adPv） |
| "关键词推广这几天每天花费/ROI 怎么走的" / "某场景分日趋势" | `scene-daily --biz keyword --date X --end-date Y`（按天时序 + 合计行） |
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

`report-*` 输出格式：

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

**完整指标 (queryFieldIn)**（v0.10 起含 `adPv` 展现量，报表输出已带"展现"列）：
`adPv`(展现量) / `charge`(花费) / `click`(点击量) / `ctr`(点击率) / `ecpc`(平均点击花费) / `alipayInshopAmt`(成交金额) / `alipayInshopNum`(成交笔数) / `alipayDirNum`(直接成交单数) / `cartInshopNum`(加购数) / `cvr`(转化率) / `roi`(投产比) / `cartRate`(加购率) / `cartCost`(加购成本) / `colCartCost`(收藏加购成本) / `itemColCartCost`(商品收藏加购成本) / `inshopPotentialUvRate`(潜客率) / `newAlipayInshopUvRate`(新成交客户率)

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

请求体：`{bizCode, offset, pageSize, statusList:[start,pause,end], campaignId?, itemId?, adgroupId?}`。代码见 `fetch_all_adgroups()` + `_adgroup_unit()`，`promo-units`/`promo-items` 都走它。

**三个服务端过滤参数（默认优先用，别再全量拉回客户端筛）**：
| body 参数 | 作用 | 实测 |
|---|---|---|
| `campaignId` | 只取某计划下的单元 | `promo-items` 用 |
| `itemId`（数字）| 只取某宝贝ID的单元 | **返回该商品散落各计划的全部单元**（验过 1 商品命中 15 单元）；`promo-units --item` 用 |
| `adgroupId`（数字）| 精确定位某个单元ID | count=1 命中即停；`promo-units --unit` 用 |

> ⚠️ 工作准则：**有 ID（计划/宝贝/单元）就走服务端过滤，命中即停；不要把全量(关键词单元上千)拉回客户端再 filter**——慢且易超时。仅当用户要"全表"才不带过滤。

**为什么不用"计划级 findPage + adgroupRequired"取单元**（踩过的坑）：

| 玩法 | 计划级嵌套单元 material | 单元级接口 material | 备注 |
|---|---|---|---|
| 货品全站 onebpSite | ✅ 有宝贝ID | ✅ | 一计划=一商品 |
| 人群推广 onebpDisplay | ✅ 有宝贝ID | ✅ | 一计划=多商品；同商品常进多计划 |
| 关键词 onebpSearch | **❌ 恒 null** | ✅ 有宝贝ID | 计划级认不出商品，**必须走单元级接口** |

- 计划级 `adgroupRequired:true` 对关键词推广 **material 恒 null**，且单元巨多（单计划见过 266/1848 总），响应体大易超时 → **单元/商品查询一律用单元级接口**，不要再用 adgroupRequired 取单元。
- 单请求超时默认 30s（`ALIMAMA_TIMEOUT` 可覆盖）；onebpSearch 服务端偏慢，`fetch_all_adgroups` 用 pageSize=50。
- `_promo_item()`/`_promo_all_items()`（计划级取单元）仅保留给货品全站/人群的快速取首图场景。

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

## 字段字典与发现方法论（v0.12+，AI 取数主力走这里）

**主力不是背命令，是查字典。** `tb/platforms/alimama/fields.json` 是机器可读字段字典，每条 = `字段码 → {cn 中文名, scope 适用命令, fmt 格式, status, note 口径备注}`。

**标准取数动线：**
1. **先读 `fields.json`** 找到要的字段码 + 它的 `note`（口径警告）
2. **用 `--fields` 选列取数**：`report-keyword --fields charge,roi,alipayInshopUv --date X --end-date Y`；想要字典里某命令的全部字段用 `--all-fields`
3. 预设命令（`charge-summary`/`scene-summary` 等）只是常用查询的快捷方式，不是唯一入口

`status: candidate` 的字段中文名尚未破译，用前先验证；`note` 里的口径警告**必须遵守**（见下方坑规矩）。

### 坑规矩（口径警告，写数前必看）

- **自然流量两列**（`naturalPayAmt`/`orgNaturalPv`）：**T-2 之前的日期才可信**，最新 1-2 天恒为 0（归因未完成）。
- **单日成交/ROI 归因未完成会偏低**：复盘查 7 天+区间（`scene-summary`/`scene-daily` 默认已 14 天）。

> 配套工具：**sycm-cli**（生意参谋店铺数据体检）同样有 `fields.json` 字典，广告×自然流量交叉复盘两个一起用。

---

## 安全护栏

作者自己的店每天都在用。只要是正常范围内的查询，基本没遇到过风控；就算碰上，淘宝也只是弹一个验证提醒。

| 项 | 默认值 | 触发后 |
|---|---|---|
| 请求间隔（随机抖动） | 1.8 ~ 3.5 秒 | 自动等待 |
| 累计请求提醒 | 200 次 | 提醒一次，**继续运行** |
| 可选硬上限 | 无（默认不启用）| 设 `ALIMAMA_REQUEST_LIMIT=N` 启用，达到 N 次停 |
| 风控关键词 | "滑块/验证码/操作过于频繁/请重新登录/异常请求/风控/需要登录" | 停下，退出码 3；请用户在浏览器里过一下验证再继续 |
| 写操作 | 名字像写操作的接口一律拒绝；插件只放行逐个登记的查询接口 | 拒绝调用 |

**风控按"短时高频"判定，不按总量** — 日常批量拉报表无问题。

---

## 典型 AI 代理调用示例

### 场景 1：用户问"昨天广告效果怎么样"

```bash
DATE=$(date -v-1d +%Y-%m-%d)
scripts/alimama.sh charge-summary --date $DATE --out /tmp/wxt-$DATE.json
scripts/alimama.sh report-campaign --date $DATE --limit 10 --out /tmp/wxt-camp-$DATE.json
# 然后读两个 JSON，告诉用户：总花费 / ROI / Top 3 计划 / Bottom 3 计划
```

### 场景 2：用户问"现在哪些关键词推广计划在跑"

```bash
scripts/alimama.sh promo-keyword --limit 30 --out /tmp/promo-kw.json
# 读 JSON，告诉用户：共 N 个计划，X 个在投，Y 个暂停，前 5 个按预算
```

### 场景 3：用户问"找出在投但 ROI < 1 的计划（赔本货）"

```bash
DATE=$(date -v-1d +%Y-%m-%d)
scripts/alimama.sh report-campaign --date $DATE --limit 100 --raw \
  | jq '[.data.list[] | select(.charge > 50 and .roi < 1)]'
```

---

## 故障排查

| 现象 | 原因 | 处理 |
|---|---|---|
| `doctor` 报未登录、登录失效 | Chrome 没登录 one.alimama.com | 请用户在 Chrome 打开 one.alimama.com 登录 |
| 「子账号需要有权限」/「用于会话的 cookie 异常」 | 当前账号没有万相台权限 | 换有权限的账号登录 |
| 「没有连上浏览器插件」 | 插件没装、被停用，或 Chrome 没开 | 照 `extension/README.md` 装好；插件每 30 秒检查一次，等一会儿再试 |
| 插件「太旧」或「文件夹不见了」 | 装的是旧版，或当初加载的文件夹被删了 | `chrome://extensions` 移除旧的取数桥，再加载本目录的 `extension/unpacked` |
| Windows 报 `AppData\Roaming\uv\python: 拒绝访问` | AI 沙箱只允许访问工作区 | 运行 `scripts\alimama.cmd doctor`；Python、依赖和运行数据都放在本目录的 `.runtime/` 里 |
| 任意子命令返回 list:[] 但 count > 0 | 缺关键参数（如 orderBy） | CLI 已内置正确参数，正常不会遇到 |
| 提示触发风控（退出码 3） | 万相台弹了验证 | 停下，请用户在浏览器里打开万相台过一下验证，再继续 |

## 局限性

- 只覆盖**读**接口；创建/调价/开关/删除一律不做（避免误操作烧钱）
- 推广类只做了 3 种（关键词/人群/全站），其他（店铺直选/内容营销/智惠券）未做
- 部分 row 字段（如 `bidUnit`）服务端可能返回 None，CLI 已处理但不保证完美
- 不同 `--window`（1/7/15 天）会影响转化数据，默认 15
