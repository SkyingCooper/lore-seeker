import type { Page, Route } from '@playwright/test'

type Handler = (route: Route) => Promise<void> | void

export async function installApiMock(page: Page, handlers: Record<string, Handler>) {
  await page.route('**/api/v1/**', async (route) => {
    const url = new URL(route.request().url())
    const key = `${route.request().method()} ${url.pathname}`
    const handler = handlers[key]
    if (handler) {
      await handler(route)
      return
    }
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: '{}',
    })
  })
}

export function json(route: Route, body: unknown, status = 200) {
  return route.fulfill({
    status,
    contentType: 'application/json',
    body: JSON.stringify(body),
  })
}
