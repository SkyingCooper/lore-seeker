# 前端设计

## 技术框架

- Vue 3
- TypeScript
- Vite
- Tailwind CSS
- Naive UI
- @lucide/vue
- Pinia
- Vue Router
- Axios
- md-editor-v3

## 视觉与交互基线

- 整体参考 Notion：克制灰阶、低对比边框、阅读优先、大留白
- 组件层优先使用 Naive UI，页面排版和间距控制交给 Tailwind
- 图标统一使用 `@lucide/vue`，避免按钮、导航和状态区域只剩纯文字
- Markdown 阅读体验继续由 `md-editor-v3` 承担，不自行实现渲染器

## 搭建说明

1. 安装依赖：`cd frontend && npm install`
2. 本地开发：`npm run dev`
3. 生产构建：`npm run build`

当前关键接入点：
- `vite.config.ts`：注册 `@tailwindcss/vite`
- `src/main.ts`：引入 `src/style.css` 和 `md-editor-v3` 样式
- `src/App.vue`：挂载 Naive UI 的 Config / Message / Dialog / Notification Provider
- `src/theme/naive.ts`：集中维护 Notion 风格的 Naive UI 主题覆盖
- `src/style.css`：维护 Tailwind 入口和全局设计 token
- `@lucide/vue`：为导航、按钮、视图标签、状态区块提供统一图标
- `src/assets/logo-book.avif` / `src/assets/logo-word.avif`：当前前端主用品牌资源，分别用于图标 mark 和 wordmark
- `tsconfig.json` / `tsconfig.node.json` / `src/env.d.ts`：保证 `vue-tsc` 和 `vite build` 可执行

## 页面结构

```
/login              登录页（游客 / 注册 / 登录）
/browse             首页工作区（搜索入口 + 数据库式报告列表）
/browse/:reportId   报告阅读页（左侧 TOC + 右侧 Markdown）
/chat               与 Lore Seeker 对话入口
/inbox              收件箱 / 通知入口
/profile            个人信息页
/reports            报告历史列表页
/settings           设置页（主题管理 + 偏好编辑）
```

未登录时访问 `/browse` 等需要认证的路由，路由守卫自动触发游客登录（浏览器指纹），无感知跳转。

## 组件设计

### MainLayout

Notion 风格工作台壳子，左侧固定导航，右侧内容区阅读优先。

左侧拆成两层：
- **状态栏**：品牌 icon、当前用户名（游客显示“游客”）、下拉箭头、独立的侧栏折叠按钮
- **工具栏**：主页、与 Lore Seeker 对话、收件箱、搜索、中英切换
- **内容层**：工具栏下方拆成两段，先是帮助 / 任务 / 知识库 / 垃圾箱，再是“我的分类”折叠分组和文件夹操作菜单

交互约定：
- 展开态下，状态栏中的 logo 和用户名分开布局，logo 按原始比例显示，避免被挤压变形
- 收缩态下，只保留清晰的图标按钮列；顶部品牌按钮和主页按钮都可直接展开侧边栏
- 工具栏按钮统一使用 tooltip 暴露名称，不依赖页面常驻文字
- 身份入口点击后弹出账户层，包含设置、个人信息、语言切换，以及游客的注册/登录或正式用户的登出动作
- “我的分类”标题左侧带折叠按钮，右侧 `...` 操作菜单提供“添加文件夹 / 删除文件夹”入口，当前先保留前端占位交互

当前已补上 `ChatView`、`InboxView`、`ProfileView` 三个页面壳子，避免工具栏和账户层出现“有入口无落点”的状态。

当前使用自定义圆角导航项、工具栏图标和会话卡片，提升识别度和轻盈感。

最近一轮针对侧栏又补了两条约束：
- 状态栏的品牌 logo 固定在左上角，独立于用户名按钮，避免图标被文字容器挤压变形
- 状态栏、工具栏和收缩态图标统一放大一档，并同步增加按钮尺寸和间距，保证图标尺度与容器匹配
- 状态栏、工具栏、工作区列表和底部会话卡片的上下留白统一拉开，避免局部拥挤和图标漂浮感
- 侧栏最下方不再展示 workspace 卡片，只保留单一的“开启对话”入口，避免信息重复和底部噪音
- 侧栏布局继续向 Notion 的紧凑列表风格收敛：减少大卡片包裹、缩小纵向间距、让工具区和列表区更像连续工作区而不是独立面板
- 右下角圆形按钮语义调整为“创建任务”，用于发起用户输入主题和地址的搜索任务；悬浮提示不再显示“开启对话”

