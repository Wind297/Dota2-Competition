<script setup lang="ts">
import { computed, h, onMounted, ref, watch } from "vue";
import { useRouter } from "vue-router";
import {
  NButton,
  NCard,
  NCheckbox,
  NDataTable,
  NInput,
  NInputNumber,
  NModal,
  NSpace,
  NSwitch,
  NTag,
  NText,
  useDialog,
  useMessage,
  type DataTableColumns,
} from "naive-ui";
import type { Preset, PresetFilter, Player } from "@/api";
import {
  bulkImportPlayers,
  createMatch,
  createPlayer,
  deletePlayer,
  fetchPlayers,
  fetchPresets,
  patchPlayer,
  isAdmin,
} from "@/api";
import MainLayout from "@/components/MainLayout.vue";
import PageHeader from "@/components/PageHeader.vue";

const router = useRouter();
const message = useMessage();
const dialog = useDialog();

// 是否管理员模式
const adminMode = isAdmin();

const players = ref<Player[]>([]);
const loading = ref(false);
const presets = ref<Preset[]>([]);
const activePresetId = ref<string | null>(null);
const newName = ref("");
/** 新选手入库时的累计积分（线下已取得的胜场数） */
const newInitialScore = ref<number>(0);

const filters = ref<PresetFilter>({});

// 本地搜索关键词
const searchKeyword = ref("");

const checkedRowKeys = ref<Array<string | number>>([]);

const selectedCount = computed(() => checkedRowKeys.value.length);
const canCreate = computed(() => selectedCount.value === 10);

// 经过本地搜索过滤后的选手列表
const filteredPlayers = computed(() => {
  const kw = searchKeyword.value.trim().toLowerCase();
  if (!kw) return players.value;
  return players.value.filter((p) => p.name.toLowerCase().includes(kw));
});

// 是否显示已退出本赛季的选手
const showInactive = ref(false);

let debounceTimer: number | undefined;

function scheduleReload() {
  window.clearTimeout(debounceTimer);
  debounceTimer = window.setTimeout(() => void loadPlayers(), 280);
}

watch(
  filters,
  () => {
    scheduleReload();
  },
  { deep: true },
);

watch(showInactive, () => {
  scheduleReload();
});

async function loadPlayers() {
  loading.value = true;
  try {
    players.value = await fetchPlayers(filters.value, showInactive.value);
  } catch {
    message.error("加载选手列表失败");
  } finally {
    loading.value = false;
  }
}

async function loadPresets() {
  try {
    presets.value = await fetchPresets();
  } catch {
    message.error("加载快捷方案失败");
  }
}

function applyPreset(p: Preset) {
  activePresetId.value = p.id;
  filters.value = { ...p.filters };
}

function clearPresetBadge() {
  activePresetId.value = null;
}

function setTier(v: string | null) {
  clearPresetBadge();
  if (!v) {
    const { tier: _, ...rest } = filters.value;
    filters.value = rest;
    return;
  }
  filters.value = { ...filters.value, tier: v };
}

function toggleFilter(key: keyof PresetFilter, checked: boolean) {
  clearPresetBadge();
  const next = { ...filters.value };
  if (!checked) {
    delete next[key];
    filters.value = next;
    return;
  }
  if (key === "tier") return;
  (next as Record<string, unknown>)[key] = true;
  filters.value = next;
}

onMounted(async () => {
  await loadPresets();
  await loadPlayers();
});

async function onToggleOnline(row: Player, val: boolean) {
  try {
    const updated = await patchPlayer(row.id, { is_online: val });
    const idx = players.value.findIndex((p) => p.id === row.id);
    if (idx >= 0) players.value[idx] = updated;
  } catch {
    message.error("更新在线状态失败");
    await loadPlayers();
  }
}

// ── 积分修改 Modal ──────────────────────────────────────────────
const scoreModalShow = ref(false);
const scoreEditing = ref<Player | null>(null);
const scoreDraft = ref<number>(0);
const scoreSaving = ref(false);

function openScoreModal(row: Player) {
  scoreEditing.value = row;
  scoreDraft.value = row.current_score;
  scoreModalShow.value = true;
}

async function saveScoreFromModal() {
  if (!scoreEditing.value) return;
  const raw = scoreDraft.value;
  const v = raw == null || Number.isNaN(Number(raw)) ? 0 : Math.max(0, Math.floor(Number(raw)));
  scoreSaving.value = true;
  try {
    const updated = await patchPlayer(scoreEditing.value.id, { current_score: v });
    const idx = players.value.findIndex((p) => p.id === updated.id);
    if (idx >= 0) players.value[idx] = updated;
    message.success("积分已更新");
    scoreModalShow.value = false;
  } catch (e) {
    message.error((e as Error).message);
  } finally {
    scoreSaving.value = false;
  }
}

