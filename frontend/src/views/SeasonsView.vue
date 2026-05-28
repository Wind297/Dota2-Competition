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
import type { Season } from "@/api";
import {
  createSeason,
  endSeason,
  fetchSeasons,
  isAdmin,
  rolloverSeason,
} from "@/api";
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

function viewRankings(s: Season) {
  router.push({ path: "/rankings", query: { season_id: String(s.id) } });
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
    width: 220,
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
      if (adminMode && row.is_current) {
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
