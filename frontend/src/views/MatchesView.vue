<script setup lang="ts">
import { h, onMounted, ref, watch } from "vue";
import { useRouter } from "vue-router";
import { NButton, NCard, NDataTable, NSelect, NTag, NSpace, useDialog, useMessage, type DataTableColumns } from "naive-ui";
import type { MatchRecord } from "@/api";
import { deleteMatch, fetchMatches } from "@/api";
import MainLayout from "@/components/MainLayout.vue";

const router = useRouter();
const message = useMessage();
const dialog = useDialog();
const rows = ref<MatchRecord[]>([]);
const loading = ref(false);
const status = ref<string | "all">("all");

const statusOptions = [
  { label: "全部", value: "all" },
  { label: "已确认", value: "confirmed" },
  { label: "已完赛", value: "completed" },
];

async function load() {
  loading.value = true;
  try {
    const s = status.value === "all" ? undefined : status.value;
    rows.value = await fetchMatches(s ? { status: s } : undefined);
  } catch {
    message.error("加载比赛失败");
  } finally {
    loading.value = false;
  }
}

onMounted(load);
watch(status, load);

function confirmDeleteRow(row: MatchRecord) {
  dialog.error({
    title: `删除比赛 #${row.id}？`,
    content:
      row.status === "completed"
        ? "已完赛：删除后将回退本场胜者获得的积分。"
        : "已确认未完成：删除不产生积分变化。",
    positiveText: "删除",
    negativeText: "取消",
    onPositiveClick: async () => {
      try {
        await deleteMatch(row.id);
        message.success("已删除");
        await load();
        return true;
      } catch (e) {
        message.error((e as Error).message);
        return false;
      }
    },
  });
}

const columns: DataTableColumns<MatchRecord> = [
  { title: "ID", key: "id", width: 70 },
  {
    title: "状态",
    key: "status",
    width: 100,
    render(row) {
      const type = row.status === "completed" ? "success" : "warning";
      const text = row.status === "completed" ? "已完赛" : "已确认";
      return h(NTag, { type }, { default: () => text });
    },
  },
  {
    title: "比赛日窗口起点",
    key: "matchday_start",
    render(row) {
      return new Date(row.matchday_start).toLocaleString("zh-CN");
    },
  },
  {
    title: "创建时间",
    key: "created_at",
    render(row) {
      return new Date(row.created_at).toLocaleString("zh-CN");
    },
  },
  {
    title: "操作",
    key: "actions",
    width: 200,
    render(row) {
      return h(
        NSpace,
        { size: "small" },
        {
          default: () => [
            h(
              NButton,
              {
                size: "small",
                type: "primary",
                quaternary: true,
                onClick: () => router.push({ name: "match-detail", params: { id: String(row.id) } }),
              },
              { default: () => "详情" },
            ),
            h(
              NButton,
              {
                size: "small",
                type: "error",
                quaternary: true,
                onClick: () => confirmDeleteRow(row),
              },
              { default: () => "删除" },
            ),
          ],
        },
      );
    },
  },
];
</script>

<template>
  <main-layout>
    <n-card title="历史比赛">
      <div style="margin-bottom: 12px; display: flex; gap: 12px; align-items: center; flex-wrap: wrap">
        <span>状态筛选</span>
        <n-select v-model:value="status" :options="statusOptions" style="width: 200px" />
        <n-button @click="load">刷新</n-button>
      </div>
      <n-data-table :loading="loading" :columns="columns" :data="rows" :row-key="(r: MatchRecord) => r.id" />
    </n-card>
  </main-layout>
</template>
