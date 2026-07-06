<script setup lang="ts">
import { computed, ref, watch } from "vue";
import {
  NButton,
  NCard,
  NInput,
  NModal,
  NSpace,
  NSpin,
  useMessage,
} from "naive-ui";
import type { Player, PlayerSocial, ScoreAuditEntry } from "@/api";
import {
  createTag,
  fetchPlayerById,
  fetchPlayerScoreHistory,
  fetchPlayerSocial,
  getVoterNickname,
  isAdmin,
  setVoterNickname,
  togglePlayerLike,
  togglePlayerTag,
} from "@/api";

const props = withDefaults(
  defineProps<{
    show: boolean;
    /** 直接传完整 Player 对象（选手池入口用） */
    player?: Player | null;
    /** 仅传 player id（排行榜入口用，内部按 id fetch 完整 Player） */
    playerId?: number | null;
  }>(),
  {
    player: null,
    playerId: null,
  },
);

const emit = defineEmits<{
  (e: "update:show", v: boolean): void;
  /** 当点赞/标签发生变更时通知父组件刷新列表 */
  (e: "changed"): void;
}>();

const message = useMessage();
const adminMode = isAdmin();

// 当只传 playerId 时，按 id fetch 的完整 Player
const internalPlayer = ref<Player | null>(null);
const effectivePlayer = computed<Player | null>(
  () => props.player ?? internalPlayer.value,
);
const effectivePlayerId = computed<number | null>(
  () => props.player?.id ?? props.playerId ?? null,
);

// 管理员新建标签
const showCreateTagModal = ref(false);
const newTagLabel = ref("");
const newTagIsPublic = ref(true);
const creatingTag = ref(false);

async function onCreateTag() {
  const label = newTagLabel.value.trim();
  if (!label) {
    message.warning("请输入标签名");
    return;
  }
  if (label.length > 16) {
    message.warning("标签不能超过 16 字");
    return;
  }
  creatingTag.value = true;
  try {
    const playerId = newTagIsPublic.value ? null : (effectivePlayer.value?.id ?? null);
    await createTag(label, 999, playerId);
    newTagLabel.value = "";
    showCreateTagModal.value = false;
    message.success("标签已创建");
    await loadSocial();
  } catch (e) {
    message.error((e as Error).message);
  } finally {
    creatingTag.value = false;
  }
}

const social = ref<PlayerSocial | null>(null);
const loading = ref(false);

// 积分明细
const scoreHistory = ref<ScoreAuditEntry[]>([]);
const loadingHistory = ref(false);
const showAllHistory = ref(false);

const reasonLabelMap: Record<string, string> = {
  match_result: "比赛",
  match_edit: "比赛编辑",
  match_delete: "比赛删除",
  manual_adjust: "管理员调整",
  bulk_import: "批量导入",
  initial_score: "初始积分",
};

function reasonLabel(reason: string): string {
  return reasonLabelMap[reason] ?? reason;
}

const historySum = computed(() =>
  scoreHistory.value.reduce((acc, e) => acc + e.delta, 0),
);

const scoreDiff = computed(() => {
  const cur = effectivePlayer.value?.current_score ?? 0;
  return cur - historySum.value;
});

const visibleHistory = computed(() => {
  // 倒序：最新在前
  const list = [...scoreHistory.value].reverse();
  if (showAllHistory.value) return list;
  return list.slice(0, 30);
});

function formatHistoryTime(iso: string): string {
  const d = new Date(iso);
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  const dd = String(d.getDate()).padStart(2, "0");
  const hh = String(d.getHours()).padStart(2, "0");
  const mi = String(d.getMinutes()).padStart(2, "0");
  return `${mm}-${dd} ${hh}:${mi}`;
}

// 昵称引导
const showNicknameModal = ref(false);
const nicknameDraft = ref("");
const pendingAction = ref<(() => Promise<void>) | null>(null);

async function loadSocial() {
  const pid = effectivePlayerId.value;
  if (pid == null) {
    social.value = null;
    return;
  }
  loading.value = true;
  try {
    social.value = await fetchPlayerSocial(pid);
  } catch (e) {
    message.error((e as Error).message);
  } finally {
    loading.value = false;
  }
}

