import { test, expect } from '@playwright/test';

const HOST_EMAIL = 'host@waitlist.test';
const HOST_PASSWORD = 'host1234';

test('a guest joining from a separate session shows up live on the host board', async ({ browser }) => {
  // Session 1 (host): sign in and land on the queue board.
  const hostContext = await browser.newContext();
  const hostPage = await hostContext.newPage();

  await hostPage.goto('/login');
  await hostPage.getByLabel('Email').fill(HOST_EMAIL);
  await hostPage.getByLabel('Password').fill(HOST_PASSWORD);
  await hostPage.getByRole('button', { name: /sign in/i }).click();
  await expect(hostPage).toHaveURL('/host');

  const joinLinkHref = await hostPage.getByRole('link', { name: /guest check-in link/i }).getAttribute('href');
  expect(joinLinkHref).toBe('/join');

  // Session 2 (guest): a separate browser context - genuinely a different
  // client/session, not just a second tab sharing cookies - opens the link
  // the host shares and joins the waitlist.
  const guestContext = await browser.newContext();
  const guestPage = await guestContext.newPage();

  await guestPage.goto(joinLinkHref!);
  const guestName = `E2E Guest ${Date.now()}`;
  await guestPage.getByLabel('Name').fill(guestName);
  await guestPage.getByLabel('Phone number').fill('555-0100');
  await guestPage.getByLabel('Party size').fill('3');
  await guestPage.getByRole('button', { name: /join waitlist/i }).click();

  await expect(guestPage).toHaveURL(/\/status\/.+/);
  await expect(guestPage.getByRole('heading', { name: guestName })).toBeVisible();

  // Back on session 1, without ever reloading: the host board must pick up
  // the new party on its own, via RestWaitlistService.onHostQueueUpdate's
  // 3s poll (see AGENTS.md - there's no WebSocket gateway).
  await expect(hostPage.getByText(guestName)).toBeVisible({ timeout: 10_000 });

  await hostContext.close();
  await guestContext.close();
});