// ── 改名 Modal ──────────────────────────────────────────────────
const renameModalShow = ref(false);
const renameEditing = ref<Player | null>(null);
const renameDraft = ref("");
const renameSaving = ref(false);

function openRenameModal(row: Player) {
  renameEditing.value = row;
  renameDraft.value = row.name;
  renameModalShow.value = true;
}

async function saveRename() {
  if (!renameEditing.value) return;
  const newNameVal = renameDraft.value.trim();
  if (!newNameVal) {
    message.warning("姓名不能为空");
    return;
  }
  renameSaving.value = true;
  try {
    const updated = await patchPlayer(renameEditing.value.id, { name: newNameVal });
    const idx = players.value.findIndex((p) => p.id === updated.id);
    if (idx >= 0) players.value[idx] = updated;
    message.success("姓名已更新");
    renameModalShow.value = false;
  } catch (e) {
    message.error((e as Error).message);
  } finally {
    renameSaving.value = false;
  }
}

// ── 批量导入 ────────────────────────────────────────────────────
function parseBulkPlayerText(text: string): { name: string; current_score: number }[] {
  const byName = new Map<string, { name: string; current_score: number }>();
  for (const line of text.split(/\r?\n/)) {
    const s = line.trim();
    if (!s || s.startsWith("#")) continue;
    const parts = s.split(/[\t,，]/).map((x) => x.trim());
    const name = (parts[0] ?? "").trim();
    if (!name) continue;
    let current_score = 0;
    if (parts.length >= 2 && parts[1] !== "") {
      const n = Number.parseInt(parts[1], 10);
      if (!Number.isNaN(n)) current_score = Math.max(0, n);
    }
    byName.set(name, { name, current_score });
  }
  return [...byName.values()];
}

const bulkText = ref("");
const bulkImporting = ref(false);

async function runBulkImport() {
  const items = parseBulkPlayerText(bulkText.value);
  if (items.length === 0) {
    message.warning("没有有效行：每行「姓名」或「姓名,积分」，# 开头为注释");
    return;
  }
  bulkImporting.value = true;
  try {
    const r = await bulkImportPlayers(items);
    message.success(`导入完成：新建 ${r.created} 人，更新 ${r.updated} 人`);
    bulkText.value = "";
    checkedRowKeys.value = [];
    await loadPlayers();
  } catch (e) {
    message.error((e as Error).message);
  } finally {
    bulkImporting.value = false;
  }
}

function confirmDeletePlayer(row: Player) {
  dialog.warning({
    title: `把「${row.name}」从本赛季选手池移除？`,
    content:
      "该选手将在选手池里隐藏，无法被选入新比赛。\n" +
      "已有的比赛记录、积分、和队友们的同场记录都完整保留。\n" +
      "选手回归时点「恢复参赛」即可，积分接着累计。",
    positiveText: "移出本赛季",
    negativeText: "取消",
    onPositiveClick: async () => {
      try {
        await deletePlayer(row.id);
        message.success("已移出本赛季选手池");
        checkedRowKeys.value = checkedRowKeys.value.filter((k) => Number(k) !== row.id);
        await loadPlayers();
        return true;
      } catch (e) {
        message.error((e as Error).message);
        return false;
      }
    },
  });
}

async function restorePlayer(row: Player) {
  try {
    await patchPlayer(row.id, { is_active: true });
    message.success("已恢复为本赛季参赛");
    await loadPlayers();
  } catch (e) {
    message.error((e as Error).message);
  }
}

function onCheckedRowKeys(keys: Array<string | number>) {
  if (keys.length > 10) {
    message.warning("一场比赛最多选择 10 人");
    return;
  }
  checkedRowKeys.value = keys;
}

