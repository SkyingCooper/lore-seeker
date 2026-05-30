<template>
  <n-layout has-sider class="min-h-screen bg-[radial-gradient(circle_at_top_left,_rgba(110,137,166,0.08),_transparent_24%),var(--ls-bg)]">
    <n-layout-sider
      bordered
      collapse-mode="width"
      :collapsed="collapsed"
      :collapsed-width="86"
      :width="312"
      content-style="padding: 6px 8px 10px 8px;"
      class="bg-[linear-gradient(180deg,#f2eadf_0%,#efe7db_100%)]"
    >
      <div class="flex h-full flex-col">
        <div v-if="!collapsed" class="mb-1 flex h-[76px] items-center gap-0 pl-0 pr-0">
          <div class="flex shrink-0 items-center">
            <img :src="logoMark" alt="Lore Seeker" class="block h-[67px] w-auto max-w-[67px] object-contain" />
            <img :src="logoWord" alt="Lore Seeker" class="block h-[38px] w-auto -ml-4 translate-y-[5px] object-contain" />
          </div>

          <div class="ml-auto flex shrink-0 items-center justify-end">
            <n-popover trigger="click" placement="bottom-start" class="w-[340px] rounded-[24px] p-0">
              <template #trigger>
                <button
                  class="flex shrink-0 items-center gap-0 rounded-[18px] px-0 py-0 text-left transition"
                >
                  <div class="flex h-12 w-12 shrink-0 items-center justify-center rounded-full bg-[#d8beb6] text-[20px] font-semibold text-[#4f4338] shadow-[0_6px_18px_rgba(126,112,93,0.16)]">
                    {{ avatarFallback }}
                  </div>
                  <ChevronDown :size="16" class="-ml-0.5 shrink-0 text-[#8e8172]" />
                </button>
              </template>

            <div class="overflow-hidden rounded-[24px] bg-white">
              <div class="border-b border-[#ece4d8] px-6 py-5">
                <div class="flex items-start gap-4">
                  <div class="flex h-14 w-14 shrink-0 items-center justify-center rounded-2xl bg-[#d8beb6] text-[24px] font-semibold text-[#4f4338] shadow-[0_6px_18px_rgba(126,112,93,0.16)]">
                    {{ avatarFallback }}
                  </div>
                  <div class="min-w-0 flex-1">
                    <div class="truncate text-2xl font-semibold text-[#2f3238]">{{ displayName }}</div>
                    <div class="mt-1 text-sm text-[#5f564c]">
                      {{ auth.isGuest ? copy.guestPrompt : copy.memberPlan }}
                    </div>
                  </div>
                </div>

                <div v-if="!auth.isGuest" class="mt-5 flex gap-3">
                  <n-button secondary class="rounded-2xl" @click="router.push('/settings')">
                    <template #icon>
                      <Settings2 :size="17" />
                    </template>
                    {{ copy.settings }}
                  </n-button>
                  <n-button secondary class="rounded-2xl" @click="showProfile()">
                    <template #icon>
                      <UserRound :size="17" />
                    </template>
                    {{ copy.profile }}
                  </n-button>
                </div>
              </div>

              <div class="px-6 py-5">
                <div class="space-y-2 border-t border-[#efe7dc] pt-4">
                  <template v-if="auth.isGuest">
                    <button
                      class="flex w-full items-center gap-3 rounded-2xl px-3 py-3 text-left text-[15px] font-medium text-[#2f3238] transition hover:bg-[#f8f5ef]"
                      @click="router.push('/login')"
                    >
                      <UserPlus :size="18" />
                      <span>{{ copy.register }}</span>
                    </button>
                    <button
                      class="flex w-full items-center gap-3 rounded-2xl px-3 py-3 text-left text-[15px] font-medium text-[#2f3238] transition hover:bg-[#f8f5ef]"
                      @click="router.push('/login')"
                    >
                      <LogIn :size="18" />
                      <span>{{ copy.login }}</span>
                    </button>
                  </template>

                  <template v-else>
                    <button
                      class="flex w-full items-center gap-3 rounded-2xl px-3 py-3 text-left text-[15px] font-medium text-[#2f3238] transition hover:bg-[#f8f5ef]"
                      @click="showProfile()"
                    >
                      <UserRound :size="18" />
                      <span>{{ copy.accountInfo }}</span>
                    </button>
                    <button
                      class="flex w-full items-center gap-3 rounded-2xl px-3 py-3 text-left text-[15px] font-medium text-[#2f3238] transition hover:bg-[#f8f5ef]"
                      @click="showCommunity()"
                    >
                      <Users :size="18" />
                      <span>{{ copy.community }}</span>
                    </button>
                    <button
                      class="flex w-full items-center gap-3 rounded-2xl px-3 py-3 text-left text-[15px] font-medium text-[#2f3238] transition hover:bg-[#f8f5ef]"
                      @click="router.push('/settings')"
                    >
                      <Settings2 :size="18" />
                      <span>{{ copy.settings }}</span>
                    </button>
                  </template>

                  <div class="flex items-center gap-2 border-t border-[#efe7dc] pt-4">
                    <div class="flex items-center gap-2 rounded-2xl bg-[#f8f3ea] p-1">
                      <button
                        v-for="option in localeOptions"
                        :key="option.value"
                        class="rounded-xl px-3 py-2 text-sm font-medium transition"
                        :class="locale.locale === option.value ? 'bg-white text-[#2f3238] shadow-[0_8px_24px_rgba(100,120,147,0.12)]' : 'text-[#5f564c] hover:bg-white/60'"
                        @click="handleLocaleChange(option.value)"
                      >
                        {{ option.label }}
                      </button>
                    </div>

                    <button
                      v-if="!auth.isGuest"
                      class="ml-auto flex h-11 w-11 items-center justify-center rounded-2xl border border-[#e7dfd3] text-[#6f665b] transition hover:bg-[#f8f5ef]"
                      @click="handleLogout()"
                    >
                      <LogOut :size="18" />
                    </button>
                  </div>
                </div>
              </div>
            </div>
            </n-popover>
          </div>
        </div>

        <div v-else class="mb-1 flex flex-col items-center gap-2">
          <n-tooltip placement="right">
            <template #trigger>
              <button
                class="flex h-16 w-16 items-center justify-center rounded-[18px] transition"
                @click="expandSidebar()"
              >
                <img :src="logoMarkCollapsed" alt="Lore Seeker" class="block h-14 w-auto max-w-[56px] object-contain" />
              </button>
            </template>
            {{ copy.expandSidebar }}
          </n-tooltip>
        </div>

        <div class="mb-1 px-2" :class="collapsed ? '' : ''">
          <div
            :class="
              collapsed
                ? 'flex min-h-[208px] flex-col items-center gap-2 px-2.5 py-2.5'
                : 'flex items-center gap-3'
            "
          >
            <n-tooltip v-for="item in toolbarItems" :key="item.key" :placement="collapsed ? 'right' : 'bottom'">
              <template #trigger>
                <button
                  class="flex items-center justify-center rounded-full bg-white/58 text-[#73685c] transition hover:bg-white/85 hover:text-[#384a61]"
                  :class="
                    [
                      collapsed
                        ? item.key === 'locale'
                          ? 'mt-auto h-11 w-11 text-[#5a6f87]'
                          : 'h-12 w-12'
                        : item.key === 'home'
                          ? 'h-12 w-12 shrink-0 self-center'
                          : 'h-11 w-11 shrink-0 self-center',
                      toolbarActiveKey === item.activeKey ? 'bg-[#f4efe6] text-[#2f4257] shadow-[0_10px_28px_rgba(115,132,154,0.12)]' : '',
                    ]
                  "
                  @click="handleToolbarAction(item.key)"
                >
                  <component :is="item.icon" :size="collapsed ? 21 : item.key === 'home' ? 22 : 20" />
                </button>
              </template>
              {{ item.label }}
            </n-tooltip>

            <n-tooltip :placement="collapsed ? 'right' : 'bottom'">
              <template #trigger>
                <button
                  class="flex h-11 w-11 shrink-0 items-center justify-center rounded-full border border-white/70 bg-white/78 text-[#6f665b] shadow-[0_10px_24px_rgba(148,131,105,0.08)] transition hover:bg-white"
                  @click="collapsed = !collapsed"
                >
                <PanelRightOpen v-if="collapsed" :size="18" />
                <ChevronsLeft v-else :size="18" />
                </button>
              </template>
              {{ collapsed ? copy.expandSidebar : copy.collapseSidebar }}
            </n-tooltip>
          </div>
        </div>

        <div v-if="!collapsed" class="mb-2 px-3">
          <div class="space-y-1">
            <button
              v-for="item in utilityEntries"
              :key="item.key"
              class="flex w-full items-center gap-4 rounded-2xl px-3 py-2 text-left text-[15px] text-[#5d6470] transition hover:bg-white/55"
              @click="handleUtilityAction(item.key)"
            >
              <component :is="item.icon" :size="20" class="text-[#8f8578]" />
              <span class="truncate font-semibold">{{ item.label }}</span>
            </button>
          </div>
        </div>

        <div v-if="!collapsed" class="mb-2 px-3">
          <div class="mb-1.5 flex items-center justify-between gap-3 rounded-2xl bg-white/40 px-3 py-2">
            <button class="flex items-center gap-3 text-left" @click="foldersExpanded = !foldersExpanded">
              <ChevronDown :size="16" class="text-[#9b907f] transition" :class="foldersExpanded ? '' : '-rotate-90'" />
              <span class="text-[15px] font-semibold text-[#5d5347]">{{ copy.myCategories }}</span>
            </button>

            <n-popover trigger="click" placement="bottom-end" class="rounded-2xl p-0">
              <template #trigger>
                <button class="flex h-8 w-8 items-center justify-center rounded-full text-[#94897a] transition hover:bg-white/70 hover:text-[#5f738e]">
                  <MoreHorizontal :size="18" />
                </button>
              </template>

              <div class="min-w-[180px] rounded-2xl bg-white p-2">
                <button
                  class="flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-left text-sm text-[#4f5a67] transition hover:bg-[#f7f1e8]"
                  @click="handleFolderMenuAction('add')"
                >
                  <FolderPlus :size="16" />
                  <span>{{ copy.addFolder }}</span>
                </button>
              </div>
            </n-popover>
          </div>

          <div v-if="foldersExpanded" class="space-y-1">
            <button
              v-for="item in workspaceEntries"
              :key="item.key"
              class="flex w-full items-center gap-4 rounded-2xl px-3 py-2 text-left text-[15px] text-[#5d6470] transition hover:bg-white/55"
              @click="handleToolbarAction(item.actionKey)"
            >
              <component :is="item.icon" :size="18" class="text-[#9a9187]" />
              <span class="truncate font-medium">{{ item.label }}</span>
            </button>
          </div>
        </div>

        <div class="mt-auto flex items-center gap-3 px-2">
          <button
            v-if="!collapsed"
            class="flex min-w-0 flex-1 items-center gap-3 rounded-full border border-white/75 bg-white/72 px-4 py-3 text-left shadow-[0_14px_36px_rgba(148,131,105,0.08)] backdrop-blur-sm transition hover:bg-white"
            @click="handleToolbarAction('chat')"
          >
            <div class="flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl bg-[#f7f0e7] text-[#6b7f98]">
              <MessageCircleMore :size="20" />
            </div>
            <span class="truncate text-[15px] font-semibold text-[#343841]">{{ copy.startChat }}</span>
          </button>

          <n-tooltip :placement="collapsed ? 'right' : 'top'">
            <template #trigger>
              <button
                class="flex h-11 w-11 shrink-0 items-center justify-center rounded-full border border-white/75 bg-white/72 text-[#7e7468] shadow-[0_14px_36px_rgba(148,131,105,0.08)] backdrop-blur-sm transition hover:bg-white hover:text-[#556d88]"
                @click="handleToolbarAction('search')"
              >
                <SquarePen :size="22" />
              </button>
            </template>
            {{ copy.createTask }}
          </n-tooltip>
        </div>
      </div>
    </n-layout-sider>

    <n-layout-content content-style="min-height: 100vh;">
      <div class="mx-auto min-h-screen max-w-6xl px-7 py-8 lg:px-11">
        <router-view />
      </div>
    </n-layout-content>
  </n-layout>
