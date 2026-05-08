<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import {
  NButton,
  NCard,
  NCheckbox,
  NSpace,
  NTag,
  NText,
  useDialog,
  useMessage,
} from "naive-ui";
import type { MatchRecord } from "@/api";
import { deleteMatch, fetchMatch, submitMatchResult } from "@/api";
import MainLayout from "@/components/MainLayout.vue";

const props = defineProps<{ id: string }>();
const router = useRouter();
const message = useMessage();
const dialog = useDialog();

const matchId = computed(() => Number(props.id));
const match = ref<MatchRecord | null>(null);
const loading = ref(false);
const submitting = ref(false);
const winners = ref<Set<number>>(new Set());

async function load() {
  loading.value = true;
  try {
    match.value = await fetchMatch(matchId.value);
    const w = new Set<number>();
    for (const p of match.value.players) {
      if (p.is_winner === true) w.add(p.player_id);
    }
    winners.value = w;
  } catch {
    message.error("加载比赛失败");
    match.value = null;
  } finally {
    loading.value = false;
  }
}

onMounted(load);

function toggleWinner(pid: number, checked: boolean) {
  const next = new Set(winners.value);
  if (checked) {
    if (next.size >= 5) {
      message.warning("最多选择 5 名获胜者");
      return;
    }
    next.add(pid);
  } else {
    next.delete(pid);
  }
  winners.value = next;
}

const canSubmit = computed(() => {
  if (!match.value || match.value.status !== "confirmed") return false;
  return winners.value.size === 5;
});

const canSaveWinnerCorrection = computed(() => {
  if (!match.value || match.value.status !== "completed") return false;
  return winners.value.size === 5;
});

function submit() {
  if (!match.value || !canSubmit.value) return;
  dialog.warning({
    title: "确认提交结果？",
    content: "提交后将计为已完赛并给胜者加分。",
    positiveText: "提交",
    negativeText: "取消",
    onPositiveClick: async () => {
      submitting.value = true;
      try {
        await submitMatchResult(match.value!.id, Array.from(winners.value));
        message.success("结果已保存");
        await router.push("/");
        return true;
      } catch (e) {
        message.error((e as Error).message);
        return false;
      } finally {
        submitting.value = false;
      }
    },
  });
}

function saveWinnerCorrection() {
  if (!match.value || !canSaveWinnerCorrection.value) return;
  dialog.warning({
    title: "保存胜者修正？",
    content: "将按新的 5 名胜者差额调整积分（仅改变胜负勾选差异部分）。",
    positiveText: "保存",
    negativeText: "取消",
    onPositiveClick: async () => {
      submitting.value = true;
      try {
        await submitMatchResult(match.value!.id, Array.from(winners.value));
        message.success("已更新胜者与本场相关积分");
        await load();
        return true;
      } catch (e) {
        message.error((e as Error).message);
        return false;
      } finally {
        submitting.value = false;
      }
    },
  });
}

function confirmDelete() {
  if (!match.value) return;
  dialog.error({
    title: "删除这场比赛？",
    content:
      match.value.status === "completed"
        ? "已完赛记录将被删除，胜者此前因本场获得的 +1 积分会回退。"
        : "未提交结果的已确认比赛将被删除，不产生积分变化。",
    positiveText: "删除",
    negativeText: "取消",
    onPositiveClick: async () => {
      submitting.value = true;
      try {
        await deleteMatch(match.value!.id);
        message.success("已删除");
        await router.push("/matches");
        return true;
      } catch (e) {
        message.error((e as Error).message);
        return false;
      } finally {
        submitting.value = false;
      }
    },
  });
}
</script>

<template>
  <main-layout>
    <n-card v-if="match" :title="`比赛 #${match.id}`">
      <n-space vertical size="large">
        <n-space align="center">
          <n-text>状态：</n-text>
          <n-tag :type="match.status === 'completed' ? 'success' : 'warning'">
            {{ match.status === "completed" ? "已完赛" : "已确认" }}
          </n-tag>
          <n-text depth="3">比赛日窗口：{{ new Date(match.matchday_start).toLocaleString("zh-CN") }}</n-text>
        </n-space>

        <div>
          <n-text strong>上场名单</n-text>
          <n-space vertical style="margin-top: 8px">
            <div v-for="p in match.players" :key="p.player_id" style="display: flex; align-items: center; gap: 10px">
              <n-checkbox
                :checked="winners.has(p.player_id)"
                @update:checked="(v: boolean) => toggleWinner(p.player_id, v)"
              >
                {{ p.name }}
              </n-checkbox>
              <n-tag v-if="match.status === 'completed'" size="small" :type="p.is_winner ? 'success' : 'default'">
                {{ p.is_winner ? "胜" : "负" }}
              </n-tag>
            </div>
          </n-space>
        </div>

        <n-text v-if="match.status === 'confirmed'" depth="3">
          请勾选恰好 5 名获胜者，然后提交结果。
        </n-text>
        <n-text v-if="match.status === 'completed'" depth="3">
          如需纠错：调整胜者勾选（仍为恰好 5 人）后点「保存胜者修正」。删除整场请用下方删除按钮。
        </n-text>

        <n-space>
          <n-button @click="router.push('/matches')">返回列表</n-button>
          <n-button v-if="match.status === 'confirmed'" type="primary" :disabled="!canSubmit" :loading="submitting" @click="submit">
            提交结果
          </n-button>
          <n-button
            v-if="match.status === 'completed'"
            type="primary"
            :disabled="!canSaveWinnerCorrection"
            :loading="submitting"
            @click="saveWinnerCorrection"
          >
            保存胜者修正
          </n-button>
          <n-button type="error" secondary :loading="submitting" @click="confirmDelete">删除本场</n-button>
        </n-space>
      </n-space>
    </n-card>

    <n-card v-else-if="!loading" title="比赛不存在" />
  </main-layout>
</template>
