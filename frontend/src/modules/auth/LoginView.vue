<template>
  <div class="login">
    <form class="panel" @submit.prevent="submit">
      <div class="brand">
        <span class="mark">知</span>
        <h1>知枢</h1>
      </div>
      <p class="lead">登录后进入工作区知识库</p>
      <label>
        用户名
        <input v-model="username" autocomplete="username" />
      </label>
      <label>
        密码
        <input v-model="password" type="password" autocomplete="current-password" />
      </label>
      <button type="submit" :disabled="loading">{{ loading ? "登录中…" : "登录" }}</button>
      <p class="hint">演示账号：admin / admin123（L4）· member / member123（L2）</p>
    </form>
  </div>
</template>

<script setup lang="ts">
import { ref } from "vue";
import { useRouter } from "vue-router";
import { message } from "ant-design-vue";
import { login } from "@/api/client";
import { setSession } from "@/shared/auth";

const router = useRouter();
const username = ref("admin");
const password = ref("admin123");
const loading = ref(false);

async function submit() {
  loading.value = true;
  try {
    const data = await login(username.value.trim(), password.value);
    setSession(data.access_token, data.user, data.workspaces);
    message.success(`欢迎，${data.user.display_name || data.user.username}`);
    await router.replace("/");
  } catch (e: any) {
    message.error(e?.response?.data?.detail || "登录失败");
  } finally {
    loading.value = false;
  }
}
</script>

<style lang="less" scoped>
.login {
  min-height: calc(100vh - 80px);
  display: grid;
  place-items: center;
  padding: 24px;
}
.panel {
  width: min(400px, 100%);
  display: flex;
  flex-direction: column;
  gap: 14px;
  padding: 28px 26px;
  border: 1px solid var(--zs-line);
  border-radius: 20px;
  background: rgba(255, 255, 255, 0.72);
  box-shadow: var(--zs-shadow);
  animation: zs-rise 0.5s ease both;
}
.brand {
  display: flex;
  align-items: center;
  gap: 12px;
}
.mark {
  width: 40px;
  height: 40px;
  border-radius: 12px;
  display: grid;
  place-items: center;
  background: linear-gradient(145deg, var(--zs-accent), var(--zs-accent-deep));
  color: #fff;
  font-family: var(--zs-font-display);
}
.brand h1 {
  margin: 0;
  font-family: var(--zs-font-display);
  letter-spacing: 0.1em;
  color: var(--zs-accent-deep);
}
.lead {
  margin: 0;
  color: var(--zs-muted);
  font-size: 14px;
}
label {
  display: flex;
  flex-direction: column;
  gap: 6px;
  font-size: 13px;
  color: var(--zs-muted);
}
input {
  border: 1px solid var(--zs-line);
  border-radius: 10px;
  padding: 10px 12px;
  font: inherit;
  color: var(--zs-ink);
  background: #fff;
}
button {
  border: 0;
  border-radius: 12px;
  padding: 12px;
  background: var(--zs-accent);
  color: #fff;
  font-weight: 600;
  cursor: pointer;
}
button:disabled {
  opacity: 0.5;
}
.hint {
  margin: 0;
  font-size: 12px;
  color: var(--zs-muted);
  line-height: 1.5;
}
</style>
