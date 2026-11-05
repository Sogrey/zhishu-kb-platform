<template>
  <div class="page">
    <header class="hero">
      <h1>设置</h1>
      <p>配置问答推理渠道：DeepSeek 在线、本地 Ollama、本地 llama.cpp，或 Stub 模板。</p>
    </header>

    <section class="card" v-if="form">
      <h2>推理渠道</h2>

      <label class="field">
        <span>渠道</span>
        <select v-model="form.provider" @change="onProviderChange">
          <option v-for="p in form.providers" :key="p.id" :value="p.id">
            {{ p.label }}
          </option>
        </select>
      </label>

      <template v-if="form.provider !== 'stub'">
        <label class="field">
          <span>Base URL</span>
          <input v-model="form.base_url" type="url" spellcheck="false" placeholder="https://… 或 http://127.0.0.1:…" />
        </label>

        <label v-if="needsKey" class="field">
          <span>
            API Key
            <em v-if="form.api_key_set && !apiKeyDraft">已保存 {{ form.api_key_masked }}</em>
          </span>
          <input
            v-model="apiKeyDraft"
            type="password"
            autocomplete="off"
            :placeholder="form.api_key_set ? '留空则保留原 Key' : '粘贴 DeepSeek API Key'"
          />
        </label>

        <div class="field model-row">
          <span>模型</span>
          <div class="model-controls">
            <select
              v-if="modelOptions.length"
              v-model="form.model"
              class="model-select"
            >
              <option v-for="m in modelOptions" :key="m.id" :value="m.id">
                {{ m.name }}
              </option>
            </select>
            <input
              v-model="form.model"
              type="text"
              spellcheck="false"
              :placeholder="canListModels ? '可手填或点拉取列表' : '模型名'"
            />
            <button
              v-if="canListModels"
              type="button"
              class="ghost"
              :disabled="listing"
              @click="refreshModels"
            >
              {{ listing ? "拉取中…" : "拉取模型列表" }}
            </button>
          </div>
          <p v-if="listHint" class="hint">{{ listHint }}</p>
        </div>
      </template>

      <p v-else class="hint">Stub 模式不调用外部模型，回答由检索片段模板生成（适合无 GPU 演示）。</p>

      <div class="actions">
        <button type="button" class="primary" :disabled="saving" @click="onSave">
          {{ saving ? "保存中…" : "保存" }}
        </button>
        <button
          v-if="form.provider !== 'stub'"
          type="button"
          class="ghost"
          :disabled="testing"
          @click="onTest"
        >
          {{ testing ? "测试中…" : "连通测试" }}
        </button>
      </div>
      <p v-if="testReply" class="ok">{{ testReply }}</p>
    </section>

    <p v-else-if="loadError" class="err">{{ loadError }}</p>
    <p v-else class="hint">加载中…</p>
  </div>
</template>

<script setup lang="ts">
/**
 * 管理员：推理渠道设置（DeepSeek / Ollama / llama.cpp / Stub）。
 */
import { computed, onMounted, ref } from "vue";
import { message } from "ant-design-vue";
import {
  getLlmSettings,
  listLlmModels,
  saveLlmSettings,
  testLlmSettings,
} from "@/api/client";
import type { LlmProviderId, LlmSettings } from "@/api/types";

const form = ref<LlmSettings | null>(null);
const apiKeyDraft = ref("");
const modelOptions = ref<{ id: string; name: string }[]>([]);
const listing = ref(false);
const saving = ref(false);
const testing = ref(false);
const loadError = ref("");
const listHint = ref("");
const testReply = ref("");

const meta = computed(() =>
  form.value?.providers.find((p) => p.id === form.value?.provider),
);
const needsKey = computed(() => Boolean(meta.value?.needs_key));
const canListModels = computed(() => Boolean(meta.value?.list_models));

async function load() {
  loadError.value = "";
  try {
    form.value = await getLlmSettings();
    apiKeyDraft.value = "";
    modelOptions.value = [];
    listHint.value = "";
    if (canListModels.value) {
      void refreshModels(false);
    }
  } catch (e: any) {
    loadError.value = e?.response?.data?.detail || e?.message || "加载失败（需管理员）";
  }
}

function onProviderChange() {
  if (!form.value) return;
  const p = form.value.providers.find((x) => x.id === form.value!.provider);
  if (p?.default_base_url) form.value.base_url = p.default_base_url;
  if (form.value.provider === "stub") {
    form.value.model = "";
    modelOptions.value = [];
    listHint.value = "";
    return;
  }
  if (!form.value.model && form.value.provider === "deepseek") {
    form.value.model = "deepseek-chat";
  }
  modelOptions.value = [];
  if (canListModels.value) void refreshModels(false);
}

