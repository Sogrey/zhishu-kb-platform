<template>
  <header class="hero">
    <p class="eyebrow">企业智能知识库</p>
    <h1>知枢</h1>
    <p class="lead">把制度问清楚。回答可溯源，知识可治理。</p>
    <div class="samples">
      <button
        v-for="q in WELCOME_SAMPLES"
        :key="q"
        class="sample"
        type="button"
        @click="$emit('ask', q)"
      >
        {{ q }}
      </button>
    </div>
  </header>
</template>

<script setup lang="ts">
/**
 * 空会话欢迎区：品牌 + 两列推荐问题。
 * 点击问题由父组件填入输入框并发起 send。
 */
import { WELCOME_SAMPLES } from "./samples";

defineEmits<{ ask: [q: string] }>();
</script>

<style lang="less" scoped>
.hero {
  margin: auto;
  padding: 16px 8px 20px;
  max-width: 44em;
  width: 100%;
  text-align: left;
  animation: zs-rise 0.7s ease both;
}
.eyebrow {
  margin: 0 0 10px;
  color: var(--zs-muted);
  letter-spacing: 0.18em;
  font-size: 12px;
}
.hero h1 {
  margin: 0;
  font-family: var(--zs-font-display);
  font-size: clamp(40px, 6vw, 60px);
  line-height: 1;
  letter-spacing: 0.08em;
  color: var(--zs-accent-deep);
  font-weight: 700;
}
.lead {
  margin: 14px 0 0;
  max-width: 28em;
  color: var(--zs-muted);
  font-size: 15px;
  line-height: 1.6;
}
.samples {
  margin-top: 20px;
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;

  @media (max-width: 720px) {
    grid-template-columns: 1fr;
  }
}
.sample {
  border: 1px solid var(--zs-line);
  background: rgba(255, 255, 255, 0.55);
  color: var(--zs-accent-deep);
  border-radius: 12px;
  padding: 12px 14px;
  cursor: pointer;
  font-size: 13px;
  text-align: left;
  line-height: 1.4;
  transition: background 0.15s ease, border-color 0.15s ease, transform 0.15s ease;

  &:hover {
    background: #fff;
    border-color: var(--zs-accent);
    transform: translateY(-1px);
    box-shadow: var(--zs-shadow);
  }
}
</style>
