# Frontend Testing

## Scope

前端测试分为三层：

1. 单元测试与组件测试：`Vitest + @vue/test-utils`
2. 端到端测试：`Playwright + Page Object Model`
3. 视觉回归测试：`Playwright screenshot baseline`

## Commands

```bash
cd frontend
npm run test:unit
npm run test:e2e
npm run test:visual
```

## Unit / Component Tests

- 配置文件：`frontend/vitest.config.ts`
- 与 Vite 共享别名和基础构建配置。
- 运行环境：`jsdom`
- 组件覆盖：
  - `SliderCaptcha`
  - `ChatView`

测试重点：

- DOM 是否按中英文状态正确渲染
- 用户输入、点击、拖拽是否触发正确行为
- API 成功与失败场景
- 组件暴露方法 `reset / markFailed`
- 会话级 `session_id` 注入

## E2E Tests

- 配置文件：`frontend/playwright.config.ts`
- 测试目录：`frontend/tests/e2e`
- 采用 `Page Object Model`
  - `pages/LoginPage.ts`
  - `pages/BrowsePage.ts`
  - `pages/TaskCreatePage.ts`
- API 使用 `page.route()` 本地 mock，不依赖后端服务。

核心流程：

1. 注册登录 -> 首页快速搜索 -> 打开报告
2. 创建任务 -> 查看任务详情 -> 查看个人中心 token 流水

定位策略：

- 优先 `getByRole`
- 其次 `getByPlaceholder`
- 对滑块、关键提交按钮等补充 `data-test`

## Visual Regression

当前视觉回归直接使用 Playwright 原生截图基线能力，而不是引入外部 SaaS。

原因：

1. 本地即可运行，不依赖额外云端 token。
2. 基线图、差异图、失败截图均由 Playwright 本地生成。
3. 对当前项目更直接，适合作为默认视觉回归方案。

配置点：

- `playwright.config.ts`
  - `snapshotPathTemplate`
  - `expect.toHaveScreenshot.maxDiffPixelRatio`
  - `reporter: html`

基线逻辑：

- 首次运行生成基线图：
  - `tests/e2e/__screenshots__/...`
- 后续运行自动对比：
  - 若视觉差异超阈值，测试失败
  - Playwright 报告中会输出差异截图

当前视觉页覆盖：

1. `LoginView`
2. `BrowseView`

## Notes

- 如果后续要接 Percy / Applitools，可在当前 Playwright 测试基础上追加 provider SDK，不需要推翻现有测试结构。
- 当前默认使用 Chromium；如需扩展 Safari / Firefox，可直接在 `projects` 中追加浏览器配置。
