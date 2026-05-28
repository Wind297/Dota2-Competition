import { createRouter, createWebHistory } from "vue-router";
import { TOKEN_KEY } from "@/api";

import LoginView from "@/views/LoginView.vue";
import PlayersView from "@/views/PlayersView.vue";
import MatchesView from "@/views/MatchesView.vue";
import MatchDetailView from "@/views/MatchDetailView.vue";
import RankingsView from "@/views/RankingsView.vue";

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: "/login", name: "login", component: LoginView, meta: { public: true } },
    { path: "/", name: "players", component: PlayersView },
    { path: "/matches", name: "matches", component: MatchesView },
    { path: "/matches/:id", name: "match-detail", component: MatchDetailView, props: true },
    { path: "/rankings", name: "rankings", component: RankingsView },
  ],
});

router.beforeEach((to) => {
  const token = localStorage.getItem(TOKEN_KEY);

  if (to.meta.public) {
    if (token && to.name === "login") return { path: "/" };
    return true;
  }

  if (!token) return { path: "/login", query: { redirect: to.fullPath } };
  return true;
});

export default router;
