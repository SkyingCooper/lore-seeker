# 前端设计

## 页面结构

```
/login              登录页（游客 / 注册 / 登录）
/browse             浏览页（搜索入口 + 报告卡片列表）
/browse/:reportId   报告阅读页（左侧 TOC + 右侧 Markdown）
/reports            报告历史列表页
/settings           设置页（主题管理 + 偏好编辑）
```

未登录时访问 `/browse` 等需要认证的路由，路由守卫自动触发游客登录（浏览器指纹），无感知跳转。

## 组件设计

### MainLayout

侧边栏导航，包含：浏览、报告、设置三个入口，底部显示用户身份（游客/用户ID前8位），游客显示"注册/登录"按钮。

### LoginView

支持三种操作：
1. 游客继续（浏览器指纹自动登录）
2. 注册（邮箱 + 密码）
3. 登录（已注册用户）

### BrowseView

- 顶部搜索栏：查询输入 + 搜索模式选择（API / 爬虫 / 混合）+ 启动按钮
- 任务状态条：显示当前任务 ID 和状态，3 秒轮询
- 报告卡片列表：标题、摘要、日期、质量分，点击进入阅读页

### ReportView（核心阅读体验）

VitePress 风格双栏布局：
- 左侧：固定 TOC 导航，`level-2` 加粗，`level-3` 缩进，点击平滑滚动
- 右侧：`MdPreview`（md-editor-v3）渲染 Markdown，Shiki 代码高亮

```
┌──────────────┬──────────────────────────────────────┐
│   目录        │  # 文档标题                           │
│              │                                       │
│  ## 章节一   │  ## 章节一                             │
│    ### 小节  │  内容...                               │
│  ## 章节二   │                                       │
│              │  ### 小节                              │
│              │  内容...                               │
└──────────────┴──────────────────────────────────────┘
```

### SettingsView

两个区块：
1. **主题管理**：列表展示已有主题，表单新增（名称、描述、目标网站、搜索模式）
2. **个性化偏好**：JSON 编辑器展示 Agent 总结的偏好，用户可手动修改

## 状态管理

使用 Pinia，当前只有一个 store：

**`auth.ts`**：
- `token`、`userId`、`isGuest` 持久化到 `localStorage`
- `guestLogin()`：调用 FingerprintJS 获取指纹，请求 `/auth/guest`
- `register()` / `login()` / `logout()`
- 初始化时自动从 localStorage 恢复 token 并设置 axios 默认 Header

## API 客户端

`src/api/client.ts`：axios 实例，`baseURL='/'`，通过 Vite proxy 转发到后端。

Token 注入：在 `auth.ts` 的 `setAuth()` 中直接设置 `api.defaults.headers.common['Authorization']`。

## 相关文件

- `frontend/src/router/index.ts` — 路由定义 + 守卫
- `frontend/src/stores/auth.ts` — 认证状态
- `frontend/src/api/client.ts` — axios 实例
- `frontend/src/layouts/MainLayout.vue`
- `frontend/src/views/` — 各页面组件

---

## 2025-05-27 — 初始设计

**背景**：确定前端页面结构和核心阅读体验。

**决策**：
- 使用 `md-editor-v3` 的 `MdPreview` 组件（只读模式），不引入完整编辑器，减少包体积
- TOC 点击滚动使用原生 `scrollIntoView`，不引入额外滚动库
- 任务状态轮询间隔 3 秒，在 `BrowseView` 组件内管理，任务完成后自动清除定时器

**放弃的方案**：
- VitePress 直接集成：需要 SSG 构建流程，与 Vue SPA 架构不兼容
- 自己实现 Markdown 渲染：工作量大，md-editor-v3 已提供完整方案

**待解决**：
- 任务状态推送依赖轮询，后续升级为 WebSocket
- 报告阅读页未实现内联问答（在报告页直接提问）

**影响范围**：`frontend/src/` 所有文件
