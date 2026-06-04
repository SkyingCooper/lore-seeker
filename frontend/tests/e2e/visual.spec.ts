import { expect, test } from '@playwright/test'
import { installApiMock, json } from './support/mockApi'

test('login page visual baseline', async ({ page }) => {
  await installApiMock(page, {
    'POST /api/v1/auth/captcha/challenge': (route) => json(route, { slider_token: 'slider-token-1' }),
  })

  await page.goto('/login')
  await expect(page).toHaveScreenshot('login-page.png', { fullPage: true })
})

test('browse home visual baseline', async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem('token', 'access-token')
    localStorage.setItem('refreshToken', 'refresh-token')
    localStorage.setItem('userId', 'u-1')
    localStorage.setItem('username', 'Gin')
    localStorage.setItem('isGuest', 'false')
  })

  await installApiMock(page, {
    'GET /api/v1/reports/': (route) => json(route, [{
      id: '1',
      title: 'AI 安全周报',
      summary: '这是一段用于视觉基线的摘要内容。',
      status: 'completed',
      quality_score: 90,
      created_at: '2026-06-04T10:00:00Z',
      user_satisfaction: 'satisfied',
    }]),
  })

  await page.goto('/browse')
  await expect(page).toHaveScreenshot('browse-home.png', { fullPage: true })
})
