import { ref } from "vue";

export type AuthUser = {
  id: number;
  username: string;
  display_name: string;
  role: string;
  clearance: number;
};

export type WorkspaceItem = {
  id: number;
  name: string;
  role: string;
};

const TOKEN_KEY = "zs_token";
const USER_KEY = "zs_user";
const WS_KEY = "zs_workspace";
const WS_LIST_KEY = "zs_workspaces";

export const tokenRef = ref<string | null>(localStorage.getItem(TOKEN_KEY));
export const userRef = ref<AuthUser | null>(_readJson(USER_KEY));
export const workspaceRef = ref<WorkspaceItem | null>(_readJson(WS_KEY));
export const workspacesRef = ref<WorkspaceItem[]>(_readJson(WS_LIST_KEY) || []);

function _readJson<T>(key: string): T | null {
  try {
    const raw = localStorage.getItem(key);
    return raw ? (JSON.parse(raw) as T) : null;
  } catch {
    return null;
  }
}

export function setSession(token: string, user: AuthUser, workspaces: WorkspaceItem[]) {
  tokenRef.value = token;
  userRef.value = user;
  workspacesRef.value = workspaces;
  localStorage.setItem(TOKEN_KEY, token);
  localStorage.setItem(USER_KEY, JSON.stringify(user));
  localStorage.setItem(WS_LIST_KEY, JSON.stringify(workspaces));

  const prevId = workspaceRef.value?.id;
  const keep = prevId ? workspaces.find((w) => w.id === prevId) : null;
  const ws = keep || workspaces[0] || null;
  workspaceRef.value = ws;
  if (ws) localStorage.setItem(WS_KEY, JSON.stringify(ws));
  else localStorage.removeItem(WS_KEY);
}

export function setWorkspace(ws: WorkspaceItem) {
  workspaceRef.value = ws;
  localStorage.setItem(WS_KEY, JSON.stringify(ws));
}

export function clearSession() {
  tokenRef.value = null;
  userRef.value = null;
  workspaceRef.value = null;
  workspacesRef.value = [];
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
  localStorage.removeItem(WS_KEY);
  localStorage.removeItem(WS_LIST_KEY);
}

export function isLoggedIn() {
  return Boolean(tokenRef.value);
}
