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
import type { Player, PlayerSocial } from "@/api";
import {
  createTag,
  fetchPlayerSocial,
  getVoterNickname,
  isAdmin,
  setVoterNickname,
  togglePlayerLike,
  togglePlayerTag,
} from "@/api";

const props = defineProps<{
  show: boolean;
  player: Player | null;
}>();
const emit = defineEmits<{
  (e: "update:show", v: boolean): void;
  /** 当点赞/标签发生变更时通知父组件刷新列表 */
  (e: "changed"): void;
}>();

const message = useMessage();
const adminMode = isAdmin();

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
    const playerId = newTagIsPublic.value ? null : (props.player?.id ?? null);
    await createTag(label, 999, playerId);
    newTagLabel.value = "";
    showCreateTagModal.value = false;
    message.success("标签已创建");
    await loadSocial(); // 刷新显示新标签
  } catch (e) {
    message.error((e as Error).message);
  } finally {
    creatingTag.value = false;
  }
}

const social = ref<PlayerSocial | null>(null);
const loading = ref(false);

// 昵称引导
const showNicknameModal = ref(false);
const nicknameDraft = ref("");
const pendingAction = ref<(() => Promise<void>) | null>(null);

async function loadSocial() {
  if (!props.player) {
    social.value = null;
    return;
  }
  loading.value = true;
  try {
    social.value = await fetchPlayerSocial(props.player.id);
  } catch (e) {
    message.error((e as Error).message);
  } finally {
    loading.value = false;
  }
}

watch(
  () => [props.show, props.player?.id],
  ([show]) => {
    if (show) loadSocial();
  },
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
  if (!props.player) return;
  ensureNickname(async () => {
    try {
      social.value = await togglePlayerLike(props.player!.id);
      emit("changed");
    } catch (e) {
      message.error((e as Error).message);
    }
  });
}

async function onToggleTag(tagId: number) {
  if (!props.player) return;
  ensureNickname(async () => {
    try {
      social.value = await togglePlayerTag(props.player!.id, tagId);
      emit("changed");
    } catch (e) {
      message.error((e as Error).message);
    }
  });
}

const sortedTags = computed(() => {
  if (!social.value) return [];
  // 先按得票数降序，再按 voted_by_me，最后按 label
  return [...social.value.tags].sort((a, b) => {
    if (b.count !== a.count) return b.count - a.count;
    if (a.voted_by_me !== b.voted_by_me) return a.voted_by_me ? -1 : 1;
    return a.label.localeCompare(b.label);
  });
});

const winRatePercent = computed(() => {
  if (!props.player) return 0;
  return Math.round(props.player.win_rate * 100);
});
</script>

<template>
  <n-modal :show="show" :mask-closable="true" @update:show="onUpdateShow">
    <n-card class="detail-card" :bordered="false" size="small">
      <template v-if="player" #header>
        <div class="detail-header">
          <span class="detail-name">{{ player.name }}</span>
          <span class="detail-meta">
            <span class="meta-pill">本赛季积分 <b>{{ player.current_score }}</b></span>
          </span>
        </div>
      </template>

      <template v-if="player">
        <!-- 战绩区 -->
        <div class="stats-row">
          <div class="stat-cell">
            <div class="stat-label">总场次</div>
            <div class="stat-value">{{ player.total_played }}</div>
          </div>
          <div class="stat-cell">
            <div class="stat-label">胜场</div>
            <div class="stat-value win">{{ player.total_won }}</div>
          </div>
          <div class="stat-cell">
            <div class="stat-label">胜率</div>
            <div class="stat-value">
              {{ player.total_played > 0 ? `${winRatePercent}%` : "—" }}
            </div>
          </div>
          <div class="stat-cell">
            <div class="stat-label">今日</div>
            <div class="stat-value">
              {{ player.stats.matches_played }} 场 / {{ player.stats.matches_won }} 胜
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
          公共标签会出现在所有选手的标签栏中；专属标签仅在「{{ player?.name }}」的标签栏中显示。
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
</style>
