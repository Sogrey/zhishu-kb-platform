<template>
  <div class="page">
    <nav class="crumb">
      <RouterLink to="/governance">治理</RouterLink>
      <span>/</span>
      <em>Hit Test</em>
    </nav>
    <header class="hero">
      <h1>Hit Test</h1>
      <p>解释「为什么这样答」：分路召回、RRF 融合、注入块全文。问答也会自动落库快照。</p>
    </header>

    <form class="run" @submit.prevent="onRun">
      <input v-model="query" type="search" placeholder="输入问题，即时跑一次 Hit Test…" />
      <button type="submit" :disabled="running || !query.trim()">
        {{ running ? "检索中…" : "运行" }}
      </button>
    </form>

    <div class="layout">
      <aside class="list">
        <div class="list-head">
          <span>历史快照</span>
          <select v-model="sourceFilter" @change="refreshList">
            <option value="">全部来源</option>
            <option value="hit_test">手动</option>
            <option value="chat">问答</option>
          </select>
        </div>
        <button
          v-for="item in items"
          :key="item.id"
          type="button"
          class="item"
          :class="{ active: activeId === item.id }"
          @click="open(item.id)"
        >
          <strong>#{{ item.id }} · {{ item.source }}</strong>
          <span>{{ item.query }}</span>
          <em>
            向量 {{ item.vector_hits ?? "—" }} · 关键词 {{ item.keyword_hits ?? "—" }} ·
            注入 {{ item.injected ?? "—" }}
          </em>
        </button>
        <p v-if="!items.length" class="empty">暂无记录。上方运行一次，或去问答提问。</p>
      </aside>

      <section class="detail" v-if="detail">
        <DynamicWatermark :active="detailNeedsWm" />
        <header class="detail-head">
          <div>
            <h2>#{{ detail.id }} {{ detail.query }}</h2>
            <p>
              {{ detail.source }} · L{{ detail.clearance }} ·
              {{ detail.created_at ? new Date(detail.created_at).toLocaleString() : "—" }}
              <template v-if="detail.conversation_id">
                · 会话 #{{ detail.conversation_id }}
              </template>
              <span v-if="detailNeedsWm" class="wm-hint"> · L3+ 水印中</span>
            </p>
          </div>
        </header>

        <div class="meta-cards" v-if="detail.context_snapshot?.meta">
          <div class="card">
            <span>向量召回</span>
            <strong>{{ detail.context_snapshot.meta.vector_hits }}</strong>
          </div>
          <div class="card">
            <span>关键词召回</span>
            <strong>{{ detail.context_snapshot.meta.keyword_hits }}</strong>
          </div>
          <div class="card">
            <span>RRF 融合</span>
            <strong>{{ detail.context_snapshot.meta.fused }}</strong>
          </div>
          <div class="card">
            <span>最终注入</span>
            <strong>{{ detail.context_snapshot.meta.injected }}</strong>
          </div>
          <div class="card" v-if="detail.context_snapshot.meta.table_full_inject">
            <span>表格全表</span>
            <strong>{{ detail.context_snapshot.meta.table_hits || 1 }}</strong>
          </div>
        </div>

        <div class="debug" v-if="detail.context_snapshot?.debug">
          <h3>分路 chunk id</h3>
          <p>
            <b>vector</b>：{{ (detail.context_snapshot.debug.vector_ids || []).join(", ") || "—" }}
          </p>
          <p>
            <b>keyword</b>：{{ (detail.context_snapshot.debug.keyword_ids || []).join(", ") || "—" }}
          </p>
          <p>
            <b>fused</b>：{{ (detail.context_snapshot.debug.fused_ids || []).join(", ") || "—" }}
          </p>
        </div>

        <div class="injects">
          <h3>注入上下文（{{ (detail.context_snapshot.injected || []).length }}）</h3>
          <article
            v-for="block in detail.context_snapshot.injected || []"
            :key="block.chunk_id"
            class="inject"
          >
            <div class="inject-meta">
              <span class="rank">#{{ block.rank || "?" }}</span>
              <strong>{{ block.title }}</strong>
              <span>doc #{{ block.doc_id }} · chunk #{{ block.chunk_id }}</span>
              <span>score {{ block.score }}</span>
              <span v-if="block.page_no != null">p.{{ block.page_no }}</span>
              <span v-if="block.is_table || block.table_full_inject" class="tag">全表注入</span>
              <span
                v-for="ch in block.channels || []"
                :key="ch"
                class="ch"
              >{{ ch }}</span>
            </div>
            <pre>{{ block.content || block.preview }}</pre>
          </article>
          <p v-if="!(detail.context_snapshot.injected || []).length" class="empty">
            本次无注入块（可能无命中或密级/有效期过滤为空）。
          </p>
        </div>
      </section>

      <section v-else class="detail empty-pane">
        选择左侧快照，或运行一次 Hit Test。
      </section>
    </div>
  </div>