async function loadScoreHistory() {
  const pid = effectivePlayerId.value;
  if (pid == null) {
    scoreHistory.value = [];
    return;
  }
  loadingHistory.value = true;
  try {
    scoreHistory.value = await fetchPlayerScoreHistory(pid);
  } catch (e) {
    message.error((e as Error).message);
  } finally {
    loadingHistory.value = false;
  }
}

async function loadInternalPlayer() {
  // 仅当外部没传 player 且传了 playerId 时才 fetch
  if (props.player != null || props.playerId == null) return;
  try {
    internalPlayer.value = await fetchPlayerById(props.playerId);
  } catch (e) {
    message.error((e as Error).message);
  }
}

watch(
  () => [props.show, effectivePlayerId.value],
  ([show]) => {
    if (!show) return;
    if (props.player == null && props.playerId != null) {
      void loadInternalPlayer();
    } else if (props.player != null) {
      // 外部传了完整 player，重置 internal 避免串台
      internalPlayer.value = null;
    }
    void loadSocial();
    void loadScoreHistory();
  },
  { immediate: true },
);

function close() {
  emit("update:show", false);
}

function onUpdateShow(v: boolean) {
  emit("update:show", v);
}

/** 在执行任何互动前确保有昵称；没有则弹昵称设置框，存好再继续。 */
function ensureNickname(action: () => Promise<void>): void {
  const nick = getVoterNickname();
  if (nick && nick.trim()) {
    void action();
    return;
  }
  pendingAction.value = action;
  nicknameDraft.value = "";
  showNicknameModal.value = true;
}

async function confirmNickname() {
  const v = nicknameDraft.value.trim();
  if (!v) {
    message.warning("请输入一个昵称");
    return;
  }
  setVoterNickname(v);
  showNicknameModal.value = false;
  if (pendingAction.value) {
    const action = pendingAction.value;
    pendingAction.value = null;
    await action();
  }
}

async function onToggleLike() {
  const pid = effectivePlayerId.value;
  if (pid == null) return;
  ensureNickname(async () => {
    try {
      social.value = await togglePlayerLike(pid);
      emit("changed");
    } catch (e) {
      message.error((e as Error).message);
    }
  });
}

async function onToggleTag(tagId: number) {
  const pid = effectivePlayerId.value;
  if (pid == null) return;
  ensureNickname(async () => {
    try {
      social.value = await togglePlayerTag(pid, tagId);
      emit("changed");
    } catch (e) {
      message.error((e as Error).message);
    }
  });
}

const sortedTags = computed(() => {
  if (!social.value) return [];
  return [...social.value.tags].sort((a, b) => {
    if (b.count !== a.count) return b.count - a.count;
    if (a.voted_by_me !== b.voted_by_me) return a.voted_by_me ? -1 : 1;
    return a.label.localeCompare(b.label);
  });
});

const winRatePercent = computed(() => {
  if (!effectivePlayer.value) return 0;
  return Math.round(effectivePlayer.value.win_rate * 100);
});
</script>

