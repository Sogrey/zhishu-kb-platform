<template>
  <div class="page">
    <header class="hero">
      <h1>治理</h1>
      <p>
        有效期、归并、密级、审计与 Hit Test 的统一入口。操作仍落在知识库 / 专用台，这里聚合导航与待办。
      </p>
    </header>

    <div class="stats">
      <div class="stat">
        <span>归并待办</span>
        <strong>{{ mergeCount }}</strong>
      </div>
      <div class="stat">
        <span>近期审计</span>
        <strong>{{ auditCount }}</strong>
      </div>
      <div class="stat">
        <span>你的密级</span>
        <strong>L{{ userRef?.clearance ?? "—" }}</strong>
      </div>
    </div>

    <div class="cards">
      <article class="card" v-for="item in cards" :key="item.to">
        <h2>{{ item.title }}</h2>
        <p>{{ item.desc }}</p>
        <div class="card-foot">
          <RouterLink class="go" :to="item.to">{{ item.cta }}</RouterLink>
          <em v-if="item.badge">{{ item.badge }}</em>
        </div>
      </article>
    </div>

    <section class="quick">
      <h2>快捷操作</h2>
      <div class="quick-row">
        <button
          v-if="canManage"
          type="button"
          :disabled="scanning"
          @click="onRetireScan"
        >
          {{ scanning ? "扫描中…" : "扫描过期退休" }}
        </button>
        <RouterLink class="linkbtn" to="/knowledge#merge">打开归并待办</RouterLink>
        <RouterLink class="linkbtn" to="/hit-test">跑一次 Hit Test</RouterLink>
        <RouterLink class="linkbtn" to="/eval">跑金标评测</RouterLink>
        <RouterLink class="linkbtn" to="/audit">导出审计</RouterLink>
      </div>
      <p class="tip">
        L3+ 文档在分块抽屉、问答引用、Hit Test 详情会自动叠动态水印（用户 + 时间）。
        评测页可看夜间回归 / 退休调度状态，并手动触发。
        问答助手消息可打开 Trace（检索→注入→生成），与 Hit Test 互补。
      </p>
    </section>
  </div>
</template>

<script setup lang="ts">
/**
 * 治理中枢（C-013）：聚合有效期/归并/审计/Hit Test/水印说明。
 */
import { computed, onMounted, ref } from "vue";
import { message } from "ant-design-vue";
import { listAudits, listMergeSuggestions, retireScan } from "@/api/client";
import { userRef } from "@/shared/auth";

const mergeCount = ref(0);
const auditCount = ref(0);
const scanning = ref(false);

const canManage = computed(
  () => userRef.value && ["admin", "librarian"].includes(userRef.value.role),
);

const cards = computed(() => [
  {
    title: "有效期 · 密级",
    desc: "在知识库改文档有效期与 L1~L4；过期可扫描退休，检索层即时过滤。",
    to: "/knowledge",
    cta: "去知识库",
    badge: null as string | null,
  },
  {
    title: "归并待办",
    desc: "相似新稿提示 → 确认后旧稿 is_current=false，不再参与回答。",
    to: "/knowledge#merge",
    cta: "处理归并",
    badge: mergeCount.value ? `${mergeCount.value} 条待办` : null,
  },
  {
    title: "Hit Test",
    desc: "看分路召回、RRF、注入全文与表格全表，解释「为什么这样答」。",
    to: "/hit-test",
    cta: "打开 Hit Test",
    badge: null,
  },
  {
    title: "审计导出",
    desc: "上传/密级/有效期/归并等操作只增不改，可筛人筛动作，导出 CSV/JSON。",
    to: "/audit",
    cta: "打开审计",
    badge: auditCount.value ? `近 ${auditCount.value} 条` : null,
  },
  {
    title: "金标评测",
    desc: "金标集 v0 + stub 四指标 Runner；可手动跑通并看通过率（M3-2）。",
    to: "/eval",
    cta: "打开评测",
    badge: null,
  },
]);

async function refresh() {
  try {
    if (canManage.value) {
      const merges = await listMergeSuggestions("pending");
      mergeCount.value = merges.length;
    } else {
      mergeCount.value = 0;
    }
  } catch {
    mergeCount.value = 0;
  }
  try {
    if (userRef.value && ["admin", "auditor", "librarian"].includes(userRef.value.role)) {
      const audits = await listAudits({ limit: 30 });
      auditCount.value = audits.length;
    }
  } catch {
    auditCount.value = 0;
  }
}

async function onRetireScan() {
  scanning.value = true;
  try {
    const r = await retireScan();
    message.success(`退休扫描完成：${r.retired ?? 0} 份`);
    await refresh();
  } catch (e: any) {
    message.error(e?.response?.data?.detail || e?.message || "扫描失败");
  } finally {
    scanning.value = false;
  }
}

onMounted(() => {
  void refresh();
});
</script>

<style lang="less" scoped>
.page {
  animation: zs-rise 0.45s ease both;
  padding: 0 0 48px;
  width: 100%;
  box-sizing: border-box;
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
    max-width: 52rem;
    line-height: 1.6;
  }
}
.stats {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
  margin: 22px 0 18px;
}
.stat {
  border: 1px solid var(--zs-line);
  border-radius: 14px;
  padding: 14px 16px;
  background: rgba(255, 255, 255, 0.55);

  span {
    display: block;
    font-size: 12px;
    color: var(--zs-muted);
  }
  strong {
    display: block;
    margin-top: 6px;
    font-size: 22px;
    color: var(--zs-accent-deep);
    font-family: var(--zs-font-display);
  }
}
.cards {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
}
.card {
  border: 1px solid var(--zs-line);
  border-radius: 16px;
  padding: 18px 18px 14px;
  background: linear-gradient(165deg, rgba(255, 255, 255, 0.72), rgba(244, 250, 247, 0.55));

  h2 {
    margin: 0;
    font-size: 18px;
    font-family: var(--zs-font-display);
    color: var(--zs-ink);
  }
  p {
    margin: 8px 0 0;
    color: var(--zs-muted);
    font-size: 13px;
    line-height: 1.55;
    min-height: 3.2em;
  }
}
.card-foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-top: 14px;
}
.go {
  text-decoration: none;
  border-radius: 999px;
  padding: 7px 14px;
  background: var(--zs-accent);
  color: #fff;
  font-size: 13px;
}
em {
  font-style: normal;
  font-size: 12px;
  color: var(--zs-danger);
  font-weight: 600;
}
.quick {
  margin-top: 28px;

  h2 {
    margin: 0 0 12px;
    font-size: 16px;
    font-family: var(--zs-font-display);
  }
}
.quick-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.quick-row button,
.linkbtn {
  border: 1px solid var(--zs-line);
  border-radius: 999px;
  padding: 8px 14px;
  background: rgba(255, 255, 255, 0.7);
  color: var(--zs-accent-deep);
  font: inherit;
  font-size: 13px;
  cursor: pointer;
  text-decoration: none;
}
.quick-row button:disabled {
  opacity: 0.6;
  cursor: wait;
}
.tip {
  margin: 14px 0 0;
  color: var(--zs-muted);
  font-size: 12px;
  line-height: 1.5;
}
@media (max-width: 800px) {
  .stats,
  .cards {
    grid-template-columns: 1fr;
  }
}
</style>
