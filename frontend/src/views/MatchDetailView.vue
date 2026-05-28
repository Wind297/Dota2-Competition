<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import {
  NButton,
  NCard,
  NCheckbox,
  NDatePicker,
  NInputNumber,
  NModal,
  NSelect,
  NSpace,
  NTag,
  NText,
  useDialog,
  useMessage,
} from "naive-ui";
import type { MatchRecord, Player } from "@/api";
import {
  deleteMatch,
  fetchMatch,
  fetchPlayers,
  formatMatchTitle,
  isAdmin,
  patchMatch,
  submitMatchResult,
} from "@/api";
import MainLayout from "@/components/MainLayout.vue";
import PageHeader from "@/components/PageHeader.vue";

const props = defineProps<{ id: string }>();
const router = useRouter();
const message = useMessage();
const dialog = useDialog();

const adminMode = isAdmin();

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

const matchTitle = computed(() => (match.value ? formatMatchTitle(match.value) : ""));

// ── 扣分确认 Modal ──────────────────────────────────────────────
type DeductCandidate = { player_id: number; name: string; current_score: number; deduct: boolean };
const deductModalShow = ref(false);
const deductCandidates = ref<DeductCandidate[]>([]);
const deductSaving = ref(false);
// 暂存待提交的胜者集合（弹扣分框时还没提交）
const pendingWinnerIds = ref<number[]>([]);
// 本次弹扣分框是首次提交还是修正
const deductModeForCorrection = ref(false);

/** 计算「现在的负方中谁积分 >10」。
 *  注意：现有 player.current_score 已经包含了本场比赛此前产生的 score_delta。
 *  为了得到「不计本场的真实积分」，需要减去 score_delta。 */
async function buildDeductCandidates(winnerIds: Set<number>): Promise<DeductCandidate[]> {
  if (!match.value) return [];
  const allPlayers = await fetchPlayers({});
  const scoreMap = new Map<number, number>();
  for (const p of allPlayers) scoreMap.set(p.id, p.current_score);

  const candidates: DeductCandidate[] = [];
  for (const mp of match.value.players) {
    if (winnerIds.has(mp.player_id)) continue;
    const currentScore = scoreMap.get(mp.player_id) ?? 0;
    // 还原为「不计本场影响」的积分
    const baseScore = currentScore - mp.score_delta;
    if (baseScore > 10) {
      candidates.push({
        player_id: mp.player_id,
        name: mp.name,
        current_score: baseScore,
        deduct: mp.is_deducted, // 默认沿用上次的扣分选择
      });
    }
  }
  return candidates;
}

async function submitFlow(opts: { isCorrection: boolean }) {
  if (!match.value) return;
  const winnerIds = new Set(winners.value);

  submitting.value = true;
  try {
    const candidates = await buildDeductCandidates(winnerIds);
    if (candidates.length > 0) {
      // 弹扣分确认框，等用户决定
      pendingWinnerIds.value = Array.from(winnerIds);
      deductModeForCorrection.value = opts.isCorrection;
      deductCandidates.value = candidates;
      deductModalShow.value = true;
    } else {
      // 没有 >10 分的负方，直接提交（不带扣分名单）
      await submitMatchResult(match.value.id, Array.from(winnerIds), []);
      message.success(opts.isCorrection ? "已更新结果与积分" : "结果已保存");
      if (opts.isCorrection) await load();
      else await router.push("/");
    }
  } catch (e) {
    message.error((e as Error).message);
  } finally {
    submitting.value = false;
  }
}

function submit() {
  if (!match.value || !canSubmit.value) return;
  dialog.warning({
    title: "确认提交结果？",
    content: "提交后将计为已完赛并按名单调整积分。",
    positiveText: "提交",
    negativeText: "取消",
    onPositiveClick: () => submitFlow({ isCorrection: false }),
  });
}