<template>
  <n-modal :show="show" :mask-closable="true" @update:show="onUpdateShow">
    <n-card class="detail-card" :bordered="false" size="small">
      <template v-if="effectivePlayer" #header>
        <div class="detail-header">
          <span class="detail-name">{{ effectivePlayer.name }}</span>
          <span class="detail-meta">
            <span class="meta-pill">本赛季积分 <b>{{ effectivePlayer.current_score }}</b></span>
          </span>
        </div>
      </template>

      <template v-if="effectivePlayer">
        <!-- 战绩区 -->
        <div class="stats-row">
          <div class="stat-cell">
            <div class="stat-label">总场次</div>
            <div class="stat-value">{{ effectivePlayer.total_played }}</div>
          </div>
          <div class="stat-cell">
            <div class="stat-label">胜场</div>
            <div class="stat-value win">{{ effectivePlayer.total_won }}</div>
          </div>
          <div class="stat-cell">
            <div class="stat-label">胜率</div>
            <div class="stat-value">
              {{ effectivePlayer.total_played > 0 ? `${winRatePercent}%` : "—" }}
            </div>
          </div>
          <div class="stat-cell">
            <div class="stat-label">今日</div>
            <div class="stat-value">
              {{ effectivePlayer.stats.matches_played }} 场 / {{ effectivePlayer.stats.matches_won }} 胜
            </div>
          </div>
        </div>

        <!-- 积分明细 -->
        <div class="section">
          <div class="section-title">
            <span>积分明细</span>
            <button
              v-if="scoreHistory.length > 30"
              class="add-tag-btn"
              @click="showAllHistory = !showAllHistory"
            >
              {{ showAllHistory ? "收起" : `显示全部 (${scoreHistory.length})` }}
            </button>
          </div>
          <div class="audit-summary">
            明细加总 <b>{{ historySum }}</b> · 当前积分 <b>{{ effectivePlayer.current_score }}</b>
            <span v-if="scoreDiff !== 0" class="audit-diff">
              （差额 {{ scoreDiff > 0 ? "+" : "" }}{{ scoreDiff }}，可点「按比赛记录重置积分」或手动补调整）
            </span>
          </div>
          <n-spin v-if="loadingHistory" size="small" style="display: block; margin: 12px auto" />
          <div v-else-if="visibleHistory.length === 0" class="audit-empty">
            暂无积分变更记录
          </div>
          <div v-else class="audit-list">
            <div v-for="e in visibleHistory" :key="e.id" class="audit-row">
              <span class="audit-time">{{ formatHistoryTime(e.created_at) }}</span>
              <span
                class="audit-delta"
                :class="{ pos: e.delta > 0, neg: e.delta < 0 }"
              >
                {{ e.delta > 0 ? "+" : "" }}{{ e.delta }}
              </span>
              <span class="audit-reason">{{ reasonLabel(e.reason) }}</span>
              <span class="audit-desc">
                {{ e.match_summary ?? e.note ?? "" }}
              </span>
            </div>
          </div>
        </div>

        <n-spin v-if="loading" size="small" style="display: block; margin: 24px auto" />

        <template v-else-if="social">
          <!-- 点赞区 -->
          <div class="section">
            <div class="section-title">大家的反馈</div>
            <button
              class="like-btn"
              :class="{ liked: social.liked_by_me }"
              @click="onToggleLike"
            >
              <span class="like-heart">{{ social.liked_by_me ? "❤" : "♡" }}</span>
              <span class="like-count">{{ social.like_count }}</span>
              <span class="like-text">{{ social.liked_by_me ? "已点赞" : "点个赞" }}</span>
            </button>
          </div>

          <!-- 标签区 -->
          <div class="section">
            <div class="section-title">
              <span>选手印象 · 点击投票</span>
              <button v-if="adminMode" class="add-tag-btn" @click="showCreateTagModal = true">
                ＋ 新建标签
              </button>
            </div>

            <div class="tag-grid">
              <button
                v-for="t in sortedTags"
                :key="t.tag_id"
                class="tag-chip"
                :class="{ voted: t.voted_by_me, hot: t.count >= 3 }"
                @click="onToggleTag(t.tag_id)"
              >
                <span class="tag-label">{{ t.label }}</span>
                <span class="tag-count">{{ t.count }}</span>
              </button>
            </div>
          </div>
        </template>

        <div class="footer">
          <n-button size="small" @click="close">关闭</n-button>
        </div>
      </template>
    </n-card>
  </n-modal>

  <!-- 昵称设置 Modal（独立挂载，避免嵌套导致 slot 警告） -->
  <n-modal v-model:show="showNicknameModal" :mask-closable="false" style="width: 380px">
    <n-card title="给自己起个昵称吧" :bordered="false" size="small">
      <n-space vertical size="large">
        <div style="font-size: 12px; color: #7a8390">
          你的昵称会和点赞、标签一起记录。可以是你的网名、外号，随意。
        </div>
        <n-input
          v-model:value="nicknameDraft"
          placeholder="如：小明、点神七号"
          maxlength="20"
          show-count
          @keydown.enter="confirmNickname"
        />
        <n-space justify="end">
          <n-button @click="showNicknameModal = false">取消</n-button>
          <n-button type="primary" @click="confirmNickname">确定</n-button>
        </n-space>
      </n-space>
    </n-card>
  </n-modal>

  <!-- 管理员新建标签 Modal -->
  <n-modal v-if="adminMode" v-model:show="showCreateTagModal" :mask-closable="false" style="width: 400px">
    <n-card title="新建标签" :bordered="false" size="small">
      <n-space vertical size="large">
        <div>
          <div style="font-size: 13px; font-weight: 500; margin-bottom: 6px; color: #1a2435">标签名称</div>
          <n-input
            v-model:value="newTagLabel"
            placeholder="如：团战发动机"
            maxlength="16"
            show-count
            @keydown.enter="onCreateTag"
          />
        </div>
        <div style="display: flex; gap: 12px; align-items: center">
          <span style="font-size: 13px; font-weight: 500; color: #1a2435">类型：</span>
          <label style="display: flex; align-items: center; gap: 4px; cursor: pointer; font-size: 13px">
            <input type="radio" :value="true" v-model="newTagIsPublic" />
            公共标签（所有选手通用）
          </label>
          <label style="display: flex; align-items: center; gap: 4px; cursor: pointer; font-size: 13px">
            <input type="radio" :value="false" v-model="newTagIsPublic" />
            专属标签（仅此选手）
          </label>
        </div>
        <div style="font-size: 11px; color: #7a8390">
          公共标签会出现在所有选手的标签栏中；专属标签仅在「{{ effectivePlayer?.name }}」的标签栏中显示。
        </div>
        <n-space justify="end">
          <n-button @click="showCreateTagModal = false">取消</n-button>
          <n-button type="primary" :loading="creatingTag" :disabled="!newTagLabel.trim()" @click="onCreateTag">
            创建
          </n-button>
        </n-space>
      </n-space>
    </n-card>
  </n-modal>
