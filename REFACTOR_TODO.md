# 代码优化 & 重构备忘录

> ⚠️ **本文档已让位给 [`项目代码审计.md`](./项目代码审计.md)**
>
> 自 2026-07-13 起，`项目代码审计.md` 是本项目的**权威审计与架构说明文档**，由 Cursor 规则 `.cursor/rules/项目代码审计维护.mdc` 强制维护。
>
> 本文档保留作为早期技术债清单的历史快照，**不再主动维护**。两者内容冲突时以 `项目代码审计.md` 为准；新风险、新改进、变更日志一律写入 `项目代码审计.md`，不要再追加到本文档。

---

> 目的：记录已知的技术债和优化方向，后续重构时直接参考本文档而不需要重新审查全部代码。  
> 规则：每次有新代码改动后，在「变更日志」章节追加简要说明。

---

## 一、当前已知问题（按优先级）

### 🔴 高优先级（性能/安全）

| # | 文件 | 问题 | 修复方案 |
|---|------|------|----------|
| 1 | `backend/app/routers/matches.py` | `_compute_sequence_no()` 每次转换一场比赛就执行一次 COUNT 查询。`list_matches` 返回 N 场就多 N 次 SQL（N+1） | 批量预计算：在 `list_matches` 里先按 matchday_start 分组 COUNT，传入 map 给 `_match_to_out` |
| 2 | `backend/app/routers/matches.py` | `_ensure_active_season_match()` 用了 `__import__("app.models", ...)` 绕过类型系统 | 改为文件顶部正常 `from app.models import Season`（已 import SeasonStatus，漏了 Season） |
| 3 | `backend/app/routers/players.py` | `patch_player` 为返回单个选手加载了全赛季 4 次聚合查询（today_stats/total_stats/like_counts/top_tags） | 做单选手版本：只查该 player_id 的聚合 |
| 4 | `backend/app/routers/seasons.py` | `list_seasons` 对每个赛季执行 2 次 COUNT（player_count + match_count），10 个赛季 = 20 次查询 | 改为一次 GROUP BY 聚合 |

### 🟡 中优先级（可维护性/DRY）

| # | 文件 | 问题 | 修复方案 |
|---|------|------|----------|
| 5 | `backend/app/main.py` | startup `on_startup()` ~90 行，职责不清 | 拆成 `_run_migrations(conn)`、`_init_first_season(conn)`、`_seed_tags(conn)` |
| 6 | `backend/app/routers/matches.py` | `selectinload(Match.players).selectinload(MatchPlayer.player)` 出现 5 次 | 提取为模块级常量 `_MATCH_EAGER_OPTS` |
| 7 | `backend/app/routers/matches.py` | "查 match + options + first + 404" 模式出现 4 次 | 提取 `_get_match_or_404(db, match_id)` |
| 8 | `frontend/src/views/PlayersView.vue` | ~520 行，混入多个 modal 逻辑 | 拆出 `ScoreEditModal`、`RenameModal`、`BulkImportCard`、`CreateMatchBar` |
| 9 | `backend/app/routers/players.py` | `_load_player_total_stats` 和 `stats.py:load_matchday_stats` 查询模式相似 | 合并为通用 `aggregate_player_stats(db, **filters)` |

### 🟢 低优先级（整洁）

| # | 文件 | 问题 |
|---|------|------|
| 10 | `frontend/src/api.ts` | `fetchTags`、`patchTag`、`deleteTag` 当前无前端调用（管理面板预留） |
| 11 | `frontend/src/views/PlayersView.vue` | import 了 `NTag`、`NText` 但模板未使用 |
| 12 | `backend/app/models.py` | `Player.current_score` / `Player.is_online` 是历史遗留列，新代码不使用（保留为兼容） |
| 13 | `frontend/src/api.ts` | `VOTER_TOKEN_KEY` / `VOTER_NICKNAME_KEY` 仅内部使用但 export 了 |

---

## 二、架构参考信息（节约未来读取）

