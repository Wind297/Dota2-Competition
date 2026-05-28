<script setup lang="ts">
import {
  NConfigProvider,
  NDialogProvider,
  NGlobalStyle,
  NMessageProvider,
  lightTheme,
  type GlobalThemeOverrides,
} from "naive-ui";
import zhCN from "naive-ui/es/locales/common/zhCN.mjs";

const theme = lightTheme;

// ── 浅色主题：清爽的白底蓝灰仪表盘风格 ─────────────────────────
// 主色：深青蓝（#2c6dc1）；次色：暖琥珀（#b97324）；底色：清浅蓝灰
const themeOverrides: GlobalThemeOverrides = {
  common: {
    primaryColor: "#2c6dc1",
    primaryColorHover: "#3b80d8",
    primaryColorPressed: "#1f55a3",
    primaryColorSuppl: "#2c6dc1",
    infoColor: "#2c6dc1",
    successColor: "#3a9d57",
    successColorHover: "#4dae6a",
    warningColor: "#b97324",
    warningColorHover: "#c98839",
    errorColor: "#c1554a",
    errorColorHover: "#d36e63",
    bodyColor: "#f3f5f8",
    cardColor: "#ffffff",
    modalColor: "#ffffff",
    popoverColor: "#ffffff",
    tableColor: "#ffffff",
    tableColorHover: "#f0f5fb",
    tableColorStriped: "#fafbfd",
    borderColor: "#e1e6ed",
    dividerColor: "#e8ecf2",
    textColorBase: "#1a2435",
    textColor1: "#1a2435",
    textColor2: "#4d5663",
    textColor3: "#7a8390",
    fontFamily:
      '"PingFang SC", "Microsoft YaHei", "Hiragino Sans GB", system-ui, -apple-system, BlinkMacSystemFont, sans-serif',
    fontWeightStrong: "600",
  },
  Card: {
    borderColor: "#e1e6ed",
    titleFontSizeMedium: "15px",
    titleTextColor: "#1a2435",
  },
  Button: {
    fontWeight: "500",
  },
  DataTable: {
    thColor: "#f6f8fb",
    thTextColor: "#5a6473",
    thFontWeight: "500",
    borderColor: "#e8ecf2",
    tdColorHover: "#f0f5fb",
  },
  Tag: {
    borderRadius: "3px",
  },
  Input: {
    borderHover: "#7aa6d9",
    borderFocus: "#2c6dc1",
    boxShadowFocus: "0 0 0 2px rgba(44, 109, 193, 0.15)",
  },
  Layout: {
    headerColor: "transparent",
    color: "transparent",
  },
};
</script>

<template>
  <n-config-provider :locale="zhCN" :theme="theme" :theme-overrides="themeOverrides">
    <n-global-style />
    <n-message-provider>
      <n-dialog-provider>
        <router-view />
      </n-dialog-provider>
    </n-message-provider>
  </n-config-provider>
</template>

<style>
/* ── 全局背景 ─────────────────────────────────────────────────── */
html, body, #app {
  margin: 0;
  padding: 0;
  min-height: 100vh;
  background:
    radial-gradient(ellipse 80% 50% at 50% 0%, rgba(44, 109, 193, 0.06) 0%, transparent 65%),
    radial-gradient(ellipse 60% 40% at 100% 100%, rgba(185, 115, 36, 0.04) 0%, transparent 70%),
    linear-gradient(180deg, #f3f5f8 0%, #e9eef4 100%);
  background-attachment: fixed;
}

body {
  font-family: "PingFang SC", "Microsoft YaHei", "Hiragino Sans GB", system-ui, sans-serif;
  color: #1a2435;
  -webkit-font-smoothing: antialiased;
}

/* ── 滚动条 ───────────────────────────────────────────────────── */
::-webkit-scrollbar {
  width: 10px;
  height: 10px;
}
::-webkit-scrollbar-track {
  background: transparent;
}
::-webkit-scrollbar-thumb {
  background: rgba(0, 0, 0, 0.14);
  border-radius: 5px;
  border: 2px solid #f3f5f8;
}
::-webkit-scrollbar-thumb:hover {
  background: rgba(44, 109, 193, 0.4);
}

/* ── 全局工具类 ────────────────────────────────────────────────── */
.dota-title-cn {
  font-size: 22px;
  font-weight: 600;
  color: #1a2435;
  letter-spacing: 0.5px;
  margin: 0;
  line-height: 1.2;
}
.dota-title-en {
  font-size: 11px;
  color: #8a96a6;
  letter-spacing: 2.5px;
  text-transform: uppercase;
  margin: 4px 0 0;
  font-weight: 400;
}

/* ── 卡片 ────────────────────────────────────────────────────── */
.n-card {
  background: #ffffff !important;
  border-radius: 8px !important;
  border: 1px solid #e1e6ed !important;
  box-shadow: 0 1px 3px rgba(20, 30, 50, 0.04), 0 4px 12px rgba(20, 30, 50, 0.04) !important;
  transition: box-shadow 0.2s ease, border-color 0.2s ease;
}
.n-card:hover {
  box-shadow: 0 2px 6px rgba(20, 30, 50, 0.05), 0 8px 20px rgba(20, 30, 50, 0.06) !important;
}
.n-card > .n-card-header {
  border-bottom: 1px solid #eef1f5;
  padding: 14px 18px !important;
}
.n-card > .n-card__content {
  padding: 16px 18px !important;
}

/* 表格 */
.n-data-table .n-data-table-th {
  font-size: 11px !important;
  letter-spacing: 1.5px;
  text-transform: uppercase;
}

/* 主按钮 */
.n-button.n-button--primary-type:not(.n-button--quaternary-type):not(.n-button--tertiary-type):not(.n-button--secondary-type) {
  background: #2c6dc1 !important;
  border: none;
  font-weight: 500;
  letter-spacing: 0.5px;
  box-shadow: 0 1px 3px rgba(44, 109, 193, 0.25);
  color: #ffffff !important;
}
.n-button.n-button--primary-type:not(.n-button--quaternary-type):not(.n-button--tertiary-type):not(.n-button--secondary-type):hover {
  background: #3b80d8 !important;
  box-shadow: 0 2px 8px rgba(44, 109, 193, 0.35);
}

/* Tag */
.n-tag {
  border-radius: 3px !important;
  letter-spacing: 0.5px;
  font-size: 11px !important;
}

/* Modal mask（浅色） */
.n-modal-mask {
  background: rgba(20, 30, 50, 0.35) !important;
  backdrop-filter: blur(2px);
}
</style>
