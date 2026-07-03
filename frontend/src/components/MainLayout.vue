<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { NLayout, NLayoutContent, NLayoutHeader } from "naive-ui";
import { useRouter, useRoute } from "vue-router";
import { TOKEN_KEY, GUEST_KEY, clearAuth, fetchCurrentSeason, type Season } from "@/api";
import { loadConfig } from "@/config";

const router = useRouter();
const route = useRoute();

const isAdmin = computed(() => !!localStorage.getItem(TOKEN_KEY) && localStorage.getItem(GUEST_KEY) !== "1");
const isGuest = computed(() => localStorage.getItem(GUEST_KEY) === "1");

const currentSeason = ref<Season | null>(null);

async function loadCurrentSeason() {
  try {
    currentSeason.value = await fetchCurrentSeason();
  } catch {
    currentSeason.value = null;
  }
}

onMounted(() => {
  loadCurrentSeason();
  loadConfig();
});

function logout() {
  clearAuth();
  router.push("/login");
}

function switchToAdmin() {
  clearAuth();
  router.push("/login");
}

const navItems = [
  { path: "/", name: "players", label: "选手池" },
  { path: "/matches", name: "matches", label: "比赛记录" },
  { path: "/rankings", name: "rankings", label: "排行榜" },
  { path: "/seasons", name: "seasons", label: "赛季" },
];

function isActive(item: { path: string; name: string }): boolean {
  if (item.name === "players") return route.path === "/" || route.name === "players";
  if (item.name === "matches") return route.path.startsWith("/matches");
  if (item.name === "seasons") return route.path === "/seasons";
  return route.path === item.path;
}

function navigate(path: string) {
  router.push(path);
}
</script>

<template>
  <n-layout style="min-height: 100vh; background: transparent">
    <n-layout-header bordered class="dota-header">
      <div class="header-inner">
        <!-- 品牌区 -->
        <div class="brand" @click="router.push('/')">
          <div class="brand-logo">
            <svg viewBox="0 0 24 24" width="22" height="22" fill="none">
              <path d="M12 2 L20 7 L20 17 L12 22 L4 17 L4 7 Z"
                stroke="#2c6dc1" stroke-width="1.5" fill="rgba(44, 109, 193, 0.08)"/>
              <circle cx="12" cy="12" r="3" fill="#b97324"/>
            </svg>
          </div>
          <span class="brand-text">武汉点神杯·个人积分赛</span>
        </div>

        <div class="vertical-sep"></div>

        <!-- 导航 -->
        <nav class="nav">
          <button
            v-for="item in navItems"
            :key="item.name"
            class="nav-item"
            :class="{ active: isActive(item) }"
            @click="navigate(item.path)"
          >
            {{ item.label }}
          </button>
        </nav>

        <!-- 右侧 -->
        <div class="right-actions">
          <span v-if="currentSeason" class="season-tag" @click="router.push('/seasons')" title="点击查看赛季列表">
            {{ currentSeason.name }}
          </span>
          <span v-if="isAdmin" class="role-tag role-admin">
            <span class="role-dot"></span>管理员
          </span>
          <span v-else-if="isGuest" class="role-tag role-guest">
            <span class="role-dot"></span>观战者
          </span>
          <button v-if="isAdmin" class="action-btn" @click="logout">退出</button>
          <button v-else-if="isGuest" class="action-btn primary" @click="switchToAdmin">
            管理员登录
          </button>
        </div>
      </div>
    </n-layout-header>

    <n-layout-content style="padding: 28px 20px; background: transparent">
      <div class="content-wrap">
        <slot />
      </div>
    </n-layout-content>
  </n-layout>
</template>

<style scoped>
.dota-header {
  background: rgba(255, 255, 255, 0.85) !important;
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  border-bottom: 1px solid #e1e6ed !important;
  padding: 0 !important;
  height: auto !important;
  position: sticky;
  top: 0;
  z-index: 100;
}
.header-inner {
  height: 56px;
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 0 24px;
  max-width: 1400px;
  margin: 0 auto;
}
.content-wrap {
  max-width: 1280px;
  margin: 0 auto;
}

/* 品牌 */
.brand {
  display: flex;
  align-items: center;
  gap: 10px;
  cursor: pointer;
  flex-shrink: 0;
  transition: opacity 0.2s;
}
.brand:hover { opacity: 0.85; }
.brand-text {
  font-size: 14px;
  font-weight: 600;
  color: #1a2435;
  letter-spacing: 0.5px;
}

.vertical-sep {
  width: 1px;
  height: 18px;
  background: #d8dee6;
}

/* 导航 */
.nav {
  display: flex;
  gap: 2px;
  flex: 1;
}
.nav-item {
  background: none;
  border: none;
  cursor: pointer;
  padding: 7px 14px;
  font-size: 13px;
  color: #5a6473;
  border-radius: 4px;
  transition: all 0.15s;
  font-family: inherit;
  position: relative;
}
.nav-item:hover {
  color: #1a2435;
  background: #f0f3f7;
}
.nav-item.active {
  color: #2c6dc1;
  background: rgba(44, 109, 193, 0.08);
  font-weight: 600;
}
.nav-item.active::after {
  content: "";
  position: absolute;
  bottom: -1px;
  left: 14px;
  right: 14px;
  height: 2px;
  background: #2c6dc1;
  border-radius: 1px;
}

/* 右侧 */
.right-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-shrink: 0;
}
.role-tag {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 10px;
  font-size: 11px;
  font-weight: 500;
  border-radius: 3px;
  letter-spacing: 0.5px;
}
.season-tag {
  display: inline-flex;
  align-items: center;
  padding: 4px 10px;
  font-size: 11px;
  font-weight: 500;
  border-radius: 3px;
  letter-spacing: 0.3px;
  cursor: pointer;
  background: rgba(44, 109, 193, 0.08);
  color: #2c6dc1;
  border: 1px solid rgba(44, 109, 193, 0.2);
  transition: all 0.15s;
}
.season-tag:hover {
  background: rgba(44, 109, 193, 0.14);
  border-color: rgba(44, 109, 193, 0.4);
}
.role-admin {
  background: rgba(185, 115, 36, 0.12);
  color: #b97324;
  border: 1px solid rgba(185, 115, 36, 0.3);
}
.role-guest {
  background: rgba(44, 109, 193, 0.1);
  color: #2c6dc1;
  border: 1px solid rgba(44, 109, 193, 0.25);
}
.role-dot {
  display: inline-block;
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: currentColor;
}
.action-btn {
  background: transparent;
  border: 1px solid #d8dee6;
  color: #4d5663;
  padding: 5px 12px;
  font-size: 12px;
  cursor: pointer;
  border-radius: 4px;
  transition: all 0.15s;
  font-family: inherit;
}
.action-btn:hover {
  border-color: #2c6dc1;
  color: #2c6dc1;
  background: rgba(44, 109, 193, 0.05);
}
.action-btn.primary {
  border-color: #2c6dc1;
  color: #2c6dc1;
  background: rgba(44, 109, 193, 0.06);
}
.action-btn.primary:hover {
  background: #2c6dc1;
  color: #ffffff;
}

@media (max-width: 880px) {
  .header-inner { padding: 0 14px; gap: 10px; }
  .vertical-sep { display: none; }
  .role-tag { display: none; }
  .season-tag { display: none; }
  .brand-text { display: none; }
}
</style>
