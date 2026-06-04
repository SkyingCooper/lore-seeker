import type { Locator, Page } from '@playwright/test'
import { expect } from '@playwright/test'

export class LoginPage {
  readonly page: Page
  readonly submitButton: Locator

  constructor(page: Page) {
    this.page = page
    this.submitButton = page.getByTestId('auth-submit')
  }

  async goto() {
    await this.page.goto('/login')
    await expect(this.page.getByRole('heading', { name: /登录|Login/ })).toBeVisible()
  }

  async switchToRegister() {
    await this.page.getByRole('button', { name: /注册|Register/ }).click()
  }

  async fillRegisterForm({ username, email, password }: { username: string; email: string; password: string }) {
    await this.page.getByTestId('username-input').locator('input').fill(username)
    await this.page.getByTestId('email-input').locator('input').fill(email)
    await this.page.getByTestId('password-input').locator('input').fill(password)
    await this.page.getByTestId('confirm-password-input').locator('input').fill(password)
  }

  async completeSlider() {
    const box = await this.page.getByTestId('slider-track').boundingBox()
    if (!box) throw new Error('slider track not found')
    await this.page.mouse.move(box.x + 10, box.y + box.height / 2)
    await this.page.mouse.down()
    await this.page.mouse.move(box.x + box.width - 10, box.y + box.height / 2, { steps: 12 })
    await this.page.mouse.up()
  }

  async submit() {
    await this.submitButton.click()
  }
}
