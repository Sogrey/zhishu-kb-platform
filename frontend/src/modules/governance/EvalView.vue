<template>
  <div class="page">
    <nav class="crumb">
      <RouterLink to="/governance">治理</RouterLink>
      <span>/</span>
      <em>评测</em>
    </nav>
    <header class="hero">
      <h1>评测</h1>
      <p>
        金标 50 条；裁判默认启发式。设置页切到 DeepSeek/Ollama/llama.cpp 后（或
        <code>EVAL_LLM_JUDGE=1</code>）走 LLM 裁判。上传样例后运行；看板看趋势。
      </p>
    </header>

    <section class="board">
      <div class="board-head">
        <h2>看板趋势</h2>
        <button type="button" class="ghost" @click="refreshBoard">刷新</button>
      </div>
      <p v-if="board?.latest?.metrics?.engine" class="engine">
        裁判引擎：<strong>{{ board.latest.metrics.engine }}</strong>
        <span v-if="board.latest.metrics.engine_counts">
          · {{ formatEngineCounts(board.latest.metrics.engine_counts) }}
        </span>
      </p>
      <div class="kpis" v-if="board?.latest">
        <div v-for="k in kpiKeys" :key="k" class="kpi">
          <span>{{ k }}</span>
          <strong>{{ pct(board.latest.metrics?.[k]) }}</strong>
          <em v-if="board.delta?.[k] != null" :data-up="(board.delta[k] || 0) >= 0">
            {{ deltaText(board.delta[k]) }}
          </em>
        </div>
      </div>
      <p v-else class="empty">尚无完成跑次。先运行评测或夜间回归。</p>
      <div class="charts" v-if="passSeries.length">
        <div class="chart-card">
          <h3>pass_rate</h3>
          <EvalTrendChart :values="passSeries" :labels="runLabels" label="pass_rate" />
        </div>
        <div class="chart-card">
          <h3>citation_hit</h3>
          <EvalTrendChart :values="citeSeries" :labels="runLabels" label="citation_hit" />
        </div>
      </div>
      <div class="run-table" v-if="board?.series?.length">
        <button
          v-for="r in [...board.series].reverse()"
          :key="r.id"
          type="button"
          class="run-row"
          @click="openRun(r.id)"
        >
          <strong>#{{ r.id }}</strong>
          <span>{{ r.finished_at ? new Date(r.finished_at).toLocaleString() : "—" }}</span>
          <span>通过 {{ r.passed_count }}/{{ r.case_count }}</span>
          <span>pass {{ pct(r.metrics?.pass_rate) }}</span>
        </button>
      </div>
    </section>

    <section class="sched" v-if="sched">
      <h2>夜间回归 / 退休调度</h2>
      <p class="sched-lead">
        stub 进程内线程兜底；正式环境用 Celery beat（01:30 退休 / {{ sched.config?.eval_nightly_hour ?? 2 }}:00 评测）。
        当前：{{ sched.enabled ? "运行中" : "关闭" }} · {{ sched.mode }}
        <template v-if="sched.config?.stub_fast"> · stub 加速</template>
      </p>
      <div class="sched-actions">
        <button type="button" :disabled="busyNightly" @click="onNightly">
          {{ busyNightly ? "夜间评测中…" : "立即跑夜间评测" }}
        </button>
        <button type="button" class="ghost" :disabled="busyRetire" @click="onRetire">
          {{ busyRetire ? "扫描中…" : "立即退休扫描" }}
        </button>
        <button type="button" class="ghost" @click="refreshSched">刷新状态</button>
      </div>
      <pre class="sched-json">{{ schedSummary }}</pre>
    </section>

    <section class="sets">
      <article v-for="s in sets" :key="s.id" class="set-card">
        <div>
          <h2>{{ s.name }} <small>{{ s.version }}</small></h2>
          <p>{{ s.description || "—" }}</p>
          <p class="meta">{{ s.case_count }} 条用例</p>
        </div>
        <div class="actions">
          <button type="button" :disabled="running === s.id" @click="onRun(s.id)">
            {{ running === s.id ? "运行中…" : "运行评测" }}
          </button>
          <button type="button" class="ghost" @click="openCases(s.id)">查看用例</button>
        </div>
        <div v-if="s.last_run" class="last">
          最近 #<strong>{{ s.last_run.id }}</strong>
          · {{ s.last_run.status }}
          · 通过 {{ s.last_run.passed_count }}/{{ s.last_run.case_count }}
          · pass_rate {{ pct(s.last_run.metrics?.pass_rate) }}
        </div>
      </article>
      <p v-if="!sets.length" class="empty">暂无评测集。重启 API 以导入金标 v0。</p>
    </section>

    <section v-if="detail" class="detail">
      <header>
        <h2>运行 #{{ detail.id }}</h2>
        <p>
          {{ detail.status }} · 通过 {{ detail.passed_count }}/{{ detail.case_count }} ·
          {{ detail.finished_at ? new Date(detail.finished_at).toLocaleString() : "进行中" }}
        </p>
      </header>
      <div class="metrics" v-if="detail.metrics">
        <div v-for="(v, k) in metricCards" :key="k" class="m">
          <span>{{ k }}</span>
          <strong>{{ pct(v) }}</strong>
        </div>
      </div>
      <div class="items">
        <article v-for="it in detail.items || []" :key="it.id" class="item" :class="{ fail: !it.passed }">
          <div class="q">
            <span class="badge" :data-ok="it.passed">{{ it.passed ? "过" : "未过" }}</span>
            {{ it.question }}
          </div>
          <div class="scores">
            <em v-for="(sv, sk) in it.scores" :key="sk">{{ sk }} {{ pct(sv) }}</em>
          </div>
          <div class="hits">命中：{{ (it.hit_doc_titles || []).join(" · ") || "—" }}</div>
        </article>
      </div>
    </section>

    <section v-if="cases" class="cases">
      <h2>用例 · {{ cases.set.name }}</h2>
      <ol>
        <li v-for="c in cases.items" :key="c.id">
          <strong>{{ c.question }}</strong>
          <span>{{ (c.expected_doc_titles || []).join(", ") }}</span>
        </li>
      </ol>
    </section>
  </div>
