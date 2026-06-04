import { expect, test } from '@playwright/test'
import { LoginPage } from './pages/LoginPage'
import { BrowsePage } from './pages/BrowsePage'
import { installApiMock, json } from './support/mockApi'

test.setTimeout(60_000)

test('registers and starts a quick search flow', async ({ page }) => {
  let reportList = [] as Array<Record<string, unknown>>
  let pollCount = 0

  await installApiMock(page, {
    'POST /api/v1/auth/captcha/challenge': (route) => json(route, { slider_token: 'slider-token-1' }),
    'POST /api/v1/auth/register': async (route) => {
      await json(route, {
        access_token: 'access-token',
        refresh_token: 'refresh-token',
        user_id: 'u-1',
        username: 'Gin',
        avatar_url: null,
        is_guest: false,
      })
    },
    'GET /api/v1/reports/': (route) => json(route, reportList),
    'POST /api/v1/search/start': (route) => json(route, { task_id: '101', status: 'fetching' }),
    'GET /api/v1/search/tasks/101': (route) => {
      pollCount += 1
      if (pollCount > 1) {
        reportList = [{
          id: '501',
          title: 'AI 安全周报',
          summary: '这是新生成的搜索报告',
          status: 'completed',
          quality_score: 92,
          user_satisfaction: 'satisfied',
          created_at: '2026-06-04T10:00:00Z',
        }]
        return json(route, { task_id: '101', status: 'completed' })
      }
      return json(route, { task_id: '101', status: 'fetching' })
    },
    'GET /api/v1/reports/501': (route) => json(route, {
      id: '501',
      title: 'AI 安全周报',
      summary: '这是新生成的搜索报告',
      toc: [{ level: 2, title: '概览', anchor: 'overview' }],
      content_md: '# 概览\n\n正文',
      quality_score: 92,
      result_count: 8,
      token_usage: { total: 1200, breakdown: { planner: { input_tokens: 500, output_tokens: 100, total: 600 } }, model_used: { planner: 'qwen-plus' } },
      cost_usage: { total_usd: 0.01, breakdown: {} },
      user_satisfaction: 'satisfied',
      created_at: '2026-06-04T10:00:00Z',
    }),
  })

  const loginPage = new LoginPage(page)
  await loginPage.goto()
  await loginPage.switchToRegister()
  await loginPage.fillRegisterForm({ username: 'gin', email: 'gin@example.com', password: 'Password123' })
  await loginPage.completeSlider()
  await loginPage.submit()

  const browsePage = new BrowsePage(page)
  await browsePage.expectLoaded()
  await browsePage.quickSearch('AI 安全')

  await expect(page.getByText(/任务 101/i)).toBeVisible()
  await expect(page.getByText('AI 安全周报')).toBeVisible({ timeout: 10_000 })
  await page.getByRole('button', { name: /AI 安全周报/ }).click()
  await expect(page.locator('h2', { hasText: 'AI 安全周报' })).toBeVisible()
  await expect(page.getByText('1200')).toBeVisible()
})
