<script setup lang="ts">
import { ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { NButton, NInput, useMessage } from "naive-ui";
import { login, enterGuest } from "@/api";

const router = useRouter();
const route = useRoute();
const message = useMessage();
const password = ref("");
const loading = ref(false);
const showAdminForm = ref(false);

async function onAdminLogin() {
  if (!password.value) {
    message.warning("请输入管理员密码");
    return;
  }
  loading.value = true;
  try {
    await login(password.value);
    const redirect = (route.query.redirect as string) || "/";
    await router.replace(redirect);
  } catch (e) {
    message.error((e as Error).message);
  } finally {
    loading.value = false;
  }
}

async function onGuestEnter() {
  loading.value = true;
  try {
    await enterGuest();
    router.replace("/rankings");
  } catch (e) {
    message.error((e as Error).message);
  } finally {
    loading.value = false;
  }
}
</script>

<template>
  <div class="login-bg">
    <div class="bg-grid" />
    <div class="bg-glow bg-glow-1" />
    <div class="bg-glow bg-glow-2" />

    <div class="login-container">
      <!-- Logo -->
      <div class="logo-area">
        <div class="logo-mark">
          <svg viewBox="0 0 64 64" width="56" height="56" fill="none">
            <path d="M32 4 L56 18 L56 46 L32 60 L8 46 L8 18 Z"
              stroke="#2c6dc1" stroke-width="1.5" fill="rgba(44, 109, 193, 0.08)"/>
            <path d="M32 14 L46 22 L46 42 L32 50 L18 42 L18 22 Z"
              stroke="rgba(44, 109, 193, 0.4)" stroke-width="1" fill="none"/>
            <circle cx="32" cy="32" r="5" fill="#b97324"/>
            <circle cx="32" cy="32" r="2" fill="#ffffff"/>
          </svg>
        </div>
        <div class="title-block">
          <h1 class="login-title">个人积分赛</h1>
          <p class="login-subtitle">PERSONAL LEAGUE</p>
        </div>
      </div>

      <!-- 卡片 -->
      <div class="login-card">
        <template v-if="!showAdminForm">
          <p class="card-prompt">选择身份进入</p>

          <button class="entry-btn entry-guest" :disabled="loading" @click="onGuestEnter">
            <div class="entry-content">
              <div class="entry-label">观战者</div>
              <div class="entry-desc">浏览排行榜与比赛记录</div>
            </div>
            <div class="entry-arrow">→</div>
          </button>

          <button class="entry-btn entry-admin" @click="showAdminForm = true">
            <div class="entry-content">
              <div class="entry-label">管理员</div>
              <div class="entry-desc">完整管理权限</div>
            </div>
            <div class="entry-arrow">→</div>
          </button>
        </template>

        <template v-else>
          <button class="back-btn" @click="showAdminForm = false">
            ← 返回
          </button>
          <p class="card-prompt" style="margin-top: 6px">管理员认证</p>

          <div class="input-wrap">
            <n-input
              v-model:value="password"
              type="password"
              show-password-on="click"
              placeholder="请输入密码"
              size="large"
              :input-props="{ autocomplete: 'current-password' }"
              @keyup.enter="onAdminLogin"
            />
          </div>

          <n-button
            type="primary"
            block
            size="large"
            :loading="loading"
            @click="onAdminLogin"
          >
            登录
          </n-button>
        </template>
      </div>

      <p class="footer-text">v0.1 · Personal League System</p>
    </div>
  </div>
</template>

<style scoped>
.login-bg {
  min-height: 100vh;
  background:
    radial-gradient(ellipse 70% 50% at 50% 30%, rgba(44, 109, 193, 0.08) 0%, transparent 65%),
    linear-gradient(180deg, #f3f5f8 0%, #e9eef4 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 32px 16px;
  position: relative;
  overflow: hidden;
}

.bg-grid {
  position: absolute;
  inset: 0;
  background-image:
    linear-gradient(rgba(44, 109, 193, 0.04) 1px, transparent 1px),
    linear-gradient(90deg, rgba(44, 109, 193, 0.04) 1px, transparent 1px);
  background-size: 48px 48px;
  mask-image: radial-gradient(ellipse at center, black 0%, transparent 75%);
  pointer-events: none;
}

.bg-glow {
  position: absolute;
  border-radius: 50%;
  filter: blur(120px);
  pointer-events: none;
}
.bg-glow-1 {
  width: 480px; height: 480px;
  background: radial-gradient(circle, rgba(44, 109, 193, 0.18) 0%, transparent 70%);
  top: -150px; left: 50%;
  transform: translateX(-50%);
}
.bg-glow-2 {
  width: 320px; height: 320px;
  background: radial-gradient(circle, rgba(185, 115, 36, 0.10) 0%, transparent 70%);
  bottom: -100px; right: -50px;
}

.login-container {
  width: 100%;
  max-width: 380px;
  position: relative;
  z-index: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
}

.logo-area {
  display: flex;
  flex-direction: column;
  align-items: center;
  margin-bottom: 32px;
  gap: 16px;
}
.logo-mark {
  filter: drop-shadow(0 4px 12px rgba(44, 109, 193, 0.2));
}
.title-block {
  text-align: center;
}
.login-title {
  font-size: 26px;
  font-weight: 600;
  color: #1a2435;
  letter-spacing: 2px;
  margin: 0;
}
.login-subtitle {
  font-size: 11px;
  letter-spacing: 4px;
  color: #8a96a6;
  margin: 6px 0 0;
}

.login-card {
  width: 100%;
  background: #ffffff;
  border: 1px solid #e1e6ed;
  border-radius: 10px;
  padding: 24px 22px;
  box-shadow: 0 12px 40px rgba(20, 30, 50, 0.06), 0 2px 6px rgba(20, 30, 50, 0.03);
}

.card-prompt {
  text-align: center;
  margin: 0 0 18px;
  font-size: 12px;
  color: #7a8390;
  letter-spacing: 2px;
}

.entry-btn {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 14px 16px;
  border: 1px solid #e1e6ed;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.18s ease;
  text-align: left;
  background: #fafbfd;
  font-family: inherit;
  margin-bottom: 10px;
}
.entry-btn:last-child { margin-bottom: 0; }
.entry-btn:disabled { opacity: 0.6; cursor: wait; }

.entry-guest:hover:not(:disabled) {
  border-color: #2c6dc1;
  background: rgba(44, 109, 193, 0.05);
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(44, 109, 193, 0.10);
}
.entry-admin:hover {
  border-color: #b97324;
  background: rgba(185, 115, 36, 0.05);
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(185, 115, 36, 0.10);
}

.entry-content { flex: 1; line-height: 1.3; }
.entry-label {
  font-size: 14px;
  font-weight: 600;
  color: #1a2435;
}
.entry-desc {
  font-size: 12px;
  color: #7a8390;
  margin-top: 3px;
}
.entry-arrow {
  font-size: 18px;
  color: #aab3bf;
  transition: all 0.18s ease;
}
.entry-guest:hover .entry-arrow { color: #2c6dc1; transform: translateX(3px); }
.entry-admin:hover .entry-arrow { color: #b97324; transform: translateX(3px); }

.back-btn {
  background: none;
  border: none;
  color: #7a8390;
  cursor: pointer;
  font-size: 12px;
  padding: 0;
  font-family: inherit;
  transition: color 0.2s;
}
.back-btn:hover { color: #2c6dc1; }

.input-wrap { margin: 16px 0 14px; }

.footer-text {
  margin-top: 20px;
  font-size: 11px;
  color: #aab3bf;
  letter-spacing: 1px;
  text-align: center;
}
</style>
