export const TOKEN_KEY = "dota2_admin_token";

export type PlayerStats = {
  matches_played: number;
  matches_won: number;
};

export type Player = {
  id: number;
  name: string;
  current_score: number;
  is_online: boolean;
  stats: PlayerStats;
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
};

export type MatchRecord = {
  id: number;
  matchday_start: string;
  actual_time: string | null;
  status: "confirmed" | "completed";
  created_at: string;
  players: MatchPlayerBrief[];
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
    localStorage.removeItem(TOKEN_KEY);
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

export async function fetchPlayers(filters: PresetFilter): Promise<Player[]> {
  const res = await apiFetch(`/api/players${buildPlayersQuery(filters)}`);
  if (!res.ok) throw new Error("加载选手失败");
  return res.json();
}

export async function patchPlayer(
  id: number,
  body: { is_online?: boolean; current_score?: number },
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
}): Promise<MatchRecord[]> {
  const q = new URLSearchParams();
  if (params?.status) q.set("status", params.status);
  if (params?.matchday) q.set("matchday", params.matchday);
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
): Promise<MatchRecord> {
  const res = await apiFetch(`/api/matches/${matchId}/result`, {
    method: "PATCH",
    body: JSON.stringify({ winner_player_ids }),
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

export async function fetchRankings(): Promise<RankingRow[]> {
  const res = await apiFetch("/api/rankings");
  if (!res.ok) throw new Error("加载排行榜失败");
  return res.json();
}
