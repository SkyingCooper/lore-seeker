import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

let guestLoginPromise: Promise<void> | null = null

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', redirect: '/browse' },
    { path: '/login', component: () => import('@/views/LoginView.vue') },
    {
      path: '/',
      component: () => import('@/layouts/MainLayout.vue'),
      meta: { requiresAuth: true },
      children: [
        { path: 'browse', component: () => import('@/views/BrowseView.vue') },
        { path: 'browse/:reportId', component: () => import('@/views/ReportView.vue') },
        { path: 'chat', component: () => import('@/views/ChatView.vue') },
        { path: 'community', component: () => import('@/views/CommunityView.vue') },
        { path: 'inbox', component: () => import('@/views/InboxView.vue') },
        { path: 'help', component: () => import('@/views/HelpView.vue') },
        { path: 'profile', component: () => import('@/views/ProfileView.vue') },
        { path: 'reports', component: () => import('@/views/ReportsView.vue') },
        { path: 'settings', component: () => import('@/views/SettingsView.vue') },
        { path: 'tasks', component: () => import('@/views/TasksView.vue') },
        { path: 'tasks/new', component: () => import('@/views/TaskCreateView.vue') },
        { path: 'tasks/:id', component: () => import('@/views/TaskDetailView.vue') },
        { path: 'trash', component: () => import('@/views/TrashView.vue') },
      ],
    },
  ],
})

router.beforeEach(async (to) => {
  if (!to.meta.requiresAuth) return true
  const auth = useAuthStore()

  // 游客会话不会持有 access token。刷新页面时如果本地已经有游客 userId，
  // 直接放行，避免每次进入工作台都等待 /auth/guest 导致首屏空白。
  if (auth.token || (auth.isGuest && auth.userId)) {
    return true
  }

  if (!auth.token) {
    guestLoginPromise ??= auth.guestLogin().finally(() => {
      guestLoginPromise = null
    })
    await guestLoginPromise
  }
  return true
})

export default router
