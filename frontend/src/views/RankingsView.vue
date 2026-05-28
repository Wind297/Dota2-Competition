<script setup lang="ts">
import { h, onMounted, ref } from "vue";
import { NButton, NCard, NDataTable, useMessage, type DataTableColumns } from "naive-ui";
import type { RankingRow } from "@/api";
import { fetchRankings } from "@/api";
import MainLayout from "@/components/MainLayout.vue";
import PageHeader from "@/components/PageHeader.vue";

const message = useMessage();
const rows = ref<RankingRow[]>([]);
const loading = ref(false);

async function load() {
  loading.value = true;
  try {
    rows.value = await fetchRankings();
  } catch {
    message.error("加载排行榜失败");
  } finally {
    loading.value = false;
  }
}

onMounted(load);

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
      return h(
        "span",
        {
          style: {
            color: "#1a2435",
            fontWeight: isTop3 ? "600" : "400",
          },
        },
        row.name,
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
    <page-header title="排行榜" subtitle="Rankings" />

    <n-card>
      <template #header-extra>
        <n-button size="small" tertiary @click="load">刷新</n-button>
      </template>
      <n-data-table
        :loading="loading"
        :columns="columns"
        :data="rows"
        :row-key="(r: RankingRow) => r.player_id"
      />
    </n-card>
  </main-layout>
</template>
