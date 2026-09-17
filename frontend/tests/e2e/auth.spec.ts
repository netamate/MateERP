import { expect, test } from "@playwright/test";

test("anonymous browser reaches the secure MateERP sign-in experience", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: /MateERP/i })).toBeVisible();
  await expect(page.getByRole("button", { name: "Sign in" })).toBeVisible();
});