async function refreshModels(toast = true) {
  if (!form.value || !canListModels.value) return;
  listing.value = true;
  listHint.value = "";
  try {
    const data = await listLlmModels({
      provider: form.value.provider,
      base_url: form.value.base_url,
      api_key: apiKeyDraft.value || null,
    });
    modelOptions.value = data.items || [];
    if (!modelOptions.value.length) {
      listHint.value = "未拉到模型，请检查服务是否启动、地址是否正确。";
    } else if (
      form.value.model &&
      !modelOptions.value.some((m) => m.id === form.value!.model)
    ) {
      // 当前模型不在列表时保留手填，并追加选项
      modelOptions.value = [
        { id: form.value.model, name: form.value.model },
        ...modelOptions.value,
      ];
    } else if (!form.value.model && modelOptions.value[0]) {
      form.value.model = modelOptions.value[0].id;
    }
    if (toast) message.success(`已拉取 ${modelOptions.value.length} 个模型`);
  } catch (e: any) {
    listHint.value = e?.response?.data?.detail || e?.message || "拉取失败";
    if (toast) message.error(listHint.value);
  } finally {
    listing.value = false;
  }
}

async function onSave() {
  if (!form.value) return;
  saving.value = true;
  testReply.value = "";
  try {
    const body: {
      provider: LlmProviderId;
      base_url: string;
      model: string;
      api_key?: string | null;
    } = {
      provider: form.value.provider,
      base_url: form.value.base_url,
      model: form.value.model,
    };
    if (needsKey.value) {
      body.api_key = apiKeyDraft.value.trim() ? apiKeyDraft.value.trim() : null;
    }
    form.value = await saveLlmSettings(body);
    apiKeyDraft.value = "";
    message.success("已保存");
  } catch (e: any) {
    message.error(e?.response?.data?.detail || e?.message || "保存失败");
  } finally {
    saving.value = false;
  }
}

async function onTest() {
  if (!form.value) return;
  testing.value = true;
  testReply.value = "";
  try {
    // 先落库再测，避免测到旧配置
    const body: {
      provider: LlmProviderId;
      base_url: string;
      model: string;
      api_key?: string | null;
    } = {
      provider: form.value.provider,
      base_url: form.value.base_url,
      model: form.value.model,
    };
    if (needsKey.value) {
      body.api_key = apiKeyDraft.value.trim() ? apiKeyDraft.value.trim() : null;
    }
    form.value = await saveLlmSettings(body);
    apiKeyDraft.value = "";
    const r = await testLlmSettings();
    testReply.value = r.reply
      ? `连通成功（${r.provider}/${r.model}）：${r.reply}`
      : r.detail || "连通成功";
    message.success("连通成功");
  } catch (e: any) {
    message.error(e?.response?.data?.detail || e?.message || "连通失败");
  } finally {
    testing.value = false;
  }
}

onMounted(() => {
  void load();
});
</script>

<style lang="less" scoped>
.page {
  max-width: 720px;
  padding: 8px 16px 48px;
  animation: zs-rise 0.45s ease both;
}
.hero {
  margin-bottom: 20px;
  h1 {
    margin: 0 0 6px;
    font-size: 28px;
  }
  p {
    margin: 0;
    color: var(--zs-muted);
    line-height: 1.55;
  }
}
.card {
  padding: 20px 22px 24px;
  border: 1px solid var(--zs-line);
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.72);

  h2 {
    margin: 0 0 16px;
    font-size: 16px;
  }
}
.field {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-bottom: 14px;

  > span {
    font-size: 12px;
    color: var(--zs-muted);
    letter-spacing: 0.04em;

    em {
      font-style: normal;
      margin-left: 8px;
      color: var(--zs-accent-deep);
    }
  }

  input,
  select {
    border: 1px solid var(--zs-line);
    border-radius: 10px;
    padding: 10px 12px;
    font: inherit;
    background: #fff;
  }
}
.model-controls {
  display: grid;
  grid-template-columns: 1fr;
  gap: 8px;

  @media (min-width: 640px) {
    grid-template-columns: minmax(0, 1fr) auto;
    .model-select {
      grid-column: 1 / -1;
    }
  }
}
.actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 8px;
}
.primary,
.ghost {
  border-radius: 999px;
  padding: 8px 18px;
  font: inherit;
  cursor: pointer;
}
.primary {
  border: none;
  background: var(--zs-accent-deep, #1f6b4a);
  color: #fff;
}
.ghost {
  border: 1px solid var(--zs-line);
  background: #fff;
  color: var(--zs-ink);
}
.hint,
.err,
.ok {
  font-size: 13px;
  line-height: 1.5;
}
.hint {
  color: var(--zs-muted);
  margin: 4px 0 0;
}
.err {
  color: #b42318;
}
.ok {
  margin-top: 12px;
  color: var(--zs-accent-deep);
}
button:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}
</style>
