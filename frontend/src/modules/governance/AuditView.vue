<template>
  <div class="page">
    <nav class="crumb">
      <RouterLink to="/governance">治理</RouterLink>
      <span>/</span>
      <em>审计</em>
    </nav>
    <header class="hero">
      <h1>审计</h1>
      <p>关键操作只增不改。可按动作/操作人筛选，导出 CSV / JSON。</p>
    </header>

    <div class="toolbar">
      <input v-model="action" placeholder="动作，如 document.upload" @keyup.enter="refresh" />
      <input v-model="actor" placeholder="操作人" @keyup.enter="refresh" />
      <button type="button" @click="refresh">查询</button>
      <button type="button" class="ghost" @click="download('csv')">导出 CSV</button>
      <button type="button" class="ghost" @click="download('json')">导出 JSON</button>
    </div>

    <p v-if="loading" class="hint">加载中…</p>
    <div v-else class="list">
      <article v-for="row in items" :key="row.id" class="row">
        <div class="when">{{ row.created_at ? new Date(row.created_at).toLocaleString() : "—" }}</div>
        <div class="who">{{ row.actor_name || "—" }}</div>
        <div class="act">{{ row.action }}</div>
        <div class="res">
          <span v-if="row.resource_type">{{ row.resource_type }}#{{ row.resource_id }}</span>
          <span v-else>—</span>
        </div>
        <div class="detail">{{ row.detail ? JSON.stringify(row.detail) : "" }}</div>
      </article>
      <p v-if="!items.length" class="hint">暂无审计记录</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from "vue";
import { message } from "ant-design-vue";
import { auditExportUrl, listAudits, type AuditItem } from "@/api/client";
import { tokenRef, workspaceRef } from "@/shared/auth";

const items = ref<AuditItem[]>([]);
const action = ref("");
const actor = ref("");
const loading = ref(false);

async function refresh() {
  loading.value = true;
  try {
    items.value = await listAudits({
      action: action.value.trim() || undefined,
      actor: actor.value.trim() || undefined,
      limit: 80,
    });
  } catch (e: any) {
    message.error(e?.response?.data?.detail || "加载审计失败");
  } finally {
    loading.value = false;
  }
}

function exportHref(format: "csv" | "json") {
  const u = new URL(auditExportUrl(format), window.location.origin);
  // fetch with auth via window open won't send headers; use blob download
  return u.pathname + u.search;
}

async function download(format: "csv" | "json") {
  try {
    const headers: Record<string, string> = {};
    if (tokenRef.value) headers.Authorization = `Bearer ${tokenRef.value}`;
    if (workspaceRef.value?.id) headers["X-Workspace-Id"] = String(workspaceRef.value.id);
    const resp = await fetch(exportHref(format), { headers });
    if (!resp.ok) throw new Error(`export ${resp.status}`);
    const blob = await resp.blob();
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `audit.${format}`;
    a.click();
    URL.revokeObjectURL(a.href);
  } catch (e: any) {
    message.error(e?.message || "导出失败");
  }
}

onMounted(() => {
  void refresh();
});
</script>

<style lang="less" scoped>
.page {
  animation: zs-rise 0.45s ease both;
  padding: 0 0 40px;
  width: 100%;
  box-sizing: border-box;
}
.crumb {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 8px 0 4px;
  font-size: 13px;
  color: var(--zs-muted);

  a {
    color: var(--zs-accent-deep);
    text-decoration: none;
  }
  em {
    font-style: normal;
    color: var(--zs-ink);
  }
}
.hero h1 {
  margin: 0;
  font-family: var(--zs-font-display);
  font-size: clamp(32px, 5vw, 46px);
  color: var(--zs-accent-deep);
  letter-spacing: 0.06em;
}
.hero p {
  margin: 10px 0 0;
  color: var(--zs-muted);
}
.toolbar {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin: 20px 0 12px;
}
.toolbar input {
  border: 1px solid var(--zs-line);
  border-radius: 10px;
  padding: 8px 12px;
  background: rgba(255, 255, 255, 0.75);
  font: inherit;
  min-width: 160px;
}
.toolbar button {
  border: 0;
  border-radius: 999px;
  padding: 8px 14px;
  background: var(--zs-accent);
  color: #fff;
  cursor: pointer;
  font-size: 13px;
}
.toolbar .ghost {
  background: rgba(255, 255, 255, 0.7);
  color: var(--zs-accent-deep);
  border: 1px solid var(--zs-line);
}
.row {
  display: grid;
  grid-template-columns: 160px 90px 170px 120px 1fr;
  gap: 10px;
  padding: 12px 4px;
  border-top: 1px solid var(--zs-line);
  font-size: 13px;
  align-items: start;
}
.when,
.who,
.res {
  color: var(--zs-muted);
}
.act {
  color: var(--zs-accent-deep);
  font-weight: 600;
}
.detail {
  color: var(--zs-muted);
  word-break: break-all;
  font-size: 12px;
}
.hint {
  color: var(--zs-muted);
  font-size: 13px;
}
@media (max-width: 900px) {
  .row {
    grid-template-columns: 1fr;
  }
}
</style>