</template>

<style scoped>
.detail-card {
  width: min(540px, 92vw);
  max-height: 90vh;
  overflow: auto;
}

.detail-header {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 14px;
  flex-wrap: wrap;
}
.detail-name {
  font-size: 18px;
  font-weight: 600;
  color: #1a2435;
}
.detail-meta {
  display: flex;
  gap: 10px;
}
.meta-pill {
  font-size: 12px;
  color: #4d5663;
  padding: 2px 10px;
  background: rgba(44, 109, 193, 0.08);
  border-radius: 3px;
}
.meta-pill b {
  color: #2c6dc1;
  font-family: '"SF Mono", "Courier New", monospace';
  margin-left: 4px;
}

/* 战绩区 */
.stats-row {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 8px;
  margin-bottom: 6px;
}
.stat-cell {
  background: #f6f8fb;
  border: 1px solid #eef1f5;
  border-radius: 6px;
  padding: 10px 8px;
  text-align: center;
}
.stat-label {
  font-size: 11px;
  color: #7a8390;
  margin-bottom: 4px;
}
.stat-value {
  font-size: 16px;
  font-weight: 600;
  color: #1a2435;
  font-family: '"SF Mono", "Courier New", monospace';
}
.stat-value.win {
  color: #3a9d57;
}

/* 区块 */
.section {
  margin-top: 18px;
}
.section-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 13px;
  color: #4d5663;
  font-weight: 500;
  margin-bottom: 10px;
  padding-bottom: 6px;
  border-bottom: 1px solid #eef1f5;
}
.add-tag-btn {
  background: none;
  border: 1px solid #d8dee6;
  color: #2c6dc1;
  font-size: 12px;
  cursor: pointer;
  padding: 3px 10px;
  border-radius: 4px;
  font-family: inherit;
  transition: all 0.15s;
}
.add-tag-btn:hover {
  background: rgba(44, 109, 193, 0.08);
  border-color: #2c6dc1;
}

