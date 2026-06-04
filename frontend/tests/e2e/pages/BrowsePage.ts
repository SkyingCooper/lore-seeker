import type { Locator, Page } from '@playwright/test'
import { expect } from '@playwright/test'

export class BrowsePage {
  readonly page: Page
  readonly searchInput: Locator

  constructor(page: Page) {
    this.page = page
    this.searchInput = page.getByPlaceholder(/输入新的搜索主题|Type a new research topic/i)
  }

  async expectLoaded() {
    await expect(this.page.locator('h1', { hasText: /首页|Home/ })).toBeVisible()
  }

  async quickSearch(query: string) {
    await this.searchInput.fill(query)
    await this.page.getByRole('button', { name: /新页面|New page/ }).click()
  }

  async openReport(title: string) {
    await this.page.getByRole('button', { name: new RegExp(title) }).click()
  }
}
