<template>
  <div class="layout">
    <nav class="sidebar">
      <div class="logo">Lore Seeker</div>
      <router-link to="/browse">浏览</router-link>
      <router-link to="/reports">报告</router-link>
      <router-link to="/settings">设置</router-link>
      <div class="spacer" />
      <span class="user-badge">{{ auth.isGuest ? '游客' : auth.userId?.slice(0, 8) }}</span>
      <button v-if="auth.isGuest" @click="$router.push('/login')">注册/登录</button>
      <button v-else @click="auth.logout()">退出</button>
    </nav>
    <main class="content">
      <router-view />
    </main>
  </div>
</template>

<script setup lang="ts">
import { useAuthStore } from '@/stores/auth'
const auth = useAuthStore()
</script>

<style scoped>
.layout { display: flex; height: 100vh; }
.sidebar {
  width: 200px; padding: 24px 16px; background: #1a1a2e;
  color: #e0e0e0; display: flex; flex-direction: column; gap: 12px;
}
.logo { font-size: 18px; font-weight: 700; color: #7c83fd; margin-bottom: 16px; }
.sidebar a { color: #c0c0d0; text-decoration: none; padding: 8px 12px; border-radius: 6px; }
.sidebar a.router-link-active { background: #2d2d4e; color: #fff; }
.spacer { flex: 1; }
.user-badge { font-size: 12px; color: #888; }
.content { flex: 1; overflow: auto; background: #f8f9fa; }
</style>
