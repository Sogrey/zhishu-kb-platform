<template>
  <div class="page">
    <header class="hero">
      <h1>知识库</h1>
      <p>批量入库、查看分块、失败可重跑。相同文件按 SHA-256 秒级去重。</p>
    </header>

    <div
      class="drop"
      :class="{ busy: uploading, over: dragOver }"
      @dragenter.prevent="dragOver = true"
      @dragover.prevent="dragOver = true"
      @dragleave.prevent="dragOver = false"
      @drop.prevent="onDrop"
    >
      <label class="drop-main">
        <input
          type="file"
          multiple
          accept=".pdf,.docx,.md,.txt,.markdown"
          hidden
          :disabled="uploading"
          @change="onInputChange"
        />
        <strong>{{ uploading ? `处理中（${uploadQueue.length}）…` : "拖入多个文件，或点击选择" }}</strong>
        <span>PDF / Word / Markdown / 文本 · 当前上传密级 L{{ uploadLevel }}</span>
      </label>
      <div class="level-row">
        <span>上传密级</span>
        <select v-model.number="uploadLevel">
          <option v-for="n in 4" :key="n" :value="n" :disabled="n > (userRef?.clearance || 2)">
            L{{ n }}
          </option>
        </select>
      </div>
      <ul v-if="uploadQueue.length" class="queue">
        <li v-for="name in uploadQueue" :key="name">{{ name }}</li>
      </ul>
    </div>

    <div id="merge" v-if="canMerge" class="merge-box" :class="{ empty: !merges.length }">
      <h2>归并待办 <em>{{ merges.length }}</em></h2>
      <p class="merge-lead">新稿与现行稿相似时出现。确认后旧稿退出检索（is_current=false）。</p>
      <p v-if="!merges.length" class="merge-empty">暂无待办。从「治理」可跳转至此。</p>
      <article v-for="m in merges" :key="m.id" class="merge-row">
        <div>
          <strong :class="m.strength">{{ m.strength === "strong" ? "强相似" : "弱相似" }}</strong>
          · {{ (m.score * 100).toFixed(1) }}%
          <p>
            新稿「{{ m.newer_title }}」≈ 旧稿「{{ m.older_title }}」
          </p>
        </div>
        <div class="merge-actions">
          <button type="button" class="ok" @click="onConfirmMerge(m)">确认归并</button>
          <button type="button" @click="onIgnoreMerge(m)">忽略</button>
        </div>
      </article>
    </div>

    <div class="toolbar">
      <input v-model="keyword" class="search" type="search" placeholder="按标题筛选" />
      <select v-model="statusFilter">
        <option value="">全部状态</option>
        <option value="ready">可用</option>
        <option value="pending">排队中</option>
        <option value="parsing">解析中</option>
        <option value="embedding">向量化</option>
        <option value="failed">失败</option>
        <option value="retired">已退休</option>
      </select>
      <button
        v-if="userRef && ['admin', 'librarian'].includes(userRef.role)"
        type="button"
        class="scan"
        @click="onRetireScan"
      >
        扫描过期退休
      </button>
      <span class="hint">{{ filteredHint }}</span>
    </div>

    <div class="list">
      <article v-for="d in docs" :key="d.id" class="row">
        <div class="row-top">
          <div class="meta">
            <h3>
              {{ d.title }}
              <span v-if="d.is_current === false" class="hist-tag">历史稿</span>
            </h3>
            <p>
              #{{ d.id }} · L{{ d.classification || 2 }} · {{ statusLabel(d.status) }}
              · {{ validityLabel(d.validity) }}
              <span v-if="d.superseded_by"> · 被 #{{ d.superseded_by }} 取代</span>
              <span v-if="d.chunk_count"> · {{ d.chunk_count }} 块</span>
              · {{ new Date(d.created_at).toLocaleString() }}
            </p>
            <p v-if="d.error_message" class="err">{{ d.error_message }}</p>
          </div>
          <div class="status-col">
            <span class="badge" :data-s="d.status">{{ statusLabel(d.status) }}</span>
            <div class="bar" :title="`${d.progress}%`">
              <i :style="{ width: `${d.progress}%` }" />
            </div>
          </div>
        </div>
        <div class="btns">
          <button type="button" :disabled="d.status !== 'ready'" @click="openChunks(d)">分块</button>
          <a
            v-if="d.status === 'ready'"
            class="linkbtn"
            :href="parsedDownloadUrl(d.id)"
            target="_blank"
            rel="noopener"
          >解析下载</a>
          <button type="button" @click="onReingest(d)">重跑</button>
          <select
            v-if="userRef && ['admin', 'librarian'].includes(userRef.role)"
            class="level-select"
            :value="d.classification || 2"
            @change="onSetLevel(d, Number(($event.target as HTMLSelectElement).value))"
          >
            <option v-for="n in 4" :key="n" :value="n" :disabled="n > userRef.clearance">
              L{{ n }}
            </option>
          </select>
          <button
            v-if="userRef && ['admin', 'librarian'].includes(userRef.role)"
            type="button"
            @click="onSetValidity(d)"
          >
            有效期
          </button>
          <button type="button" class="danger" @click="onDelete(d)">删除</button>
        </div>
      </article>
    </div>

    <div v-if="activeDoc" class="drawer-mask" @click.self="closeChunks">
      <aside class="drawer">
        <DynamicWatermark :active="needsWatermark(activeDoc.classification)" />
        <header>
          <div>
            <h2>{{ activeDoc.title }}</h2>
            <p>
              分块透明化 · 共 {{ chunks.length }} 块
              <span v-if="needsWatermark(activeDoc.classification)" class="wm-hint">
                · L{{ activeDoc.classification }} 水印中
              </span>
            </p>
          </div>
          <button type="button" class="close" @click="closeChunks">关闭</button>
        </header>
        <div v-if="chunksLoading" class="loading">加载中…</div>
        <div v-else class="chunks">
          <article v-for="c in chunks" :key="c.id" class="chunk">
            <div class="chunk-meta">
              <span>#{{ c.seq }}</span>
              <span v-if="c.page_no != null">p.{{ c.page_no }}</span>
              <span v-if="c.is_table">表格</span>
              <span v-if="c.token_count">≈{{ c.token_count }} tok</span>
            </div>
            <MarkdownBody :source="c.content" />
          </article>
        </div>
      </aside>
    </div>
  </div>
