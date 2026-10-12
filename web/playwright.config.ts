import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./tests",
  fullyParallel: false,
  workers: 1,
  reporter: "list",
  outputDir: "test-results",
  use: {
    baseURL: "http://127.0.0.1:3100",
    trace: "on-first-retry",
  },
  webServer: [
    {
      command:
        "cd .. && mkdir -p web/test-results && rm -f web/test-results/playwright-dev.db && export APP_ENV=test AUTH_MODE=dev DEBUG=true LLM_PROVIDER=fake DATABASE_URL=sqlite:///../web/test-results/playwright-dev.db CORS_ALLOWED_ORIGINS=http://127.0.0.1:3100,http://localhost:3100 && cd backend && PYTHONPATH=. ../.venv/bin/alembic -c alembic.ini upgrade head && PYTHONPATH=. ../.venv/bin/python scripts/dev_seed.py && PYTHONPATH=. ../.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8010",
      port: 8010,
      reuseExistingServer: false,
      timeout: 120_000,
    },
    {
      command:
        "NEXT_PUBLIC_API_BASE_URL=/api/v1 NEXT_PUBLIC_AUTH_MODE=dev npm run dev -- --hostname 127.0.0.1 --port 3100",
      port: 3100,
      reuseExistingServer: false,
      timeout: 120_000,
    },
  ],
  projects: [
    {
      name: "chromium",
      use: {
        ...devices["Desktop Chrome"],
      },
    },
  ],
});
