<script setup lang="ts">
import { h, onMounted, ref, watch } from "vue";
import { useRouter } from "vue-router";
import { NButton, NCard, NDataTable, NSelect, NTag, NSpace, useDialog, useMessage, type DataTableColumns } from "naive-ui";
import type { MatchRecord } from "@/api";
import { deleteMatch, fetchMatches, formatMatchTitle, isAdmin } from "@/api";
import MainLayout from "@/components/MainLayout.vue";
import PageHeader from "@/components/PageHeader.vue";

const router = useRouter();
const message = useMessage();
const dialog = useDialog();
const rows = ref<MatchRecord[]>([]);
const loading = ref(false);
const status = ref<string | "all">("all");
const adminMode = isAdmin();

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

function goDetail(row: MatchRecord) {
  router.push({ name: "match-detail", params: { id: String(row.id) } });
}

const columns: DataTableColumns<MatchRecord> = [
  {
    title: "ID",
    key: "id",
    width: 80,
    render(row) {
      return h(
        "span",
        {
          style: {
            color: "#7a8390",
            fontFamily: '"SF Mono", "Courier New", monospace',
            fontSize: "12px",
          },
        },
        `#${row.id}`,
      );
    },
  },
  {
    title: "状态",
    key: "status",
    width: 110,
    render(row) {
      const isCompleted = row.status === "completed";
      return h(
        "span",
        {
          style: {
            display: "inline-flex",
            alignItems: "center",
            gap: "6px",
            padding: "3px 10px",
            fontSize: "12px",
            fontWeight: "500",
            borderRadius: "3px",
            background: isCompleted ? "rgba(58, 157, 87, 0.10)" : "rgba(185, 115, 36, 0.10)",
            color: isCompleted ? "#3a9d57" : "#b97324",
          },
        },
        [
          h("span", {
            style: {
              width: "6px",
              height: "6px",
              borderRadius: "50%",
              background: "currentColor",
            },
          }),
          isCompleted ? "已完赛" : "已确认",
        ],
      );
    },
  },
  {
    title: "比赛名称",
    key: "title",
    render(row) {
      return h(
        "span",
        { style: { color: "#1a2435", fontSize: "13px", fontWeight: "500" } },
        formatMatchTitle(row),
      );
    },
  },
  {
    title: "创建时间",
    key: "created_at",
    width: 180,
    render(row) {
      return h(
        "span",
        { style: { color: "#7a8390", fontSize: "12px" } },
        new Date(row.created_at).toLocaleString("zh-CN"),
      );
    },
  },
  {
    title: "操作",
    key: "actions",
    width: adminMode ? 200 : 120,
    render(row) {
      const buttons: ReturnType<typeof h>[] = [
        h(
          "button",
          {
            class: "row-action-btn primary",
            onClick: () => goDetail(row),
          },
          "查看详情",
        ),
      ];
      if (adminMode) {
        buttons.push(
          h(
            "button",
            {
              class: "row-action-btn danger",
              onClick: () => confirmDeleteRow(row),
            },
            "删除",
          ),
        );
      }
      return h("div", { class: "row-actions" }, buttons);
    },
  },
];
</script>

<template>
  <main-layout>
    <page-header title="比赛记录" subtitle="Match History" />

    <n-card>
      <div class="filter-bar">
        <span class="filter-label">状态</span>
        <n-select v-model:value="status" :options="statusOptions" style="width: 160px" size="small" />
        <n-button size="small" tertiary @click="load">刷新</n-button>
      </div>
      <n-data-table :loading="loading" :columns="columns" :data="rows" :row-key="(r: MatchRecord) => r.id" />
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
/* 操作列按钮（非 scoped，避免 h() 渲染时类名失效） */
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
