import { test, expect } from "@playwright/test";

test.describe("Fresh start", () => {
  test("shows default watchlist and $10k balance", async ({ page }) => {
    await page.goto("/");
    // Header shows default portfolio value and cash
    await expect(page.getByText("$10,000.00").first()).toBeVisible();
    // App title renders
    await expect(page.getByRole("heading", { level: 1 })).toContainText(
      "FinAlly"
    );
  });

  test("prices are streaming via SSE", async ({ page }) => {
    await page.goto("/");
    // Wait for connection status to show connected
    await expect(page.getByText("connected")).toBeVisible({ timeout: 10_000 });
    // At least one ticker should show a numeric price
    await expect(page.locator("td.tabular-nums").first()).not.toHaveText("--", {
      timeout: 10_000,
    });
  });
});

test.describe("Watchlist CRUD", () => {
  test("add and remove a ticker", async ({ page }) => {
    await page.goto("/");

    // Add a ticker
    const input = page.getByPlaceholder("Add ticker");
    await input.fill("SNAP");
    await input.press("Enter");
    await expect(page.getByText("SNAP")).toBeVisible({ timeout: 5_000 });

    // Remove the ticker
    const snapRow = page.locator("tr", { hasText: "SNAP" });
    await snapRow.getByTitle("Remove").click();
    await expect(page.getByText("SNAP")).not.toBeVisible({ timeout: 5_000 });
  });
});

test.describe("Trading", () => {
  test("buy shares: cash decreases and position appears", async ({ page }) => {
    await page.goto("/");
    // Wait for a live SSE connection so the ticker has a market price
    await expect(page.getByText("connected", { exact: true })).toBeVisible({
      timeout: 10_000,
    });

    await page.getByPlaceholder("Ticker", { exact: true }).fill("AAPL");
    await page.getByPlaceholder("Qty").fill("1");
    await page.getByRole("button", { name: "BUY" }).click();

    // Trade-bar confirmation shows the executed fill
    await expect(page.getByText(/BUY 1 AAPL @ \$/i)).toBeVisible({
      timeout: 10_000,
    });
  });

  test("sell shares: cash increases and position updates", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByText("connected", { exact: true })).toBeVisible({
      timeout: 10_000,
    });

    // Buy first so there is a position to sell
    await page.getByPlaceholder("Ticker", { exact: true }).fill("MSFT");
    await page.getByPlaceholder("Qty").fill("2");
    await page.getByRole("button", { name: "BUY" }).click();
    await expect(page.getByText(/BUY 2 MSFT @ \$/i)).toBeVisible({
      timeout: 10_000,
    });

    // Then sell part of it
    await page.getByPlaceholder("Ticker", { exact: true }).fill("MSFT");
    await page.getByPlaceholder("Qty").fill("1");
    await page.getByRole("button", { name: "SELL" }).click();
    await expect(page.getByText(/SELL 1 MSFT @ \$/i)).toBeVisible({
      timeout: 10_000,
    });
  });
});

test.describe("Portfolio visualization", () => {
  test("heatmap panel renders", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByText("Portfolio Heatmap")).toBeVisible();
  });

  test("P&L panel renders", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByText("P&L")).toBeVisible();
  });
});

test.describe("AI Chat", () => {
  test("send a message and get a response", async ({ page }) => {
    await page.goto("/");

    // Chat panel should be visible
    await expect(page.getByText("AI Chat")).toBeVisible();

    // Empty state message
    await expect(
      page.getByText("Ask about stocks, trade, or manage your watchlist.")
    ).toBeVisible();

    // Type and send a message
    const chatInput = page.getByPlaceholder("Message...");
    await chatInput.fill("What stocks should I buy?");
    await page.getByRole("button", { name: "Send" }).click();

    // User message should appear
    await expect(
      page.getByText("What stocks should I buy?")
    ).toBeVisible();

    // Wait for assistant response (mocked or real)
    await expect(
      page.locator(".bg-bg-secondary.text-text-primary").first()
    ).toBeVisible({ timeout: 15_000 });
  });

  test("chat panel collapses and expands", async ({ page }) => {
    await page.goto("/");

    // Collapse
    await page.getByLabel("Collapse chat").click();
    await expect(page.getByText("AI Chat")).not.toBeVisible();

    // Expand
    await page.getByLabel("Expand chat").click();
    await expect(page.getByText("AI Chat")).toBeVisible();
  });
});

test.describe("SSE resilience", () => {
  test("reconnects after disconnect", async ({ page }) => {
    await page.goto("/");
    // Wait for initial connection
    await expect(page.getByText("connected", { exact: true })).toBeVisible({
      timeout: 10_000,
    });

    // Block the SSE endpoint and reload so the new EventSource fails to connect
    await page.route("**/api/stream/prices", (route) => route.abort());
    await page.reload();

    // App should report it is no longer connected
    await expect(
      page
        .getByText("reconnecting", { exact: true })
        .or(page.getByText("disconnected", { exact: true }))
    ).toBeVisible({ timeout: 10_000 });

    // Restore the endpoint — native EventSource auto-reconnects
    await page.unroute("**/api/stream/prices");

    // Should reconnect
    await expect(page.getByText("connected", { exact: true })).toBeVisible({
      timeout: 20_000,
    });
  });
});
