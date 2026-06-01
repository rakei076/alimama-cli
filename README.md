# alimama-cli

万相台 AI 无界（`one.alimama.com` / 阿里妈妈 onebp）**只读**数据查询 CLI。

给 AI 代理一行命令拉取自家店铺的广告推广数据 — 不会改/不会调价/不会建删计划。

---

## 万相台 完整模块树（**重要：理解结构再用**）

```
万相台 AI 无界 (one.alimama.com)
│
├─ 📊【报表】模块 (左侧"基础报表"折叠组) ─ 看历史数据复盘
│   │   接口：POST /report/query.json (一个接口，rptType 区分)
│   │   子命令前缀：report-*
│   │
│   ├─ 营销场景报表     → charge-summary   (用 /report/chargeSum.json)
│   ├─ 计划报表         → report-campaign  (rptType=campaign)
│   ├─ 单元报表         → report-adgroup   (rptType=adgroup)
│   ├─ 关键词报表       → report-keyword   (rptType=bidword)
│   ├─ 人群报表         → report-crowd     (rptType=crowd)
│   ├─ 商品报表         → report-item      (rptType=item_promotion)
│   ├─ 创意报表         → report-creative  (rptType=creative)
│   ├─ 地域报表         → report-area      (rptType=area)
│   ├─ 权益报表         → report-coupon    (rptType=coupon)
│   ├─ 实时报表         → report-realtime  (rptType=real_time)
│   └─ 其他推广报表     → report-other     (rptType=other_promotion)
│
├─ 🚀【推广】模块 (左侧"营销场景"折叠组) ─ 看/管"当前在投"的计划
│   │   接口：POST /campaign/horizontal/findPage.json?bizCode=X
│   │   子命令前缀：promo-*
│   │
│   ├─ 货品全站推广     → promo-wholesite  (bizCode=onebpSite)
│   ├─ 关键词推广       → promo-keyword    (bizCode=onebpSearch)
│   ├─ 人群推广         → promo-crowd      (bizCode=onebpDisplay)
│   ├─ 店铺直选         → ✗ 未做（用户没用这个）
│   ├─ 内容营销         → ✗ 未做（用户没用这个）
│   └─ 活动专属/智惠券  → ✗ 未做（活动期才用）
│
└─ 🔧 账户/工具类
    ├─ doctor          ─ 检查 cookie/登录态
    ├─ account-balance ─ 账户余额
    ├─ activity-list   ─ 营销活动列表
    ├─ campaign-list   ─ 推广计划清单（无数据，仅 ID+名字）
    └─ api <path>      ─ 通用接口探测（debug 用）
```

---

## "报表" vs "推广" 怎么区分？（别再搞混）

| 维度 | 📊 报表 | 🚀 推广 |
|---|---|---|
| 时间 | **历史数据** | **当前快照** |
| 关心 | "昨天/上周花了多少、ROI 多少、哪个关键词转化好" | "我现在哪些计划在跑、出价多少、日预算多少" |
| 例子 | "上周关键词推广花了 ¥16,969" | "现在关键词推广 33 个计划都在跑，最大日预算 ¥260" |
| 接口 | `/report/query.json` (有时间窗口参数) | `/campaign/horizontal/findPage.json` (无日期，看当前) |
| 操作类型 | 看数 | 看配置 |

**你日常的两件事**：
1. 早上看报表 → 昨天花了多少 ROI 多少
2. 看推广列表 → 哪些计划现在在跑，哪个该调

---

## 装机

```bash
git clone git@github.com:rakei076/alimama-cli.git ~/.claude/skills/alimama-cli
# 装 uv（如未装）：
curl -LsSf https://astral.sh/uv/install.sh | sh
# 验证：
~/.claude/skills/alimama-cli/scripts/alimama.sh doctor
```

前置条件：本机 Chrome 已登录 one.alimama.com（CLI 自动复用浏览器 cookie，不需要重新登录）。

---

## 典型用法（5 个最高频的）

### 1. 早上看广告花了多少（最常用）

```bash
~/.claude/skills/alimama-cli/scripts/alimama.sh charge-summary
```

输出：
```
# 万相台 推广花费汇总
# 区间: YYYY-MM-DD ~ YYYY-MM-DD
场景             花费(元)    占比
关键词推广     16,969.55  53.6%
人群推广       14,664.84  46.4%
总花费         31,634.39 100.0%
```

### 2. 看哪些计划在赚钱、哪些在赔钱

```bash
~/.claude/skills/alimama-cli/scripts/alimama.sh report-campaign --limit 20
```

输出（按花费降序，含 ROI）：
```
#  名称                            花费    成交     ROI    点击    CTR
1  <计划 A 名字>              ¥335   ¥6,330  18.90   817   6.4%   🟢
2  <计划 B 名字>              ¥344   ¥4,107  11.93   867   4.4%   🟢
10 <计划 J 名字>              ¥17    ¥0       0.00    37   4.7%   🔴
```

### 3. 看现在关键词推广有哪些计划在跑

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

### 4. 看哪个关键词花得多但不出单（要砍）

```bash
~/.claude/skills/alimama-cli/scripts/alimama.sh report-keyword --limit 50 --raw \
  | jq '[.data.list[] | select(.charge > 5 and .alipayInshopAmt == 0)]'
```

### 5. 看货品全站推广在投商品

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
| `promo-wholesite` | 🚀 推广 | 货品全站推广 - 当前计划 |
| `promo-keyword` | 🚀 推广 | 关键词推广 - 当前计划 |
| `promo-crowd` | 🚀 推广 | 人群推广 - 当前计划 |

**通用参数**：
- 报表类：`--date YYYY-MM-DD --end-date YYYY-MM-DD --limit N --window 1|7|15 --raw --out file`
- 推广类：`--limit N --page N --status start pause --raw --out file`

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

**只读，不写**：
- ✅ findPage / findList / report / query / chargeSum / checkRealBalance
- ❌ add / create / modify / update / delete / save / batch（绝对不调）

---

## 鉴权机制（技术细节）

- 不开新 Chrome，不用 CDP，不用 Playwright
- 用 `browser_cookie3` 从本机 Chrome SQLite 直读 alimama.com 域 cookie
- 用 `curl_cffi` 伪 TLS 指纹（impersonate=chrome120）
- 万相台需要 CSRF：CLI 启动时自动 POST `/member/checkAccess.json` 拿 csrfId 缓存
- 所有 POST 自动注入 `?bizCode=universalBP&csrfId=xxx`

---

## License

MIT — © 2026


---

如果这个工具帮到了你，欢迎给个 ⭐️。
