# 马拉松个人赛历和推荐

采集中国马拉松赛事日历，提供基于田协认证（A/B/C类）和世界田联标牌（白金标/金标/精英标）的赛事分级推荐。

## 用途

本技能供 AI 工具（如 WorkBuddy/Codex）加载后，能够：

- 回答"有什么马拉松可以跑"、"最近有什么比赛"等赛事推荐问题
- 查询赛事田协认证级别（A/B/C类）和世界田联标牌等级
- 基于用户 IP 地理位置推荐就近的高级别赛事
- 生成赛事报名状态一览表（支持 HTML 页面或图片长图）

## 数据来源

| 优先级 | 来源 | 用途 |
|--------|------|------|
| 🥇 | 中国田协年度赛事目录 | A/B/C类认证（唯一权威） |
| 🥇 | 世界田联官网 | 白金标/金标/精英标/标牌 |
| 🥉 | nowrun.cn（闹跑） | 赛事详情（日期、起终点、爬升、报名费） |

## 安装方式

### WorkBuddy 安装
```bash
clawhub install 马拉松个人赛历和推荐
```
或通过 WorkBuddy 的技能市场搜索安装。

### 手动安装
将本仓库 clone 到 WorkBuddy 的 skills 目录：
```bash
git clone https://github.com/feijiangbin-hub/marathon-calendar-skill.git ~/.workbuddy/skills/马拉松个人赛历和推荐
```

## 目录结构
```
marathon-calendar-skill/
├── SKILL.md          # 技能定义（核心）
├── marathon_calendar.py  # 赛历采集脚本
└── README.md         # 本文件
```

## 采集脚本用法
```bash
python marathon_calendar.py
```
- 从 nowrun.cn 获取全部 492 场赛事列表
- 自动抓取近期赛事详情（日期、起终点、爬升、报名费、规模等）
- 输出 JSON 和 HTML 赛历文件

## 已报名的赛事记录（示例）
可在 skill 记忆文件中记录用户已报名的赛事，避免重复推荐：
- 杭州马拉松（金标）— 11月1日
- 上海马拉松（白金标/大满贯候选）— 12月6日

## 许可
MIT