</template>

<script setup lang="ts">
/**
 * Hit Test 台（C-012）
 * - 手动 query → GET /chat/hit-test（落库）
 * - 列表/详情 → /chat/hit-tests
 * - 展示分路 id、注入全文，解释「为什么这样答」
 */
import { computed, onMounted, ref } from "vue";
import { useRoute } from "vue-router";
import { message } from "ant-design-vue";
import {
  getHitTest,
  listHitTests,
  runHitTest,
  type HitTestDetail,
  type HitTestListItem,
} from "@/api/client";
import DynamicWatermark from "@/shared/DynamicWatermark.vue";
import { maxClassification, needsWatermark } from "@/shared/clearance";

const route = useRoute();

const query = ref("差旅住宿标准是多少？");
const running = ref(false);
const items = ref<HitTestListItem[]>([]);
const sourceFilter = ref("");
const activeId = ref<number | null>(null);
const detail = ref<HitTestDetail | null>(null);

const detailNeedsWm = computed(() => {
  const inj = detail.value?.context_snapshot?.injected || [];
  return needsWatermark(maxClassification(inj.map((b) => b.classification)));
});

async function refreshList() {
  try {
    items.value = await listHitTests({
      limit: 50,
      source: sourceFilter.value || undefined,
    });
  } catch (e: any) {
    message.error(e?.response?.data?.detail || "加载 Hit Test 列表失败");
  }
}

async function open(id: number) {
  activeId.value = id;
  try {
    detail.value = await getHitTest(id);
  } catch (e: any) {
    message.error(e?.response?.data?.detail || "加载详情失败");
  }
}

async function onRun() {
  const q = query.value.trim();
  if (!q || running.value) return;
  running.value = true;
  try {
    const data = await runHitTest(q, true);
    message.success(`已落库 Hit Test #${data.id}`);
    await refreshList();
    if (data.id) await open(data.id);
  } catch (e: any) {
    message.error(e?.response?.data?.detail || "Hit Test 失败");
  } finally {
    running.value = false;
  }
}

onMounted(async () => {
  await refreshList();
  const qid = Number(route.query.id);
  if (qid) {
    await open(qid);
    return;
  }
  if (items.value[0]) await open(items.value[0].id);
});
</script>

