# 前端设计

本文档负责前端技术栈、路由、主布局、状态管理和页面交互细节。系统级架构见 `DESIGN_SUMMARY.md` 和 `overview.md`。

## 1. 技术基线

### 背景

前端需要同时承载工作台导航、搜索任务创建、报告阅读、知识问答、设置和账户管理。界面需要接近 Notion 的高频工具体验，但保留 Lore Seeker 的品牌和研究系统属性。

### 决策

前端使用 Vue 3 + TypeScript + Vite + Tailwind + Naive UI，状态管理使用 Pinia，Markdown 报告使用 `md-editor-v3` 渲染，图标统一使用 `@lucide/vue`。

### 实现要点

| 技术 | 职责 |
|---|---|
| Vue 3 | 页面和组件组织 |
| TypeScript | 前端类型约束 |
| Vite | 本地开发和构建 |
| Tailwind CSS | 页面布局、间距、响应式样式 |
| Naive UI | 表单、弹层、按钮、消息、菜单 |
| Pinia | 认证状态、语言状态 |
| Vue Router | 路由与访问守卫 |
| Axios | API 客户端与 token 刷新 |
| md-editor-v3 | Markdown 报告渲染 |
| @lucide/vue | 工具栏、菜单、列表图标 |

核心目录：

| 路径 | 职责 |
|---|---|
| `src/main.ts` | 应用初始化 |
| `src/App.vue` | Naive Provider 和全局挂载 |
| `src/router/index.ts` | 路由表和访问守卫 |
| `src/layouts/MainLayout.vue` | 工作台主框架 |
| `src/views/` | 页面级组件 |
| `src/stores/` | Pinia store |
| `src/api/client.ts` | Axios 实例 |
| `src/theme/naive.ts` | Naive UI 主题 |
| `src/style.css` | 全局样式和 Markdown 覆盖 |

### 验收标准

- `cd frontend && npm run build` 通过。
- 新页面继续使用 Vue 3 Composition API + TypeScript。
- 通用控件优先使用 Naive UI，图标优先使用 lucide。

## 2. 路由与页面

### 背景

系统从报告浏览扩展为完整工作台，需要清晰的页面归属和认证守卫。

### 决策

`/login` 独立展示；其他页面挂载在 `MainLayout` 下。进入工作台时优先保证存在用户身份，未登录用户通过游客会话进入只读体验。

### 实现要点

| 路由 | 页面 | 职责 |
|---|---|---|
| `/login` | `LoginView` | 注册、登录、游客入口 |
| `/browse` | `BrowseView` | 首页、快速研究搜索 |
| `/browse/:reportId` | `ReportView` | Markdown 报告阅读 |
| `/community` | `CommunityView` | 协作社区入口 |
| `/reports` | `ReportsView` | 报告列表 |
| `/tasks` | `TasksView` | 任务列表 |
| `/tasks/new` | `TaskCreateView` | 创建任务 |
| `/tasks/:id` | `TaskDetailView` | 任务详情、启动、重试 |
| `/settings` | `SettingsView` | 主题和偏好配置 |
| `/profile` | `ProfileView` | 个人信息 |
| `/chat` | `ChatView` | AI 对话入口 |
| `/inbox` | `InboxView` | 收件箱 |
| `/help` | `HelpView` | 使用帮助 |
| `/trash` | `TrashView` | 垃圾箱 |

访问规则：

- 工作台路由进入前检查 `auth` 状态。
- 游客可以浏览公开或只读内容。
- 写操作遇到 `GUEST_FORBIDDEN` 时跳转登录页。

### 验收标准

- 未登录访问工作台时能建立游客身份。
- 游客触发写操作时有明确登录引导。
- 侧边栏主要入口都有明确路由；无后端能力的入口必须给出可执行的替代路径。

## 3. 主布局

### 背景

左侧工作台是系统最高频区域，需要紧凑、图标清晰、可展开收缩，并能承载品牌、工具栏、模块入口和底部任务入口。

### 决策

`MainLayout` 分为状态栏、工具栏、内容层和底部动作区。展开态显示完整品牌与分类；收缩态保留图标导航和任务入口。

### 实现要点

状态栏：

- 展开态品牌使用 `logo-book.avif` 和 `logo-word.avif`。
- 收缩态顶部品牌图使用 `logo-book-anti.avif`。
- 无头像用户显示用户名第一个字母或汉字，游客显示 `G`。
- 默认头像使用偏暖的深底色，并带浅阴影区分背景。
- 头像右侧箭头打开账户弹窗。

账户弹窗：

- 游客展示头像、名称、引导文案、注册、登录、语言切换。
- 注册用户展示头像、名称、账户信息、协作社区、设置、退出登录、语言切换。
- 游客和注册用户使用同一视觉结构，不使用品牌 logo 代替头像。

工具栏：

- 首页。
- 知识库或收件箱入口。
- 搜索。
- 中英文切换。
- 收缩 / 展开侧边栏。
- 工具按钮使用圆形图标按钮，hover 显示名称。

内容层：

- 第一层固定入口：任务、知识库、帮助、垃圾箱。
- 第二层为“我的分类”：左侧箭头控制展开收缩，右侧 `...` 打开分类菜单。
- 分类菜单操作包含新增分类。
- 分类展开时展示用户分类列表；收缩时只保留标题行。

底部动作区：

