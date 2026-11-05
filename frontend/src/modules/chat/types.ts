/**
 * 问答页本地消息模型。
 * 与后端 Message 对齐：assistant 可附带 citations / citation_groups。
 */
import type { Citation, CitationGroups } from "@/api/types";

export type ChatMsg = {
  role: "user" | "assistant";
  content: string;
  citations?: Citation[];
  groups?: CitationGroups | null;
  /** FR-14 轻量 Trace id（UUID） */
  trace_id?: string | null;
  hit_test_id?: number | null;
};
