<template>
  <aside class="rail">
    <div class="rail-head">
      <h2>引用原文</h2>
      <p>核对回答依据</p>
    </div>
    <div v-if="!citations.length" class="rail-empty">
      点「参考来源」标签，在此展开原文片段。
    </div>
    <div v-for="(c, i) in citations" :key="i" class="snippet">
      <div class="snippet-meta">
        <strong>{{ c.title }}</strong>
        <span v-if="(c.classification || 0) >= 3" class="lvl">L{{ c.classification }}</span>
        <span v-if="c.page">p.{{ c.page }}</span>
      </div>
      <MarkdownBody class="snippet-md" :source="c.snippet" />
    </div>
  </aside>
</template>

<script setup lang="ts">
/** 右侧引用原文轨：展示当前选中的 citation snippet。 */
import MarkdownBody from "@/shared/MarkdownBody.vue";
import type { Citation } from "@/api/types";

defineProps<{ citations: Citation[] }>();
</script>

<style lang="less" scoped>
.rail {
  border-left: 1px solid var(--zs-line);
  padding: 8px 0 12px 16px;
  min-width: 0;
  min-height: 0;
  overflow: auto;
}
.rail-head {
  h2 {
    margin: 0;
    font-family: var(--zs-font-display);
    font-size: 18px;
  }
  p {
    margin: 4px 0 14px;
    color: var(--zs-muted);
    font-size: 12px;
  }
}
.rail-empty {
  color: var(--zs-muted);
  font-size: 13px;
  line-height: 1.6;
}
.snippet {
  padding: 12px 0;
  border-top: 1px solid var(--zs-line);
}
.snippet-meta {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 8px;
  font-size: 13px;

  span {
    color: var(--zs-muted);
  }
  .lvl {
    color: var(--zs-danger);
    font-weight: 600;
  }
}
.snippet-md {
  font-size: 13px;
  color: var(--zs-muted);

  /* 窄栏内表格横滑，禁止逐字竖折 */
  :deep(.md-table) {
    margin: 0.5em 0;
  }
  :deep(table) {
    font-size: 12px;
  }
  :deep(th),
  :deep(td) {
    padding: 7px 10px;
    white-space: nowrap;
  }
}
</style>
