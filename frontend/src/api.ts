export const TOKEN_KEY = "dota2_admin_token";
export const GUEST_KEY = "dota2_guest_mode";
export const VOTER_TOKEN_KEY = "dota2_voter_token";
export const VOTER_NICKNAME_KEY = "dota2_voter_nickname";

/** 获取游客匿名 voter token；不存在则生成。 */
export function getVoterToken(): string {
  let t = localStorage.getItem(VOTER_TOKEN_KEY);
  if (!t) {
    // 生成 UUID v4（避免依赖 crypto.randomUUID 兼容性）
    t = "guest-" + (window.crypto?.randomUUID?.() ?? Math.random().toString(36).slice(2) + Date.now().toString(36));
    localStorage.setItem(VOTER_TOKEN_KEY, t);
  }
  return t;
}

export function getVoterNickname(): string | null {
  return localStorage.getItem(VOTER_NICKNAME_KEY);
}

export function setVoterNickname(name: string): void {
  const v = name.trim();
  if (v) localStorage.setItem(VOTER_NICKNAME_KEY, v);
  else localStorage.removeItem(VOTER_NICKNAME_KEY);
}

/** 是否以游客身份进入（无需 token） */
export function isGuest(): boolean {
  return localStorage.getItem(GUEST_KEY) === "1";
}

/** 是否已登录管理员（有 token 且非游客模式） */
export function isAdmin(): boolean {
  return !!localStorage.getItem(TOKEN_KEY) && localStorage.getItem(GUEST_KEY) !== "1";
}

/** 进入游客模式：获取只读 token 并标记游客身份 */
export async function enterGuest(): Promise<void> {
  const res = await fetch("/api/auth/guest-token");
  if (!res.ok) throw new Error("获取游客令牌失败");
  const data = (await res.json()) as { access_token: string };
  localStorage.setItem(TOKEN_KEY, data.access_token);
  localStorage.setItem(GUEST_KEY, "1");
}

/** 退出（清除所有身份） */
export function clearAuth(): void {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(GUEST_KEY);
}

export type PlayerStats = {
  matches_played: number;
  matches_won: number;
};

export type TopTagItem = {
  tag_id: number;
  label: string;
  count: number;
};

export type Player = {
  id: number;
  name: string;
  current_score: number;
  is_online: boolean;
  is_active: boolean;
  stats: PlayerStats;
  like_count: number;
  total_played: number;
  total_won: number;
  win_rate: number;
  top_tags: TopTagItem[];
};

export type PresetFilter = {
  tier?: string | null;
  today_not_played?: boolean | null;
  today_not_won?: boolean | null;
  today_played_lte_1?: boolean | null;
  today_played_eq_1?: boolean | null;
  online_only?: boolean | null;
};

export type Preset = {
  id: string;
  label: string;
  filters: PresetFilter;
};

export type MatchPlayerBrief = {
  player_id: number;
  name: string;
  is_winner: boolean | null;
  is_deducted: boolean;
  score_delta: number;
};

export type MatchRecord = {
  id: number;
  season_id: number | null;
  matchday_start: string;
  actual_time: string | null;
  sequence_no: number | null;
  status: "confirmed" | "completed";
  created_at: string;
  players: MatchPlayerBrief[];
};

export type Season = {
  id: number;
  name: string;
  status: "active" | "archived";
  started_at: string;
  ended_at: string | null;
  is_current: boolean;
  player_count: number;
  match_count: number;
};

export type RankingRow = {
  rank: number;
  player_id: number;
  name: string;
  current_score: number;
};

function authHeaders(): HeadersInit {
  const token = localStorage.getItem(TOKEN_KEY);
  const h: Record<string, string> = { "Content-Type": "application/json" };
  if (token) h.Authorization = `Bearer ${token}`;
  return h;
}

export async function apiFetch(path: string, init: RequestInit = {}): Promise<Response> {
  const headers = new Headers(init.headers);
  const base = authHeaders() as Record<string, string>;
  for (const [k, v] of Object.entries(base)) {
    if (!headers.has(k)) headers.set(k, v);
  }
  const res = await fetch(path, { ...init, headers });
  if (res.status === 401) {
    clearAuth();
    window.location.assign("/login");
  }
  return res;
}

export async function login(password: string): Promise<void> {
  const res = await fetch("/api/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ password }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error((err as { detail?: string }).detail || "登录失败");
  }
  const data = (await res.json()) as { access_token: string };
  localStorage.setItem(TOKEN_KEY, data.access_token);
}

