<template>
  <!-- C-010：L3+ 内容页动态水印；pointer-events:none 不影响点击 -->
  <div v-if="active" class="wm" aria-hidden="true">
    <div class="wm-grid">
      <span v-for="n in tileCount" :key="n" class="wm-cell">{{ label }}</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from "vue";
import { userRef } from "@/shared/auth";

const props = withDefaults(
  defineProps<{
    /** 是否显示（由调用方按密级 L3+ 判定） */
    active?: boolean;
    /** 平铺数量 */
    tiles?: number;
  }>(),
  { active: false, tiles: 28 },
);

const now = ref(new Date());
let timer: number | null = null;

onMounted(() => {
  timer = window.setInterval(() => {
    now.value = new Date();
  }, 30_000);
});

onUnmounted(() => {
  if (timer != null) window.clearInterval(timer);
});

const tileCount = computed(() => Math.max(8, props.tiles));

const label = computed(() => {
  const u = userRef.value;
  const who = u?.display_name || u?.username || "未登录";
  const id = u?.id != null ? `#${u.id}` : "";
  const ts = formatTs(now.value);
  return `${who}${id} · ${ts} · 知枢保密`;
});

function formatTs(d: Date) {
  const p = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`;
}
</script>

<style lang="less" scoped>
.wm {
  position: absolute;
  inset: 0;
  z-index: 30;
  overflow: hidden;
  pointer-events: none;
  user-select: none;
}
.wm-grid {
  position: absolute;
  inset: -20%;
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 48px 28px;
  transform: rotate(-22deg);
  opacity: 0.14;
}
.wm-cell {
  font-size: 13px;
  letter-spacing: 0.04em;
  color: var(--zs-ink);
  white-space: nowrap;
  text-align: center;
  line-height: 1.4;
}
</style>
