import { defineConfig, devices } from '@playwright/test'
import { URL_WEB, navigateur } from './e2e/lib.mjs'

// Essais Playwright Test (« npm run e2e:pw »), à côté des scénarios de « npm run e2e » (e2e/run.mjs) : même pile
// (base jetable + API + site compilé), montée par e2e/pile.setup.mjs. Aucun navigateur n'est téléchargé : on utilise le
// Chrome ou Edge déjà installé (E2E_BROWSER pour en indiquer un autre).
function navigateurInstalle(): string | undefined {
  try {
    return navigateur()
  } catch {
    return undefined // « playwright test --list » doit marcher sans navigateur ; l'échec est signalé au lancement
  }
}

export default defineConfig({
  testDir: './e2e',
  testMatch: '**/*.spec.ts',
  globalSetup: './e2e/pile.setup.mjs',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: [['html', { open: 'never' }]],
  // Une connexion vérifie un mot de passe haché en PBKDF2 (1,5 million d'itérations) : ≈ 2 s sur une machine modeste, davantage
  // quand deux connexions se chevauchent. Les 5 s par défaut d'une attente y sont trop justes.
  expect: { timeout: 20_000 },
  use: {
    baseURL: URL_WEB,
    locale: 'fr-FR',
    trace: 'on-first-retry',
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'], launchOptions: { executablePath: navigateurInstalle() } },
    },
  ],
})
