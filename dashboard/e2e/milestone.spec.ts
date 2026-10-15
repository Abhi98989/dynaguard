import { test, expect } from '@playwright/test';

test('administrator creates project, inspects bypass evidence and verifies the fix', async ({ page }) => {
  const errors: string[] = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.goto('/');
  await page.getByLabel('Password', { exact: true }).fill('synthetic-password-must-not-appear');
  await page.getByRole('button', { name: 'Sign in', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Sign out' })).toBeVisible();
  await page.getByLabel('New project').fill('Browser milestone project');
  await page.getByRole('button', { name: 'Create project' }).click();
  await expect(page.getByRole('heading', { name: 'Browser milestone project' })).toBeVisible();
  await page.getByLabel('Environment name').fill('Vulnerable browser fixture');
  // Disposable smoke service publishes choices in the same order as its fixtures.
  const options = await page.getByLabel('Allowed target').locator('option').allTextContents();
  expect(options).toHaveLength(4);
  await page.getByLabel('Allowed target').selectOption(options[0]);
  await page.getByLabel('Build identifier').fill('fixture-vulnerable-v1');
  await page.getByRole('button', { name: 'Save target & policy' }).click();
  await expect(page.getByText('Vulnerable browser fixture', {exact: true})).toBeVisible();
  const config = page.locator('details').filter({has: page.getByText('Configure a local target', {exact: true})});
  if (!(await config.getAttribute('open'))) {
    // Boolean open attributes have an empty string; check actual form visibility first.
    if (!(await page.getByLabel('Environment name').isVisible())) await page.getByText('Configure a local target', {exact: true}).click();
  }
  await page.getByLabel('Environment name').fill('Fixed browser fixture');
  await page.getByLabel('Allowed target').selectOption(options[1]);
  await page.getByLabel('Build identifier').fill('fixture-fixed-v1');
  await page.getByRole('button', { name: 'Save target & policy' }).click();
  await expect(page.getByText('Fixed browser fixture', {exact: true})).toBeVisible();
  await page.locator('.row').filter({has: page.getByText('Vulnerable browser fixture', {exact: true})}).getByRole('button', {name: 'Start scan'}).click();
  await expect(page.getByRole('heading', {name: 'Run result failed'})).toBeVisible();
  await page.getByText('Masked evidence and integrity hash', {exact: true}).click();
  await expect(page.locator('pre').filter({hasText: 'synthetic-bob-942'})).toBeVisible();
  await expect(page.getByRole('button', {name: /Cross-owner access to designated synthetic record/})).toBeVisible();
  await page.getByRole('button', {name: /Cross-owner access to designated synthetic record/}).click();
  await page.getByLabel('Retest environment').selectOption({label: 'Fixed browser fixture'});
  await page.getByRole('button', {name: 'Run retest', exact: true}).click();
  await expect(page.getByRole('heading', {name: 'Run result passed'})).toBeVisible();
  await expect(page.getByRole('button', {name: /Cross-owner access to designated synthetic record/})).toContainText('verified fixed');
  await expect(page.getByText('Bob’s record was denied and Alice’s legitimate access remained functional.').first()).toBeVisible();
  expect(errors).toEqual([]);
  await page.screenshot({path: '../artifacts/dynaguard-milestone.png', fullPage: true});
  await page.getByRole('button', {name: 'Sign out'}).click();
  await expect(page.getByRole('heading', {name: 'Administrator sign in'})).toBeVisible();
});