const columns: DataTableColumns<Player> = [
  ...(adminMode ? [{ type: "selection" as const }] : []),
  {
    title: "选手",
    key: "name",
    sorter: (a: Player, b: Player) => a.name.localeCompare(b.name, "zh-CN"),
  },
  {
    title: "累计积分",
    key: "current_score",
    width: 100,
    sorter: (a: Player, b: Player) => a.current_score - b.current_score,
    render(row: Player) {
      return row.current_score;
    },
  },
  ...(adminMode
    ? [
        {
          title: "操作",
          key: "ops",
          width: 240,
          render(row: Player) {
            const items = [
              h(
                NButton,
                { size: "small", tertiary: true, onClick: () => openRenameModal(row) },
                { default: () => "改名" },
              ),
              h(
                NButton,
                { size: "small", tertiary: true, onClick: () => openScoreModal(row) },
                { default: () => "积分" },
              ),
            ];
            if (row.is_active) {
              items.push(
                h(
                  NButton,
                  { size: "small", type: "error", tertiary: true, onClick: () => confirmDeletePlayer(row) },
                  { default: () => "移出" },
                ),
              );
            } else {
              items.push(
                h(
                  NButton,
                  { size: "small", type: "primary", tertiary: true, onClick: () => restorePlayer(row) },
                  { default: () => "恢复参赛" },
                ),
              );
            }
            return h(NSpace, { size: "small" }, { default: () => items });
          },
        },
      ]
    : []),
  {
    title: "今日场次",
    key: "played",
    width: 100,
    render(row: Player) {
      return row.stats.matches_played;
    },
  },
  {
    title: "今日胜场",
    key: "won",
    width: 100,
    render(row: Player) {
      return row.stats.matches_won;
    },
  },
  ...(adminMode
    ? [
        {
          title: "在线",
          key: "is_online",
          width: 110,
          render(row: Player) {
            return h(NSwitch, {
              value: row.is_online,
              onUpdateValue: (v: boolean) => void onToggleOnline(row, v),
            });
          },
        },
      ]
    : [
        {
          title: "状态",
          key: "is_online",
          width: 80,
          render(row: Player) {
            return h(
              "span",
              { style: { color: row.is_online ? "#63e2b7" : "#666", fontSize: "12px" } },
              row.is_online ? "在线" : "离线",
            );
          },
        },
      ]),
];

function rowProps(row: Player) {
  if (!row.is_active) {
    return { style: { opacity: 0.5, fontStyle: "italic" } };
  }
  return {
    style: row.is_online ? undefined : { opacity: 0.6 },
  };
}

const tierForUi = computed({
  get: () => filters.value.tier ?? null,
  set: (v: string | null) => setTier(v),
});

const chk = (k: keyof PresetFilter) => filters.value[k] === true;

async function onAddPlayer() {
  const name = newName.value.trim();
  if (!name) {
    message.warning("请输入选手名称");
    return;
  }
  const raw = newInitialScore.value;
  const initial =
    raw == null || Number.isNaN(Number(raw)) ? 0 : Math.max(0, Math.floor(Number(raw)));
  try {
    await createPlayer(name, initial);
    newName.value = "";
    newInitialScore.value = 0;
    message.success("已添加");
    await loadPlayers();
  } catch (e) {
    message.error((e as Error).message);
  }
}

const creating = ref(false);

async function onCreateMatch() {
  if (!canCreate.value) return;
  creating.value = true;
  try {
    const ids = checkedRowKeys.value.map((k) => Number(k));
    const m = await createMatch(ids);
    checkedRowKeys.value = [];
    message.success("比赛已创建");
    await router.push({ name: "match-detail", params: { id: String(m.id) } });
  } catch (e) {
    message.error((e as Error).message);
  } finally {
    creating.value = false;
  }
}
</script>