function buildPlayersQuery(f: PresetFilter): string {
  const q = new URLSearchParams();
  if (f.tier) q.set("tier", f.tier);
  if (f.today_not_played === true) q.set("today_not_played", "true");
  if (f.today_not_won === true) q.set("today_not_won", "true");
  if (f.today_played_lte_1 === true) q.set("today_played_lte_1", "true");
  if (f.today_played_eq_1 === true) q.set("today_played_eq_1", "true");
  if (f.online_only === true) q.set("online_only", "true");
  const s = q.toString();
  return s ? `?${s}` : "";
}

export async function fetchPlayers(filters: PresetFilter, includeInactive = false): Promise<Player[]> {
  const q = buildPlayersQuery(filters);
  const sep = q ? "&" : "?";
  const url = `/api/players${q}${includeInactive ? `${sep}include_inactive=true` : ""}`;
  const res = await apiFetch(url);
  if (!res.ok) throw new Error("加载选手失败");
  return res.json();
}

export async function patchPlayer(
  id: number,
  body: { name?: string; is_online?: boolean; current_score?: number; is_active?: boolean },
): Promise<Player> {
  const res = await apiFetch(`/api/players/${id}`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error((err as { detail?: string }).detail || "更新选手失败");
  }
  return res.json();
}

export async function createPlayer(name: string, current_score = 0): Promise<Player> {
  const res = await apiFetch("/api/players", {
    method: "POST",
    body: JSON.stringify({ name, current_score }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error((err as { detail?: string }).detail || "添加失败");
  }
  return res.json();
}

export type PlayerBulkImportRow = { name: string; current_score: number };

export type PlayerBulkImportResult = {
  created: number;
  updated: number;
  total: number;
};

/** 按姓名批量新建或覆盖积分（已存在的同名选手会更新积分） */
export async function bulkImportPlayers(items: PlayerBulkImportRow[]): Promise<PlayerBulkImportResult> {
  const res = await apiFetch("/api/players/import", {
    method: "POST",
    body: JSON.stringify({ items }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error((err as { detail?: string }).detail || "批量导入失败");
  }
  return res.json();
}

/** 删除选手；若已有比赛记录会先被拒绝 */
export async function deletePlayer(id: number): Promise<void> {
  const res = await apiFetch(`/api/players/${id}`, { method: "DELETE" });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error((err as { detail?: string }).detail || "删除失败");
  }
}

export async function fetchPresets(): Promise<Preset[]> {
  const res = await apiFetch("/api/presets");
  if (!res.ok) throw new Error("加载快捷方案失败");
  return res.json();
}

export async function createMatch(player_ids: number[]): Promise<MatchRecord> {
  const res = await apiFetch("/api/matches", {
    method: "POST",
    body: JSON.stringify({ player_ids }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error((err as { detail?: string }).detail || "创建比赛失败");
  }
  return res.json();
}

export async function fetchMatches(params?: {
  status?: string;
  matchday?: string;
  season_id?: number;
  all_seasons?: boolean;
}): Promise<MatchRecord[]> {
  const q = new URLSearchParams();
  if (params?.status) q.set("status", params.status);
  if (params?.matchday) q.set("matchday", params.matchday);
  if (params?.season_id != null) q.set("season_id", String(params.season_id));
  if (params?.all_seasons) q.set("all_seasons", "true");
  const s = q.toString();
  const res = await apiFetch(`/api/matches${s ? `?${s}` : ""}`);
  if (!res.ok) throw new Error("加载比赛列表失败");
  return res.json();
}

export async function fetchMatch(id: number): Promise<MatchRecord> {
  const res = await apiFetch(`/api/matches/${id}`);
  if (!res.ok) throw new Error("加载比赛失败");
  return res.json();
}

export async function submitMatchResult(
  matchId: number,
  winner_player_ids: number[],
  deducted_player_ids: number[] = [],
): Promise<MatchRecord> {
  const res = await apiFetch(`/api/matches/${matchId}/result`, {
    method: "PATCH",
    body: JSON.stringify({ winner_player_ids, deducted_player_ids }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error((err as { detail?: string }).detail || "提交结果失败");
  }
  return res.json();
}

/** 删除比赛；若已完赛会先回退胜者积分 */
export async function deleteMatch(matchId: number): Promise<void> {
  const res = await apiFetch(`/api/matches/${matchId}`, { method: "DELETE" });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error((err as { detail?: string }).detail || "删除失败");
  }
}

/** 编辑已录入的比赛信息（比赛日 / 场次号 / 上场名单） */
export async function patchMatch(
  matchId: number,
  body: {
    matchday_start?: string;
    sequence_no?: number;
    clear_sequence_no?: boolean;
    player_ids?: number[];
  },
): Promise<MatchRecord> {
  const res = await apiFetch(`/api/matches/${matchId}`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error((err as { detail?: string }).detail || "编辑比赛失败");
  }
  return res.json();
}

/** 生成比赛标题：【YYYY-MM-DD】比赛日 第N场 */
export function formatMatchTitle(m: MatchRecord): string {
  const d = new Date(m.matchday_start);
  const yyyy = d.getFullYear();
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  const dd = String(d.getDate()).padStart(2, "0");
  const seq = m.sequence_no ?? "?";
  return `【${yyyy}-${mm}-${dd}】比赛日 第${seq}场`;
}

export async function fetchRankings(seasonId?: number): Promise<RankingRow[]> {
  const url = seasonId != null ? `/api/rankings?season_id=${seasonId}` : "/api/rankings";
  const res = await apiFetch(url);
  if (!res.ok) throw new Error("加载排行榜失败");
  return res.json();
}

// ── 赛季 ────────────────────────────────────────────────────────
export async function fetchSeasons(): Promise<Season[]> {
  const res = await apiFetch("/api/seasons");
  if (!res.ok) throw new Error("加载赛季列表失败");
  return res.json();
}

export async function fetchCurrentSeason(): Promise<Season | null> {
  const res = await apiFetch("/api/seasons/current");
  if (!res.ok) throw new Error("加载当前赛季失败");
  return res.json();
}

export async function createSeason(name: string, inheritActivePlayers = true): Promise<Season> {
  const res = await apiFetch("/api/seasons", {
    method: "POST",
    body: JSON.stringify({ name, inherit_active_players: inheritActivePlayers }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error((err as { detail?: string }).detail || "创建赛季失败");
  }
  return res.json();
}

export async function endSeason(seasonId: number): Promise<Season> {
  const res = await apiFetch(`/api/seasons/${seasonId}/end`, { method: "POST" });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error((err as { detail?: string }).detail || "结束赛季失败");
  }
  return res.json();
}

export async function rolloverSeason(
  newSeasonName: string,
  inheritActivePlayers = true,
): Promise<Season> {
  const res = await apiFetch("/api/seasons/rollover", {
    method: "POST",
    body: JSON.stringify({
      new_season_name: newSeasonName,
      inherit_active_players: inheritActivePlayers,
    }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error((err as { detail?: string }).detail || "切换赛季失败");
  }
  return res.json();
}


// ── 互动：标签 / 点赞 ──────────────────────────────────────────
export type Tag = {
  id: number;
  label: string;
  sort_order: number;
  is_enabled: boolean;
};

export type TagVoteRow = {
  tag_id: number;
  label: string;
  count: number;
  voted_by_me: boolean;
};

export type PlayerSocial = {
  like_count: number;
  liked_by_me: boolean;
  tags: TagVoteRow[];
};

export async function fetchTags(includeDisabled = false): Promise<Tag[]> {
  const url = includeDisabled ? "/api/tags?include_disabled=true" : "/api/tags";
  const res = await apiFetch(url);
  if (!res.ok) throw new Error("加载标签失败");
  return res.json();
}

export async function createTag(label: string, sortOrder = 0): Promise<Tag> {
  const res = await apiFetch("/api/tags", {
    method: "POST",
    body: JSON.stringify({ label, sort_order: sortOrder, is_enabled: true }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error((err as { detail?: string }).detail || "创建标签失败");
  }
  return res.json();
}

export async function patchTag(
  id: number,
  body: { label?: string; sort_order?: number; is_enabled?: boolean },
): Promise<Tag> {
  const res = await apiFetch(`/api/tags/${id}`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error((err as { detail?: string }).detail || "更新标签失败");
  }
  return res.json();
}

export async function deleteTag(id: number): Promise<void> {
  const res = await apiFetch(`/api/tags/${id}`, { method: "DELETE" });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error((err as { detail?: string }).detail || "删除标签失败");
  }
}

export async function fetchPlayerSocial(playerId: number): Promise<PlayerSocial> {
  const token = getVoterToken();
  const res = await apiFetch(`/api/players/${playerId}/social?voter_token=${encodeURIComponent(token)}`);
  if (!res.ok) throw new Error("加载选手互动数据失败");
  return res.json();
}

export async function togglePlayerLike(playerId: number): Promise<PlayerSocial> {
  const token = getVoterToken();
  const nickname = getVoterNickname();
  const res = await apiFetch(`/api/players/${playerId}/like`, {
    method: "POST",
    body: JSON.stringify({ voter_token: token, voter_nickname: nickname }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error((err as { detail?: string }).detail || "点赞失败");
  }
  return res.json();
}

export async function togglePlayerTag(playerId: number, tagId: number): Promise<PlayerSocial> {
  const token = getVoterToken();
  const nickname = getVoterNickname();
  const res = await apiFetch(`/api/players/${playerId}/tags/${tagId}`, {
    method: "POST",
    body: JSON.stringify({ voter_token: token, voter_nickname: nickname }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error((err as { detail?: string }).detail || "标签投票失败");
  }
  return res.json();
}
