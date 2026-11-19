// Browser acceptance for Go Mode product navigation, host and native captures, keyboard access, and real 404s.
import { expect, test } from "@playwright/test";

test("product website is readable, navigable, and loads host and native captures", async ({ page }, info) => {
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
  expect(fullSize.url()).toBe(new URL("/screenshots/voice-settings-light.webp", page.url()).href);
  await expect(fullSize.locator("img")).toBeVisible();
  await fullSize.close();
  expect(errors).toEqual([]);
});

test("the page follows browser appearance changes", async ({ page }, info) => {
  await page.emulateMedia({ colorScheme: "dark" });
  await page.goto("/");
  const canvas = page.locator("html");
  await expect(canvas).toHaveCSS("background-color", "rgb(13, 26, 43)");
  const capture = page.getByRole("link", { name: "Native Go Mode voice setup and language settings" });
  await capture.scrollIntoViewIfNeeded();
  await expect(capture).toHaveAttribute("href", /voice-settings-dark\.webp$/);
  await page.screenshot({ path: info.outputPath("dark.png") });

  await page.emulateMedia({ colorScheme: "light" });
  await expect(canvas).toHaveCSS("background-color", "rgb(244, 248, 251)");
  await expect(capture).toHaveAttribute("href", /voice-settings-light\.webp$/);
});

test("unknown routes return a real 404 and a working home link", async ({ page }) => {
  const response = await page.goto("/this-page-does-not-exist");
  expect(response?.status()).toBe(404);
  await expect(page.getByRole("heading", { level: 1, name: "Page not found." })).toBeVisible();
  await page.getByRole("link", { name: "Go Mode home" }).click();
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("Your app. Hands free.");
});