### 后端结构
```
backend/app/
├── main.py          -- FastAPI app、startup 迁移、SPA fallback
├── models.py        -- SQLAlchemy ORM（Season, Player, SeasonPlayer, Match, MatchPlayer, Tag, PlayerLike, PlayerTag, SystemKV）
├── schemas.py       -- Pydantic models (请求/响应)
├── database.py      -- engine + SessionLocal + Base + get_db
├── config.py        -- pydantic-settings 读环境变量
├── deps.py          -- AuthToken 依赖
├── seasons.py       -- get_active_season / get_or_create_season_player
├── stats.py         -- load_matchday_stats 聚合
├── matchday.py      -- 比赛日时区逻辑
├── datetime_norm.py -- naive datetime 时区标准化
├── daily_reset.py   -- 每日在线状态重置
└── routers/
    ├── auth.py      -- login + guest-token
    ├── players.py   -- CRUD + 社交互动(like/tag) ~310 行
    ├── matches.py   -- CRUD + 积分核算 ~240 行
    ├── rankings.py  -- 排行榜（支持按赛季）
    ├── seasons.py   -- 赛季 CRUD + rollover
    ├── presets.py   -- 静态快捷筛选方案
    └── tags.py      -- 标签 CRUD
```

### 前端结构
```
frontend/src/
├── main.ts / App.vue          -- 入口 + Naive UI 主题
├── router/index.ts            -- 路由 + 守卫
├── api.ts                     -- 所有 API 类型 + 请求函数 (~350 行)
├── components/
│   ├── MainLayout.vue         -- 顶部导航 + 布局
│   ├── PageHeader.vue         -- 页面标题条
│   └── PlayerDetailModal.vue  -- 选手详情卡（点赞/标签）
└── views/
    ├── LoginView.vue          -- 登录（游客/管理员）
    ├── PlayersView.vue        -- 选手池 (~520 行，最大)
    ├── MatchesView.vue        -- 比赛列表
    ├── MatchDetailView.vue    -- 比赛详情+结果提交+编辑
    ├── RankingsView.vue       -- 排行榜
    └── SeasonsView.vue        -- 赛季管理
```

### 核心积分逻辑
- 所有积分变化通过 `MatchPlayer.score_delta` 字段追踪
- `_set_match_player_delta(db, mp, season_id, target, skip_score=False)` 是唯一的积分调整入口
- 差额公式：`diff = target_delta - mp.score_delta`，同步到 `SeasonPlayer.current_score`
- 练习赛 `skip_score=True` 只记录胜负不改积分
- 删除/编辑比赛时先撤销（target=0）再重建

### 游客互动机制
- 前端 localStorage 存 `voter_token`（UUID）+ `voter_nickname`
- 后端 `PlayerLike` / `PlayerTag` 用 `(season_id, player_id, voter_token)` 唯一约束实现一人一票
- 标签分公共（player_id=null）和专属（player_id=N）

---

## 三、变更日志

> 每次改动后追加，格式：日期 | 改了什么 | 新增的技术债（如有）

| 日期 | 变更 | 新技术债 |
|------|------|----------|
| 2026-06-18 | 初始功能全部完成：选手管理、比赛CRUD、赛季、排行榜、游客模式、互动系统、练习赛 | 见上方全部条目 |
| 2026-06-18 | 管理员可在选手详情卡中新建公共/专属标签 | Tag 表去掉了 UNIQUE 约束（因为同名标签可分属不同选手），需要在 API 层做业务去重 |
| 2026-06-18 | 决赛名次系统：SeasonPlayer.final_rank + 上赛季奖牌展示 + 选手名布局优化 | list_players 增加一次对上赛季名次的查询（未缓存） |

---

## 四、重构执行建议

当决定重构时，建议按以下顺序（每步独立可验证）：

1. **先修 #2**（`__import__` → 正常 import），1 分钟搞定，零风险
2. **再修 #5**（main.py 拆子函数），不改逻辑只移代码
3. **然后 #6 + #7**（matches.py 提取常量和辅助函数），减少 ~40 行重复
4. **接着 #1**（序号最大的性能问题：批量 sequence_no），需要改 `_match_to_out` 签名
5. **最后 #8**（拆 PlayersView.vue），改动面大但无逻辑变化

每步做完跑一遍完整测试（前后端联调），确保不回退。
