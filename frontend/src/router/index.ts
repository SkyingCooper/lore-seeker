import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

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
  if (!auth.token) {
    await auth.guestLogin()
  }
  return true
})

export default router