/* 积分明细区 */
.audit-summary {
  font-size: 12px;
  color: #4d5663;
  margin-bottom: 10px;
  padding: 6px 10px;
  background: #f6f8fb;
  border-radius: 4px;
}
.audit-summary b {
  font-family: '"SF Mono", "Courier New", monospace';
  color: #1a2435;
  font-weight: 600;
  margin: 0 2px;
}
.audit-diff {
  color: #c1554a;
  margin-left: 6px;
}
.audit-empty {
  font-size: 12px;
  color: #7a8390;
  text-align: center;
  padding: 16px;
}
.audit-list {
  display: flex;
  flex-direction: column;
  gap: 0;
  max-height: 320px;
  overflow-y: auto;
}
.audit-row {
  display: grid;
  grid-template-columns: 84px 50px 84px 1fr;
  gap: 8px;
  align-items: center;
  padding: 7px 8px;
  border-bottom: 1px solid #f0f3f7;
  font-size: 12px;
}
.audit-time {
  color: #7a8390;
  font-family: '"SF Mono", "Courier New", monospace';
}
.audit-delta {
  font-family: '"SF Mono", "Courier New", monospace';
  font-weight: 600;
  text-align: right;
}
.audit-delta.pos {
  color: #3a9d57;
}
.audit-delta.neg {
  color: #c1554a;
}
.audit-reason {
  color: #2c6dc1;
  background: rgba(44, 109, 193, 0.08);
  padding: 1px 6px;
  border-radius: 3px;
  font-size: 11px;
  text-align: center;
  white-space: nowrap;
}
.audit-desc {
  color: #4d5663;
  font-size: 12px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* 点赞按钮 */
.like-btn {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 10px 18px;
  background: #ffffff;
  border: 1px solid #e1e6ed;
  border-radius: 24px;
  cursor: pointer;
  transition: all 0.15s;
  font-family: inherit;
  font-size: 14px;
  color: #4d5663;
}
.like-btn:hover {
  border-color: #c1554a;
  background: rgba(193, 85, 74, 0.05);
}
.like-btn.liked {
  border-color: #c1554a;
  background: rgba(193, 85, 74, 0.08);
  color: #c1554a;
}
.like-heart {
  font-size: 18px;
  color: #c1554a;
}
.like-count {
  font-weight: 600;
  font-family: '"SF Mono", "Courier New", monospace';
  min-width: 20px;
  text-align: center;
}
.like-text {
  color: #7a8390;
  font-size: 12px;
}
.like-btn.liked .like-text {
  color: #c1554a;
}

/* 标签网格 */
.tag-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.tag-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  background: #ffffff;
  border: 1px solid #d8dee6;
  border-radius: 16px;
  cursor: pointer;
  transition: all 0.15s;
  font-family: inherit;
  font-size: 13px;
  color: #4d5663;
}
.tag-chip:hover {
  border-color: #2c6dc1;
  color: #2c6dc1;
}
.tag-chip.voted {
  background: rgba(44, 109, 193, 0.1);
  border-color: #2c6dc1;
  color: #2c6dc1;
  font-weight: 500;
}
.tag-chip.hot {
  border-color: #b97324;
}
.tag-chip.hot .tag-count {
  color: #b97324;
}
.tag-chip.voted.hot {
  background: rgba(185, 115, 36, 0.1);
  border-color: #b97324;
  color: #b97324;
}
.tag-label {
  font-weight: 500;
}
.tag-count {
  font-size: 11px;
  font-family: '"SF Mono", "Courier New", monospace';
  color: #aab3bf;
  min-width: 16px;
  text-align: center;
}
.tag-chip.voted .tag-count {
  color: inherit;
}

.footer {
  margin-top: 22px;
  padding-top: 14px;
  border-top: 1px solid #eef1f5;
  display: flex;
  justify-content: flex-end;
}

@media (max-width: 640px) {
  .stats-row {
    grid-template-columns: repeat(2, 1fr);
  }
  .audit-row {
    grid-template-columns: 70px 42px 64px 1fr;
    gap: 6px;
    font-size: 11px;
    padding: 6px 6px;
  }
  .audit-reason {
    font-size: 10px;
    padding: 1px 4px;
  }
}
</style>
