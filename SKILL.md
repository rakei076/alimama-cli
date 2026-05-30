---
name: alimama-cli
description: 万相台 AI 无界（one.alimama.com / 阿里妈妈 onebp）只读数据查询 CLI。给 AI 代理一行命令拉取自家店铺的广告推广数据，用于推广复盘、计划诊断、ROI 分析。触发场景：用户提到"万相台"、"阿里妈妈"、"广告投放"、"推广复盘"、"推广计划"、"onebp"、"alimama"、"广告效果"。
author: rakel
version: "0.1.0"
tags:
  - taobao
  - alimama
  - advertising
  - ecommerce
  - cli
---

# alimama-cli — 万相台 AI 无界 只读数据查询 CLI

**适用人群**：阿里妈妈广告主自己拉取自家店铺在万相台 AI 无界（one.alimama.com）的推广数据。

**前置条件**：
- macOS（已测试），Linux/Windows 理论可用
- 本地 Chrome 已登录 https://one.alimama.com
- 已装 `uv`（或 `pip` + Python 3.8+）

**只读保证**：本 CLI 永远不调用 add / update / delete / save / close 类接口，纯读。

## 一句话用法

```bash
~/.claude/skills/alimama-cli/scripts/alimama.sh campaign-list --date 2026-05-29 --limit 20
```

## 工作机制

参考 sycm-cli 的纯本地认证模型：

1. `browser_cookie3.chrome(domain_name='alimama.com')` 从本地 Chrome 直读 alimama 域 cookie
2. `curl_cffi` 伪 TLS 指纹（`impersonate='chrome120'`）直调万相台 API
3. **首次调 `/member/checkAccess.json` 自动拿 `csrfId` 并缓存到内存**（万相台强制 CSRF）
4. 每次请求 URL 自动注入 `?bizCode=universalBP&csrfId=xxx`

风控视角下和正常人工浏览没有区别。

## 子命令

| 子命令 | 用途 | 状态 |
|---|---|---|
| `doctor` | 检查 cookie / 登录态 | 已验证 |
| `campaign-list --date YYYY-MM-DD` | 推广计划列表（计划 ID / 名称 / 场景） | 已验证 |
| `activity-list` | 营销活动列表 | 已验证（接口可达） |
| `account-balance` | 账户余额 | 接口可达，返回 data=null（需账户活跃才有数据） |
| `keyword-effect --date YYYY-MM-DD` | 推广单元列表 | 未实测 |
| `daily-report --date YYYY-MM-DD` | 日维度花费汇总 | 未实测 |
| `api <path> [--body JSON]` | 通用 POST 接口探测 | 已验证 |

所有命令通用参数：`--limit N`、`--page N`、`--raw`、`--out file`。

## 通用 API 探测

```bash
alimama.sh api /member/checkAccess.json --body '{"bizCode":"universalBP"}'
alimama.sh api /report/campaign/findPage.json --body '{"pageNo":1,"pageSize":20,"startDate":"20260529","endDate":"20260529"}'
```

`bizCode` 和 `csrfId` 自动注入到 URL。

## 安全护栏（硬约束）

- 请求间隔随机 1.8 ~ 3.5 秒
- 单次运行最多 80 个请求
- 连续 2 次失败立即停止
- 响应含"滑块/验证码/操作过于频繁/请重新登录/风控"立即终止
- 夜间 1:00 – 6:00 禁跑（如必须：`ALIMAMA_BYPASS_CURFEW=1`）
- 触发风控直接退出码 2，**永远不重试**

## 反编译笔记（接口情报）

接口来源：`https://g.alicdn.com/mm/onebp/` bundle 反编译（公开 CDN）。

**鉴权机制**（关键，与生意参谋不同）：

```
POST https://one.alimama.com/<path>.json?bizCode=universalBP&csrfId=<csrfId>
Content-Type: application/json
Origin: https://one.alimama.com
Referer: https://one.alimama.com/index.html
X-Requested-With: XMLHttpRequest

<JSON body>
```

`csrfId` 必须先 POST `/member/checkAccess.json` body `{"bizCode":"universalBP"}` 拿到，从响应 `data.accessInfo.csrfId` 取，会话期内可复用。**没有动态 sign**，全 cookie + CSRF。

**已挖出的 1000+ 接口**（全在 onebp 同套鉴权下），重点只读类：

- `/account/checkRealBalance.json` — 账户余额
- `/activity/getActivityList.json` — 活动列表
- `/activity/lxkc/getCampaignInfoList.json` — 流星快车计划
- `/activity/lxkc/getDailyTrends.json` — 日趋势
- `/report/campaign/findPage.json` — 计划列表
- `/report/adgroup/findPage.json` — 单元列表
- `/report/chargeSum.json` — 花费汇总
- `/report/query.json` — 通用报表
- `/report/queryTotalCharge.json` — 总花费
- `/report/itemList.json` — 商品列表
- `/report/creativeList.json` — 创意列表
- `/adgroupocpc/report/getCiaDayList.json` — OCPC 日报
- `/liuzi/getAdPerformanceSummary.json` — 流转广告效果汇总
- `/liuzi/getAudienceTrackingSummary.json` — 人群跟踪汇总
- `/insight/promoteExplain/getItemPeriodTrend.json` — 商品周期趋势

完整接口列表见 README。

## 文件清单

- `alimama_cli.py` — 主 CLI
- `scripts/alimama.sh` — uv 包装入口
- `requirements.txt` — Python 依赖

## 局限性

- 接口列表里只验证了 4 个（doctor / activity-list / campaign-list / account-balance / api 通用），剩余 1000+ 接口需按需自行试错
- `csrfId` 是会话级的，本进程内只取一次，跨进程要重取
- `pageSize` 参数实测被服务端忽略（campaign-list 返回了全部 941 条）
- 万相台分子域 `ud.alimama.com / branding.alimama.com / dmp.taobao.com` 等需要不同的 host，本 CLI 只覆盖 `one.alimama.com`
