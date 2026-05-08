<script setup lang="ts">
import {
  NConfigProvider,
  NDialogProvider,
  NGlobalStyle,
  NMessageProvider,
  darkTheme,
} from "naive-ui";
import zhCN from "naive-ui/es/locales/common/zhCN.mjs";

const theme = darkTheme;
</script>

<template>
  <n-config-provider :locale="zhCN" :theme="theme">
    <n-global-style />
    <n-message-provider>
      <n-dialog-provider>
        <router-view />
      </n-dialog-provider>
    </n-message-provider>
  </n-config-provider>
</template>