### LoginView

支持三种操作：
1. 游客继续（浏览器指纹自动登录）
2. 注册（邮箱 + 密码）
3. 登录（已注册用户）

登录页采用双栏结构：左侧是产品说明，右侧是表单卡片，作为整个前端风格的第一屏样板。

当前已接入完整品牌 logo，并支持中英文文案切换。

### BrowseView

- 作为首页工作区，整体参考 Notion 的数据库页面
- 顶部动作区：新搜索输入框 + 新页面按钮
- 视图切换条：最近 / 星标 / 已共享 / 私人
- 列表区：数据库式表头和行项目，展示页面名、创建者、来源、上次编辑时间
- 任务状态条：显示当前任务 ID 和状态，3 秒轮询
- 视图标签、筛选按钮、表头和报告项统一带图标，减轻“纯表格文本”的僵硬感

### ReportView（核心阅读体验）

暖色调双栏阅读布局：
- 左侧：报告元信息 + TOC 导航，点击平滑滚动
- 右侧：阅读头部 + `MdPreview`（md-editor-v3）正文渲染
- 接入中英文文案切换，与首页保持一致的工作区视觉基线
- 品牌 mark、返回动作和元信息图标已经接入，阅读页不再是“纯文本面板”

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

使用 Pinia。当前已落地的 store：

**`auth.ts`**：
- `token`、`userId`、`isGuest` 持久化到 `localStorage`
- `guestLogin()`：调用 FingerprintJS 获取指纹，请求 `/auth/guest`
- `register()` / `login()` / `logout()`
- 初始化时自动从 localStorage 恢复 token 并设置 axios 默认 Header

**`locale.ts`**：
- 管理 `zh-CN / en-US` 切换
- 语言选择持久化到 `localStorage`
- 当前为主布局、首页、报告页、报告列表页、设置页提供中英文文案切换基础

## API 客户端

`src/api/client.ts`：axios 实例，`baseURL='/'`，通过 Vite proxy 转发到后端。

Token 注入：在 `auth.ts` 的 `setAuth()` 中直接设置 `api.defaults.headers.common['Authorization']`。

## 相关文件

- `frontend/src/router/index.ts` — 路由定义 + 守卫
- `frontend/src/stores/auth.ts` — 认证状态
- `frontend/src/stores/locale.ts` — 中英文切换状态
- `frontend/src/api/client.ts` — axios 实例
- `frontend/src/theme/naive.ts` — Naive UI 主题覆盖
- `frontend/src/style.css` — Tailwind 入口 + 全局 token
- `frontend/src/assets/` — Logo、品牌图形等静态资源
- `frontend/src/layouts/MainLayout.vue`
- `frontend/src/views/` — 各页面组件

---

## 2026-05-29 — 接入 Naive UI 并建立 Notion 风格基线

**背景**：前端技术约定补充为 Vue 3 + TypeScript + Vite + Tailwind + Naive UI + Pinia + md-editor-v3，同时要求整体体验参考 Notion。

**决策**：
- 引入 `naive-ui` 作为统一组件层，根组件挂载 Config / Message / Dialog / Notification Provider
- 新增 `src/theme/naive.ts` 统一覆盖组件主题，颜色和边框风格向 Notion 靠拢
- 用 Tailwind 管理布局、间距和页面级排版，保留 Naive UI 负责表单、卡片、表格、消息等交互部件
- 首批切换 `App`、`MainLayout`、`LoginView`、`BrowseView`、`ReportsView`、`SettingsView`

**放弃的方案**：
- 继续只靠 scoped CSS 逐页维护：组件形态和交互细节难统一
- 全部样式都压到 Naive UI theme：页面布局和响应式细节仍需要 Tailwind 处理

