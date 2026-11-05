<template>
  <aside class="history">
    <button type="button" class="new" title="新对话" @click="$emit('newChat')">
      <span class="new-plus">+</span>
      <span>新对话</span>
    </button>
    <div class="hist-label">历史</div>
    <div class="hist-list">
      <button
        v-for="c in conversations"
        :key="c.id"
        type="button"
        class="hist-item"
        :class="{ active: activeId === c.id }"
        :title="c.title || ''"
        @click="$emit('open', c.id)"
      >
        {{ c.title }}
      </button>
      <p v-if="!conversations.length" class="hist-empty">暂无会话</p>
    </div>
  </aside>
</template>

<script setup lang="ts">
/**
 * 左侧历史会话栏：新对话 + 标题列表。
 */
import type { ConversationItem } from "@/api/types";

defineProps<{
  conversations: ConversationItem[];
  activeId: number | null;
}>();

defineEmits<{
  newChat: [];
  open: [id: number];
}>();
</script>

<style lang="less" scoped>
.history {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 8px 12px 16px 0;
  border-right: 1px solid var(--zs-line);
  min-width: 0;
  min-height: 0;
  overflow: hidden;
  box-sizing: border-box;
}
.new {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  width: 100%;
  border: 1px dashed rgba(11, 92, 69, 0.35);
  background: transparent;
  border-radius: 10px;
  padding: 9px 12px;
  cursor: pointer;
  color: var(--zs-accent-deep);
  font-size: 13px;
  font-weight: 600;
  transition: background 0.15s ease, border-color 0.15s ease;

  &:hover {
    background: var(--zs-accent-soft);
    border-style: solid;
    border-color: var(--zs-accent);
  }
}
.new-plus {
  font-size: 16px;
  line-height: 1;
  font-weight: 500;
}
.hist-label {
  font-size: 11px;
  letter-spacing: 0.14em;
  color: var(--zs-muted);
  padding: 4px 8px 0;
  flex-shrink: 0;
}
.hist-list {
  flex: 1;
  min-height: 0;
  overflow: auto;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.hist-item {
  text-align: left;
  border: 0;
  background: transparent;
  color: var(--zs-muted);
  padding: 9px 10px;
  border-radius: 10px;
  cursor: pointer;
  font-size: 13px;
  line-height: 1.4;
  overflow: hidden;
  display: -webkit-box;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
  white-space: normal;
  word-break: break-word;

  &:hover {
    background: rgba(255, 255, 255, 0.55);
    color: var(--zs-ink);
  }

  &.active {
    background: var(--zs-accent-soft);
    color: var(--zs-accent-deep);
    font-weight: 600;
  }
}
.hist-empty {
  margin: 8px 0 0;
  color: var(--zs-muted);
  font-size: 12px;
  padding: 4px 6px;
  opacity: 0.75;
}

@media (max-width: 720px) {
  .history {
    border-right: 0;
    border-bottom: 1px solid var(--zs-line);
    max-height: 120px;
    padding: 0 0 10px;
  }
}
</style>
