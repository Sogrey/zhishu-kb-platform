/**
 * HTTP API 客户端（axios + SSE chat）。
 * 类型定义见 `./types.ts`，此处再导出以兼容 `import { … } from "@/api/client"`。
 */
import axios from "axios";
import { clearSession, tokenRef, workspaceRef } from "@/shared/auth";
import type {
  AuditItem,
  ChatHandlers,
  ChunkItem,
  ConversationItem,
  DocumentItem,
  LlmProviderId,
  LlmSettings,
  QaTraceDetail,
  RetrieveMeta,
} from "./types";

export type * from "./types";

export const api = axios.create({
  baseURL: "/api/v1",
  timeout: 120000,
});

api.interceptors.request.use((config) => {
  if (tokenRef.value) {
    config.headers.Authorization = `Bearer ${tokenRef.value}`;
  }
  if (workspaceRef.value?.id) {
    config.headers["X-Workspace-Id"] = String(workspaceRef.value.id);
  }
  return config;
});

api.interceptors.response.use(
  (r) => r,
  (err) => {
    if (err?.response?.status === 401) {
      clearSession();
      if (location.pathname !== "/login") location.href = "/login";
    }
    return Promise.reject(err);
  },
);

export async function login(username: string, password: string) {
  const { data } = await api.post("/auth/login", { username, password });
  return data as {
    access_token: string;
    user: {
      id: number;
      username: string;
      display_name: string;
      role: string;
      clearance: number;
    };
    workspaces: { id: number; name: string; role: string }[];
  };
}

export async function uploadDocument(
  file: File,
  classification = 2,
): Promise<DocumentItem> {
  const form = new FormData();
  form.append("file", file);
  form.append("classification", String(classification));
  const { data } = await api.post<DocumentItem>("/documents/upload", form);
  return data;
}

export async function setDocumentClassification(id: number, level: number) {
  const { data } = await api.patch<DocumentItem>(
    `/documents/${id}/classification`,
    null,
    { params: { level } },
  );
  return data;
}

export async function setDocumentValidity(
  id: number,
  valid_from: string | null,
  valid_to: string | null,
) {
  const { data } = await api.patch<DocumentItem>(`/documents/${id}/validity`, {
    valid_from,
    valid_to,
  });
  return data;
}

export async function retireScan() {
  const { data } = await api.post<{ ok: boolean; retired: number }>(
    "/documents/retire-scan",
  );
  return data;
}

export async function listMergeSuggestions(status = "pending") {
  const { data } = await api.get<import("./types").MergeSuggestionItem[]>(
    "/documents/merge-suggestions",
    { params: { status } },
  );
  return data;
}

export async function confirmMergeSuggestion(id: number) {
  const { data } = await api.post<import("./types").MergeSuggestionItem>(
    `/documents/merge-suggestions/${id}/confirm`,
  );
  return data;
}

export async function ignoreMergeSuggestion(id: number) {
  const { data } = await api.post<import("./types").MergeSuggestionItem>(
    `/documents/merge-suggestions/${id}/ignore`,
  );
  return data;
}

export async function listAudits(params?: {
  action?: string;
  actor?: string;
  limit?: number;
}) {
  const { data } = await api.get<{ items: AuditItem[] }>("/audit", { params });
  return data.items;
}

export function auditExportUrl(format: "csv" | "json" = "csv") {
  return `/api/v1/audit/export?format=${format}`;
}

export async function listEvalSets() {
  const { data } = await api.get<{ items: import("./types").EvalSetItem[] }>("/eval/sets");
  return data.items;
}

export async function listEvalCases(setId: number) {
  const { data } = await api.get<{
    set: { id: number; name: string; version: string };
    items: {
      id: number;
      question: string;
      expected_answer?: string | null;
      expected_doc_titles?: string[];
      tags?: string[];
      active: boolean;
    }[];
  }>(`/eval/sets/${setId}/cases`);
  return data;
}

export async function runEvalSet(setId: number, limit?: number) {
  const { data } = await api.post<import("./types").EvalRunDetail>(
    `/eval/sets/${setId}/run`,
    null,
    { params: limit ? { limit } : undefined, timeout: 300000 },
  );
  return data;
}

export async function getEvalRun(runId: number) {
  const { data } = await api.get<import("./types").EvalRunDetail>(`/eval/runs/${runId}`);
  return data;
}

export async function getEvalScheduler() {
  const { data } = await api.get<import("./types").EvalSchedulerStatus>("/eval/scheduler");
  return data;
}

export async function getEvalDashboard(limit = 30) {
  const { data } = await api.get<import("./types").EvalDashboard>("/eval/dashboard", {
    params: { limit },
  });
  return data;
}

export async function triggerNightlyEvalNow(limit?: number) {
  const { data } = await api.post<{ ok: boolean; runs: unknown[] }>(
    "/eval/scheduler/nightly-now",
    null,
    { params: limit ? { limit } : undefined, timeout: 300000 },
  );
  return data;
}

export async function triggerRetireScanNow() {
  const { data } = await api.post<{ ok: boolean; retired: number }>(
    "/eval/scheduler/retire-now",
  );
  return data;
}

export async function listDocuments(params?: {
  status?: string;
  q?: string;
}): Promise<DocumentItem[]> {
  const { data } = await api.get<DocumentItem[]>("/documents", { params });
  return data;
}