function saveWinnerCorrection() {
  if (!match.value || !canSaveWinnerCorrection.value) return;
  dialog.warning({
    title: "保存胜者修正？",
    content: "将按新的胜者名单重新核算本场的加减分（差额自动同步到选手积分）。",
    positiveText: "保存",
    negativeText: "取消",
    onPositiveClick: () => submitFlow({ isCorrection: true }),
  });
}

async function confirmDeduct() {
  if (!match.value) return;
  deductSaving.value = true;
  try {
    const toDeductIds = deductCandidates.value.filter((c) => c.deduct).map((c) => c.player_id);
    await submitMatchResult(match.value.id, pendingWinnerIds.value, toDeductIds);
    deductModalShow.value = false;
    if (toDeductIds.length > 0) {
      message.success(`已保存结果，对 ${toDeductIds.length} 名选手扣分`);
    } else {
      message.success("已保存结果，未扣分");
    }
    if (deductModeForCorrection.value) await load();
    else await router.push("/");
  } catch (e) {
    message.error((e as Error).message);
  } finally {
    deductSaving.value = false;
  }
}

async function skipDeduct() {
  if (!match.value) return;
  deductSaving.value = true;
  try {
    // 跳过扣分 = 提交时 deducted_player_ids 为空
    await submitMatchResult(match.value.id, pendingWinnerIds.value, []);
    deductModalShow.value = false;
    message.success("结果已保存，未扣分");
    if (deductModeForCorrection.value) await load();
    else await router.push("/");
  } catch (e) {
    message.error((e as Error).message);
  } finally {
    deductSaving.value = false;
  }
}

