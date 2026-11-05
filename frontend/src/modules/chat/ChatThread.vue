<template>
  <div class="thread">
    <article v-for="(m, i) in messages" :key="i" class="turn" :class="m.role">
      <div class="role">{{ m.role === "user" ? "你" : "知枢" }}</div>
      <div class="body">
        <template v-if="m.role === 'assistant'">
          <MarkdownBody v-if="m.content" :source="m.content" />
          <div
            v-else-if="loading && i === messages.length - 1"
            class="typing"
            aria-label="生成中"
          >
            <span /><span /><span />
          </div>

          <div
            v-if="m.groups?.libraries?.length || m.citations?.length || (showTrace && m.trace_id)"
            class="cite-blocks"
          >
            <div v-if="m.groups?.libraries?.length" class="cite-block">
              <h4>引用库</h4>
              <div class="cites">
                <span
                  v-for="lib in m.groups.libraries"
                  :key="lib.doc_id"
                  class="cite-chip static"
                >
                  {{ lib.title }}
                  <em>{{ lib.hit_chunks }} 块</em>
                </span>
              </div>
            </div>
            <div v-if="m.citations?.length" class="cite-block">
              <h4>参考来源</h4>
              <div class="cites">
                <button
                  v-for="(c, j) in m.citations"
                  :key="j"
                  type="button"
                  class="cite-chip"
                  @click="$emit('cite', c)"
                >
                  <span class="idx">{{ j + 1 }}</span>
                  {{ c.title }}{{ c.page ? ` · p.${c.page}` : "" }}
                </button>
              </div>
            </div>
            <div v-if="showTrace && m.trace_id" class="cite-block">
              <h4>可观测</h4>
              <div class="cites">
                <button
                  type="button"
                  class="cite-chip trace"
                  @click="$emit('trace', m.trace_id!)"
                >
                  Trace
                </button>
              </div>
            </div>
          </div>
        </template>
        <p v-else class="user-text">{{ m.content }}</p>
      </div>
    </article>
  </div>
</template>

<script setup lang="ts">
/**
 * 消息线程：用户气泡 + 助手 Markdown + 引用芯片。
 * 点击参考来源向上抛 cite，由父组件驱动右侧原文轨。
 */
import MarkdownBody from "@/shared/MarkdownBody.vue";
import type { Citation } from "@/api/types";
import type { ChatMsg } from "./types";

withDefaults(
  defineProps<{
    messages: ChatMsg[];
    loading: boolean;
    /** 管理员等角色可见 Trace 入口（C-108） */
    showTrace?: boolean;
  }>(),
  { showTrace: false },
);

defineEmits<{ cite: [c: Citation]; trace: [id: string] }>();
</script>

<style lang="less" scoped>
.thread {
  padding: 12px 4px 20px;
}
.turn {
  display: grid;
  grid-template-columns: 40px minmax(0, 1fr);
  gap: 10px;
  margin-bottom: 20px;
  animation: zs-rise 0.45s ease both;

  &.user .role {
    color: var(--zs-accent);
    font-weight: 600;
  }

  &.assistant .body {
    max-width: min(56em, 100%);
  }
}
.role {
  font-size: 12px;
  color: var(--zs-muted);
  padding-top: 8px;
}
.user-text {
  margin: 0;
  display: inline-block;
  padding: 12px 16px;
  border-radius: 16px 16px 4px 16px;
  background: linear-gradient(145deg, var(--zs-accent), var(--zs-accent-deep));
  color: #f7fffb;
  line-height: 1.6;
  max-width: 42em;
}
.typing {
  display: inline-flex;
  gap: 6px;
  padding: 14px 4px;

  span {
    width: 7px;
    height: 7px;
    border-radius: 50%;
    background: var(--zs-accent);
    animation: zs-pulse-dot 1.1s ease infinite;

    &:nth-child(2) {
      animation-delay: 0.15s;
    }
    &:nth-child(3) {
      animation-delay: 0.3s;
    }
  }
}
.cite-blocks {
  margin-top: 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.cite-block h4 {
  margin: 0 0 8px;
  font-size: 12px;
  letter-spacing: 0.08em;
  color: var(--zs-muted);
  font-weight: 600;
}
.cites {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.cite-chip {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  border: 1px solid var(--zs-line);
  background: rgba(255, 255, 255, 0.65);
  color: var(--zs-ink);
  border-radius: 999px;
  padding: 6px 12px 6px 8px;
  font-size: 12px;
  cursor: pointer;

  &.static {
    cursor: default;
    padding-left: 12px;

    em {
      font-style: normal;
      color: var(--zs-muted);
      margin-left: 4px;
    }
  }

  &:not(.static):hover {
    border-color: var(--zs-accent);
    background: #fff;
  }
}
.idx {
  width: 18px;
  height: 18px;
  border-radius: 50%;
  display: grid;
  place-items: center;
  background: var(--zs-accent-soft);
  color: var(--zs-accent-deep);
  font-size: 11px;
  font-weight: 700;
}
.cite-chip.trace {
  border-color: var(--zs-accent);
  color: var(--zs-accent-deep);
  font-weight: 600;
}
</style>
