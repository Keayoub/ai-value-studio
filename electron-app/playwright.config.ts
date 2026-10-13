import { defineConfig } from "@playwright/test";

export default defineConfig({
  fullyParallel: false,
  workers: 1,
  reporter: "list",
  outputDir: "test-results",
  webServer: [
    {
      command:
        "cd .. && mkdir -p electron-app/test-results && rm -f electron-app/test-results/electron-smoke.db && export APP_ENV=test AUTH_MODE=dev DEBUG=true LLM_PROVIDER=fake DATABASE_URL=sqlite:///../electron-app/test-results/electron-smoke.db CORS_ALLOWED_ORIGINS=http://127.0.0.1:3100,http://localhost:3100 && cd backend && PYTHONPATH=. ../.venv/bin/alembic -c alembic.ini upgrade head && PYTHONPATH=. ../.venv/bin/python scripts/dev_seed.py && PYTHONPATH=. ../.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8010",
      port: 8010,
      reuseExistingServer: false,
      timeout: 120_000,
    },
  ],
});
