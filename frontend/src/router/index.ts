import { createRouter, createWebHistory } from "vue-router";
import ChatView from "@/modules/chat/ChatView.vue";
import KnowledgeView from "@/modules/knowledge/KnowledgeView.vue";
import LoginView from "@/modules/auth/LoginView.vue";
import AuditView from "@/modules/governance/AuditView.vue";
import HitTestView from "@/modules/governance/HitTestView.vue";
import GovernanceHub from "@/modules/governance/GovernanceHub.vue";
import EvalView from "@/modules/governance/EvalView.vue";
import SettingsView from "@/modules/settings/SettingsView.vue";
import { isLoggedIn } from "@/shared/auth";

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: "/login", name: "login", component: LoginView, meta: { public: true } },
    { path: "/", name: "chat", component: ChatView },
    { path: "/knowledge", name: "knowledge", component: KnowledgeView },
    { path: "/governance", name: "governance", component: GovernanceHub },
    { path: "/audit", name: "audit", component: AuditView },
    { path: "/hit-test", name: "hit-test", component: HitTestView },
    { path: "/eval", name: "eval", component: EvalView },
    { path: "/settings", name: "settings", component: SettingsView },
  ],
});

router.beforeEach((to) => {
  if (to.meta.public) return true;
  if (!isLoggedIn()) return { path: "/login", query: { redirect: to.fullPath } };
  return true;
});

export default router;
