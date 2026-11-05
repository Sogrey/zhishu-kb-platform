<template>
  <div class="md" v-html="html" />
</template>

<script setup lang="ts">
import { computed } from "vue";
import { renderMarkdown } from "./markdown";

const props = defineProps<{ source: string }>();
const html = computed(() => renderMarkdown(props.source));
</script>

<style lang="less" scoped>
.md :deep(p) {
  margin: 0 0 0.75em;
  line-height: 1.7;
}
.md :deep(p:last-child) {
  margin-bottom: 0;
}
.md :deep(h1),
.md :deep(h2),
.md :deep(h3) {
  font-family: var(--zs-font-display);
  font-weight: 600;
  line-height: 1.35;
  margin: 1em 0 0.45em;
  color: var(--zs-ink);
}
.md :deep(h1) {
  font-size: 1.35em;
}
.md :deep(h2) {
  font-size: 1.18em;
}
.md :deep(h3) {
  font-size: 1.05em;
}
.md :deep(ul),
.md :deep(ol) {
  list-style: none;
  margin: 0.4em 0 0.95em;
  padding: 0;
}
.md :deep(ol) {
  counter-reset: zs-ol;
}
.md :deep(ul > li),
.md :deep(ol > li) {
  position: relative;
  margin: 0.35em 0;
  padding: 0 0 0 1.15em;
  line-height: 1.7;
  color: var(--zs-ink);
  border: 0;
  background: transparent;
}
.md :deep(ul > li)::before {
  content: "";
  position: absolute;
  left: 0;
  top: 0.62em;
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--zs-accent);
}
.md :deep(ol > li) {
  padding-left: 1.6em;
}
.md :deep(ol > li)::before {
  counter-increment: zs-ol;
  content: counter(zs-ol) ".";
  position: absolute;
  left: 0;
  top: 0;
  width: auto;
  height: auto;
  border-radius: 0;
  font-size: 0.92em;
  font-weight: 650;
  color: var(--zs-accent-deep);
  background: transparent;
  display: inline;
}
.md :deep(li > p) {
  margin: 0;
}
.md :deep(strong) {
  color: var(--zs-ink);
  font-weight: 650;
}
/* 「要点 / 参考来源」这类加粗小节标题 */
.md :deep(p > strong:only-child) {
  display: inline-block;
  margin-top: 0.35em;
  font-size: 0.82em;
  letter-spacing: 0.1em;
  color: var(--zs-accent-deep);
  font-weight: 700;
}
.md :deep(code) {
  font-family: "IBM Plex Mono", "Cascadia Code", Consolas, monospace;
  font-size: 0.9em;
  padding: 0.1em 0.35em;
  background: var(--zs-accent-soft);
  border-radius: 4px;
}
.md :deep(blockquote) {
  margin: 0.6em 0;
  padding: 0.35em 0 0.35em 0.9em;
  border-left: 3px solid var(--zs-accent);
  color: var(--zs-muted);
}
.md :deep(a) {
  color: var(--zs-accent);
  text-decoration: underline;
  text-underline-offset: 3px;
}
.md :deep(hr) {
  border: none;
  border-top: 1px solid var(--zs-line);
  margin: 1em 0;
}

/* 对话 / 分块：Markdown 表格 */
.md :deep(.md-table) {
  margin: 0.85em 0 1.15em;
  overflow-x: auto;
  border: 1px solid var(--zs-line);
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.72);
  box-shadow: 0 1px 0 rgba(255, 255, 255, 0.8) inset;
  -webkit-overflow-scrolling: touch;
}
.md :deep(table) {
  width: max-content;
  min-width: 100%;
  border-collapse: collapse;
  font-size: 13px;
  line-height: 1.45;
}
.md :deep(thead th) {
  position: sticky;
  top: 0;
  background: linear-gradient(180deg, #e7f3ec, var(--zs-accent-soft));
  color: var(--zs-accent-deep);
  font-weight: 650;
  text-align: left;
  white-space: nowrap;
  padding: 10px 14px;
  border-bottom: 1px solid rgba(11, 92, 69, 0.22);
}
.md :deep(tbody td) {
  padding: 9px 14px;
  border-top: 1px solid var(--zs-line);
  color: var(--zs-ink);
  vertical-align: top;
  white-space: nowrap;
}
.md :deep(tbody tr:nth-child(even) td) {
  background: rgba(212, 235, 225, 0.28);
}
.md :deep(tbody tr:hover td) {
  background: rgba(11, 92, 69, 0.08);
}
.md :deep(th:first-child),
.md :deep(td:first-child) {
  font-weight: 600;
  white-space: nowrap;
}
</style>
