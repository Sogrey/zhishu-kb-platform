/**
 * 问答会话状态机（composable）
 *
 * 职责：
 * - 维护当前 conversationId、消息列表、历史侧栏、引用侧栏、检索可观测条
 * - 调用 SSE chatStream，把 block_delta / block_replace 落到最后一条 assistant
 * - 打开历史会话时回放消息与最后一轮 citations
 *
 * 不负责：布局 UI（由 ChatView 与子组件承担）
 */
import { nextTick, onMounted, ref } from "vue";
import { message } from "ant-design-vue";
import {
  chatStream,
  getConversation,
  listConversations,
  type Citation,
  type ConversationItem,
  type RetrieveMeta,
} from "@/api/client";
import type { ChatMsg } from "./types";

export function useChatSession() {
  const input = ref("");
  const loading = ref(false);
  /** 当前会话 ID；null 表示尚未落库的新对话 */
  const conversationId = ref<number | null>(null);
  const messages = ref<ChatMsg[]>([]);
  /** 消息滚动容器，send/流式时滚到底 */
  const listRef = ref<HTMLElement | null>(null);
  /** 右侧「引用原文」当前展示的片段（可多条） */
  const activeCitations = ref<Citation[]>([]);
  const conversations = ref<ConversationItem[]>([]);
  /** 最近一次检索的分路统计（向量/关键词/RRF/注入） */
  const retrieveMeta = ref<RetrieveMeta | null>(null);

  async function refreshConversations() {
    try {
      conversations.value = await listConversations();
    } catch {
      /* 未登录或网络抖动时侧栏允许为空 */
    }
  }

  async function openConversation(id: number) {
    if (loading.value) return;
    try {
      const data = await getConversation(id);
      conversationId.value = data.id;
      messages.value = data.messages.map((m) => ({
        role: m.role as "user" | "assistant",
        content: m.content,
        citations: m.citations || [],
        groups: m.citation_groups || null,
        trace_id: m.trace_id || null,
        hit_test_id: m.hit_test_id ?? null,
      }));
      const last = [...messages.value].reverse().find((m) => m.role === "assistant");
      activeCitations.value = last?.citations?.length ? last.citations : [];
      retrieveMeta.value = null;
      await scrollBottom();
    } catch (e: any) {
      message.error(e?.message || "加载会话失败");
    }
  }

  /** 清空当前线程，不删服务端历史 */
  function newChat() {
    conversationId.value = null;
    messages.value = [];
    activeCitations.value = [];
    retrieveMeta.value = null;
  }

  async function send() {
    const text = input.value.trim();
    if (!text || loading.value) return;
    input.value = "";
    messages.value.push({ role: "user", content: text });
    const assistant: ChatMsg = { role: "assistant", content: "", citations: [], groups: null };
    messages.value.push(assistant);
    loading.value = true;
    activeCitations.value = [];
    retrieveMeta.value = null;
    await scrollBottom();

    try {
      await chatStream(text, conversationId.value, {
        onMeta: (id, extra) => {
          conversationId.value = id;
          if (extra?.trace_id) assistant.trace_id = extra.trace_id;
          if (extra?.hit_test_id != null) assistant.hit_test_id = extra.hit_test_id;
        },
        onRetrieveMeta: (meta) => {
          retrieveMeta.value = meta;
          if (meta.trace_id) assistant.trace_id = meta.trace_id;
          if (meta.hit_test_id != null) assistant.hit_test_id = meta.hit_test_id;
        },
        onDelta: (delta) => {
          assistant.content += delta;
          void scrollBottom();
        },
        onReplace: (content, citations, groups, extra) => {
          // 终态以 block_replace 为准（含完整 Markdown 与 citations）
          assistant.content = content;
          assistant.citations = citations;
          assistant.groups = groups || null;
          if (extra?.trace_id) assistant.trace_id = extra.trace_id;
          if (extra?.hit_test_id != null) assistant.hit_test_id = extra.hit_test_id;
          activeCitations.value = citations;
        },
        onDone: () => {
          loading.value = false;
          void refreshConversations();
        },
        onError: (err) => {
          message.error(err.message);
          loading.value = false;
        },
      });
    } finally {
      loading.value = false;
      await scrollBottom();
    }
  }

  async function scrollBottom() {
    await nextTick();
    if (listRef.value) listRef.value.scrollTop = listRef.value.scrollHeight;
  }

  function showCite(c: Citation) {
    activeCitations.value = [c];
  }

  function askSample(q: string) {
    input.value = q;
    void send();
  }

  onMounted(() => {
    void refreshConversations();
  });

  return {
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
  };
}
