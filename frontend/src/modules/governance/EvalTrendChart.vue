<template>
  <div class="chart" v-if="points.length">
    <svg :viewBox="`0 0 ${W} ${H}`" role="img" :aria-label="label">
      <defs>
        <linearGradient :id="gid" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stop-color="var(--zs-accent)" stop-opacity="0.28" />
          <stop offset="100%" stop-color="var(--zs-accent)" stop-opacity="0" />
        </linearGradient>
      </defs>
      <!-- grid -->
      <line
        v-for="g in gridYs"
        :key="g"
        :x1="PAD.l"
        :x2="W - PAD.r"
        :y1="g"
        :y2="g"
        class="grid"
      />
      <path :d="areaD" class="area" :fill="`url(#${gid})`" />
      <path :d="lineD" class="line" />
      <circle
        v-for="(p, i) in points"
        :key="i"
        :cx="p.x"
        :cy="p.y"
        r="3.5"
        class="dot"
      >
        <title>{{ p.label }}: {{ (p.v * 100).toFixed(0) }}%</title>
      </circle>
      <text
        v-for="(t, i) in yTicks"
        :key="'y' + i"
        :x="PAD.l - 6"
        :y="t.y + 4"
        class="tick"
        text-anchor="end"
      >
        {{ t.label }}
      </text>
    </svg>
    <div class="xlabels">
      <span v-for="(p, i) in edgeLabels" :key="i">{{ p }}</span>
    </div>
  </div>
  <p v-else class="empty">暂无足够跑次画趋势（至少 1 次 done）。</p>
</template>

<script setup lang="ts">
import { computed } from "vue";

const props = defineProps<{
  values: number[];
  labels?: string[];
  label?: string;
}>();

const W = 560;
const H = 160;
const PAD = { l: 36, r: 12, t: 12, b: 18 };
const gid = `zg-${Math.random().toString(36).slice(2, 8)}`;

const points = computed(() => {
  const vals = props.values.filter((v) => typeof v === "number");
  if (!vals.length) return [] as { x: number; y: number; v: number; label: string }[];
  const n = vals.length;
  const innerW = W - PAD.l - PAD.r;
  const innerH = H - PAD.t - PAD.b;
  return vals.map((v, i) => {
    const x = PAD.l + (n === 1 ? innerW / 2 : (i / (n - 1)) * innerW);
    const clamped = Math.min(1, Math.max(0, v));
    const y = PAD.t + (1 - clamped) * innerH;
    return {
      x,
      y,
      v: clamped,
      label: props.labels?.[i] || `#${i + 1}`,
    };
  });
});

const lineD = computed(() => {
  if (!points.value.length) return "";
  return points.value
    .map((p, i) => `${i === 0 ? "M" : "L"}${p.x.toFixed(1)} ${p.y.toFixed(1)}`)
    .join(" ");
});

const areaD = computed(() => {
  if (!points.value.length) return "";
  const base = H - PAD.b;
  const first = points.value[0];
  const last = points.value[points.value.length - 1];
  return `${lineD.value} L${last.x.toFixed(1)} ${base} L${first.x.toFixed(1)} ${base} Z`;
});

const gridYs = computed(() => {
  const innerH = H - PAD.t - PAD.b;
  return [0, 0.25, 0.5, 0.75, 1].map((r) => PAD.t + (1 - r) * innerH);
});

const yTicks = computed(() =>
  [0, 0.5, 1].map((r) => ({
    y: PAD.t + (1 - r) * (H - PAD.t - PAD.b),
    label: `${r * 100}%`,
  })),
);

const edgeLabels = computed(() => {
  const labs = props.labels || [];
  if (!labs.length) return [] as string[];
  if (labs.length === 1) return [labs[0]];
  return [labs[0], labs[labs.length - 1]];
});
</script>

<style lang="less" scoped>
.chart {
  width: 100%;
}
svg {
  width: 100%;
  height: auto;
  display: block;
}
.grid {
  stroke: var(--zs-line);
  stroke-width: 1;
}
.line {
  fill: none;
  stroke: var(--zs-accent);
  stroke-width: 2.2;
  stroke-linejoin: round;
  stroke-linecap: round;
}
.dot {
  fill: #fff;
  stroke: var(--zs-accent-deep);
  stroke-width: 1.6;
}
.tick {
  font-size: 10px;
  fill: var(--zs-muted);
}
.xlabels {
  display: flex;
  justify-content: space-between;
  margin-top: 2px;
  font-size: 11px;
  color: var(--zs-muted);
  padding: 0 8px 0 36px;
}
.empty {
  margin: 0;
  color: var(--zs-muted);
  font-size: 13px;
}
</style>
