# alimama-cli

万相台 AI 无界（one.alimama.com / 阿里妈妈 onebp）只读数据查询 CLI。

给 AI 代理一行命令拉取自家店铺的广告推广数据。

## 装机

```bash
git clone https://github.com/rakei076/alimama-cli ~/.claude/skills/alimama-cli
# 已装 uv 直接跑；否则 pip install -r requirements.txt
```

## 用法

```bash
# 1) 自检 cookie / 登录态
~/.claude/skills/alimama-cli/scripts/alimama.sh doctor

# 2) 拉推广计划列表
~/.claude/skills/alimama-cli/scripts/alimama.sh campaign-list --date 2026-05-29 --limit 20

# 3) 拉活动列表
~/.claude/skills/alimama-cli/scripts/alimama.sh activity-list

# 4) 通用接口探测
~/.claude/skills/alimama-cli/scripts/alimama.sh api /report/campaign/findPage.json \
  --body '{"pageNo":1,"pageSize":10,"startDate":"20260529","endDate":"20260529"}'
```

所有命令通用：`--raw`（输出原始 JSON）、`--out file`（写文件）。

## 工作机制

- `browser_cookie3` 从 Chrome 直读 alimama 域 cookie
- 首次请求自动调 `/member/checkAccess.json` 拿 `csrfId` 并缓存
- 后续请求自动注入 `?bizCode=universalBP&csrfId=xxx`
- `curl_cffi` 伪 Chrome TLS 指纹

详见 [SKILL.md](SKILL.md)。

## 合规与安全

- **仅供商家拉取自家店铺数据。** 不要用于抓取他人账号
- **只读保证**：本 CLI 不调用任何 add / update / delete / save / close 类接口
- 内置硬性安全护栏：80 次/run 上限、1.8–3.5 秒随机延迟、夜间 1–6 点禁跑、风控关键词检测立即终止
- 触发风控**永远不重试**

## License

MIT
