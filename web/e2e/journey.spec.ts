import { expect, test } from '@playwright/test'

const shots = process.env.SHOTS_DIR || '../docs/screenshots'
const TEAM_CODE = process.env.TEAM_CODE || 'local'

test('main passenger journey: book → Safe Journey → stop + deviation check-ins → dashboard', async ({ page }) => {
  const errors: string[] = []
  page.on('pageerror', (e) => errors.push(e.message))

  await page.goto('/')
  await page.getByPlaceholder('e.g. Thandi').fill('Thandi')
  await page.getByPlaceholder('Name', { exact: true }).fill('Mom')
  await page.getByPlaceholder('082 123 4567').fill('082 555 0101')
  await page.getByPlaceholder('WhatsApp number').fill('082 555 0102')
  await expect(page.getByText('Shared ride · 2 riders')).toBeVisible()
  await page.screenshot({ path: `${shots}/01-book.png` })
  await page.getByRole('button', { name: /Request simulated ride/ }).click()

  await expect(page.getByText('Your driver')).toBeVisible()
  await expect(page.getByText(/Check-ins arrive there automatically|also arrive on WhatsApp/)).toBeVisible()
  await page.getByRole('button', { name: /Check plate/ }).click()
  await expect(page.getByText(/registered with MzansiRide/)).toBeVisible()
  await page.screenshot({ path: `${shots}/02-driver.png` })
  await page.getByRole('button', { name: /Start trip/ }).click()

  await page.getByLabel('Simulation speed').selectOption('30')
  await page.waitForTimeout(2500)
  await page.getByRole('button', { name: /Simulate prolonged stop/ }).click()
  const dialog = page.getByRole('dialog')
  await expect(dialog).toBeVisible({ timeout: 30_000 })
  await expect(dialog.getByText(/Prolonged stop/)).toBeVisible()
  await expect(dialog.locator('.animate-pulse').first()).toBeHidden({ timeout: 30_000 }) // AI text loaded
  await page.screenshot({ path: `${shots}/03-checkin-stop.png` })
  await dialog.getByRole('button', { name: "I'm OK" }).click()
  await expect(dialog).toBeHidden()

  await page.waitForTimeout(3000)
  await page.getByRole('button', { name: /Simulate off-route/ }).click()
  await expect(dialog).toBeVisible({ timeout: 30_000 })
  await expect(dialog.getByText(/Route deviation/)).toBeVisible()
  await page.screenshot({ path: `${shots}/04-checkin-deviation.png` })
  await dialog.getByRole('button', { name: 'I need help' }).click()
  await expect(page.getByText(/Help requested/)).toBeVisible()
  await expect(page.getByText('Escalated').first()).toBeVisible({ timeout: 10_000 })
  await page.screenshot({ path: `${shots}/05-safety-log.png`, fullPage: true })

  await page.getByRole('link', { name: 'Fleet' }).first().click()
  await page.getByPlaceholder('Team code').fill(TEAM_CODE)
  await page.getByRole('button', { name: 'Open dashboard' }).click()
  await expect(page.getByText('Fleet safety dashboard')).toBeVisible()
  await expect(page.getByRole('cell', { name: /Prolonged stop/ }).first()).toBeVisible()
  await page.screenshot({ path: `${shots}/06-dashboard.png`, fullPage: true })

  expect(errors).toEqual([])
})

test('fleet dashboard: demo fleet → unanswered check-in turns red with AI triage → operator acknowledges', async ({ page }) => {
  test.setTimeout(120_000)
  await page.goto('/dashboard')
  await page.getByPlaceholder('Team code').fill(TEAM_CODE)
  await page.getByRole('button', { name: 'Open dashboard' }).click()
  await page.getByRole('button', { name: 'Run demo fleet' }).click()
  await expect(page.locator('[data-risk="green"]').first()).toBeVisible({ timeout: 20_000 })
  const red = page.locator('[data-risk="red"]', { hasText: 'Sarah' })
  await expect(red).toBeVisible({ timeout: 60_000 })
  await expect(red.getByText(/triage/i)).toBeVisible()
  await page.screenshot({ path: `${shots}/10-fleet-dashboard.png`, fullPage: true })
  await red.getByRole('button', { name: 'Called driver' }).click()
  // Sarah's car is still stopped, so a newer alert may already be open: just check the ack was recorded.
  await expect(page.getByText(/✔ Called driver/).first()).toBeVisible({ timeout: 10_000 })
  await page.getByRole('button', { name: 'Stop demo fleet' }).click()
})

test('WhatsApp simulator: driver check and AI question', async ({ page }) => {
  await page.goto('/whatsapp')
  const box = page.getByPlaceholder('Message')
  await box.fill('check CA 123-456')
  await box.press('Enter')
  await expect(page.getByText('Registered driver')).toBeVisible()
  await box.fill('check BX 33 KK GP')
  await box.press('Enter')
  await expect(page.getByText(/do not take this ride/)).toBeVisible()
  await box.fill('The driver locked the doors and is asking for more money')
  await box.press('Enter')
  await expect(page.getByText(/10111/).last()).toBeVisible({ timeout: 30_000 })
  await page.screenshot({ path: `${shots}/07-whatsapp-simulator.png`, fullPage: true })
})

test('assistant chat answers @mobile', async ({ page }) => {
  await page.goto('/')
  await page.screenshot({ path: `${shots}/08-mobile-home.png`, fullPage: true })
  await page.goto('/assistant')
  await page.getByRole('button', { name: /What happens when I press/ }).click()
  await expect(page.locator('.bg-slate-100').nth(1)).toBeVisible({ timeout: 30_000 })
  await page.screenshot({ path: `${shots}/09-mobile-assistant.png` })
})