<template>
  <main-layout>
    <page-header
      :title="adminMode ? '选手池' : '选手浏览'"
      :subtitle="adminMode ? 'Player Pool' : 'Players'"
    />

    <n-space vertical size="large">
      <!-- 快捷方案 -->
      <n-card v-if="adminMode" title="快捷方案">
        <div class="preset-list">
          <button
            v-for="p in presets"
            :key="p.id"
            class="preset-chip"
            :class="{ active: activePresetId === p.id }"
            @click="applyPreset(p)"
          >
            {{ p.label }}
          </button>
        </div>
      </n-card>

      <!-- 高级筛选 -->
      <n-card v-if="adminMode" title="高级筛选">
        <div class="filter-row">
          <span class="filter-key">积分档位</span>
          <button class="tier-btn" :class="{ active: tierForUi == null }" @click="tierForUi = null">不限</button>
          <button class="tier-btn" :class="{ active: tierForUi === 'low' }" @click="tierForUi = 'low'">低分 0–4</button>
          <button class="tier-btn" :class="{ active: tierForUi === 'mid' }" @click="tierForUi = 'mid'">中分 5–9</button>
          <button class="tier-btn" :class="{ active: tierForUi === 'high' }" @click="tierForUi = 'high'">高分 ≥10</button>
        </div>
        <div class="filter-row" style="margin-top: 12px">
          <span class="filter-key">今日状态</span>
          <n-checkbox :checked="chk('today_not_played')" @update:checked="(v) => toggleFilter('today_not_played', v)">
            未参赛
          </n-checkbox>
          <n-checkbox :checked="chk('today_not_won')" @update:checked="(v) => toggleFilter('today_not_won', v)">
            未获胜
          </n-checkbox>
          <n-checkbox :checked="chk('today_played_lte_1')" @update:checked="(v) => toggleFilter('today_played_lte_1', v)">
            参赛 ≤1 场
          </n-checkbox>
          <n-checkbox :checked="chk('today_played_eq_1')" @update:checked="(v) => toggleFilter('today_played_eq_1', v)">
            仅参赛 1 场
          </n-checkbox>
          <n-checkbox :checked="chk('online_only')" @update:checked="(v) => toggleFilter('online_only', v)">
            仅在线
          </n-checkbox>
        </div>
      </n-card>

      <!-- 选手列表 -->
      <n-card title="选手列表">
        <template #header-extra>
          <span class="roster-count">{{ filteredPlayers.length }} / {{ players.length }}</span>
        </template>
        <div class="search-bar">
          <n-input
            v-model:value="searchKeyword"
            placeholder="搜索选手姓名"
            clearable
            size="small"
            style="max-width: 280px"
          />
          <n-checkbox v-if="adminMode" v-model:checked="showInactive" style="margin-left: 12px">
            <span style="font-size: 12px">显示已退出本赛季</span>
          </n-checkbox>
        </div>
        <n-data-table
          :loading="loading"
          :columns="columns"
          :data="filteredPlayers"
          :row-key="(row: Player) => row.id"
          :checked-row-keys="checkedRowKeys"
          :row-props="rowProps"
          @update:checked-row-keys="onCheckedRowKeys"
        />
      </n-card>
    </n-space>

    <!-- 创建比赛悬浮栏（仅管理员） -->
    <div v-if="adminMode" class="create-bar">
      <div class="create-bar-info">
        <div class="create-progress">
          <div class="progress-bar">
            <div
              class="progress-fill"
              :style="{ width: `${Math.min(100, (selectedCount / 10) * 100)}%` }"
            ></div>
          </div>
          <div class="create-bar-label">已选 <b>{{ selectedCount }}</b> / 10</div>
        </div>
      </div>
      <n-button type="primary" :disabled="!canCreate" :loading="creating" @click="onCreateMatch">
        创建比赛
      </n-button>
    </div>

    <!-- 管理区域（仅管理员） -->
    <n-space v-if="adminMode" vertical size="large" style="margin-top: 16px">
      <n-card title="添加选手" size="small">
        <div class="hint-text">「累计积分」为入库前的胜场累计；之后录入的比赛仍会照常加减。</div>
        <n-space align="center" style="flex-wrap: wrap; margin-top: 10px" :size="10">
          <n-input v-model:value="newName" placeholder="选手名称" style="max-width: 240px" size="small" />
          <span class="inline-label">初始积分</span>
          <n-input-number v-model:value="newInitialScore" :min="0" :precision="0" placeholder="0" style="width: 110px" size="small" />
          <n-button type="primary" size="small" @click="onAddPlayer">添加</n-button>
        </n-space>
      </n-card>

      <n-card title="批量导入选手" size="small">
        <div class="hint-text">
          每行一名选手：「姓名」或「姓名,积分」（可用英文逗号、中文逗号或 Tab 分隔）。
        </div>
        <n-input
          v-model:value="bulkText"
          type="textarea"
          placeholder="张三,3&#10;李四&#10;王五,0"
          :rows="6"
          spellcheck="false"
          style="margin-top: 10px"
        />
        <div style="margin-top: 10px">
          <n-button type="primary" size="small" :loading="bulkImporting" @click="runBulkImport">
            执行导入
          </n-button>
        </div>
      </n-card>
    </n-space>

    <!-- 积分修改 Modal -->
    <n-modal v-if="adminMode" v-model:show="scoreModalShow" :mask-closable="false" style="width: 440px">
      <n-card title="修改累计积分" :bordered="false" size="small">
        <n-space vertical size="large">
          <n-space vertical>
            <n-text v-if="scoreEditing">选手：<b style="color:#1a2435">{{ scoreEditing.name }}</b></n-text>
            <n-space align="center">
              <span class="inline-label">累计积分（胜场数）</span>
              <n-input-number v-model:value="scoreDraft" :min="0" :precision="0" style="width: 160px" />
            </n-space>
            <n-text depth="3" style="font-size: 12px">用于补录线下已有成绩；积分为非负整数。</n-text>
          </n-space>
          <n-space justify="end">
            <n-button @click="scoreModalShow = false">取消</n-button>
            <n-button type="primary" :loading="scoreSaving" @click="saveScoreFromModal">保存</n-button>
          </n-space>
        </n-space>
      </n-card>
    </n-modal>

    <!-- 改名 Modal -->
    <n-modal v-if="adminMode" v-model:show="renameModalShow" :mask-closable="false" style="width: 440px">
      <n-card title="修改选手姓名" :bordered="false" size="small">
        <n-space vertical size="large">
          <n-space vertical>
            <n-text depth="3">可用于更新游戏 ID 或昵称，历史比赛记录中的姓名也会同步更新。</n-text>
            <n-space align="center">
              <span class="inline-label">姓名</span>
              <n-input
                v-model:value="renameDraft"
                placeholder="新姓名"
                style="width: 240px"
                @keydown.enter="saveRename"
              />
            </n-space>
          </n-space>
          <n-space justify="end">
            <n-button @click="renameModalShow = false">取消</n-button>
            <n-button type="primary" :loading="renameSaving" @click="saveRename">保存</n-button>
          </n-space>
        </n-space>
      </n-card>
    </n-modal>
  </main-layout>
