import type { Page } from '@playwright/test'
import { expect } from '@playwright/test'

export class TaskCreatePage {
  constructor(private readonly page: Page) {}

  async goto() {
    await this.page.goto('/tasks/new')
    await expect(this.page.locator('h1', { hasText: /新建任务|New Task/ })).toBeVisible()
  }

  async fillBasicForm(title: string, description: string) {
    await this.page.getByTestId('task-topic-title').locator('input').fill(title)
    await this.page.getByTestId('task-description').locator('textarea').fill(description)
  }

  async submit() {
    await this.page.getByTestId('task-submit').click()
  }
}
