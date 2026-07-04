<script setup lang="ts">
import { computed, h, onMounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { NButton, NCard, NDataTable, NSelect, useMessage, type DataTableColumns } from "naive-ui";
import type { RankingRow, Season } from "@/api";
import { fetchRankings, fetchSeasons } from "@/api";
import MainLayout from "@/components/MainLayout.vue";
import PageHeader from "@/components/PageHeader.vue";
import { useIsMobile } from "@/composables/useIsMobile";

const route = useRoute();
const router = useRouter();
const message = useMessage();
const rows = ref<RankingRow[]>([]);
const loading = ref(false);
const seasons = ref<Season[]>([]);
// null = 当前赛季
const selectedSeasonId = ref<number | null>(null);
const isMobile = useIsMobile();

const seasonOptions = computed(() => {
  const opts: { label: string; value: number | null }[] = [
    { label: "当前赛季", value: null },
  ];
  for (const s of seasons.value) {
    opts.push({
      label: `${s.name}${s.is_current ? "（进行中）" : "（已封存）"}`,
      value: s.id,
    });
  }
  return opts;
});

const currentSeasonName = computed(() => {
  if (selectedSeasonId.value == null) {
    const cur = seasons.value.find((s) => s.is_current);
    return cur?.name ?? "当前赛季";
  }
  return seasons.value.find((s) => s.id === selectedSeasonId.value)?.name ?? "";
});

async function load() {
  loading.value = true;
  try {
    rows.value = await fetchRankings(selectedSeasonId.value ?? undefined);
  } catch (e) {
    message.error((e as Error).message);
  } finally {
    loading.value = false;
  }
}

async function loadSeasons() {
  try {
    seasons.value = await fetchSeasons();
  } catch {
    // 忽略
  }
}

onMounted(async () => {
  await loadSeasons();
  // 从 URL ?season_id=N 读取初始值
  const fromQuery = route.query.season_id;
  if (typeof fromQuery === "string") {
    const id = Number(fromQuery);
    if (!Number.isNaN(id)) selectedSeasonId.value = id;
  }
  await load();
});

watch(selectedSeasonId, (v) => {
  // 同步到 URL，便于分享
  router.replace({
    path: "/rankings",
    query: v == null ? {} : { season_id: String(v) },
  });
  load();
});

function rankColor(rank: number): string {
  if (rank === 1) return "#c9962a";
  if (rank === 2) return "#7a8896";
  if (rank === 3) return "#a86a30";
  return "#7a8390";
}

function renderRankBadge(row: RankingRow) {
  const color = rankColor(row.rank);
  const isTop3 = row.rank <= 3;
  return h(
    "div",
    {
      style: {
        display: "inline-flex",
        alignItems: "center",
        justifyContent: "center",
        minWidth: "32px",
        height: "26px",
        padding: "0 10px",
        background: isTop3 ? `${color}1a` : "#f6f8fb",
        border: isTop3 ? `1px solid ${color}55` : "1px solid #e8ecf2",
        borderRadius: "3px",
        color: color,
        fontWeight: isTop3 ? "700" : "500",
        fontSize: "13px",
        fontFamily: '"SF Mono", "Courier New", monospace',
      },
    },
    String(row.rank).padStart(2, "0"),
  );
}

function renderPlayerCell(row: RankingRow, compact: boolean) {
  const isTop3 = row.rank <= 3;
  const medal =
    row.prev_season_rank === 1
      ? "🥇"
      : row.prev_season_rank === 2
        ? "🥈"
        : row.prev_season_rank === 3
          ? "🥉"
          : null;
  const nameRow = h(
    "span",
    {
      style: {
        display: "inline-flex",
        alignItems: "center",
        gap: "5px",
        color: "#1a2435",
        fontWeight: isTop3 ? "600" : "400",
        fontSize: compact ? "14px" : "13px",
        whiteSpace: "nowrap",
        overflow: "hidden",
        textOverflow: "ellipsis",
        maxWidth: "100%",
      },
    },
    [
      medal ? h("span", { style: { fontSize: "14px" } }, medal) : null,
      h("span", null, row.name),
    ],
  );
  const tagChips = (row.top_tags ?? []).slice(0, 3).map((t) =>
    h(
      "span",
      { class: "mini-tag", key: t.tag_id, title: `${t.label} · ${t.count} 票` },
      [
        h("span", { class: "mini-tag-label" }, t.label),
        h("span", { class: "mini-tag-count" }, String(t.count)),
      ],
    ),
  );
  const tagRow = tagChips.length > 0 ? h("div", { class: "mini-tag-row" }, tagChips) : null;
  return h("div", { class: "rk-player-cell" }, [nameRow, tagRow].filter(Boolean));
}

function renderScoreCell(row: RankingRow, compact: boolean) {
  return h(
    "span",
    {
      style: {
        color: "#2c6dc1",
        fontWeight: "600",
        fontSize: compact ? "16px" : "15px",
        fontFamily: '"SF Mono", "Courier New", monospace',
      },
    },
    row.current_score,
  );
}

const desktopColumns: DataTableColumns<RankingRow> = [
  {
    title: "名次",
    key: "rank",
    width: 90,
    render: renderRankBadge,
  },
  {
    title: "选手",
    key: "name",
    render: (row) => renderPlayerCell(row, false),
  },
  {
    title: "积分",
    key: "current_score",
    width: 140,
    render: (row) => renderScoreCell(row, false),
  },
];

const mobileColumns: DataTableColumns<RankingRow> = [
  {
    title: "名次",
    key: "rank",
    width: 56,
    render: renderRankBadge,
  },
  {
    title: "选手",
    key: "name",
    render: (row) => renderPlayerCell(row, true),
  },
  {
    title: "积分",
    key: "current_score",
    width: 70,
    render: (row) => renderScoreCell(row, true),
  },
];

const columns = computed<DataTableColumns<RankingRow>>(() =>
  isMobile.value ? mobileColumns : desktopColumns,
);
</script>

<template>
  <main-layout>
    <page-header title="排行榜" :subtitle="currentSeasonName" />

    <n-card>
      <div class="filter-bar">
        <span class="filter-label">赛季</span>
        <n-select
          v-model:value="selectedSeasonId"
          :options="seasonOptions"
          style="width: 220px"
          size="small"
        />
        <n-button size="small" tertiary @click="load">刷新</n-button>
      </div>
      <n-data-table
        :loading="loading"
        :columns="columns"
        :data="rows"
        :row-key="(r: RankingRow) => r.player_id"
      />
    </n-card>
  </main-layout>
</template>

<style scoped>
.filter-bar {
  display: flex;
  gap: 10px;
  align-items: center;
  flex-wrap: wrap;
  margin-bottom: 14px;
  padding-bottom: 14px;
  border-bottom: 1px solid #eef1f5;
}
.filter-label {
  color: #5a6473;
  font-size: 12px;
  font-weight: 500;
}
</style>

<style>
/* h() 渲染的单元格需要非 scoped；与 PlayersView 的 mini-tag 样式保持一致 */
.rk-player-cell {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 2px 0;
  min-width: 0;
}
.mini-tag-row {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}
.mini-tag {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  padding: 1px 7px;
  font-size: 11px;
  border-radius: 10px;
  background: rgba(44, 109, 193, 0.07);
  color: #4d5663;
  border: 1px solid rgba(44, 109, 193, 0.18);
  line-height: 1.5;
}
.mini-tag-label {
  font-weight: 500;
}
.mini-tag-count {
  font-family: '"SF Mono", "Courier New", monospace';
  font-size: 10px;
  color: #2c6dc1;
  font-weight: 600;
}
</style>