</template>

<script setup lang="ts">
/**
 * 评测台（M3-2）：看板趋势、金标集、Runner、夜间调度。
 */
import { computed, onMounted, ref } from "vue";
import { message } from "ant-design-vue";
import {
  getEvalDashboard,
  getEvalRun,
  getEvalScheduler,
  listEvalCases,
  listEvalSets,
  runEvalSet,
  triggerNightlyEvalNow,
  triggerRetireScanNow,
  type EvalDashboard,
  type EvalRunDetail,
  type EvalSchedulerStatus,
  type EvalSetItem,
} from "@/api/client";
import EvalTrendChart from "./EvalTrendChart.vue";

const sets = ref<EvalSetItem[]>([]);
const running = ref<number | null>(null);
const detail = ref<EvalRunDetail | null>(null);
const board = ref<EvalDashboard | null>(null);
const sched = ref<EvalSchedulerStatus | null>(null);
const busyNightly = ref(false);
const busyRetire = ref(false);
const kpiKeys = [
  "pass_rate",
  "citation_hit",
  "context_recall",
  "answer_relevancy",
  "faithfulness",
] as const;
const cases = ref<{ set: { name: string }; items: { id: number; question: string; expected_doc_titles?: string[] }[] } | null>(
  null,
);

const schedSummary = computed(() => {
  if (!sched.value) return "";
  const j = sched.value.jobs || {};
  return JSON.stringify(
    {
      last_eval_date: sched.value.last_eval_date,
      last_retire_date: sched.value.last_retire_date,
      retire: j.retire,
      nightly_eval: j.nightly_eval,
    },
    null,
    2,
  );
});

const metricCards = computed(() => {
  const m = detail.value?.metrics || {};
  const out: Record<string, number> = {};
  for (const k of kpiKeys) {
    if (typeof m[k] === "number") out[k] = m[k] as number;
  }
  return out;
});

const passSeries = computed(() =>
  (board.value?.series || [])
    .map((r) => r.metrics?.pass_rate)
    .filter((v): v is number => typeof v === "number"),
);

const citeSeries = computed(() =>
  (board.value?.series || [])
    .map((r) => r.metrics?.citation_hit)
    .filter((v): v is number => typeof v === "number"),
);

const runLabels = computed(() =>
  (board.value?.series || []).map((r) => `#${r.id}`),
);

function pct(v: unknown) {
  if (typeof v !== "number") return "—";
  return `${(v * 100).toFixed(0)}%`;
}

function deltaText(v: number | null | undefined) {
  if (v == null || Number.isNaN(v)) return "";
  const sign = v >= 0 ? "+" : "";
  return `${sign}${(v * 100).toFixed(0)}pt`;
}

function formatEngineCounts(counts: unknown) {
  if (!counts || typeof counts !== "object") return "";
  return Object.entries(counts as Record<string, number>)
    .map(([k, v]) => `${k}:${v}`)
    .join(" ");
}

async function refresh() {
  sets.value = await listEvalSets();
}

async function refreshBoard() {
  try {
    board.value = await getEvalDashboard(30);
  } catch {
    board.value = null;
  }
}

async function openRun(id: number) {
  try {
    detail.value = await getEvalRun(id);
  } catch (e: any) {
    message.error(e?.response?.data?.detail || "加载跑次失败");
  }
}