- 展开态显示“开启任务”按钮。
- 收缩态显示任务图标按钮。
- hover 提示为“创建任务”。

### 验收标准

- 展开和收缩状态下 logo 不变形、不带多余背景底格。
- 状态栏品牌图、wordmark、头像在同一视觉基线上。
- 工具栏图标尺寸、圆形背景和间距一致。
- 收缩态不再出现包裹所有按钮的大胶囊背景。
- 所有图标按钮都有 tooltip，且 tooltip 不遮挡按钮主体。

## 4. 状态管理

### 背景

前端需要同时处理游客 Cookie、注册用户 token、语言偏好和接口错误。

### 决策

认证状态和语言状态分别由 Pinia store 管理；Axios 统一注入 token，并处理 401 刷新。

### 实现要点

认证：

- `auth.ts` 保存 `token`、`refreshToken`、`userId`、`username`、`avatarUrl`、`isGuest`。
- 游客登录调用 `/api/v1/auth/guest`，通过 Cookie 保持身份。
- 注册 / 登录保存 token 到 localStorage。
- `api/client.ts` 对 401 执行 refresh token。
- `GUEST_FORBIDDEN` 触发登录引导。

语言：

- `locale.ts` 保存 `zh-CN / en-US`。
- 语言偏好持久化到 localStorage。
- 主布局、首页、任务、报告、设置页面读取同一个 locale store。

### 验收标准

- 注册用户刷新页面后保持登录。
- 游客刷新页面后保留游客会话。
- 中英文切换后核心页面文案同步更新。
- token 过期时优先自动刷新，而不是直接退出。

## 5. 任务页面

### 背景

搜索任务需要可创建、可启动、可查看状态和报告结果，不能只依赖首页快速搜索。

### 决策

任务管理使用 `/api/v1/tasks`，快速搜索仍保留在首页入口。任务列表以主题标题为主展示字段。

### 实现要点

- `TasksView` 调用 `GET /api/v1/tasks`。
- 列表展示 `topic_title`、状态、搜索模式、频率、创建时间。
- `TaskCreateView` 支持选择已有主题或创建新主题。
- 创建任务提交 `source_sites`、`search_mode`、`frequency`。
- 混合搜索模式提交 `mixed`。
- `TaskDetailView` 展示主题、关键词、来源站点、报告列表，并支持启动和重试。
- `TaskDetailView` 启动任务后轮询刷新任务状态和报告列表。

### 验收标准

- 任务列表优先显示 `topic_title`。
- 创建任务最多提交 5 个来源站点。
- 启动任务后状态进入执行态。
- 失败任务在详情页可重试。
- 任务完成后详情页能显示生成的报告。

## 6. 报告阅读与 Markdown

### 背景

报告是 Agent 的核心产物，需要稳定的阅读体验、章节定位和一致的 Markdown 样式。

### 决策

报告详情页采用左侧 TOC + 右侧 Markdown 阅读布局，Markdown 渲染由 `md-editor-v3` 负责。

### 实现要点

- `ReportView` 调用 `/api/v1/reports/{id}`。
- `MdPreview` 渲染 `content_md`。
- TOC 使用后端返回的 `toc`。
- Markdown 标题、表格、代码块、引用样式在 `src/style.css` 中统一覆盖。
- 报告不存在、无权限或加载失败时展示明确状态。

### 验收标准

- TOC 可跳转到对应章节。
- Markdown 表格、代码块、引用和标题显示稳定。
- 无权限或不存在报告不会出现空白页。

## 7. 知识问答与通知

### 背景

前端需要把已有知识检索和任务状态能力接起来，不能只保留导航占位。

### 决策

`ChatView` 接入 `/api/v1/knowledge/query`，`InboxView` 基于 `/api/v1/tasks` 聚合任务通知。

### 实现要点

- `ChatView` 提供问答消息流、输入框、示例问题和来源引用。
- 知识问答只对注册用户开放，游客触发接口时由 Axios 的 `GUEST_FORBIDDEN` 逻辑引导登录。
- `InboxView` 将 `pending/fetching/organizing/completed/failed` 任务映射为通知卡片。
- 通知卡片点击进入对应任务详情。
- `HelpView` 汇总当前已接入的功能入口。
- `TrashView` 提供垃圾箱路由和空状态；恢复接口未实现前不伪造数据。

### 验收标准

- 对话页能提交问题并展示回答和来源。
- 收件箱能展示任务状态通知。
- 帮助和垃圾箱入口不再停留在 toast 占位。

## 8. 视觉规范

### 背景

界面需要借鉴 Notion 的紧凑工作区结构，同时避免复制其品牌、logo 和专有表达。

### 决策

采用暖中性色背景、蓝色品牌标识、低对比边框、圆形图标按钮和中等偏紧凑的信息密度。

### 实现要点

- 不使用 Notion logo 或其专有标识。
- 品牌资源统一放在 `frontend/src/assets/`。
- 图标按钮优先使用图形表达，文字只用于明确命令或列表项。
- 工作台不做营销式 hero，不用大面积装饰图。
- 移动端和桌面端都需要避免文字溢出、图标漂移和控件重叠。

### 验收标准

- 页面第一屏呈现工作台，而不是落地页。
- 图标、按钮、列表行高度和间距统一。
- 品牌图资源背景透明，不出现白色底格或压缩变形。
