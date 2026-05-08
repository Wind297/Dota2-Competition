<script setup lang="ts">
import { onMounted, ref } from "vue";
import { NButton, NCard, NDataTable, useMessage, type DataTableColumns } from "naive-ui";
import type { RankingRow } from "@/api";
import { fetchRankings } from "@/api";
import MainLayout from "@/components/MainLayout.vue";

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

const columns: DataTableColumns<RankingRow> = [
  { title: "名次", key: "rank", width: 90 },
  { title: "选手", key: "name" },
  { title: "积分", key: "current_score", width: 120 },
];
</script>

<template>
  <main-layout>
    <n-card title="积分榜">
      <div style="margin-bottom: 12px">
        <n-button size="small" quaternary @click="load">刷新</n-button>
      </div>
      <n-data-table :loading="loading" :columns="columns" :data="rows" :row-key="(r: RankingRow) => r.player_id" />
    </n-card>
  </main-layout>
</template>
