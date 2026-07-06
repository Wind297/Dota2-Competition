<script setup lang="ts">
import { computed, h, onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import {
  NButton,
  NCard,
  NCheckbox,
  NDataTable,
  NInput,
  NModal,
  NSpace,
  NTag,
  NText,
  useDialog,
  useMessage,
  type DataTableColumns,
} from "naive-ui";
import type { Season, FinalRankEntry } from "@/api";
import {
  createSeason,
  endSeason,
  fetchPlayers,
  fetchSeasons,
  getFinalRanks,
  isAdmin,
  recalculateSeasonScores,
  rolloverSeason,
  setFinalRanks,
} from "@/api";
import { NSelect } from "naive-ui";
import MainLayout from "@/components/MainLayout.vue";
import PageHeader from "@/components/PageHeader.vue";

const router = useRouter();
const message = useMessage();
const dialog = useDialog();
const adminMode = isAdmin();

const seasons = ref<Season[]>([]);
const loading = ref(false);

async function load() {
  loading.value = true;
  try {
    seasons.value = await fetchSeasons();
  } catch (e) {
    message.error((e as Error).message);
  } finally {
    loading.value = false;
  }
}

onMounted(load);

const currentSeason = computed(() => seasons.value.find((s) => s.is_current) ?? null);
const hasCurrent = computed(() => currentSeason.value !== null);

// ── 创建/切换赛季 Modal ───────────────────────────────────────
const modalShow = ref(false);
// "create" = 没有当前赛季，仅创建一个新的
// "rollover" = 当前赛季会被结束并开启新赛季
const modalMode = ref<"create" | "rollover">("create");
const newSeasonName = ref("");
const inheritActivePlayers = ref(true);
const saving = ref(false);

function nextDefaultName(): string {
  const nextNo = seasons.value.length + 1;
  return `第 ${nextNo} 赛季`;
}

/** 智能开启新赛季：根据当前是否有活跃赛季自动选择行为 */
function openNewSeasonModal() {
  if (hasCurrent.value) {
    modalMode.value = "rollover";
    inheritActivePlayers.value = true;
  } else {
    modalMode.value = "create";
    inheritActivePlayers.value = seasons.value.length > 0; // 第一个赛季无可继承
  }
  newSeasonName.value = nextDefaultName();
  modalShow.value = true;
}

async function confirmModal() {
  const name = newSeasonName.value.trim();
  if (!name) {
    message.warning("请输入赛季名称");
    return;
  }
  saving.value = true;
  try {
    if (modalMode.value === "create") {
      await createSeason(name, inheritActivePlayers.value);
      message.success(`已开启「${name}」`);
    } else {
      await rolloverSeason(name, inheritActivePlayers.value);
      message.success(`上一赛季已封存，「${name}」开始`);
    }
    modalShow.value = false;
    await load();
  } catch (e) {
    message.error((e as Error).message);
  } finally {
    saving.value = false;
  }
}

function confirmEndSeason(s: Season) {
  dialog.warning({
    title: `结束赛季「${s.name}」？`,
    content: "结束后该赛季的所有比赛将变为只读，无法再编辑或删除。结束后可继续开启下一赛季。",
    positiveText: "结束",
    negativeText: "取消",
    onPositiveClick: async () => {
      try {
        await endSeason(s.id);
        message.success("赛季已结束并封存");
        await load();
        // 引导用户开下一赛季
        setTimeout(() => promptOpenNextSeason(), 300);
        return true;
      } catch (e) {
        message.error((e as Error).message);
        return false;
      }
    },
  });
}

function promptOpenNextSeason() {
  dialog.info({
    title: "是否开启下一赛季？",
    content: "上一赛季已封存为只读。现在可以创建新赛季并继承上赛季的活跃选手（积分清零）。",
    positiveText: "开启新赛季",
    negativeText: "稍后",
    onPositiveClick: () => {
      openNewSeasonModal();
    },
  });
}

function confirmRecalculateScores(s: Season) {
  dialog.warning({
    title: `按比赛记录重置「${s.name}」积分？`,
    content:
      "将把本赛季所有选手的当前积分重置为「比赛累计 score_delta 之和」。之前管理员手动加减的分数会被抹掉，重置后请用「修改选手」功能逐条补回（每补一条会留一条管理员调整记录）。此操作不可撤销。",
    positiveText: "确认重置",
    negativeText: "取消",
    onPositiveClick: async () => {
      try {
        const res = await recalculateSeasonScores(s.id);
        message.success(`已重置，更新 ${res.updated} 名选手。请手动补回之前的手动调整。`);
        await load();
        return true;
      } catch (e) {
        message.error((e as Error).message);
        return false;
      }
    },
  });
}

function viewRankings(s: Season) {
  router.push({ path: "/rankings", query: { season_id: String(s.id) } });
}

// ── 录入决赛名次 Modal ──────────────────────────────────────────
const rankModalShow = ref(false);
const rankSeasonId = ref<number | null>(null);
const rankSeasonName = ref("");
const rankSaving = ref(false);
const allPlayers = ref<{ label: string; value: number }[]>([]);

// 名次数据：冠军5人、亚军5人、季军5人
const champIds = ref<number[]>([]);
const runnerUpIds = ref<number[]>([]);
const thirdIds = ref<number[]>([]);

async function openRankModal(s: Season) {
  rankSeasonId.value = s.id;
  rankSeasonName.value = s.name;
  rankSaving.value = false;

  // 加载选手列表作为选项
  try {
    const players = await fetchPlayers({}, true);
    allPlayers.value = players.map((p) => ({ label: p.name, value: p.id }));
  } catch {
    message.error("加载选手列表失败");
    return;
  }

  // 加载已有名次
  try {
    const existing = await getFinalRanks(s.id);
    champIds.value = existing.filter((e) => e.rank === 1).map((e) => e.player_id);
    runnerUpIds.value = existing.filter((e) => e.rank === 2).map((e) => e.player_id);
    thirdIds.value = existing.filter((e) => e.rank === 3).map((e) => e.player_id);
  } catch {
    champIds.value = [];
    runnerUpIds.value = [];
    thirdIds.value = [];
  }

  rankModalShow.value = true;
}

async function saveRanks() {
  if (!rankSeasonId.value) return;
  const entries: FinalRankEntry[] = [
    ...champIds.value.map((id) => ({ player_id: id, rank: 1 })),
    ...runnerUpIds.value.map((id) => ({ player_id: id, rank: 2 })),
    ...thirdIds.value.map((id) => ({ player_id: id, rank: 3 })),
  ];
  if (entries.length === 0) {
    message.warning("请至少选择一名选手");
    return;
  }
  rankSaving.value = true;
  try {
    await setFinalRanks(rankSeasonId.value, entries);
    message.success("名次已保存");
    rankModalShow.value = false;
  } catch (e) {
    message.error((e as Error).message);
  } finally {
    rankSaving.value = false;
  }
}

const columns: DataTableColumns<Season> = [
  {
    title: "赛季",
    key: "name",
    render(row) {
      return h(
        "div",
        { style: { display: "flex", alignItems: "center", gap: "10px" } },
        [
          h(
            "span",
            {
              style: {
                color: "#1a2435",
                fontWeight: row.is_current ? "600" : "500",
                fontSize: "14px",
              },
            },
            row.name,
          ),
          row.is_current
            ? h(
                NTag,
                {
                  type: "success",
                  size: "small",
                  bordered: false,
                  style: {
                    background: "rgba(58, 157, 87, 0.12)",
                    color: "#3a9d57",
                  },
                },
                { default: () => "进行中" },
              )
            : h(
                NTag,
                {
                  size: "small",
                  bordered: false,
                  style: {
                    background: "#f0f3f7",
                    color: "#7a8390",
                  },
                },
                { default: () => "已封存" },
              ),
        ],
      );
    },
  },
  {
    title: "选手数",
    key: "player_count",
    width: 100,
    render(row) {
      return h(
        "span",
        { style: { fontFamily: '"SF Mono", "Courier New", monospace', color: "#4d5663" } },
        row.player_count,
      );
    },
  },
  {
    title: "比赛数",
    key: "match_count",
    width: 100,
    render(row) {
      return h(
        "span",
        { style: { fontFamily: '"SF Mono", "Courier New", monospace', color: "#4d5663" } },
        row.match_count,
      );
    },
  },
  {
    title: "起止时间",
    key: "time",
    render(row) {
      const start = new Date(row.started_at).toLocaleDateString("zh-CN");
      const end = row.ended_at ? new Date(row.ended_at).toLocaleDateString("zh-CN") : "—";
      return h(
        "span",
        { style: { fontSize: "12px", color: "#5a6473" } },
        `${start} → ${end}`,
      );
    },
  },
  {
    title: "操作",
    key: "actions",
    width: 400,
    render(row) {
      const buttons: ReturnType<typeof h>[] = [
        h(
          "button",
          {
            class: "row-action-btn primary",
            onClick: () => viewRankings(row),
          },
          "查看排行榜",
        ),
      ];
      if (adminMode) {
        buttons.push(
          h(
            "button",
            {
              class: "row-action-btn primary",
              onClick: () => openRankModal(row),
            },
            "录入名次",
          ),
        );
      }
      if (adminMode && row.is_current) {
        buttons.push(
          h(
            "button",
            {
              class: "row-action-btn danger",
              onClick: () => confirmRecalculateScores(row),
            },
            "按比赛重置积分",
          ),
        );
        buttons.push(
          h(
            "button",
            {
              class: "row-action-btn danger",
              onClick: () => confirmEndSeason(row),
            },
            "结束赛季",
          ),
        );
      }
      return h("div", { class: "row-actions" }, buttons);
    },
  },
];

const newSeasonBtnLabel = computed(() => {
  if (hasCurrent.value) return "结束当前 · 开启新赛季";
  if (seasons.value.length === 0) return "开启首个赛季";
  return "开启新赛季";
});
</script>

<template>
  <main-layout>
    <page-header title="赛季管理" subtitle="Seasons" />

    <n-card title="赛季列表">
      <template #header-extra>
        <n-space size="small">
          <n-button v-if="adminMode" type="primary" size="small" @click="openNewSeasonModal">
            {{ newSeasonBtnLabel }}
          </n-button>
          <n-button size="small" tertiary @click="load">刷新</n-button>
        </n-space>
      </template>

      <div v-if="!hasCurrent && adminMode" class="warn-banner">
        当前没有进行中的赛季。请先开启一个赛季后才能录入选手与比赛。
      </div>

      <n-data-table
        :loading="loading"
        :columns="columns"
        :data="seasons"
        :row-key="(r: Season) => r.id"
      />
    </n-card>

    <!-- 创建/切换赛季 Modal -->
    <n-modal v-if="adminMode" v-model:show="modalShow" :mask-closable="false" style="width: 480px">
      <n-card
        :title="modalMode === 'create' ? '开启新赛季' : '结束当前并开启新赛季'"
        :bordered="false"
        size="small"
      >
        <n-space vertical size="large">
          <n-text v-if="modalMode === 'rollover'" depth="3">
            将把当前赛季「{{ currentSeason?.name }}」封存为只读，然后开启新赛季。
            上赛季的活跃选手可继承到新赛季（积分清零）。
          </n-text>
          <n-text v-else depth="3">
            创建新赛季后，所有新的选手与比赛都将归属此赛季。
          </n-text>

          <div>
            <div class="field-label">新赛季名称</div>
            <n-input
              v-model:value="newSeasonName"
              placeholder="如：第 2 赛季"
              maxlength="64"
              show-count
              style="width: 100%"
              @keydown.enter="confirmModal"
            />
          </div>

          <div v-if="seasons.length > 0">
            <n-checkbox v-model:checked="inheritActivePlayers">
              继承上一赛季的活跃选手到新赛季（积分清零）
            </n-checkbox>
            <div class="field-hint">
              不勾选则新赛季选手池为空，需手动添加或导入。
            </div>
          </div>

          <n-space justify="end">
            <n-button @click="modalShow = false">取消</n-button>
            <n-button
              :type="modalMode === 'rollover' ? 'warning' : 'primary'"
              :loading="saving"
              @click="confirmModal"
            >
              {{ modalMode === "rollover" ? "确认结束并开启" : "开启新赛季" }}
            </n-button>
          </n-space>
        </n-space>
      </n-card>
    </n-modal>
    <!-- 录入名次 Modal -->
    <n-modal v-if="adminMode" v-model:show="rankModalShow" :mask-closable="false" style="width: 560px">
      <n-card :title="`录入决赛名次 · ${rankSeasonName}`" :bordered="false" size="small">
        <n-space vertical size="large">
          <n-text depth="3">
            选择冠军、亚军、季军队伍（各 5 人）。可反复录入覆盖之前的数据。
          </n-text>

          <div>
            <div class="rank-label">🥇 冠军（5 人）</div>
            <n-select
              v-model:value="champIds"
              multiple
              filterable
              :options="allPlayers"
              :max-tag-count="5"
              placeholder="搜索并选择冠军队伍"
              style="width: 100%"
            />
          </div>

          <div>
            <div class="rank-label">🥈 亚军（5 人）</div>
            <n-select
              v-model:value="runnerUpIds"
              multiple
              filterable
              :options="allPlayers"
              :max-tag-count="5"
              placeholder="搜索并选择亚军队伍"
              style="width: 100%"
            />
          </div>

          <div>
            <div class="rank-label">🥉 季军（5 人）</div>
            <n-select
              v-model:value="thirdIds"
              multiple
              filterable
              :options="allPlayers"
              :max-tag-count="5"
              placeholder="搜索并选择季军队伍"
              style="width: 100%"
            />
          </div>

          <n-space justify="end">
            <n-button @click="rankModalShow = false">取消</n-button>
            <n-button type="primary" :loading="rankSaving" @click="saveRanks">
              保存名次
            </n-button>
          </n-space>
        </n-space>
      </n-card>
    </n-modal>
  </main-layout>
</template>

<style scoped>
.warn-banner {
  margin-bottom: 14px;
  padding: 10px 14px;
  background: rgba(185, 115, 36, 0.08);
  border-left: 3px solid #b97324;
  font-size: 13px;
  color: #1a2435;
  border-radius: 0 4px 4px 0;
}
.field-label {
  font-size: 13px;
  font-weight: 500;
  color: #1a2435;
  margin-bottom: 6px;
}
.field-hint {
  font-size: 11px;
  color: #7a8390;
  margin-top: 5px;
}
.rank-label {
  font-size: 13px;
  font-weight: 600;
  color: #1a2435;
  margin-bottom: 6px;
}
</style>

<style>
.row-actions {
  display: inline-flex;
  gap: 6px;
}
.row-action-btn {
  font-family: inherit;
  font-size: 12px;
  padding: 4px 10px;
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.15s;
  border: 1px solid;
  background: #ffffff;
  line-height: 1.4;
}
.row-action-btn.primary {
  border-color: #2c6dc1;
  color: #2c6dc1;
}
.row-action-btn.primary:hover {
  background: #2c6dc1;
  color: #ffffff;
}
.row-action-btn.danger {
  border-color: #d6c0bd;
  color: #c1554a;
}
.row-action-btn.danger:hover {
  background: #c1554a;
  color: #ffffff;
  border-color: #c1554a;
}
</style>
