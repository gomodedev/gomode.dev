// Browser acceptance for Go Mode product navigation, native captures, keyboard access, and real 404s.
import { expect, test } from "@playwright/test";

test("product website is readable, navigable, and loads native captures", async ({ page }, info) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  page.on("console", (message) => {
    if (message.type() === "error") errors.push(message.text());
  });
  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("Your app. Hands free.");
  await page.keyboard.press("Tab");
  await expect(page.getByRole("link", { name: "Skip to content" })).toBeFocused();
  await page.keyboard.press("Tab");
  await expect(page.getByRole("link", { name: "Go Mode home" })).toBeFocused();
  await expect(page.getByRole("link", { name: "Set up the Android app" })).toHaveAttribute(
    "href",
    "https://docs.gomode.dev/guide/android",
  );
  const setup = page.getByRole("link", { name: "Set up the Android app" });
  for (let i = 0; i < 4; i++) await page.keyboard.press("Tab");
  await expect(setup).toBeFocused();
  for (const image of await page.locator("main img").all()) {
    await image.scrollIntoViewIfNeeded();
    await expect(image).toBeVisible();
    await expect.poll(() => image.evaluate((element) => (element as HTMLImageElement).naturalWidth)).toBeGreaterThan(0);
    await expect(image).toHaveAttribute("alt", /.+/);
  }
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.keyboard.press("Control+Home");
  await expect.poll(() => page.evaluate(() => scrollY)).toBe(0);
  await page.screenshot({ path: info.outputPath("product.png"), fullPage: true });
  await page.screenshot({ path: info.outputPath("product-top.png") });
  const capture = page.getByRole("link", { name: "Native Go Mode voice setup and language settings" });
  await capture.focus();
  const opened = page.waitForEvent("popup");
  await page.keyboard.press("Enter");
  const fullSize = await opened;
  await fullSize.waitForLoadState();
  expect(fullSize.url()).toBe(new URL("/screenshots/voice-settings.webp", page.url()).href);
  await expect(fullSize.locator("img")).toBeVisible();
  await fullSize.close();
  expect(errors).toEqual([]);
});

test("unknown routes return a real 404 and a working home link", async ({ page }) => {
  const response = await page.goto("/this-page-does-not-exist");
  expect(response?.status()).toBe(404);
  await expect(page.getByRole("heading", { level: 1, name: "Page not found." })).toBeVisible();
  await page.getByRole("link", { name: "Go Mode home" }).click();
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("Your app. Hands free.");
});
