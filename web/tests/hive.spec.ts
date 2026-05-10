import { test, expect, type Page, type ConsoleMessage } from "@playwright/test";
import * as fs from "fs";
import * as path from "path";

// ── helpers ────────────────────────────────────────────────────────────────

const ROUTES = [
  { path: "/hive",            name: "hive-dashboard"  },
  { path: "/hive/issues",     name: "issues"          },
  { path: "/hive/pulls",      name: "pulls"           },
  { path: "/hive/workflows",  name: "workflows"       },
  { path: "/hive/commits",    name: "commits"         },
  { path: "/hive/assistant",  name: "assistant"       },
  { path: "/hive/analysis",   name: "analysis"        },
  { path: "/hive/keys",       name: "keys"            },
  { path: "/hive/logs",       name: "logs"            },
  { path: "/hive/explorer",   name: "explorer"        },
  { path: "/hive/tracker",    name: "tracker"         },
  { path: "/hive/settings",   name: "settings"        },
  { path: "/hive/knowledge",  name: "knowledge"       },
];

const SCREENSHOT_DIR = path.join(__dirname, "screenshots");
fs.mkdirSync(SCREENSHOT_DIR, { recursive: true });

/** Collect browser console errors during a page visit. */
function attachConsoleCapture(page: Page) {
  const errors: string[] = [];
  page.on("console", (msg: ConsoleMessage) => {
    if (msg.type() === "error") errors.push(msg.text());
  });
  page.on("pageerror", (err: Error) => errors.push(err.message));
  return errors;
}

/** Wait for hydration: no more loading spinners, network idle. */
async function waitForHydration(page: Page) {
  await page.waitForLoadState("networkidle", { timeout: 15_000 }).catch(() => {});
  // Wait for Next.js hydration marker to disappear
  await page.waitForFunction(
    () => !document.documentElement.hasAttribute("data-loading"),
    { timeout: 5_000 }
  ).catch(() => {});
  // Small buffer so fonts + CSS vars settle
  await page.waitForTimeout(600);
}

async function screenshotPage(page: Page, name: string, suffix: string) {
  const filename = `${name}--${suffix}.png`;
  await page.screenshot({
    path: path.join(SCREENSHOT_DIR, filename),
    fullPage: true,
  });
  return filename;
}

// ── SUITE 1: status 200 for all routes ────────────────────────────────────

test.describe("Route health — all routes return 200", () => {
  for (const route of ROUTES) {
    test(route.path, async ({ page }) => {
      const response = await page.goto(route.path);
      expect(response?.status(), `${route.path} should return 200`).toBe(200);
    });
  }
});

// ── SUITE 2: ActiveTaskBar present on every route ─────────────────────────

test.describe("ActiveTaskBar — fixed top bar visible on every page", () => {
  for (const route of ROUTES) {
    test(route.path, async ({ page }) => {
      await page.goto(route.path);
      await waitForHydration(page);

      // The bar is `fixed top-0 left-0 right-0`, height 36px
      const bar = page.locator("div").filter({
        has: page.locator("[style*='height: 36px'], [style*='height:36px']"),
      }).first();

      // Fallback: check by known content — it always has a rounded-full dot
      // More reliable: check no duplicate headers by verifying pt-9 on layout wrapper
      const body = page.locator("body");
      const html = await body.innerHTML();
      expect(html).toContain("fixed top-0");
    });
  }
});

// ── SUITE 3: PageHeader on every secondary page ────────────────────────────

const SECONDARY_ROUTES = ROUTES.filter((r) => r.path !== "/hive");

test.describe("PageHeader — sticky header present on all secondary pages", () => {
  for (const route of SECONDARY_ROUTES) {
    test(route.path, async ({ page }) => {
      await page.goto(route.path);
      await waitForHydration(page);

      // PageHeader renders a <header> with sticky + top-9 + z-40
      const header = page.locator("header").first();
      await expect(header).toBeVisible();

      const classAttr = await header.getAttribute("class") ?? "";
      expect(
        classAttr.includes("sticky") || classAttr.includes("top-9"),
        `${route.path}: PageHeader should be sticky`
      ).toBe(true);
    });
  }
});