<style lang="less" scoped>
.page {
  animation: zs-rise 0.45s ease both;
  padding: 0 0 40px;
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
    max-width: 46em;
    line-height: 1.55;
  }
}
.run {
  display: flex;
  gap: 10px;
  margin: 20px 0 16px;

  input {
    flex: 1;
    border: 1px solid var(--zs-line);
    border-radius: 12px;
    padding: 11px 14px;
    font: inherit;
    background: rgba(255, 255, 255, 0.8);
  }
  button {
    border: 0;
    border-radius: 12px;
    padding: 0 18px;
    background: var(--zs-accent);
    color: #fff;
    font-weight: 600;
    cursor: pointer;
    &:disabled {
      opacity: 0.45;
    }
  }
}
.layout {
  display: grid;
  grid-template-columns: 280px minmax(0, 1fr);
  gap: 18px;
  min-height: 480px;
}
.list {
  border-right: 1px solid var(--zs-line);
  padding-right: 12px;
  min-height: 0;
  max-height: calc(100vh - 240px);
  overflow: auto;
}
.list-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
  font-size: 12px;
  color: var(--zs-muted);

  select {
    border: 1px solid var(--zs-line);
    border-radius: 8px;
    padding: 4px 8px;
    background: #fff;
    font: inherit;
  }
}
.item {
  display: flex;
  flex-direction: column;
  gap: 4px;
  width: 100%;
  text-align: left;
  border: 0;
  background: transparent;
  padding: 10px 8px;
  border-radius: 10px;
  cursor: pointer;
  margin-bottom: 4px;

  strong {
    font-size: 12px;
    color: var(--zs-accent-deep);
  }
  span {
    font-size: 13px;
    color: var(--zs-ink);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  em {
    font-style: normal;
    font-size: 11px;
    color: var(--zs-muted);
  }
  &:hover,
  &.active {
    background: var(--zs-accent-soft);
  }
}
.detail {
  position: relative;
  min-width: 0;
}
.wm-hint {
  color: var(--zs-danger);
  font-weight: 600;
}
.detail-head {
  h2 {
    margin: 0;
    font-size: 18px;
    line-height: 1.4;
    color: var(--zs-ink);
  }
  p {
    margin: 6px 0 0;
    font-size: 12px;
    color: var(--zs-muted);
  }
}
.meta-cards {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
  margin: 16px 0;
}
.card {
  padding: 12px;
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.65);
  border: 1px solid var(--zs-line);

  span {
    display: block;
    font-size: 11px;
    color: var(--zs-muted);
  }
  strong {
    font-size: 22px;
    color: var(--zs-accent-deep);
  }
}
.debug {
  margin-bottom: 16px;
  padding: 12px 14px;
  border-radius: 12px;
  background: rgba(20, 36, 28, 0.04);
  font-size: 12px;
  color: var(--zs-muted);
  line-height: 1.6;

  h3 {
    margin: 0 0 8px;
    font-size: 13px;
    color: var(--zs-ink);
  }
  p {
    margin: 4px 0;
    word-break: break-all;
  }
  b {
    color: var(--zs-accent-deep);
  }
}
.injects h3 {
  margin: 0 0 10px;
  font-size: 14px;
}
.inject {
  padding: 12px 0;
  border-top: 1px solid var(--zs-line);
}
.inject-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
  margin-bottom: 8px;
  font-size: 12px;
  color: var(--zs-muted);

  .rank {
    width: 22px;
    height: 22px;
    border-radius: 50%;
    display: grid;
    place-items: center;
    background: var(--zs-accent-soft);
    color: var(--zs-accent-deep);
    font-weight: 700;
  }
  strong {
    color: var(--zs-ink);
  }
  .ch,
  .tag {
    border-radius: 999px;
    padding: 1px 8px;
    background: rgba(255, 255, 255, 0.8);
    border: 1px solid var(--zs-line);
  }
  .tag {
    color: var(--zs-accent-deep);
  }
}
.inject pre {
  margin: 0;
  white-space: pre-wrap;
  word-break: break-word;
  font-family: var(--zs-font-body);
  font-size: 13px;
  line-height: 1.55;
  color: var(--zs-ink);
  background: rgba(255, 255, 255, 0.55);
  border-radius: 10px;
  padding: 12px;
  border: 1px solid var(--zs-line);
}
.empty,
.empty-pane {
  color: var(--zs-muted);
  font-size: 13px;
  padding: 16px 4px;
}
.empty-pane {
  display: grid;
  place-items: center;
  border: 1px dashed var(--zs-line);
  border-radius: 14px;
  min-height: 280px;
}

@media (max-width: 900px) {
  .layout {
    grid-template-columns: 1fr;
  }
  .list {
    border-right: 0;
    border-bottom: 1px solid var(--zs-line);
    max-height: 220px;
    padding-right: 0;
    padding-bottom: 12px;
  }
  .meta-cards {
    grid-template-columns: 1fr 1fr;
  }
}
</style>