**影响范围**：`frontend/package.json`、`frontend/src/App.vue`、`frontend/src/layouts/MainLayout.vue`、`frontend/src/views/LoginView.vue`、`frontend/src/views/BrowseView.vue`、`frontend/src/views/ReportsView.vue`、`frontend/src/views/SettingsView.vue`、`frontend/src/theme/naive.ts`

---

## 2026-05-29 — 首页改为数据库式工作页并支持中英文切换

**背景**：首页需要更接近 Notion 工作区页面，而不是传统仪表盘；同时要求支持页面中英文切换。

**决策**：
- 将 `/browse` 重构为数据库式工作页，视觉上参考 Notion 的 library / recents 页面
- 不拷贝 Notion logo 和专有标志，只借鉴信息组织、密度和布局节奏
- 新增 `locale.ts` Pinia store，使用 `localStorage` 持久化中英文选择
- 在 `MainLayout` 中放置语言切换入口，并先覆盖布局和首页文案

**放弃的方案**：
- 直接引入完整 i18n 框架：当前只需要轻量中英文切换，先避免额外依赖
- 在页面内零散管理语言状态：后续扩展到其他页面时会重复且不一致

**影响范围**：`frontend/src/stores/locale.ts`、`frontend/src/layouts/MainLayout.vue`、`frontend/src/views/BrowseView.vue`

---

## 2026-05-29 — 报告阅读页接入统一工作区风格

**背景**：首页已经切到数据库式工作页，但报告阅读页仍保留早期占位样式，和新的首页、主布局不一致。

**决策**：
- 保留“左侧目录 + 右侧正文”的阅读模型
- 将配色、边框、阴影和头部信息切换到统一的暖白工作区风格
- 接入 `locale.ts`，让阅读页文案参与中英文切换

**放弃的方案**：
- 将阅读页改成单栏长文：会丢失知识报告的结构导航能力
- 只改颜色不改信息头部：页面层次仍然不完整

**影响范围**：`frontend/src/views/ReportView.vue`、`docs/frontend.md`

---

## 2026-05-29 — 统一剩余页面文案与 Markdown 阅读样式

**背景**：首页和阅读页已经接入新的工作区风格，但报告列表页、设置页和 Markdown 正文细节仍未完全收口。

**决策**：
- 将 `ReportsView` 和 `SettingsView` 的标题、按钮、空状态、提示语接到 `locale.ts`
- 在 `src/style.css` 中增加 `md-editor-v3` 预览区覆盖样式，统一标题层级、代码块、引用块和表格的阅读观感

**放弃的方案**：
- 只在页面组件局部覆写 Markdown 样式：会导致后续阅读页样式分散
- 继续让剩余页面保留单语言文案：会破坏中英文切换的一致性

**影响范围**：`frontend/src/views/ReportsView.vue`、`frontend/src/views/SettingsView.vue`、`frontend/src/style.css`、`docs/frontend.md`

---

## 2026-05-29 — 第二轮视觉打磨：圆润化与图标系统

**背景**：第一轮改造完成了结构和技术栈落地，但页面仍偏硬、偏直、偏纯文字，缺少参考图中的圆润和活泼感。

**决策**：
- 引入 `@lucide/vue` 作为统一图标库
- 将主布局导航从纯文字菜单切换为自定义圆角导航项
- 在首页的视图标签、动作按钮、表头、报告项以及设置页卡片头部中加入图标
- 提升圆角、透明层、柔和阴影和局部高光，让工作区从“管理台”更接近“知识工作台”

**放弃的方案**：
- 自绘零散 SVG：维护成本高，也不利于后续统一风格
- 只在按钮前加图标、不调整整体层次：页面依旧会显得板

**影响范围**：`frontend/package.json`、`frontend/src/layouts/MainLayout.vue`、`frontend/src/views/BrowseView.vue`、`frontend/src/views/SettingsView.vue`、`docs/frontend.md`

---

## 2026-05-29 — 品牌 Logo 资源接入前端

**背景**：项目已有明确的 Lore Seeker 品牌 logo，需要作为真实静态资源接入前端，而不是继续使用临时符号或纯文字占位。