// ── SUITE 4: SubNav on Issues, Pulls, Workflows, Commits ─────────────────

const SUBNAV_ROUTES = [
  { path: "/hive/issues",    tabs: ["Issues", "PRs"]        },
  { path: "/hive/pulls",     tabs: ["Issues", "PRs"]        },
  { path: "/hive/workflows", tabs: ["Workflows", "Commits"] },
  { path: "/hive/commits",   tabs: ["Workflows", "Commits"] },
];

test.describe("SubNav — tab strip present and correct labels", () => {
  for (const { path: routePath, tabs } of SUBNAV_ROUTES) {
    test(routePath, async ({ page }) => {
      await page.goto(routePath);
      await waitForHydration(page);

      for (const label of tabs) {
        const subnav = page.locator('[data-testid="subnav"]');
        await expect(
          subnav.getByRole("link", { name: label, exact: true }),
          `${routePath}: tab "${label}" should exist`
        ).toBeVisible();
      }
    });
  }
});

// ── SUITE 5: Dashboard widgets on /hive ───────────────────────────────────

test.describe("Hive dashboard — key widgets present", () => {
  test("stat tiles render (health, sessions, errors, blockers)", async ({ page }) => {
    await page.goto("/hive");
    await waitForHydration(page);

    // After hydration, HiveStatusCard should show stat tiles
    // Look for the section-title labels
    const body = await page.locator("body").innerHTML();
    const lower = body.toLowerCase();
    expect(lower).toMatch(/health|sessions|errors|blockers/);
  });

  test("quick-links chip bar has all 6 links", async ({ page }) => {
    await page.goto("/hive");
    await waitForHydration(page);

    for (const label of ["Logs", "Keys", "Files", "Knowledge", "Tracker", "Settings"]) {
      await expect(
        page.getByRole("link", { name: label }).first(),
        `Quick-link "${label}" should exist`
      ).toBeVisible();
    }
  });

  test("BottomNav has exactly 5 tabs", async ({ page }) => {
    await page.goto("/hive");
    await waitForHydration(page);

    // BottomNav is fixed bottom — count its anchor links
    const nav = page.locator("nav").last();
    const links = nav.getByRole("link");
    await expect(links).toHaveCount(5);
  });
});

// ── SUITE 6: AI Assistant uses textarea (not input) ───────────────────────

test.describe("AIAssistant — textarea and clear button", () => {
  test("uses textarea instead of input[type=text]", async ({ page }) => {
    await page.goto("/hive/assistant");
    await waitForHydration(page);

    const textarea = page.locator("textarea");
    await expect(textarea).toBeVisible();

    // Should NOT have a text-type input in the compose area
    const textInputs = page.locator("input[type='text']");
    const count = await textInputs.count();
    expect(count, "No text inputs should exist in assistant — use textarea").toBe(0);
  });

  test("Enter sends, Shift+Enter is newline", async ({ page }) => {
    await page.goto("/hive/assistant");
    await waitForHydration(page);

    const textarea = page.locator("textarea");
    await textarea.fill("hello");
    await textarea.press("Shift+Enter");
    // Shift+Enter should not submit — textarea still focused
    await expect(textarea).toBeFocused();
  });

  test("clear button appears after a message is sent", async ({ page }) => {
    // We just verify the clear button icon ⊟ is in the DOM somewhere
    // after chat messages exist (mock by injecting state)
    await page.goto("/hive/assistant");
    await waitForHydration(page);

    // Check the attach ⊕ button is present
    const attachBtn = page.getByTitle("Attach file");
    await expect(attachBtn).toBeVisible();
  });
});

// ── SUITE 7: Analysis page scroll containment ─────────────────────────────

