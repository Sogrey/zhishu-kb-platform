/**
 * 前后端共享的 API DTO 类型（仅类型，无运行时代码）。
 * 业务请求函数仍从 `@/api/client` 引入；组件需要类型时可从本文件引入。
 */

export type DocumentItem = {
  id: number;
  workspace_id?: number;
  title: string;
  source_type: string;
  status: string;
  progress: number;
  classification?: number;
  is_current?: boolean;
  superseded_by?: number | null;
  valid_from?: string | null;
  valid_to?: string | null;
  validity?: string;
  error_message?: string | null;
  sha256?: string | null;
  created_at: string;
  chunk_count?: number;
  deduplicated?: boolean;
};

export type MergeSuggestionItem = {
  id: number;
  newer_doc_id: number;
  older_doc_id: number;
  newer_title: string;
  older_title: string;
  score: number;
  strength: string;
  status: string;
  created_at?: string | null;
};

export type AuditItem = {
  id: number;
  workspace_id?: number | null;
  actor_id?: number | null;
  actor_name?: string | null;
  action: string;
  resource_type?: string | null;
  resource_id?: string | null;
  detail?: Record<string, unknown> | null;
  ip?: string | null;
  created_at?: string | null;
};

export type ChunkItem = {
  id: number;
  seq: number;
  content: string;
  is_table: boolean;
  page_no?: number | null;
  token_count?: number | null;
};

export type Citation = {
  doc_id: number;
  title: string;
  page?: number | null;
  snippet: string;
  chunk_id?: number | null;
  score?: number | null;
  /** 文档密级；≥3 时问答页叠动态水印 */
  classification?: number | null;
};

export type CitationGroups = {
  libraries: { doc_id: number; title: string; source_type: string; hit_chunks: number }[];
  sources: Citation[];
  graph: unknown[];
  images: unknown[];
};

export type ConversationItem = {
  id: number;
  title: string;
  created_at?: string | null;
};

export type RetrieveMeta = {
  vector_hits: number;
  keyword_hits: number;
  fused: number;
  injected: number;
  rrf_k: number;
  hit_test_id?: number;
  trace_id?: string;
};

export type ChatHandlers = {
  onMeta?: (conversationId: number, extra?: { trace_id?: string; hit_test_id?: number }) => void;
  onRetrieveMeta?: (meta: RetrieveMeta) => void;
  onDelta?: (delta: string) => void;
  onReplace?: (
    content: string,
    citations: Citation[],
    groups?: CitationGroups | null,
    extra?: { trace_id?: string; hit_test_id?: number },
  ) => void;
  onDone?: () => void;
  onError?: (err: Error) => void;
};

export type TraceSpan = {
  name: string;
  status: string;
  duration_ms: number;
  meta?: Record<string, unknown>;
};

export type QaTraceDetail = {
  id: string;
  workspace_id: number;
  user_id?: number | null;
  conversation_id?: number | null;
  message_id?: number | null;
  hit_test_id?: number | null;
  query: string;
  answer_preview?: string | null;
  spans: TraceSpan[];
  latency_ms: number;
  created_at?: string | null;
  engine?: string;
};

export type LlmProviderId = "stub" | "deepseek" | "ollama" | "llamacpp";

export type LlmProviderMeta = {
  id: LlmProviderId;
  label: string;
  default_base_url: string;
  needs_key: boolean;
  list_models: boolean;
};

export type LlmSettings = {
  provider: LlmProviderId;
  base_url: string;
  model: string;
  api_key_set: boolean;
  api_key_masked: string;
  providers: LlmProviderMeta[];
  updated_at?: string | null;
};

export type HitTestListItem = {
  id: number;
  query: string;
  source: string;
  clearance: number;
  conversation_id?: number | null;
  injected?: number;
  vector_hits?: number;
  keyword_hits?: number;
  created_at?: string | null;
};

export type HitTestInjected = {
  rank?: number;
  chunk_id: number;
  doc_id: number;
  title: string;
  classification?: number;
  score: number;
  channels: string[];
  is_table?: boolean;
  table_full_inject?: boolean;
  page_no?: number | null;
  content?: string;
  preview?: string;
};

export type HitTestDetail = {
  id: number;
  query: string;
  source: string;
  clearance: number;
  workspace_id: number;
  conversation_id?: number | null;
  created_at?: string | null;
  context_snapshot: {
    debug?: {
      vector_ids?: number[];
      keyword_ids?: number[];
      fused_ids?: number[];
      rrf_k?: number;
    };
    meta?: {
      vector_hits?: number;
      keyword_hits?: number;
      fused?: number;
      injected?: number;
      rrf_k?: number;
      table_full_inject?: boolean;
      table_hits?: number;
      inject_order?: string;
    };
    injected?: HitTestInjected[];
  };
};

export type EvalSetItem = {
  id: number;
  name: string;
  version: string;
  description?: string | null;
  case_count: number;
  created_at?: string | null;
  last_run?: EvalRunBrief | null;
};

export type EvalRunBrief = {
  id: number;
  set_id: number;
  status: string;
  case_count: number;
  passed_count: number;
  metrics?: Record<string, number | string>;
  error_message?: string | null;
  started_at?: string | null;
  finished_at?: string | null;
};

export type EvalRunItem = {
  id: number;
  case_id: number;
  question: string;
  answer: string;
  hit_doc_titles: string[];
  scores: Record<string, number>;
  passed: boolean;
  latency_ms: number;
};

export type EvalRunDetail = EvalRunBrief & {
  items: EvalRunItem[];
};

export type EvalSchedulerStatus = {
  enabled: boolean;
  mode: string;
  last_retire_date?: string | null;
  last_eval_date?: string | null;
  tick?: number;
  jobs?: {
    retire?: Record<string, unknown> | null;
    nightly_eval?: Record<string, unknown> | null;
  };
  config?: {
    scheduler_enabled?: boolean;
    retire_interval_hours?: number;
    eval_nightly_hour?: number;
    scheduler_timezone?: string;
    stub_fast?: boolean;
  };
};

export type EvalDashboard = {
  series: EvalRunBrief[];
  latest?: EvalRunBrief | null;
  previous?: EvalRunBrief | null;
  delta?: Record<string, number | null>;
  run_count: number;
};