export async function getDocument(id: number): Promise<DocumentItem> {
  const { data } = await api.get<DocumentItem>(`/documents/${id}`);
  return data;
}

export async function listChunks(id: number): Promise<ChunkItem[]> {
  const { data } = await api.get<ChunkItem[]>(`/documents/${id}/chunks`);
  return data;
}

export async function reingestDocument(id: number): Promise<DocumentItem> {
  const { data } = await api.post<DocumentItem>(`/documents/${id}/reingest`);
  return data;
}

export async function deleteDocument(id: number): Promise<void> {
  await api.delete(`/documents/${id}`);
}

export function parsedDownloadUrl(id: number): string {
  return `/api/v1/documents/${id}/parsed`;
}

export async function runHitTest(q: string, persist = true) {
  const { data } = await api.get("/chat/hit-test", {
    params: { q, persist },
  });
  return data as {
    id: number | null;
    query: string;
    injected: import("./types").HitTestInjected[];
    debug: Record<string, unknown>;
    context_snapshot?: import("./types").HitTestDetail["context_snapshot"];
  };
}

export async function listHitTests(params?: { limit?: number; source?: string }) {
  const { data } = await api.get<{ items: import("./types").HitTestListItem[] }>(
    "/chat/hit-tests",
    { params },
  );
  return data.items;
}

export async function getHitTest(id: number) {
  const { data } = await api.get<import("./types").HitTestDetail>(
    `/chat/hit-tests/${id}`,
  );
  return data;
}

export async function listConversations(): Promise<ConversationItem[]> {
  const { data } = await api.get<ConversationItem[]>("/chat/conversations");
  return data;
}

export async function getConversation(id: number): Promise<{
  id: number;
  title: string | null;
  messages: {
    id: number;
    role: string;
    content: string;
    citations?: Citation[];
    citation_groups?: CitationGroups | null;
    trace_id?: string | null;
    hit_test_id?: number | null;
  }[];
}> {
  const { data } = await api.get(`/chat/conversations/${id}`);
  return data;
}

export async function getQaTrace(traceId: string) {
  const { data } = await api.get<QaTraceDetail>(`/chat/traces/${traceId}`);
  return data;
}

export async function getLlmSettings() {
  const { data } = await api.get<LlmSettings>("/settings/llm");
  return data;
}

export async function saveLlmSettings(body: {
  provider: LlmProviderId;
  base_url: string;
  model: string;
  api_key?: string | null;
}) {
  const { data } = await api.put<LlmSettings>("/settings/llm", body);
  return data;
}

export async function listLlmModels(body: {
  provider: LlmProviderId;
  base_url?: string;
  api_key?: string | null;
}) {
  const { data } = await api.post<{
    items: { id: string; name: string }[];
    provider: string;
    base_url: string;
  }>("/settings/llm/models", body);
  return data;
}

export async function testLlmSettings() {
  const { data } = await api.post<{
    ok: boolean;
    provider: string;
    model?: string;
    reply?: string;
    detail?: string;
  }>("/settings/llm/test");
  return data;
}

export async function chatStream(
  message: string,
  conversationId: number | null,
  handlers: ChatHandlers,
): Promise<void> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    Accept: "text/event-stream",
  };
  if (tokenRef.value) headers.Authorization = `Bearer ${tokenRef.value}`;
  if (workspaceRef.value?.id) headers["X-Workspace-Id"] = String(workspaceRef.value.id);

  const resp = await fetch("/api/v1/chat", {
    method: "POST",
    headers,
    body: JSON.stringify({ message, conversation_id: conversationId }),
  });
  if (!resp.ok || !resp.body) {
    if (resp.status === 401) {
      clearSession();
      location.href = "/login";
    }
    handlers.onError?.(new Error(`chat failed: ${resp.status}`));
    return;
  }
  const reader = resp.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let eventName = "message";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const chunks = buffer.split("\n");
    buffer = chunks.pop() || "";
    for (const raw of chunks) {
      const line = raw.replace(/\r$/, "");
      if (!line) continue;
      if (line.startsWith("event:")) {
        eventName = line.slice(6).trim();
        continue;
      }
      if (!line.startsWith("data:")) continue;
      const dataStr = line.slice(5).trim();
      if (dataStr === "[DONE]" || eventName === "done") {
        handlers.onDone?.();
        continue;
      }
      try {
        const data = JSON.parse(dataStr);
        if (eventName === "conversation_meta") {
          handlers.onMeta?.(data.conversation_id, {
            trace_id: data.trace_id,
            hit_test_id: data.hit_test_id,
          });
        } else if (eventName === "retrieve_meta") {
          handlers.onRetrieveMeta?.(data as RetrieveMeta);
        } else if (eventName === "block_delta") {
          handlers.onDelta?.(data.delta || "");
        } else if (eventName === "block_replace") {
          const block = data.blocks?.[0];
          handlers.onReplace?.(
            block?.content || "",
            block?.citations || [],
            block?.citation_groups || null,
            {
              trace_id: block?.trace_id || data.trace_id,
              hit_test_id: block?.hit_test_id || data.hit_test_id,
            },
          );
        }
      } catch {
        // ignore malformed
      }
    }
  }
}