</template>

<script setup lang="ts">
/**
 * 知识库页：批量上传、列表、密级/有效期、分块抽屉、退休扫描。
 * SFC 顺序：template → script → style(less)
 */
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from "vue";
import { useRoute } from "vue-router";
import { message } from "ant-design-vue";
import MarkdownBody from "@/shared/MarkdownBody.vue";
import DynamicWatermark from "@/shared/DynamicWatermark.vue";
import { needsWatermark } from "@/shared/clearance";
import {
  confirmMergeSuggestion,
  deleteDocument,
  getDocument,
  ignoreMergeSuggestion,
  listChunks,
  listDocuments,
  listMergeSuggestions,
  parsedDownloadUrl,
  reingestDocument,
  retireScan,
  setDocumentClassification,
  setDocumentValidity,
  uploadDocument,
  type ChunkItem,
  type DocumentItem,
  type MergeSuggestionItem,
} from "@/api/client";
import { userRef } from "@/shared/auth";

const route = useRoute();
const docs = ref<DocumentItem[]>([]);
const merges = ref<MergeSuggestionItem[]>([]);
const uploading = ref(false);
const uploadQueue = ref<string[]>([]);
const dragOver = ref(false);
const statusFilter = ref("");
const keyword = ref("");
const uploadLevel = ref(2);
const pollingIds = ref<Set<number>>(new Set());
let timer: number | null = null;

const activeDoc = ref<DocumentItem | null>(null);
const chunks = ref<ChunkItem[]>([]);
const chunksLoading = ref(false);

