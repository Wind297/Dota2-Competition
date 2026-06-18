<script setup lang="ts">
import { computed, h, onMounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { NButton, NCard, NDataTable, NSelect, useMessage, type DataTableColumns } from "naive-ui";
import type { RankingRow, Season } from "@/api";
import { fetchRankings, fetchSeasons } from "@/api";
import MainLayout from "@/components/MainLayout.vue";
import PageHeader from "@/components/PageHeader.vue";

const route = useRoute();
const router = useRouter();
const message = useMessage();
const rows = ref<RankingRow[]>([]);
const loading = ref(false);
const seasons = ref<Season[]>([]);
// null = 当前赛季
const selectedSeasonId = ref<number | null>(null);

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

const columns: DataTableColumns<RankingRow> = [
  {
    title: "名次",
    key: "rank",
    width: 90,
    render(row) {
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
    },
  },
  {
    title: "选手",
    key: "name",
    render(row) {
      const isTop3 = row.rank <= 3;
      const medal =
        row.prev_season_rank === 1
          ? "🥇"
          : row.prev_season_rank === 2
            ? "🥈"
            : row.prev_season_rank === 3
              ? "🥉"
              : null;
      return h(
        "span",
        {
          style: {
            display: "inline-flex",
            alignItems: "center",
            gap: "5px",
            color: "#1a2435",
            fontWeight: isTop3 ? "600" : "400",
          },
        },
        [
          medal ? h("span", { style: { fontSize: "14px" } }, medal) : null,
          h("span", null, row.name),
        ],
      );
    },
  },
  {
    title: "积分",
    key: "current_score",
    width: 140,
    render(row) {
      return h(
        "span",
        {
          style: {
            color: "#2c6dc1",
            fontWeight: "600",
            fontSize: "15px",
            fontFamily: '"SF Mono", "Courier New", monospace',
          },
        },
        row.current_score,
      );
    },
  },
];
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
