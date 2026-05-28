<script setup lang="ts">
defineProps<{
  /** 中文标题 */
  title: string;
  /** 英文副标题 */
  subtitle?: string;
}>();
</script>

<template>
  <div class="page-header">
    <div class="page-header-bar"></div>
    <div class="page-header-text">
      <h1 class="dota-title-cn">{{ title }}</h1>
      <p v-if="subtitle" class="dota-title-en">{{ subtitle }}</p>
    </div>
  </div>
</template>

<style scoped>
.page-header {
  display: flex;
  align-items: center;
  gap: 14px;
  margin-bottom: 22px;
  padding: 0 4px;
}
.page-header-bar {
  width: 3px;
  height: 30px;
  background: linear-gradient(180deg, #5b9dd9 0%, #d4954a 100%);
  border-radius: 1px;
  flex-shrink: 0;
}
.page-header-text {
  flex: 1;
  min-width: 0;
}
</style>