</template>

<script setup lang="ts">
// 文件说明：
// MainLayout 提供整个前端工作区的统一外壳：状态栏、工具栏、工作区列表、快捷动作和当前会话信息。
// 这里将左上角拆成两层：第一层是状态栏（身份入口 + 折叠按钮），第二层是工具栏（主页、对话、收件箱、搜索、语言切换）。
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useMessage, NButton, NLayout, NLayoutContent, NLayoutSider, NPopover, NTooltip } from 'naive-ui'
import {
  ChevronDown,
  Home,
  Inbox,
  Languages,
  ChevronsLeft,
  CircleHelp,
  FolderPlus,
  LogIn,
  LogOut,
  MessageCircleMore,
  MoreHorizontal,
  PanelTopOpen,
  PanelRightOpen,
  Search,
  Settings2,
  SquarePen,
  Sparkles,
  Trash2,
  UserPlus,
  UserRound,
  Users,
} from '@lucide/vue'
import { useAuthStore } from '@/stores/auth'
import logoMark from '@/assets/logo-book.avif'
import logoMarkCollapsed from '@/assets/logo-book-anti.avif'
import logoWord from '@/assets/logo-word.avif'
import { type Locale, useLocaleStore } from '@/stores/locale'

const auth = useAuthStore()
const locale = useLocaleStore()
const route = useRoute()
const router = useRouter()
const message = useMessage()
const collapsed = ref(false)
const foldersExpanded = ref(true)

