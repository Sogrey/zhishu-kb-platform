<template>
  <!-- 三栏：历史 | 对话（欢迎/线程 + 底栏输入） | 引用原文；L3+ 引用时叠水印 -->
  <div class="page" :class="{ filled: messages.length }">
    <DynamicWatermark :active="secretOnPage" />
    <ChatHistoryAside
      :conversations="conversations"
      :active-id="conversationId"
      @new-chat="newChat"
      @open="openConversation"
    />

    <section class="stage">
      <div ref="listRef" class="scroll">
        <ChatWelcome v-if="!messages.length" @ask="askSample" />
        <ChatThread
          v-else
          :messages="messages"
          :loading="loading"
          :show-trace="canSeeTrace"
          @cite="showCite"
          @trace="openTrace"
        />
      </div>
      <ChatComposer
        v-model="input"
        :loading="loading"
        :retrieve-meta="retrieveMeta"
        @send="send"
      />
      <TracePanel :open="traceOpen" :trace-id="activeTraceId" @close="closeTrace" />
    </section>

    <CitationRail :citations="activeCitations" />
  </div>
</template>

<script setup lang="ts">
/**
 * 问答页编排层（薄容器）。
 * 状态见 useChatSession；UI 拆到 History / Welcome / Thread / Composer / Rail / Trace。
 *
 * SFC 约定：template → script → style(lang="less")
 */
import { computed, ref } from "vue";
import DynamicWatermark from "@/shared/DynamicWatermark.vue";
import { userRef } from "@/shared/auth";
import { maxClassification, needsWatermark } from "@/shared/clearance";
import ChatHistoryAside from "./ChatHistoryAside.vue";
import ChatWelcome from "./ChatWelcome.vue";
import ChatThread from "./ChatThread.vue";
import ChatComposer from "./ChatComposer.vue";
import CitationRail from "./CitationRail.vue";
import TracePanel from "./TracePanel.vue";
import { useChatSession } from "./useChatSession";

const {
  input,
  loading,
  conversationId,
  messages,
  listRef,
  activeCitations,
  conversations,
  retrieveMeta,
  openConversation,
  newChat,
  send,
  showCite,
  askSample,
} = useChatSession();

/** 管理员/知识管理员/审计员可见 Trace（C-108）；本人也可看自己的（后端放行） */
const canSeeTrace = computed(() => {
  const role = userRef.value?.role;
  return ["admin", "librarian", "auditor", "member"].includes(role || "");
});

const traceOpen = ref(false);
const activeTraceId = ref<string | null>(null);

function openTrace(id: string) {
  activeTraceId.value = id;
  traceOpen.value = true;
}

function closeTrace() {
  traceOpen.value = false;
}

/** 当前线程或引用轨出现 L3+ 文档时叠加动态水印 */
const secretOnPage = computed(() => {
  const levels = [
    ...activeCitations.value.map((c) => c.classification),
    ...messages.value.flatMap((m) => (m.citations || []).map((c) => c.classification)),
  ];
  return needsWatermark(maxClassification(levels));
});
</script>

<style lang="less" scoped>
.page {
  position: relative;
  flex: 1;
  display: grid;
  grid-template-columns: 232px minmax(0, 1fr) minmax(360px, 26vw);
  gap: 0;
  min-height: 0;
  height: calc(100vh - 78px);
  max-height: calc(100vh - 78px);
}
.stage {
  position: relative;
  display: flex;
  flex-direction: column;
  min-width: 0;
  min-height: 0;
  height: 100%;
  padding: 0 16px;
}
.scroll {
  flex: 1;
  min-height: 0;
  overflow: auto;
  display: flex;
  flex-direction: column;
}

@media (max-width: 1280px) {
  .page {
    grid-template-columns: 210px minmax(0, 1fr) minmax(320px, 360px);
  }
}

@media (max-width: 1100px) {
  .page {
    grid-template-columns: 200px minmax(0, 1fr);

    :deep(.rail) {
      display: none;
    }
  }
}

@media (max-width: 720px) {
  .page {
    grid-template-columns: 1fr;
    height: auto;
    max-height: none;
  }
  .stage {
    height: calc(100vh - 220px);
    padding: 0;
  }
}
</style>
