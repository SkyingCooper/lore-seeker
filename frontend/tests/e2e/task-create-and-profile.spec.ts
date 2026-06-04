import { expect, test } from '@playwright/test'
import { TaskCreatePage } from './pages/TaskCreatePage'
import { installApiMock, json } from './support/mockApi'

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem('token', 'access-token')
    localStorage.setItem('refreshToken', 'refresh-token')
    localStorage.setItem('userId', 'u-1')
    localStorage.setItem('username', 'Gin')
    localStorage.setItem('isGuest', 'false')
  })
})

test('creates a task and renders profile token usage', async ({ page }) => {
  await installApiMock(page, {
    'GET /api/v1/search/topics': (route) => json(route, []),
    'POST /api/v1/tasks': (route) => json(route, { id: 88 }),
    'GET /api/v1/tasks/88': (route) => json(route, {
      id: 88,
      topic_id: 9,
      query: null,
      topic: { id: 9, title: 'Rust 异步编程', keywords: ['rust', 'async'], description: '关注 Tokio 与工程实践' },
      source_sites: ['GitHub', 'Stack Overflow'],
      search_mode: 'mixed',
      frequency: 'weekly',
      status: 'pending',
      created_at: '2026-06-04T10:00:00Z',
      updated_at: '2026-06-04T10:00:00Z',
    }),
    'GET /api/v1/reports': (route) => json(route, []),
    'GET /api/v1/users/me': (route) => json(route, {
      id: 'u-1',
      username: 'Gin',
      email: 'gin@example.com',
      avatar_url: null,
      is_guest: false,
      last_login_at: '2026-06-04T10:00:00Z',
      created_at: '2026-06-03T10:00:00Z',
      preferences: { output_lang: 'zh-CN' },
    }),
    'GET /api/v1/users/me/token-balance': (route) => json(route, {
      user_id: 'u-1',
      balance: 8888,
      total_consumed: 1112,
      updated_at: '2026-06-04T10:00:00Z',
      last_reset_at: null,
    }),
    'GET /api/v1/users/me/token-consumption': (route) => json(route, {
      items: [{
        id: 1,
        task_id: '88',
        stage: 'planner',
        provider: 'qwen',
        model: 'qwen-plus',
        input_tokens: 120,
        output_tokens: 80,
        actual_consumed: 200,
        balance_after: 8688,
        created_at: '2026-06-04T10:00:00Z',
      }],
    }),
  })

  const createPage = new TaskCreatePage(page)
  await createPage.goto()
  await createPage.fillBasicForm('Rust 异步编程', '关注 Tokio 与工程实践')
  await createPage.submit()

  await expect(page.getByRole('heading', { name: 'Rust 异步编程' })).toBeVisible()
  await expect(page.getByText('GitHub, Stack Overflow')).toBeVisible()

  await page.goto('/profile')
  await expect(page.getByText('8888')).toBeVisible()
  await expect(page.getByText('planner')).toBeVisible()
  await expect(page.getByText('qwen-plus')).toBeVisible()
})