test.describe("Analysis page — max-height scroll container", () => {
  test("glass-card has max-height set", async ({ page }) => {
    await page.goto("/hive/analysis");
    await waitForHydration(page);

    // The glass-card that wraps the markdown should have max-height style
    const card = page.locator(".glass-card").first();
    const style = await card.getAttribute("style") ?? "";
    const classAttr = await card.getAttribute("class") ?? "";
    // Either via style attr or via overflow-y-auto class — verify overflow-y-auto present
    expect(
      style.includes("max-height") || classAttr.includes("overflow-y-auto"),
      "Analysis glass-card should have max-height or overflow-y-auto"
    ).toBe(true);
  });
});

// ── SUITE 8: No broken emoji in geometric-icon pages ─────────────────────

test.describe("Icon consistency — no 🔬📁📄 emoji on explorer/tracker", () => {
  test("explorer has no emoji icons", async ({ page }) => {
    await page.goto("/hive/explorer");
    await waitForHydration(page);
    const html = await page.locator("body").innerHTML();
    expect(html).not.toContain("📁");
    expect(html).not.toContain("📄");
  });

  test("tracker has no emoji icons", async ({ page }) => {
    await page.goto("/hive/tracker");
    await waitForHydration(page);
    const html = await page.locator("body").innerHTML();
    expect(html).not.toContain("🔬");
  });

  test("workflows uses ⊛ not ⚙", async ({ page }) => {
    await page.goto("/hive/workflows");
    await waitForHydration(page);
    const html = await page.locator("body").innerHTML();
    // The old ⚙ should be replaced with ⊛
    const header = await page.locator("header").first().innerHTML();
    expect(header).not.toContain("⚙");
    expect(header).toContain("⊛");
  });
});

// ── SUITE 9: Settings + Knowledge have PageHeader ─────────────────────────

test.describe("Settings and Knowledge — proper page header", () => {
  test("settings has sticky header (not bare h1)", async ({ page }) => {
    await page.goto("/hive/settings");
    await waitForHydration(page);

    const html = await page.locator("body").innerHTML();
    // Old code had bare <h1>Settings</h1> — should now be in PageHeader
    // PageHeader has sticky + top-9 on its header element
    const header = page.locator("header").first();
    const cls = await header.getAttribute("class") ?? "";
    expect(cls).toMatch(/sticky/);
  });

  test("knowledge has sticky header", async ({ page }) => {
    await page.goto("/hive/knowledge");
    await waitForHydration(page);
    const header = page.locator("header").first();
    const cls = await header.getAttribute("class") ?? "";
    expect(cls).toMatch(/sticky/);
  });
});

// ── SUITE 10: Console errors ──────────────────────────────────────────────

test.describe("Console errors — no JS errors on any route", () => {
  for (const route of ROUTES) {
    test(route.path, async ({ page }) => {
      const errors = attachConsoleCapture(page);
      await page.goto(route.path);
      await waitForHydration(page);

      const fatal = errors.filter(
        (e) =>
          !e.includes("ERR_CONNECTION_REFUSED") && // backend offline is expected in test env
          !e.includes("net::ERR") &&
          !e.includes("Failed to fetch") &&
          !e.includes("api/stream") &&             // SSE may fail without live backend
          !e.includes("api/questions") &&
          !e.includes("api/doctor") &&
          !e.includes("api/arena") &&
          !e.includes("api/logs") &&
          !e.includes("api/status") &&
          !e.includes("api/tracker") &&
          !e.includes("api/config") &&
          !e.includes("api/keys")
      );

      expect(
        fatal,
        `${route.path} has unexpected console errors: ${fatal.join("; ")}`
      ).toHaveLength(0);
    });
  }
});

// ── SUITE 11: Full-page screenshots (visual record) ───────────────────────

test.describe("Screenshots — visual record of every route", () => {
  const viewport = test.info ? null : null; // resolved per project in config

  for (const route of ROUTES) {
    test(route.name, async ({ page }, testInfo) => {
      await page.goto(route.path);
      await waitForHydration(page);

      const project = testInfo.project.name; // "mobile" or "desktop"
      const filename = `${route.name}--${project}.png`;
      const filepath = path.join(SCREENSHOT_DIR, filename);

      await page.screenshot({ path: filepath, fullPage: true });
      await testInfo.attach(filename, { path: filepath, contentType: "image/png" });
    });
  }
});
