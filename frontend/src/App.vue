<template>
  <div class="shell">
    <header class="top">
      <button class="brand" type="button" @click="$router.push('/')">
        <span class="mark">知</span>
        <span class="name">知枢</span>
      </button>
      <nav v-if="userRef" class="nav">
        <RouterLink class="link" to="/">问答</RouterLink>
        <RouterLink class="link" to="/knowledge">知识库</RouterLink>
        <RouterLink
          v-if="['admin', 'auditor', 'librarian'].includes(userRef.role)"
          class="link"
          to="/governance"
        >
          治理
        </RouterLink>
        <RouterLink v-if="userRef.role === 'admin'" class="link" to="/settings">
          设置
        </RouterLink>
      </nav>
      <div v-if="userRef" class="userbox">
        <label class="ws-wrap" v-if="workspacesRef.length">
          <span class="sr">工作区</span>
          <select
            class="ws-select"
            :value="workspaceRef?.id"
            @change="onWorkspaceChange"
          >
            <option v-for="w in workspacesRef" :key="w.id" :value="w.id">
              {{ wsLabel(w) }}
            </option>
          </select>
        </label>
        <span v-else class="ws">工作区</span>
        <span class="who">
          {{ userRef.display_name || userRef.username }} · L{{ userRef.clearance }}
        </span>
        <button type="button" class="out" @click="logout">退出</button>
      </div>
      <span v-else class="env">内网 POC</span>
    </header>
    <main class="main">
      <router-view :key="workspaceRef?.id || 0" />
    </main>
  </div>
</template>

<script setup lang="ts">
import { useRouter } from "vue-router";
import {
  clearSession,
  setWorkspace,
  userRef,
  workspaceRef,
  workspacesRef,
  type WorkspaceItem,
} from "@/shared/auth";

const router = useRouter();

function logout() {
  clearSession();
  router.push("/login");
}

function onWorkspaceChange(e: Event) {
  const id = Number((e.target as HTMLSelectElement).value);
  const ws = workspacesRef.value.find((w) => w.id === id);
  if (!ws || ws.id === workspaceRef.value?.id) return;
  setWorkspace(ws);
}

function wsLabel(w: WorkspaceItem) {
  return w.name;
}
</script>

<style lang="less" scoped>
.shell {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}
.top {
  display: flex;
  align-items: center;
  gap: 28px;
  padding: 18px 16px 10px;
  animation: zs-fade 0.6s ease both;
}
.brand {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  border: 0;
  background: transparent;
  cursor: pointer;
  padding: 0;
}
.mark {
  width: 34px;
  height: 34px;
  border-radius: 10px;
  display: grid;
  place-items: center;
  background: linear-gradient(145deg, var(--zs-accent), var(--zs-accent-deep));
  color: #f4faf7;
  font-family: var(--zs-font-display);
  font-size: 18px;
  box-shadow: 0 8px 20px rgba(11, 92, 69, 0.28);
}
.name {
  font-family: var(--zs-font-display);
  font-size: 26px;
  letter-spacing: 0.12em;
  color: var(--zs-accent-deep);
  font-weight: 700;
}
.nav {
  display: flex;
  gap: 6px;
  flex: 1;
}
.link {
  text-decoration: none;
  color: var(--zs-muted);
  padding: 8px 14px;
  border-radius: 999px;
  font-size: 14px;
}
.link:hover {
  color: var(--zs-ink);
  background: rgba(255, 255, 255, 0.45);
}
.link.router-link-active {
  color: var(--zs-accent-deep);
  background: var(--zs-accent-soft);
  font-weight: 600;
}
.userbox {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 12px;
  color: var(--zs-muted);
}
.ws-wrap {
  display: inline-flex;
  align-items: center;
}
.sr {
  position: absolute;
  width: 1px;
  height: 1px;
  overflow: hidden;
  clip: rect(0 0 0 0);
}
.ws-select {
  appearance: none;
  border: 1px solid var(--zs-line);
  border-radius: 999px;
  padding: 5px 28px 5px 12px;
  background:
    linear-gradient(45deg, transparent 50%, var(--zs-muted) 50%) right 12px top 11px / 5px 5px no-repeat,
    linear-gradient(135deg, var(--zs-muted) 50%, transparent 50%) right 7px top 11px / 5px 5px no-repeat,
    rgba(255, 255, 255, 0.55);
  color: var(--zs-ink);
  font: inherit;
  font-size: 12px;
  max-width: 160px;
  cursor: pointer;
  outline: none;
}
.ws-select:focus {
  border-color: var(--zs-accent);
}
.ws {
  border: 1px solid var(--zs-line);
  border-radius: 999px;
  padding: 4px 10px;
  background: rgba(255, 255, 255, 0.45);
}
.who {
  max-width: 180px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.out {
  border: 0;
  background: transparent;
  color: var(--zs-accent-deep);
  cursor: pointer;
  font-size: 12px;
}
.env {
  font-size: 12px;
  color: var(--zs-muted);
  border: 1px solid var(--zs-line);
  border-radius: 999px;
  padding: 4px 10px;
}
.main {
  flex: 1;
  display: flex;
  flex-direction: column;
  width: 100%;
  margin: 0;
  padding: 0 16px;
  box-sizing: border-box;
  min-width: 0;
  min-height: 0;
}
@media (max-width: 720px) {
  .top {
    padding: 14px 16px 6px;
    gap: 14px;
    flex-wrap: wrap;
  }
}
</style>