const copy = computed(() =>
  locale.isChinese
    ? {
        guestPlan: '免费版 · 游客会话',
        guestPrompt: '快来注册登录吧',
        memberPlan: '正式账号 · 已登录',
        settings: '设置',
        accountInfo: '账户信息',
        community: '协作社区',
        profile: '个人信息',
        guestEmail: '游客',
        registerWorkspace: '注册 / 登录',
        register: '注册',
        login: '登录',
        logout: '登出',
        workspace: 'Workspace',
        guestSession: '游客会话',
        memberSession: '已登录用户',
        guestHint: '当前使用浏览器指纹登录。',
        userIdLabel: '用户 ID',
        signIn: '注册 / 登录',
        signOut: '退出当前会话',
        startChat: '开启对话',
        createTask: '创建任务',
        guestBadge: '游客会话',
        memberBadge: '已登录',
        browse: '主页',
        chat: '对话',
        inbox: '收件箱',
        search: '搜索',
        language: '中英切换',
        expandSidebar: '展开侧边栏',
        collapseSidebar: '收缩侧边栏',
        reports: '报告',
        settingsNav: '设置',
        myCategories: '我的分类',
        addFolder: '新增分类',
        deleteFolder: '删除分类',
        tasks: '任务',
        knowledgeBase: '知识库',
        help: '帮助',
        trash: '垃圾箱',
        desktopNote: '从电脑桌面端开始吧！',
        weeklyTodo: 'Weekly To-do List',
        monthlyBudget: 'Monthly Budget',
        folderAddPending: '添加文件夹能力还没接后端，先保留入口。',
        folderDeletePending: '删除文件夹能力还没接后端，先保留入口。',
        helpPending: '帮助页还没接入，先保留入口。',
        trashPending: '垃圾箱还没接入，先保留入口。',
        communityPending: '协作社区还没接入，先保留入口。',
      }
    : {
        guestPlan: 'Free plan · Guest session',
        guestPrompt: 'Sign in to continue',
        memberPlan: 'Member account · Signed in',
        settings: 'Settings',
        accountInfo: 'Account info',
        community: 'Community',
        profile: 'Profile',
        guestEmail: 'Guest',
        registerWorkspace: 'Register / Sign in',
        register: 'Register',
        login: 'Login',
        logout: 'Logout',
        workspace: 'Workspace',
        guestSession: 'Guest session',
        memberSession: 'Signed-in member',
        guestHint: 'You are browsing as a guest.',
        userIdLabel: 'User ID',
        signIn: 'Register / Sign in',
        signOut: 'Sign out',
        startChat: 'Start chat',
        createTask: 'Create task',
        guestBadge: 'Guest session',
        memberBadge: 'Signed in',
        browse: 'Home',
        chat: 'Chat',
        inbox: 'Inbox',
        search: 'Search',
        language: 'Language',
        expandSidebar: 'Expand sidebar',
        collapseSidebar: 'Collapse sidebar',
        reports: 'Reports',
        settingsNav: 'Settings',
        myCategories: 'My categories',
        addFolder: 'Add category',
        deleteFolder: 'Delete category',
        tasks: 'Tasks',
        knowledgeBase: 'Knowledge base',
        help: 'Help',
        trash: 'Trash',
        desktopNote: 'Start from the desktop workspace',
        weeklyTodo: 'Weekly To-do List',
        monthlyBudget: 'Monthly Budget',
        folderAddPending: 'Add-folder behavior is not wired yet.',
        folderDeletePending: 'Delete-folder behavior is not wired yet.',
        helpPending: 'Help page is not wired yet.',
        trashPending: 'Trash view is not wired yet.',
        communityPending: 'Community is not wired yet.',
      }
)