async function refreshSched() {
  try {
    sched.value = await getEvalScheduler();
  } catch {
    sched.value = null;
  }
}

async function onNightly() {
  busyNightly.value = true;
  try {
    const r = await triggerNightlyEvalNow(10);
    message.success(`夜间评测完成：${(r.runs || []).length} 个工作区`);
    await refresh();
    await refreshSched();
    await refreshBoard();
    const last = sets.value[0]?.last_run;
    if (last?.id) detail.value = await getEvalRun(last.id);
  } catch (e: any) {
    message.error(e?.response?.data?.detail || e?.message || "夜间评测失败");
  } finally {
    busyNightly.value = false;
  }
}

async function onRetire() {
  busyRetire.value = true;
  try {
    const r = await triggerRetireScanNow();
    message.success(`退休扫描：${r.retired ?? 0} 份`);
    await refreshSched();
  } catch (e: any) {
    message.error(e?.response?.data?.detail || e?.message || "扫描失败");
  } finally {
    busyRetire.value = false;
  }
}

async function onRun(setId: number) {
  running.value = setId;
  cases.value = null;
  try {
    detail.value = await runEvalSet(setId);
    message.success(
      `评测完成：通过 ${detail.value.passed_count}/${detail.value.case_count}`,
    );
    await refresh();
    await refreshBoard();
  } catch (e: any) {
    message.error(e?.response?.data?.detail || e?.message || "评测失败");
  } finally {
    running.value = null;
  }
}

async function openCases(setId: number) {
  try {
    cases.value = await listEvalCases(setId);
    const last = sets.value.find((s) => s.id === setId)?.last_run;
    if (last?.id) detail.value = await getEvalRun(last.id);
  } catch (e: any) {
    message.error(e?.response?.data?.detail || "加载用例失败");
  }
}

onMounted(() => {
  void refresh().catch((e) => message.error(e?.message || "加载失败"));
  void refreshSched();
  void refreshBoard();
});
</script>

