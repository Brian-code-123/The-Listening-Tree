import { test, expect } from './support/fixtures';

test.skip(({ isMobile }) => isMobile, 'desktop projects are enough for the alarm timing test');

test.describe('Black-box: reminder alarm', () => {
  test('fires on /history (not only /chat): loops audio, alerts, then removes the reminder', async ({ authedPage: page }) => {
    const dialogs: string[] = [];
    page.on('dialog', async (d) => {
      dialogs.push(d.message());
      await d.accept();
    });
    await page.addInitScript(() => {
      (window as any).__played = [];
      HTMLMediaElement.prototype.play = function () {
        (window as any).__played.push({ src: this.src, loop: this.loop });
        return Promise.resolve();
      };
    });

    // Fixed clock, 30s before the reminder minute, well away from midnight.
    await page.clock.install({ time: new Date('2030-01-15T09:29:30+08:00') });

    const api = page.context().request;
    const created = await api.post('/reminders', { form: { label: 'Take medicine', time: '09:30' } });
    expect(created.ok()).toBeTruthy();

    const meDone = page.waitForResponse((r) => r.url().endsWith('/me') && r.ok());
    await page.goto('/history');
    await meDone;

    await page.clock.fastForward(35_000); // -> 09:30:05

    await expect.poll(() => dialogs.length, { timeout: 15_000 }).toBe(1);
    expect(dialogs[0]).toContain('Take medicine');

    const played = await page.evaluate(() => (window as any).__played);
    expect(played[0].src).toContain('notification.mp3');
    expect(played[0].loop).toBe(true);

    await expect
      .poll(async () => (await (await api.get('/get_reminders')).json()).reminders.length, { timeout: 15_000 })
      .toBe(0);
  });

  test('a daily reminder rings, is kept, and rings again the next day in the same open tab', async ({ authedPage: page }) => {
    const dialogs: string[] = [];
    page.on('dialog', async (d) => {
      dialogs.push(d.message());
      await d.accept();
    });
    await page.addInitScript(() => {
      HTMLMediaElement.prototype.play = () => Promise.resolve();
    });
    await page.clock.install({ time: new Date('2030-01-15T09:29:30+08:00') });

    const api = page.context().request;
    await api.post('/reminders', { form: { label: 'Morning walk', time: '09:30', repeat: 'daily' } });

    const meDone = page.waitForResponse((r) => r.url().endsWith('/me') && r.ok());
    await page.goto('/history');
    await meDone;

    await page.clock.fastForward(35_000); // -> 09:30:05
    await expect.poll(() => dialogs.length, { timeout: 15_000 }).toBe(1);

    // Ringing must not consume a daily reminder.
    const list = (await (await api.get('/get_reminders')).json()).reminders;
    expect(list.map((r: { label: string }) => r.label)).toEqual(['Morning walk']);

    await page.clock.fastForward(24 * 60 * 60 * 1000); // -> 09:30:05 the next day
    await expect.poll(() => dialogs.length, { timeout: 15_000 }).toBe(2);
  });

  test('a reminder for another minute does not fire', async ({ authedPage: page }) => {
    const dialogs: string[] = [];
    page.on('dialog', async (d) => {
      dialogs.push(d.message());
      await d.accept();
    });
    await page.clock.install({ time: new Date('2030-01-15T09:29:30+08:00') });
    await page.context().request.post('/reminders', { form: { label: 'Later', time: '18:00' } });
    const meDone = page.waitForResponse((r) => r.url().endsWith('/me') && r.ok());
    await page.goto('/history');
    await meDone;
    await page.clock.fastForward(35_000);
    await page.waitForTimeout(1_000);
    expect(dialogs).toHaveLength(0);
  });
});