function confirmDelete() {
  if (!match.value) return;
  dialog.error({
    title: "删除这场比赛？",
    content:
      match.value.status === "completed"
        ? "已完赛记录将被删除，本场对每位选手产生的加减分会自动回退。"
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

// ── 编辑比赛信息 Modal ────────────────────────────────────────
const editModalShow = ref(false);
const editSaving = ref(false);
const allPlayers = ref<Player[]>([]);
const editMatchdayMs = ref<number | null>(null);
const editSequenceNo = ref<number | null>(null);
const editPlayerIds = ref<number[]>([]);

const playerOptions = computed(() =>
  allPlayers.value.map((p) => ({
    label: `${p.name}（${p.current_score} 分）`,
    value: p.id,
  })),
);

function buildMatchdayIso(ms: number): string {
  const d = new Date(ms);
  const yyyy = d.getFullYear();
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  const dd = String(d.getDate()).padStart(2, "0");
  return `${yyyy}-${mm}-${dd}T09:00:00+08:00`;
}

async function openEditModal() {
  if (!match.value) return;
  try {
    allPlayers.value = await fetchPlayers({});
  } catch {
    message.error("加载选手列表失败");
    return;
  }
  const md = new Date(match.value.matchday_start);
  editMatchdayMs.value = md.getTime();
  editSequenceNo.value = match.value.sequence_no ?? null;
  editPlayerIds.value = match.value.players.map((p) => p.player_id);
  editModalShow.value = true;
}

async function saveEdit() {
  if (!match.value) return;
  if (editPlayerIds.value.length !== 10) {
    message.warning("必须恰好选择 10 名选手");
    return;
  }
  if (new Set(editPlayerIds.value).size !== 10) {
    message.warning("选手不能重复");
    return;
  }
  editSaving.value = true;
  try {
    const body: {
      matchday_start?: string;
      sequence_no?: number;
      clear_sequence_no?: boolean;
      player_ids?: number[];
    } = {};

    if (editMatchdayMs.value != null) {
      const newIso = buildMatchdayIso(editMatchdayMs.value);
      const oldIso = new Date(match.value.matchday_start).toISOString();
      if (new Date(newIso).getTime() !== new Date(oldIso).getTime()) {
        body.matchday_start = newIso;
      }
    }

    if (editSequenceNo.value == null) {
      if (match.value.sequence_no != null) {
        body.clear_sequence_no = true;
      }
    } else if (editSequenceNo.value !== match.value.sequence_no) {
      body.sequence_no = editSequenceNo.value;
    }

    const oldIds = new Set(match.value.players.map((p) => p.player_id));
    const newIds = new Set(editPlayerIds.value);
    const changed =
      oldIds.size !== newIds.size || [...newIds].some((id) => !oldIds.has(id));
    if (changed) {
      body.player_ids = editPlayerIds.value;
    }

    if (Object.keys(body).length === 0) {
      message.info("没有修改内容");
      editModalShow.value = false;
      return;
    }

    await patchMatch(match.value.id, body);
    message.success("比赛信息已更新");
    editModalShow.value = false;
    await load();
  } catch (e) {
    message.error((e as Error).message);
  } finally {
    editSaving.value = false;
  }
}

/** 渲染单个选手的本场分值变化标签 */
function deltaText(delta: number): string {
  if (delta === 0) return "";
  return delta > 0 ? `+${delta}` : `${delta}`;
}
function deltaColor(delta: number): string {
  if (delta > 0) return "#2d8048";
  if (delta < 0) return "#a64238";
  return "#7a8390";
}
</script>

<template>
  <main-layout>
    <page-header
      v-if="match"
      :title="matchTitle"
      :subtitle="`Match #${match.id}`"
    />
    <page-header v-else title="比赛详情" subtitle="Match Detail" />

    <n-card v-if="match">
      <!-- 元信息栏 -->
      <div class="meta-row">
        <div class="meta-item">
          <span class="meta-label">状态</span>
          <span
            class="status-pill"
            :class="match.status === 'completed' ? 'status-completed' : 'status-confirmed'"
          >
            <span class="status-dot"></span>
            {{ match.status === "completed" ? "已完赛" : "已确认" }}
          </span>
        </div>
        <div class="meta-item">
          <span class="meta-label">比赛日</span>
          <span class="meta-value">{{ new Date(match.matchday_start).toLocaleDateString("zh-CN") }}</span>
        </div>
        <div class="meta-item">
          <span class="meta-label">场次</span>
          <span class="meta-value">
            {{ match.sequence_no != null ? `第 ${match.sequence_no} 场（手工）` : "自动编号" }}
          </span>
        </div>
      </div>

      <!-- 上场名单 -->
      <div class="roster-section">
        <div class="section-title">
          <span>上场名单</span>
          <span class="section-count">10 人</span>
        </div>

        <div class="roster-list">
          <div
            v-for="(p, idx) in match.players"
            :key="p.player_id"
            class="roster-item"
            :class="{
              'is-winner': match.status === 'completed' && p.is_winner,
              'is-loser': match.status === 'completed' && !p.is_winner,
              'is-deducted': p.is_deducted,
            }"
          >
            <div class="roster-num">{{ String(idx + 1).padStart(2, "0") }}</div>
            <div class="roster-checkbox">
              <n-checkbox
                v-if="adminMode"
                :checked="winners.has(p.player_id)"
                @update:checked="(v: boolean) => toggleWinner(p.player_id, v)"
              />
              <span v-else style="display: inline-block; width: 16px"></span>
            </div>
            <div class="roster-name">{{ p.name }}</div>
            <div class="roster-tags">
              <span
                v-if="match.status === 'completed'"
                class="result-pill"
                :class="p.is_winner ? 'pill-win' : 'pill-lose'"
              >
                {{ p.is_winner ? "胜" : "负" }}
              </span>
              <span v-if="p.is_deducted" class="result-pill pill-deduct">扣分</span>
              <span
                v-if="match.status === 'completed' && p.score_delta !== 0"
                class="delta-badge"
                :style="{ color: deltaColor(p.score_delta) }"
              >
                {{ deltaText(p.score_delta) }}
              </span>
            </div>
          </div>
        </div>
      </div>

      <!-- 提示 -->
      <div class="hint-box" v-if="adminMode && match.status === 'confirmed'">
        请勾选恰好 5 名获胜者后提交结果。若负方有积分 &gt; 10 的选手，将弹出扣分确认。
      </div>
      <div class="hint-box" v-if="adminMode && match.status === 'completed'">
        如需纠错：调整胜者勾选（仍为恰好 5 人）后点「保存胜者修正」，会重新核算本场加减分。
      </div>
      <div class="hint-box guest" v-if="!adminMode">
        观战者模式，仅可查看比赛信息
      </div>

      <!-- 操作 -->
      <div class="action-bar">
        <n-button @click="router.push('/matches')">返回列表</n-button>
        <template v-if="adminMode">
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
          <n-button secondary :loading="submitting" @click="openEditModal">编辑比赛信息</n-button>
          <n-button type="error" secondary :loading="submitting" @click="confirmDelete">删除本场</n-button>
        </template>
      </div>
    </n-card>

    <n-card v-else-if="!loading" title="比赛不存在" />

    <!-- 扣分确认 Modal -->
    <n-modal v-model:show="deductModalShow" :mask-closable="false" style="width: 480px">
      <n-card title="是否对负方高分选手扣分？" :bordered="false" size="small">
        <n-space vertical size="large">
          <n-text depth="3">
            以下负方选手积分 &gt; 10 分（不计本场影响），根据当前规则可扣分（每人 -1）。
            勾选要扣分的选手后确认，或点「跳过」不扣分。
          </n-text>
          <n-space vertical>
            <div
              v-for="c in deductCandidates"
              :key="c.player_id"
              class="deduct-row"
            >
              <n-checkbox v-model:checked="c.deduct">
                {{ c.name }}
              </n-checkbox>
              <span class="deduct-base">基础积分 {{ c.current_score }}</span>
              <span v-if="c.deduct" class="deduct-arrow">→ {{ c.current_score - 1 }}</span>
            </div>
          </n-space>
          <n-space justify="end">
            <n-button :loading="deductSaving" @click="skipDeduct">跳过，不扣分</n-button>
            <n-button type="error" :loading="deductSaving" @click="confirmDeduct">
              确认扣分（{{ deductCandidates.filter((c) => c.deduct).length }} 人）
            </n-button>
          </n-space>
        </n-space>
      </n-card>
    </n-modal>

    <!-- 编辑比赛信息 Modal -->
    <n-modal v-if="adminMode" v-model:show="editModalShow" :mask-closable="false" style="width: 560px">
      <n-card title="编辑比赛信息" :bordered="false" size="small">
        <n-space vertical size="large">
          <n-text depth="3">
            可修改比赛归属日期、场次号、上场名单。被移除的选手会自动撤销其在本场的所有加减分（含扣分）。
          </n-text>

          <div>
            <div class="field-label">比赛日（归属日期）</div>
            <n-date-picker v-model:value="editMatchdayMs" type="date" clearable style="width: 100%" />
            <div class="field-hint">比赛日窗口固定为该日 09:00 至次日 08:59（上海时区）</div>
          </div>

          <div>
            <div class="field-label">场次号（可选）</div>
            <n-input-number
              v-model:value="editSequenceNo"
              :min="1"
              :max="999"
              :precision="0"
              clearable
              placeholder="留空则按创建时间自动计算"
              style="width: 100%"
            />
            <div class="field-hint">手工指定后列表显示「第 N 场」；清空后恢复为自动编号</div>
          </div>

          <div>
            <div class="field-label">上场名单（{{ editPlayerIds.length }} / 10）</div>
            <n-select
              v-model:value="editPlayerIds"
              multiple
              filterable
              :options="playerOptions"
              :max-tag-count="5"
              placeholder="搜索并选择 10 名选手"
              style="width: 100%"
            />
            <div class="field-hint">移除已计分的选手会回退本场对其产生的所有积分</div>
          </div>

          <n-space justify="end">
            <n-button @click="editModalShow = false">取消</n-button>
            <n-button
              type="primary"
              :loading="editSaving"
              :disabled="editPlayerIds.length !== 10"
              @click="saveEdit"
            >
              保存
            </n-button>
          </n-space>
        </n-space>
      </n-card>
    </n-modal>
  </main-layout>
</template>

<style scoped>
/* 元信息栏 */
.meta-row {
  display: flex;
  align-items: center;
  gap: 28px;
  padding: 12px 16px;
  background: #f6f8fb;
  border: 1px solid #e8ecf2;
  border-radius: 6px;
  margin-bottom: 24px;
  flex-wrap: wrap;
}
.meta-item {
  display: flex;
  align-items: center;
  gap: 10px;
}
.meta-label {
  font-size: 11px;
  color: #7a8390;
  letter-spacing: 0.5px;
}
.meta-value {
  color: #1a2435;
  font-size: 13px;
  font-weight: 500;
}

/* 状态药丸 */
.status-pill {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 3px 10px;
  font-size: 12px;
  border-radius: 3px;
  font-weight: 500;
}
.status-pill .status-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: currentColor;
}
.status-completed {
  background: rgba(58, 157, 87, 0.12);
  color: #3a9d57;
}
.status-confirmed {
  background: rgba(185, 115, 36, 0.12);
  color: #b97324;
}

/* 区块标题 */
.section-title {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 12px;
  font-size: 14px;
  color: #1a2435;
  font-weight: 600;
}
.section-count {
  font-size: 11px;
  color: #5a6473;
  font-weight: 500;
  padding: 2px 8px;
  background: #f0f3f7;
  border-radius: 3px;
}

/* 名单 */
.roster-section {
  margin-bottom: 20px;
}
.roster-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.roster-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 14px;
  background: #fafbfd;
  border-radius: 6px;
  border-left: 3px solid transparent;
  transition: all 0.15s ease;
}
.roster-item:hover {
  background: #f0f5fb;
}
.roster-item.is-winner {
  border-left-color: #3a9d57;
  background: rgba(58, 157, 87, 0.06);
}
.roster-item.is-loser {
  border-left-color: #d6c0bd;
}
.roster-item.is-deducted {
  background: rgba(193, 85, 74, 0.06);
}
.roster-num {
  font-family: '"SF Mono", "Courier New", monospace';
  font-size: 11px;
  color: #aab3bf;
  min-width: 22px;
  font-weight: 500;
}
.roster-checkbox {
  flex-shrink: 0;
}
.roster-name {
  flex: 1;
  color: #1a2435;
  font-size: 13px;
}
.roster-item.is-winner .roster-name {
  color: #1a2435;
  font-weight: 600;
}
.roster-tags {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-shrink: 0;
}
.result-pill {
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 3px;
  font-weight: 500;
}
.pill-win {
  background: rgba(58, 157, 87, 0.15);
  color: #2d8048;
}
.pill-lose {
  background: #eff1f5;
  color: #5a6473;
}
.pill-deduct {
  background: rgba(193, 85, 74, 0.12);
  color: #a64238;
}
.delta-badge {
  font-family: '"SF Mono", "Courier New", monospace';
  font-size: 12px;
  font-weight: 700;
  padding: 2px 8px;
  background: #ffffff;
  border: 1px solid #e1e6ed;
  border-radius: 3px;
}

/* 提示 */
.hint-box {
  margin: 16px 0;
  padding: 10px 14px;
  background: rgba(44, 109, 193, 0.06);
  border-left: 3px solid #2c6dc1;
  font-size: 12px;
  color: #1a2435;
  line-height: 1.6;
  border-radius: 0 4px 4px 0;
}
.hint-box.guest {
  background: #f6f8fb;
  border-left-color: #aab3bf;
  color: #4d5663;
}

/* 操作栏 */
.action-bar {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  padding-top: 16px;
  border-top: 1px solid #eef1f5;
}

/* 扣分行 */
.deduct-row {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 6px 0;
}
.deduct-base {
  font-size: 12px;
  color: #b97324;
  background: rgba(185, 115, 36, 0.10);
  padding: 2px 8px;
  border-radius: 3px;
}
.deduct-arrow {
  font-size: 12px;
  color: #a64238;
  font-weight: 500;
}

/* 字段 */
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