</template>

<style scoped>
/* 快捷方案 chip */
.preset-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.preset-chip {
  background: #ffffff;
  border: 1px solid #d8dee6;
  color: #4d5663;
  padding: 6px 12px;
  font-size: 12px;
  cursor: pointer;
  border-radius: 4px;
  transition: all 0.15s;
  font-family: inherit;
}
.preset-chip:hover {
  border-color: #2c6dc1;
  color: #2c6dc1;
  background: rgba(44, 109, 193, 0.04);
}
.preset-chip.active {
  background: #2c6dc1;
  border-color: #2c6dc1;
  color: #ffffff;
  font-weight: 500;
}

/* 筛选行 */
.filter-row {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
}
.filter-key {
  font-size: 12px;
  color: #5a6473;
  font-weight: 500;
  margin-right: 6px;
  flex-shrink: 0;
}
.tier-btn {
  background: #ffffff;
  border: 1px solid #d8dee6;
  color: #4d5663;
  padding: 4px 12px;
  font-size: 12px;
  cursor: pointer;
  border-radius: 4px;
  transition: all 0.15s;
  font-family: inherit;
}
.tier-btn:hover {
  border-color: #2c6dc1;
  color: #2c6dc1;
}
.tier-btn.active {
  background: rgba(44, 109, 193, 0.1);
  border-color: #2c6dc1;
  color: #2c6dc1;
  font-weight: 500;
}

/* 搜索栏 */
.search-bar {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 12px;
  margin-bottom: 12px;
  padding-bottom: 12px;
  border-bottom: 1px solid #eef1f5;
}
.roster-count {
  font-size: 12px;
  color: #5a6473;
  font-family: '"SF Mono", "Courier New", monospace';
  font-weight: 500;
}

/* 创建比赛悬浮栏 */
.create-bar {
  position: sticky;
  bottom: 16px;
  margin-top: 20px;
  padding: 14px 18px;
  background: #ffffff;
  border: 1px solid #2c6dc1;
  border-radius: 8px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  flex-wrap: wrap;
  box-shadow: 0 8px 24px rgba(44, 109, 193, 0.18);
  z-index: 10;
}
.create-bar-info {
  flex: 1;
  min-width: 200px;
}
.create-progress {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.progress-bar {
  height: 4px;
  background: #eef1f5;
  border-radius: 2px;
  overflow: hidden;
}
.progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #2c6dc1 0%, #b97324 100%);
  border-radius: 2px;
  transition: width 0.3s ease;
}
.create-bar-label {
  color: #1a2435;
  font-size: 13px;
}
.create-bar-label b {
  color: #2c6dc1;
  font-size: 16px;
  font-weight: 700;
  font-family: '"SF Mono", "Courier New", monospace';
  margin: 0 2px;
}

/* 提示文字 */
.hint-text {
  font-size: 12px;
  color: #5a6473;
  line-height: 1.6;
}
.inline-label {
  font-size: 12px;
  color: #4d5663;
  font-weight: 500;
}
</style>
