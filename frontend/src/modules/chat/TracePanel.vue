<template>
  <aside v-if="open" class="trace-panel" aria-label="问答 Trace">
    <header class="head">
      <div>
        <h2>Trace</h2>
        <p v-if="detail">全链路 · {{ detail.engine || "zhishu-local" }}</p>
        <p v-else>加载中…</p>
      </div>
      <button type="button" class="close" @click="$emit('close')">关闭</button>
    </header>

    <p v-if="error" class="err">{{ error }}</p>

    <template v-if="detail">
      <div class="id">{{ detail.id }}</div>
      <p class="q">{{ detail.query }}</p>
      <div class="kpi">
        <span>总耗时</span>
        <strong>{{ detail.latency_ms }} ms</strong>
      </div>

      <ol class="spans">
        <li v-for="(s, i) in detail.spans" :key="i">
          <div class="span-top">
            <strong>{{ spanLabel(s.name) }}</strong>
            <em>{{ s.duration_ms }} ms · {{ s.status }}</em>
          </div>
          <pre v-if="s.meta && Object.keys(s.meta).length" class="meta">{{
            formatMeta(s.meta)
          }}</pre>
        </li>
      </ol>

      <p v-if="detail.answer_preview" class="preview">
        <span>回答摘要</span>
        {{ detail.answer_preview }}
      </p>

      <div class="links" v-if="detail.hit_test_id && canHit">
        <RouterLink :to="`/hit-test?id=${detail.hit_test_id}`">
          打开关联 Hit Test #{{ detail.hit_test_id }}
        </RouterLink>
      </div>
    </template>
  </aside>
</template>

<script setup lang="ts">
/**
 * FR-14：单次问答 Trace 侧栏（轻量自建，非 Langfuse）。
 */
import { computed, ref, watch } from "vue";
import { getQaTrace } from "@/api/client";
import type { QaTraceDetail } from "@/api/types";
import { userRef } from "@/shared/auth";

const props = defineProps<{
  open: boolean;
  traceId: string | null;
}>();

defineEmits<{ close: [] }>();

const detail = ref<QaTraceDetail | null>(null);
const error = ref("");
const canHit = computed(() =>
  ["admin", "librarian", "auditor"].includes(userRef.value?.role || ""),
);

watch(
  () => [props.open, props.traceId] as const,
  async ([open, id]) => {
    detail.value = null;
    error.value = "";
    if (!open || !id) return;
    try {
      detail.value = await getQaTrace(id);
    } catch (e: any) {
      error.value = e?.response?.data?.detail || e?.message || "加载 Trace 失败";
    }
  },
  { immediate: true },
);

function spanLabel(name: string) {
  const map: Record<string, string> = {
    retrieve: "检索（向量+关键词+RRF）",
    rerank_inject: "重排与上下文注入",
    generate: "生成回答",
  };
  return map[name] || name;
}

function formatMeta(meta: Record<string, unknown>) {
  return JSON.stringify(meta, null, 2);
}
</script>

<style lang="less" scoped>
.trace-panel {
  position: absolute;
  top: 12px;
  right: 12px;
  bottom: 12px;
  width: min(380px, 92vw);
  z-index: 40;
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 16px;
  border-radius: 16px;
  border: 1px solid var(--zs-line);
  background: rgba(255, 255, 255, 0.96);
  box-shadow: 0 18px 48px rgba(20, 40, 30, 0.12);
  overflow: auto;
}
.head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;

  h2 {
    margin: 0;
    font-size: 18px;
  }
  p {
    margin: 4px 0 0;
    font-size: 12px;
    color: var(--zs-muted);
  }
}
.close {
  border: 1px solid var(--zs-line);
  background: #fff;
  border-radius: 999px;
  padding: 4px 12px;
  font-size: 12px;
  cursor: pointer;
}
.id {
  font-family: ui-monospace, Consolas, monospace;
  font-size: 11px;
  color: var(--zs-muted);
  word-break: break-all;
}
.q {
  margin: 0;
  font-size: 14px;
  line-height: 1.5;
}
.kpi {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  padding: 10px 12px;
  border-radius: 12px;
  background: var(--zs-accent-soft, #e8f5ef);

  span {
    font-size: 12px;
    color: var(--zs-muted);
  }
  strong {
    font-size: 18px;
  }
}
.spans {
  margin: 0;
  padding: 0;
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.span-top {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  font-size: 13px;

  em {
    font-style: normal;
    color: var(--zs-muted);
    white-space: nowrap;
  }
}
.meta {
  margin: 6px 0 0;
  padding: 8px 10px;
  border-radius: 8px;
  background: #f6f8f7;
  font-size: 11px;
  overflow: auto;
}
.preview {
  margin: 0;
  font-size: 13px;
  line-height: 1.55;
  color: var(--zs-ink);

  span {
    display: block;
    margin-bottom: 4px;
    font-size: 12px;
    color: var(--zs-muted);
  }
}
.links a {
  font-size: 13px;
  color: var(--zs-accent-deep);
}
.err {
  color: #b42318;
  font-size: 13px;
}
</style>