const activeKey = computed(() => {
  if (route.path.startsWith('/browse')) return '/browse'
  if (route.path.startsWith('/chat')) return '/chat'
  if (route.path.startsWith('/inbox')) return '/inbox'
  if (route.path.startsWith('/profile')) return '/profile'
  if (route.path.startsWith('/reports')) return '/reports'
  if (route.path.startsWith('/settings')) return '/settings'
  return route.path
})

const toolbarActiveKey = computed(() => {
  if (route.path.startsWith('/browse')) return 'home'
  if (route.path.startsWith('/inbox')) return 'inbox'
  return null
})

const toolbarItems = computed(() => [
  { key: 'home', label: copy.value.browse, icon: Home, activeKey: 'home' },
  { key: 'inbox', label: copy.value.inbox, icon: Inbox, activeKey: 'inbox' },
  { key: 'search', label: copy.value.search, icon: Search, activeKey: null },
  { key: 'locale', label: copy.value.language, icon: Languages, activeKey: null },
])

const workspaceEntries = computed(() => [
  { key: 'desktop', label: copy.value.desktopNote, icon: PanelTopOpen, actionKey: 'home' },
  { key: 'weekly', label: copy.value.weeklyTodo, icon: Inbox, actionKey: 'reports' },
  { key: 'monthly', label: copy.value.monthlyBudget, icon: Sparkles, actionKey: 'settings' },
])

