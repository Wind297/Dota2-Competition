<script setup lang="ts">
import { ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { NButton, NCard, NForm, NFormItem, NInput, useMessage } from "naive-ui";
import { login } from "@/api";

const router = useRouter();
const route = useRoute();
const message = useMessage();
const password = ref("");
const loading = ref(false);

async function onSubmit() {
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
</script>

<template>
  <div style="min-height: 100vh; display: flex; align-items: center; justify-content: center; padding: 16px">
    <n-card title="管理员登录" style="width: 100%; max-width: 400px">
      <n-form @submit.prevent="onSubmit">
        <n-form-item label="密码">
          <n-input
            v-model:value="password"
            type="password"
            show-password-on="click"
            placeholder="请输入管理密码"
            @keyup.enter="onSubmit"
          />
        </n-form-item>
        <n-button type="primary" block :loading="loading" attr-type="submit">进入系统</n-button>
      </n-form>
    </n-card>
  </div>
</template>
