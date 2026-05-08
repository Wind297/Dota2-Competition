<script setup lang="ts">
import { NButton, NLayout, NLayoutContent, NLayoutHeader, NSpace, NText } from "naive-ui";
import { useRouter, useRoute } from "vue-router";
import { TOKEN_KEY } from "@/api";

const router = useRouter();
const route = useRoute();

function logout() {
  localStorage.removeItem(TOKEN_KEY);
  router.push("/login");
}
</script>

<template>
  <n-layout style="min-height: 100vh">
    <n-layout-header
      bordered
      style="padding: 12px 16px; display: flex; align-items: center; gap: 12px; flex-wrap: wrap"
    >
      <n-text strong style="font-size: 16px">Dota2 个人积分赛</n-text>
      <n-space>
        <n-button
          quaternary
          :type="route.path === '/' || route.name === 'players' ? 'primary' : 'default'"
          @click="router.push('/')"
        >
          选手池
        </n-button>
        <n-button
          quaternary
          :type="route.path.startsWith('/matches') ? 'primary' : 'default'"
          @click="router.push('/matches')"
        >
          历史比赛
        </n-button>
        <n-button
          quaternary
          :type="route.path === '/rankings' ? 'primary' : 'default'"
          @click="router.push('/rankings')"
        >
          排行榜
        </n-button>
        <n-button quaternary @click="logout">退出</n-button>
      </n-space>
    </n-layout-header>
    <n-layout-content style="padding: 16px">
      <slot />
    </n-layout-content>
  </n-layout>
</template>
