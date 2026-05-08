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
} from "@/api";
import MainLayout from "@/components/MainLayout.vue";

const router = useRouter();
const message = useMessage();
const dialog = useDialog();

const players = ref<Player[]>([]);
const loading = ref(false);
const presets = ref<Preset[]>([]);
const activePresetId = ref<string | null>(null);
const newName = ref("");
/** 新选手入库时的累计积分（线下已取得的胜场数） */
const newInitialScore = ref<number>(0);

const filters = ref<PresetFilter>({});

const checkedRowKeys = ref<Array<string | number>>([]);

const selectedCount = computed(() => checkedRowKeys.value.length);
const canCreate = computed(() => selectedCount.value === 10);

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

async function loadPlayers() {
  loading.value = true;
  try {
    players.value = await fetchPlayers(filters.value);
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

const scoreModalShow = ref(false);
const scoreEditing = ref<Player | null>(null);
const scoreDraft = ref<number>(0);
const scoreSaving = ref(false);

function openScoreModal(row: Player) {
  scoreEditing.value = row;
  scoreDraft.value = row.current_score;
  scoreModalShow.value = true;
}

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
    title: `删除选手「${row.name}」？`,
    content: "若该选手已有比赛记录，将无法删除；请先到「历史比赛」删掉相关场次。此操作不可恢复。",
    positiveText: "删除",
    negativeText: "取消",
    onPositiveClick: async () => {
      try {
        await deletePlayer(row.id);
        message.success("已删除");
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

function onCheckedRowKeys(keys: Array<string | number>) {
  if (keys.length > 10) {
    message.warning("一场比赛最多选择 10 人");
    return;
  }
  checkedRowKeys.value = keys;
}

const columns: DataTableColumns<Player> = [
  { type: "selection" },
  { title: "选手", key: "name" },
  {
    title: "累计积分",
    key: "current_score",
    width: 100,
    render(row) {
      return row.current_score;
    },
  },
  {
    title: "操作",
    key: "ops",
    width: 168,
    render(row) {
      return h(
        NSpace,
        { size: "small" },
        {
          default: () => [
            h(
              NButton,
              { size: "small", tertiary: true, onClick: () => openScoreModal(row) },
              { default: () => "积分" },
            ),
            h(
              NButton,
              { size: "small", type: "error", tertiary: true, onClick: () => confirmDeletePlayer(row) },
              { default: () => "删除" },
            ),
          ],
        },
      );
    },
  },
  {
    title: "今日场次",
    key: "played",
    width: 100,
    render(row) {
      return row.stats.matches_played;
    },
  },
  {
    title: "今日胜场",
    key: "won",
    width: 100,
    render(row) {
      return row.stats.matches_won;
    },
  },
  {
    title: "在线",
    key: "is_online",
    width: 110,
    render(row) {
      return h(NSwitch, {
        value: row.is_online,
        onUpdateValue: (v: boolean) => void onToggleOnline(row, v),
      });
    },
  },
];

function rowProps(row: Player) {
  return {
    style: row.is_online ? undefined : { opacity: 0.55 },
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
    <n-space vertical size="large">
      <n-card title="快捷方案">
        <n-space>
          <n-tag
            v-for="p in presets"
            :key="p.id"
            :type="activePresetId === p.id ? 'success' : 'default'"
            style="cursor: pointer"
            @click="applyPreset(p)"
          >
            {{ p.label }}
          </n-tag>
        </n-space>
      </n-card>

      <n-card title="高级筛选">
        <n-space vertical>
          <n-space align="center" style="flex-wrap: wrap">
            <span>积分档位</span>
            <n-button size="small" :type="tierForUi == null ? 'primary' : 'default'" @click="tierForUi = null">
              不限
            </n-button>
            <n-button size="small" :type="tierForUi === 'low' ? 'primary' : 'default'" @click="tierForUi = 'low'">
              低分 0–4
            </n-button>
            <n-button size="small" :type="tierForUi === 'mid' ? 'primary' : 'default'" @click="tierForUi = 'mid'">
              中分 5–9
            </n-button>
            <n-button size="small" :type="tierForUi === 'high' ? 'primary' : 'default'" @click="tierForUi = 'high'">
              高分 ≥10
            </n-button>
          </n-space>
          <n-space vertical>
            <n-checkbox
              :checked="chk('today_not_played')"
              @update:checked="(v) => toggleFilter('today_not_played', v)"
            >
              今日未参赛
            </n-checkbox>
            <n-checkbox
              :checked="chk('today_not_won')"
              @update:checked="(v) => toggleFilter('today_not_won', v)"
            >
              今日未获胜
            </n-checkbox>
            <n-checkbox
              :checked="chk('today_played_lte_1')"
              @update:checked="(v) => toggleFilter('today_played_lte_1', v)"
            >
              今日参赛 ≤1 场
            </n-checkbox>
            <n-checkbox
              :checked="chk('today_played_eq_1')"
              @update:checked="(v) => toggleFilter('today_played_eq_1', v)"
            >
              今日仅参赛 1 场
            </n-checkbox>
            <n-checkbox :checked="chk('online_only')" @update:checked="(v) => toggleFilter('online_only', v)">
              仅在线
            </n-checkbox>
          </n-space>
        </n-space>
      </n-card>

      <n-card title="选手列表">
        <n-data-table
          :loading="loading"
          :columns="columns"
          :data="players"
          :row-key="(row: Player) => row.id"
          :checked-row-keys="checkedRowKeys"
          :row-props="rowProps"
          @update:checked-row-keys="onCheckedRowKeys"
        />
      </n-card>
    </n-space>

    <div
      style="
        position: sticky;
        bottom: 0;
        margin-top: 16px;
        padding: 12px 16px;
        background: rgba(24, 24, 28, 0.92);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 8px;
        display: flex;
        justify-content: space-between;
        align-items: center;
        gap: 12px;
        flex-wrap: wrap;
      "
    >
      <span>已选 {{ selectedCount }} / 10 人</span>
      <n-button type="primary" :disabled="!canCreate" :loading="creating" @click="onCreateMatch">
        创建比赛
      </n-button>
    </div>

    <n-space vertical size="large" style="margin-top: 16px">
      <n-card title="添加选手（不常用）" size="small">
        <n-space vertical>
          <n-text depth="3">「累计积分」为截至入库前的胜场累计分；之后在系统里录入的比赛仍会照常加减。</n-text>
          <n-space align="center" style="flex-wrap: wrap">
            <n-input v-model:value="newName" placeholder="选手名称" style="max-width: 240px" />
            <n-space align="center" size="small">
              <span>初始积分</span>
              <n-input-number v-model:value="newInitialScore" :min="0" :precision="0" placeholder="0" style="width: 120px" />
            </n-space>
            <n-button type="primary" @click="onAddPlayer">添加</n-button>
          </n-space>
        </n-space>
      </n-card>

      <n-card title="批量导入选手（不常用）" size="small">
        <n-space vertical>
          <n-text depth="3">
            每行一名选手：「姓名」或「姓名,积分」（可用英文逗号、中文逗号或 Tab 分隔）。同一姓名多行时以最后一行为准；库中已有同名选手将覆盖其累计积分。
          </n-text>
          <n-input
            v-model:value="bulkText"
            type="textarea"
            placeholder="张三,3&#10;李四&#10;王五,0"
            :rows="8"
            spellcheck="false"
          />
          <n-button type="primary" :loading="bulkImporting" @click="runBulkImport">执行批量导入</n-button>
        </n-space>
      </n-card>
    </n-space>

    <n-modal v-model:show="scoreModalShow" :mask-closable="false" style="width: 440px">
      <n-card title="修改累计积分" :bordered="false" size="small">
        <n-space vertical size="large">
          <n-space vertical>
            <n-text v-if="scoreEditing">选手：{{ scoreEditing.name }}</n-text>
            <n-space align="center">
              <span>累计积分（胜场数）</span>
              <n-input-number v-model:value="scoreDraft" :min="0" :precision="0" style="width: 160px" />
            </n-space>
            <n-text depth="3" style="font-size: 12px">用于补录线下已有成绩；积分为非负整数，后续本场内胜负仍会照常加减。</n-text>
          </n-space>
          <n-space justify="end">
            <n-button @click="scoreModalShow = false">取消</n-button>
            <n-button type="primary" :loading="scoreSaving" @click="saveScoreFromModal">保存</n-button>
          </n-space>
        </n-space>
      </n-card>
    </n-modal>
  </main-layout>
</template>