**决策**：
- 接入 `src/assets/logo-word.avif` 作为完整 wordmark
- 接入 `src/assets/logo-book.avif` 作为 icon mark
- 当前主用 `png` 已处理为透明背景；`avif` 保留为压缩版本参考
- 在 `MainLayout` 中使用 mark，在 `LoginView` 中使用完整 logo

**放弃的方案**：
- 继续只用文字品牌名：识别度不足，也难以建立稳定品牌印象
- 把外部图片 URL 直接写进页面：不利于版本管理和构建一致性

**影响范围**：`frontend/src/assets/logo-book.avif`、`frontend/src/assets/logo-word.avif`、`frontend/src/layouts/MainLayout.vue`、`frontend/src/views/LoginView.vue`

---

## 2026-05-29 — 品牌延展到登录页与阅读页

**背景**：logo 资源已经接入项目，但品牌只停留在局部页面，登录页、阅读页和报告页之间仍有风格落差。

**决策**：
- 登录页使用完整 logo，并补齐中英文文案切换
- 报告阅读页和报告列表页接入品牌 mark、元信息图标和更细的动作提示
- 让品牌不只体现在侧栏，而是贯穿进入应用前和阅读报告时的关键节点

**放弃的方案**：
- 只在侧栏展示品牌：用户在登录和阅读场景里感知不到连续的品牌体验
- 继续让登录页保持单语言：会和全局语言切换产生割裂

**影响范围**：`frontend/src/views/LoginView.vue`、`frontend/src/views/ReportView.vue`、`frontend/src/views/ReportsView.vue`、`docs/frontend.md`

---

## 2026-05-29 — 左上角身份入口改为 Notion 式下拉层

**背景**：左上角此前只是普通品牌块，缺少类似 Notion 的“当前身份入口 + 下拉层 + 侧栏折叠按钮”交互模型。

**决策**：
- 将左上角改为“品牌图标 + 当前用户名 + 小三角 + 单独折叠按钮”
- 点击身份入口弹出账户层，包含设置、个人信息、语言切换，以及游客注册/登录或正式用户登出
- 侧栏支持折叠到图标模式，折叠后保留核心导航和底部动作

**放弃的方案**：
- 继续把账户信息放在侧栏底部单独卡片里：不符合你给出的参考交互
- 将折叠按钮混进身份入口内：会削弱入口和结构控制的职责分离

**影响范围**：`frontend/src/layouts/MainLayout.vue`、`docs/frontend.md`

---

## 2026-05-29 — 接入 Tailwind CSS

**背景**：前端技术约定补充为 Vue 3 + TypeScript + Vite + Tailwind + md-editor-v3，仓库此前尚未完成 Tailwind 接入。

**决策**：
- 使用 Tailwind 官方 Vite 插件 `@tailwindcss/vite`
- 在 `src/style.css` 中通过 `@import "tailwindcss"` 注入全局样式层
- 在 `main.ts` 中统一引入全局样式，保留 `md-editor-v3` 样式引入不变
- 同步修正游客登录依赖，改用官方包 `@fingerprintjs/fingerprintjs`
- 补齐 `tsconfig.json` / `tsconfig.node.json` / `src/env.d.ts`，使 `vue-tsc` 和 `vite build` 可执行

**放弃的方案**：
- 继续只用 scoped CSS：不符合当前前端技术约定，后续样式复用成本高
- 引入额外 PostCSS 配置：当前接法不需要，保持最小化集成

**影响范围**：`frontend/package.json`、`frontend/vite.config.ts`、`frontend/src/main.ts`、`frontend/src/style.css`、`frontend/src/stores/auth.ts`、`frontend/tsconfig.json`、`frontend/tsconfig.node.json`、`frontend/src/env.d.ts`

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

---

## 2026-05-28 — 双令牌认证适配

**背景**：后端认证升级为 access + refresh 双令牌机制，前端需同步适配。

**决策**：
- auth store 新增 `refresh_token` 持久化存储，`setAuth()` 同时存储两个 token
- 新增 `refreshAccessToken()` 方法：access token 过期时用 refresh token 无感续期
- `logout()` 先调后端 `/auth/logout` 再清除本地状态
- `login()` 改用 `URLSearchParams` 发送 OAuth2 标准 form-data 格式

**影响范围**：`frontend/src/stores/auth.ts`