const utilityEntries = computed(() => [
  { key: 'tasks', label: copy.value.tasks, icon: SquarePen },
  { key: 'knowledge', label: copy.value.knowledgeBase, icon: PanelTopOpen },
  { key: 'help', label: copy.value.help, icon: CircleHelp },
  { key: 'trash', label: copy.value.trash, icon: Trash2 },
])

const localeOptions = [
  { label: '中文', value: 'zh-CN' },
  { label: 'EN', value: 'en-US' },
]

const displayIdentifier = computed(() => auth.userId?.slice(0, 8) ?? 'guest')
const displayName = computed(() => {
  if (auth.isGuest) return copy.value.guestEmail
  return auth.username || displayIdentifier.value
})
const displayInitial = computed(() => {
  if (auth.isGuest) return 'G'
  return (auth.username || displayIdentifier.value).slice(0, 1).toUpperCase()
})
const avatarFallback = computed(() => {
  if (auth.isGuest) return 'G'
  return (auth.username || displayIdentifier.value).slice(0, 1)
})

async function handleLogout() {
  await auth.logout()
  await auth.guestLogin()
  router.push('/browse')
}

function handleNavigate(key: string) {
  router.push(key)
}

function handleLocaleChange(value: string) {
  locale.setLocale(value as Locale)
}

function toggleLocale() {
  locale.setLocale(locale.isChinese ? 'en-US' : 'zh-CN')
}

function expandSidebar() {
  collapsed.value = false
}

function handleToolbarAction(key: string) {
  if (key === 'locale') {
    toggleLocale()
    return
  }

  if (key === 'home') {
    if (collapsed.value) expandSidebar()
    handleNavigate('/browse')
    return
  }

  if (key === 'chat') {
    handleNavigate('/chat')
    return
  }

  if (key === 'inbox') {
    handleNavigate('/inbox')
    return
  }

  if (key === 'search') {
    if (collapsed.value) expandSidebar()
    handleNavigate('/browse')
    return
  }

  if (key === 'reports') {
    handleNavigate('/reports')
    return
  }

  if (key === 'settings') {
    handleNavigate('/settings')
  }
}

function handleUtilityAction(key: string) {
  if (key === 'tasks') {
    handleToolbarAction('search')
    return
  }

  if (key === 'knowledge') {
    handleToolbarAction('reports')
    return
  }

  if (key === 'help') {
    message.info(copy.value.helpPending)
    return
  }

  if (key === 'trash') {
    message.info(copy.value.trashPending)
  }
}

function handleFolderMenuAction(action: 'add' | 'delete') {
  if (action === 'add') {
    message.info(copy.value.folderAddPending)
    return
  }

  message.info(copy.value.folderDeletePending)
}

function showCommunity() {
  message.info(copy.value.communityPending)
}

function showProfile() {
  router.push('/profile')
}
</script>