<style lang="less" scoped>
.page {
  animation: zs-rise 0.45s ease both;
  padding: 0 0 48px;
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
.hero {
  h1 {
    margin: 0;
    font-family: var(--zs-font-display);
    font-size: clamp(32px, 5vw, 46px);
    color: var(--zs-accent-deep);
    letter-spacing: 0.06em;
  }
  p {
    margin: 10px 0 0;
    color: var(--zs-muted);
    max-width: 48rem;
    line-height: 1.55;
  }
}
.board {
  margin-top: 20px;
  padding: 14px 16px 16px;
  border: 1px solid var(--zs-line);
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.55);
}
.board-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;

  h2 {
    margin: 0;
    font-size: 16px;
    font-family: var(--zs-font-display);
  }
  .ghost {
    border: 1px solid var(--zs-line);
    border-radius: 999px;
    padding: 6px 12px;
    background: rgba(255, 255, 255, 0.75);
    color: var(--zs-accent-deep);
    cursor: pointer;
    font: inherit;
    font-size: 12px;
  }
}
.engine {
  margin: 10px 0 0;
  font-size: 12px;
  color: var(--zs-muted);

  strong {
    color: var(--zs-accent-deep);
  }
}
.kpis {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 10px;
  margin-top: 12px;
}
.kpi {
  border: 1px solid var(--zs-line);
  border-radius: 12px;
  padding: 10px 12px;
  background: rgba(255, 255, 255, 0.65);

  span {
    display: block;
    font-size: 11px;
    color: var(--zs-muted);
  }
  strong {
    display: block;
    margin-top: 4px;
    font-size: 20px;
    color: var(--zs-accent-deep);
    font-family: var(--zs-font-display);
  }
  em {
    font-style: normal;
    font-size: 11px;
    color: var(--zs-danger);
    &[data-up="true"] {
      color: var(--zs-accent);
    }
  }
}
.charts {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
  margin-top: 14px;
}
.chart-card {
  border: 1px solid var(--zs-line);
  border-radius: 12px;
  padding: 10px 12px 8px;
  background: rgba(255, 255, 255, 0.5);

  h3 {
    margin: 0 0 4px;
    font-size: 12px;
    color: var(--zs-muted);
    font-weight: 600;
  }
}
.run-table {
  margin-top: 12px;
  display: flex;
  flex-direction: column;
  gap: 4px;
  max-height: 220px;
  overflow: auto;
}
.run-row {
  display: grid;
  grid-template-columns: 64px 1fr 110px 90px;
  gap: 8px;
  text-align: left;
  border: 0;
  border-top: 1px solid var(--zs-line);
  background: transparent;
  padding: 8px 4px;
  cursor: pointer;
  font: inherit;
  font-size: 12px;
  color: var(--zs-muted);

  strong {
    color: var(--zs-accent-deep);
  }
  &:hover {
    background: rgba(212, 235, 225, 0.35);
  }
}
.sched {
  margin-top: 20px;
  padding: 14px 16px;
  border: 1px solid var(--zs-line);
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.55);

  h2 {
    margin: 0;
    font-size: 16px;
    font-family: var(--zs-font-display);
  }
}
.sched-lead {
  margin: 8px 0 0;
  font-size: 13px;
  color: var(--zs-muted);
  line-height: 1.5;
}
.sched-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 12px;

  button {
    border: 0;
    border-radius: 999px;
    padding: 8px 14px;
    background: var(--zs-accent);
    color: #fff;
    cursor: pointer;
    font: inherit;
    font-size: 13px;
  }
  .ghost {
    background: rgba(255, 255, 255, 0.75);
    color: var(--zs-accent-deep);
    border: 1px solid var(--zs-line);
  }
  button:disabled {
    opacity: 0.65;
    cursor: wait;
  }
}
.sched-json {
  margin: 12px 0 0;
  padding: 10px 12px;
  border-radius: 10px;
  background: rgba(20, 36, 28, 0.04);
  font-size: 11px;
  overflow: auto;
  max-height: 160px;
  color: var(--zs-muted);
}
.sets {
  margin-top: 22px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.set-card {
  border: 1px solid var(--zs-line);
  border-radius: 14px;
  padding: 16px 18px;
  background: rgba(255, 255, 255, 0.6);

  h2 {
    margin: 0;
    font-size: 18px;
    font-family: var(--zs-font-display);

    small {
      margin-left: 8px;
      font-size: 12px;
      color: var(--zs-muted);
      font-family: var(--zs-font-body);
    }
  }
  p {
    margin: 6px 0 0;
    color: var(--zs-muted);
    font-size: 13px;
  }
  .meta {
    margin-top: 4px;
    color: var(--zs-accent-deep);
    font-weight: 600;
  }
}
.actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 12px;

  button {
    border: 0;
    border-radius: 999px;
    padding: 8px 14px;
    background: var(--zs-accent);
    color: #fff;
    cursor: pointer;
    font: inherit;
    font-size: 13px;
  }
  .ghost {
    background: rgba(255, 255, 255, 0.75);
    color: var(--zs-accent-deep);
    border: 1px solid var(--zs-line);
  }
  button:disabled {
    opacity: 0.65;
    cursor: wait;
  }
}
.last {
  margin-top: 10px;
  font-size: 12px;
  color: var(--zs-muted);
}
.detail,
.cases {
  margin-top: 28px;
}
.detail h2,
.cases h2 {
  margin: 0 0 8px;
  font-family: var(--zs-font-display);
  font-size: 20px;
}
.metrics {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 10px;
  margin: 12px 0 16px;
}
.m {
  border: 1px solid var(--zs-line);
  border-radius: 12px;
  padding: 12px;
  background: rgba(255, 255, 255, 0.55);

  span {
    display: block;
    font-size: 11px;
    color: var(--zs-muted);
  }
  strong {
    display: block;
    margin-top: 6px;
    font-size: 20px;
    color: var(--zs-accent-deep);
    font-family: var(--zs-font-display);
  }
}
.item {
  padding: 12px 0;
  border-top: 1px solid var(--zs-line);
  font-size: 13px;

  &.fail .badge {
    background: rgba(155, 44, 44, 0.12);
    color: var(--zs-danger);
  }
}
.badge {
  display: inline-block;
  min-width: 2em;
  text-align: center;
  border-radius: 6px;
  padding: 2px 6px;
  margin-right: 8px;
  font-size: 11px;
  font-weight: 700;
  background: var(--zs-accent-soft);
  color: var(--zs-accent-deep);
}
.scores {
  margin-top: 6px;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;

  em {
    font-style: normal;
    font-size: 11px;
    color: var(--zs-muted);
    border: 1px solid var(--zs-line);
    border-radius: 999px;
    padding: 2px 8px;
  }
}
.hits {
  margin-top: 4px;
  color: var(--zs-muted);
  font-size: 12px;
}
.cases ol {
  margin: 0;
  padding-left: 1.2em;
}
.cases li {
  margin: 8px 0;
  font-size: 13px;

  span {
    display: block;
    color: var(--zs-muted);
    font-size: 12px;
  }
}
.empty {
  color: var(--zs-muted);
}
@media (max-width: 900px) {
  .metrics,
  .kpis {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .charts {
    grid-template-columns: 1fr;
  }
  .run-row {
    grid-template-columns: 1fr 1fr;
  }
}
</style>