const filteredHint = computed(() => {
  if (!docs.value.length) return "还没有文档。拖入制度样例开始入库。";
  return `共 ${docs.value.length} 份`;
});

const canMerge = computed(
  () => userRef.value && ["admin", "librarian"].includes(userRef.value.role),
);

async function refreshMerges() {
  if (!canMerge.value) {
    merges.value = [];
    return;
  }
  try {
    merges.value = await listMergeSuggestions("pending");
  } catch {
    merges.value = [];
  }
}

async function refresh() {
  docs.value = await listDocuments({
    status: statusFilter.value || undefined,
    q: keyword.value.trim() || undefined,
  });
  await refreshMerges();
}

async function uploadOne(file: File) {
  uploadQueue.value = [...uploadQueue.value, file.name];
  try {
    const doc = await uploadDocument(file, uploadLevel.value);
    if (doc.deduplicated) {
      message.info(`已存在相同文件（SHA 去重）：${doc.title}`);
    } else {
      message.success(`已上传：${doc.title}`);
      watchUntilReady(doc.id);
    }
  } catch (e: any) {
    message.error(e?.response?.data?.detail || e.message || `${file.name} 上传失败`);
  } finally {
    uploadQueue.value = uploadQueue.value.filter((n) => n !== file.name);
  }
}

async function onFiles(fileList: FileList | File[]) {
  const files = Array.from(fileList);
  if (!files.length) return;
  uploading.value = true;
  for (const f of files) {
    await uploadOne(f);
  }
  await refresh();
  uploading.value = false;
}

function onInputChange(e: Event) {
  const input = e.target as HTMLInputElement;
  if (input.files?.length) void onFiles(input.files);
  input.value = "";
}

function onDrop(e: DragEvent) {
  dragOver.value = false;
  const files = e.dataTransfer?.files;
  if (files?.length) void onFiles(files);
}

function watchUntilReady(id: number) {
  pollingIds.value.add(id);
}

async function pollOnce() {
  if (!pollingIds.value.size) return;
  const ids = [...pollingIds.value];
  for (const id of ids) {
    try {
      const d = await getDocument(id);
      const idx = docs.value.findIndex((x) => x.id === id);
      if (idx >= 0) docs.value[idx] = d;
      else docs.value.unshift(d);
      if (d.status === "ready") {
        pollingIds.value.delete(id);
        message.success(`${d.title} 已入库（${d.chunk_count || 0} 块）`);
      } else if (d.status === "failed") {
        pollingIds.value.delete(id);
        message.error(d.error_message || `${d.title} 解析失败`);
      }
    } catch {
      /* ignore */
    }
  }
}

function statusLabel(s: string) {
  const map: Record<string, string> = {
    pending: "排队中",
    parsing: "解析中",
    embedding: "向量化",
    ready: "可用",
    failed: "失败",
    retired: "已退休",
  };
  return map[s] || s;
}

async function openChunks(doc: DocumentItem) {
  activeDoc.value = doc;
  chunksLoading.value = true;
  try {
    chunks.value = await listChunks(doc.id);
  } catch (e: any) {
    message.error(e?.response?.data?.detail || "加载分块失败");
    chunks.value = [];
  } finally {
    chunksLoading.value = false;
  }
}

function closeChunks() {
  activeDoc.value = null;
  chunks.value = [];
}

async function onReingest(doc: DocumentItem) {
  try {
    const d = await reingestDocument(doc.id);
    message.success(`已触发重跑：${d.title}`);
    watchUntilReady(d.id);
    await refresh();
  } catch (e: any) {
    message.error(e?.response?.data?.detail || "重跑失败");
  }
}

async function onDelete(doc: DocumentItem) {
  if (!window.confirm(`删除「${doc.title}」？此操作不可恢复。`)) return;
  try {
    await deleteDocument(doc.id);
    if (activeDoc.value?.id === doc.id) closeChunks();
    message.success("已删除");
    await refresh();
  } catch (e: any) {
    message.error(e?.response?.data?.detail || "删除失败");
  }
}

