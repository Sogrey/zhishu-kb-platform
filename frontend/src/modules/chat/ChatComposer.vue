<template>
  <footer class="dock">
    <div v-if="retrieveMeta" class="retrieve-bar">
      检索：向量 {{ retrieveMeta.vector_hits }} · 关键词 {{ retrieveMeta.keyword_hits }} ·
      RRF 融合 {{ retrieveMeta.fused }} · 注入 {{ retrieveMeta.injected }}
    </div>
    <form class="composer" @submit.prevent="$emit('send')">
      <textarea
        :value="modelValue"
        rows="2"
        :placeholder="placeholder"
        @input="$emit('update:modelValue', ($event.target as HTMLTextAreaElement).value)"
        @keydown.enter.exact.prevent="$emit('send')"
      />
      <button class="send" type="submit" :disabled="loading || !modelValue.trim()">
        {{ loading ? "…" : "发送" }}
      </button>
    </form>
  </footer>
</template>

<script setup lang="ts">
/**
 * 底部输入坞：固定贴底；Enter 发送、Shift+Enter 换行（浏览器默认）。
 * placeholder 须含真实换行符（见 samples.ts）。
 */
import type { RetrieveMeta } from "@/api/types";
import { INPUT_PLACEHOLDER } from "./samples";

withDefaults(
  defineProps<{
    modelValue: string;
    loading?: boolean;
    retrieveMeta?: RetrieveMeta | null;
    placeholder?: string;
  }>(),
  {
    loading: false,
    retrieveMeta: null,
    placeholder: INPUT_PLACEHOLDER,
  },
);

defineEmits<{
  "update:modelValue": [v: string];
  send: [];
}>();
</script>

<style lang="less" scoped>
.dock {
  flex-shrink: 0;
  padding: 6px 0 10px;
  background: linear-gradient(180deg, transparent, rgba(238, 243, 239, 0.92) 28%);
}
.retrieve-bar {
  margin-bottom: 8px;
  font-size: 12px;
  color: var(--zs-muted);
}
.composer {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 10px;
  align-items: end;
  padding: 10px 12px;
  border: 1px solid var(--zs-line);
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.82);
  backdrop-filter: blur(12px);
  box-shadow: 0 10px 28px rgba(20, 36, 28, 0.06);

  textarea {
    width: 100%;
    border: 0;
    resize: none;
    outline: none;
    background: transparent;
    font: inherit;
    color: var(--zs-ink);
    line-height: 1.55;
    padding: 6px 4px;
    max-height: 140px;
  }
}
.send {
  border: 0;
  border-radius: 11px;
  padding: 11px 16px;
  background: var(--zs-accent);
  color: #fff;
  font-weight: 600;
  cursor: pointer;

  &:disabled {
    opacity: 0.45;
    cursor: not-allowed;
  }
}
</style>