async function onSetLevel(doc: DocumentItem, level: number) {
  try {
    await setDocumentClassification(doc.id, level);
    message.success(`已将「${doc.title}」密级设为 L${level}`);
    await refresh();
  } catch (e: any) {
    message.error(e?.response?.data?.detail || "改密级失败");
  }
}

function validityLabel(v?: string) {
  const map: Record<string, string> = {
    active: "有效",
    pending: "未生效",
    expired: "已过期",
    retired: "已退休",
  };
  return map[v || "active"] || v || "有效";
}

function toLocalInput(iso?: string | null) {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

async function onSetValidity(doc: DocumentItem) {
  const fromRaw = window.prompt(
    "生效时间（留空=立即；格式 YYYY-MM-DDTHH:mm）",
    toLocalInput(doc.valid_from),
  );
  if (fromRaw === null) return;
  const toRaw = window.prompt(
    "失效时间（留空=永不过期；格式 YYYY-MM-DDTHH:mm）",
    toLocalInput(doc.valid_to),
  );
  if (toRaw === null) return;
  const valid_from = fromRaw.trim() ? new Date(fromRaw.trim()).toISOString() : null;
  const valid_to = toRaw.trim() ? new Date(toRaw.trim()).toISOString() : null;
  if (fromRaw.trim() && Number.isNaN(Date.parse(fromRaw.trim()))) {
    message.error("生效时间格式无效");
    return;
  }
  if (toRaw.trim() && Number.isNaN(Date.parse(toRaw.trim()))) {
    message.error("失效时间格式无效");
    return;
  }
  try {
    await setDocumentValidity(doc.id, valid_from, valid_to);
    message.success("有效期已更新（检索立即生效）");
    await refresh();
  } catch (e: any) {
    message.error(e?.response?.data?.detail || "改有效期失败");
  }
}

async function onRetireScan() {
  try {
    const r = await retireScan();
    message.success(`退休扫描完成：${r.retired} 份`);
    await refresh();
  } catch (e: any) {
    message.error(e?.response?.data?.detail || "扫描失败");
  }
}

async function onConfirmMerge(m: MergeSuggestionItem) {
  try {
    await confirmMergeSuggestion(m.id);
    message.success(`已归并：保留「${m.newer_title}」，旧稿不再参与检索`);
    await refresh();
  } catch (e: any) {
    message.error(e?.response?.data?.detail || "确认归并失败");
  }
}

async function onIgnoreMerge(m: MergeSuggestionItem) {
  try {
    await ignoreMergeSuggestion(m.id);
    message.info("已忽略该归并提示");
    await refreshMerges();
  } catch (e: any) {
    message.error(e?.response?.data?.detail || "忽略失败");
  }
}

watch([statusFilter, keyword], () => {
  void refresh();
});

function scrollToHash() {
  const hash = (route.hash || "").replace(/^#/, "");
  if (!hash) return;
  const el = document.getElementById(hash);
  if (el) el.scrollIntoView({ behavior: "smooth", block: "start" });
}

watch(
  () => route.hash,
  async () => {
    await nextTick();
    scrollToHash();
  },
);

onMounted(async () => {
  await refresh();
  await nextTick();
  scrollToHash();
  timer = window.setInterval(() => {
    void pollOnce();
  }, 900);
});

onUnmounted(() => {
  if (timer) window.clearInterval(timer);
});
</script>

<style lang="less" scoped>
.page {
  animation: zs-rise 0.55s ease both;
  padding: 0 0 40px;
  width: 100%;
  box-sizing: border-box;
}
.hero {
  padding: 28px 4px 20px;

  h1 {
    margin: 0;
    font-family: var(--zs-font-display);
    font-size: clamp(36px, 6vw, 52px);
    letter-spacing: 0.06em;
    color: var(--zs-accent-deep);
  }
  p {
    margin: 10px 0 0;
    color: var(--zs-muted);
    max-width: 40em;
    line-height: 1.6;
  }
}
.drop {
  border: 1.5px dashed rgba(11, 92, 69, 0.35);
  border-radius: var(--zs-radius);
  background: rgba(255, 255, 255, 0.5);
  transition: border-color 0.2s ease, background 0.2s ease, transform 0.2s ease;

  &.over {
    border-color: var(--zs-accent);
    background: rgba(212, 235, 225, 0.55);
    transform: translateY(-1px);
  }
  &.busy {
    opacity: 0.75;
  }
}
.drop-main {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 28px 26px;
  cursor: pointer;

  strong {
    font-size: 16px;
    color: var(--zs-accent-deep);
  }
  span {
    color: var(--zs-muted);
    font-size: 13px;
  }
}
.level-row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 0 26px 18px;
  color: var(--zs-muted);
  font-size: 13px;
}
.level-row select {
  border: 1px solid var(--zs-line);
  border-radius: 999px;
  padding: 4px 10px;
  background: #fff;
  font: inherit;
}
.queue {
  margin: 0;
  padding: 0 26px 18px;
  color: var(--zs-muted);
  font-size: 13px;
}
.toolbar {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: center;
  margin: 18px 0 6px;
}
.search,
.toolbar select {
  border: 1px solid var(--zs-line);
  background: rgba(255, 255, 255, 0.75);
  border-radius: 10px;
  padding: 8px 12px;
  font: inherit;
  color: var(--zs-ink);
  outline: none;
}
.search {
  min-width: 200px;
}
.hint {
  color: var(--zs-muted);
  font-size: 13px;
}
.scan {
  border: 1px solid var(--zs-line);
  background: rgba(255, 255, 255, 0.7);
  border-radius: 999px;
  padding: 7px 12px;
  font-size: 12px;
  cursor: pointer;
  color: var(--zs-accent-deep);

  &:hover {
    border-color: var(--zs-accent);
  }
}
.merge-box {
  margin: 8px 0 4px;
  padding: 14px 16px;
  border: 1px solid rgba(11, 92, 69, 0.25);
  border-radius: 14px;
  background: rgba(212, 235, 225, 0.35);

  h2 {
    margin: 0;
    font-size: 15px;
    color: var(--zs-accent-deep);

    em {
      font-style: normal;
      margin-left: 6px;
      font-size: 12px;
      padding: 1px 8px;
      border-radius: 999px;
      background: var(--zs-accent);
      color: #fff;
    }
  }
}
.merge-box.empty {
  background: rgba(255, 255, 255, 0.4);
  border-color: var(--zs-line);
}
.merge-lead {
  margin: 6px 0 10px;
  font-size: 12px;
  color: var(--zs-muted);
}
.merge-empty {
  margin: 0;
  font-size: 13px;
  color: var(--zs-muted);
}
.merge-row {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: center;
  padding: 10px 0;
  border-top: 1px solid var(--zs-line);
  font-size: 13px;

  .strong {
    color: #9b2c2c;
  }
  .weak {
    color: #8a6d3b;
  }
  p {
    margin: 4px 0 0;
    color: var(--zs-muted);
    font-size: 12px;
  }
}
.merge-actions {
  display: flex;
  gap: 6px;
  flex-shrink: 0;

  button {
    border: 1px solid var(--zs-line);
    background: #fff;
    border-radius: 999px;
    padding: 5px 12px;
    font-size: 12px;
    cursor: pointer;
  }
  .ok {
    background: var(--zs-accent);
    border-color: var(--zs-accent);
    color: #fff;
  }
}
.hist-tag {
  margin-left: 8px;
  font-size: 11px;
  font-weight: 500;
  color: var(--zs-muted);
  border: 1px solid var(--zs-line);
  border-radius: 999px;
  padding: 1px 8px;
}
.row {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 16px 4px;
  border-top: 1px solid var(--zs-line);
}
.row-top {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}
.meta {
  min-width: 0;
  flex: 1;

  h3 {
    margin: 0;
    font-size: 16px;
    font-weight: 600;
    line-height: 1.35;
  }
  p {
    margin: 6px 0 0;
    color: var(--zs-muted);
    font-size: 12px;
  }
}
.err {
  color: var(--zs-danger) !important;
}
.status-col {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 8px;
  flex-shrink: 0;
}
.badge {
  font-size: 12px;
  padding: 3px 10px;
  border-radius: 999px;
  background: var(--zs-accent-soft);
  color: var(--zs-accent-deep);
  white-space: nowrap;

  &[data-s="failed"] {
    background: #fde8e8;
    color: var(--zs-danger);
  }
  &[data-s="ready"] {
    background: #dff3ea;
  }
  &[data-s="retired"] {
    background: rgba(20, 36, 28, 0.08);
    color: var(--zs-muted);
  }
}
.bar {
  width: 96px;
  height: 4px;
  border-radius: 999px;
  background: rgba(20, 36, 28, 0.08);
  overflow: hidden;

  i {
    display: block;
    height: 100%;
    background: var(--zs-accent);
    border-radius: inherit;
    transition: width 0.3s ease;
  }
}
.btns {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;

  button,
  .linkbtn,
  .level-select {
    box-sizing: border-box;
    height: 30px;
    border: 1px solid var(--zs-line);
    background: rgba(255, 255, 255, 0.85);
    color: var(--zs-ink);
    border-radius: 999px;
    padding: 0 12px;
    font-size: 12px;
    line-height: 28px;
    cursor: pointer;
    text-decoration: none;
    display: inline-flex;
    align-items: center;
    white-space: nowrap;
    flex: 0 0 auto;
  }
  .level-select {
    appearance: none;
    padding-right: 28px;
    background-image:
      linear-gradient(45deg, transparent 50%, var(--zs-muted) 50%),
      linear-gradient(135deg, var(--zs-muted) 50%, transparent 50%);
    background-position:
      right 12px top 11px,
      right 7px top 11px;
    background-size: 5px 5px, 5px 5px;
    background-repeat: no-repeat;
    background-color: rgba(255, 255, 255, 0.85);
  }
  button:disabled {
    opacity: 0.4;
    cursor: not-allowed;
  }
  button:hover:not(:disabled),
  .linkbtn:hover,
  .level-select:hover {
    border-color: var(--zs-accent);
  }
  .danger {
    color: var(--zs-danger);
  }
}
.drawer-mask {
  position: fixed;
  inset: 0;
  background: rgba(20, 36, 28, 0.28);
  display: flex;
  justify-content: flex-end;
  z-index: 40;
  animation: zs-fade 0.25s ease both;
}
.drawer {
  position: relative;
  width: min(520px, 100%);
  height: 100%;
  background: #f7faf7;
  box-shadow: -12px 0 40px rgba(20, 36, 28, 0.12);
  padding: 22px 20px;
  overflow: auto;
  animation: zs-rise 0.3s ease both;

  header {
    display: flex;
    justify-content: space-between;
    gap: 12px;
    margin-bottom: 16px;

    p {
      margin: 6px 0 0;
      color: var(--zs-muted);
      font-size: 13px;
    }
  }
  h2 {
    margin: 0;
    font-family: var(--zs-font-display);
    font-size: 22px;
  }
}
.wm-hint {
  color: var(--zs-danger);
  font-weight: 600;
}
.close {
  border: 0;
  background: transparent;
  color: var(--zs-muted);
  cursor: pointer;
}
.chunk {
  padding: 14px 0;
  border-top: 1px solid var(--zs-line);
}
.chunk-meta {
  display: flex;
  gap: 10px;
  margin-bottom: 8px;
  color: var(--zs-muted);
  font-size: 12px;
}
.loading {
  color: var(--zs-muted);
  padding: 20px 0;
}

@media (max-width: 720px) {
  .row-top {
    flex-direction: column;
    align-items: stretch;
  }
  .status-col {
    align-items: flex-start;
  }
}
</style>
