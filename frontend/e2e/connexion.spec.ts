import { type Page, expect, test } from '@playwright/test'

// Compte de démonstration créé par seed_demo_users (voir comptes.json) ; le mot de passe est commun aux comptes d'essai.
const IDENTIFIANT = 'guichetier_stc'
const MOT_DE_PASSE = 'Demo!2024'
const PAGE_DU_GUICHETIER = '/dashboard/guichetier'

async function remplirEtValider(page: Page, motDePasse: string) {
  await page.getByLabel('Identifiant').fill(IDENTIFIANT)
  await page.getByLabel('Mot de passe').fill(motDePasse)
  await page.getByRole('button', { name: 'Se connecter' }).click()
}

test.describe('Connexion', () => {
  test("l'écran de connexion demande un identifiant et un mot de passe", async ({ page }) => {
    await page.goto('/login')
    await expect(page.getByRole('heading', { name: 'Transport Coord' })).toBeVisible()
    await expect(page.getByLabel('Identifiant')).toBeVisible()
    await expect(page.getByLabel('Mot de passe')).toBeVisible()
    await expect(page.getByRole('button', { name: 'Se connecter' })).toBeEnabled()
  })

  test('un guichetier arrive sur son tableau de bord', async ({ page }) => {
    await page.goto('/login')
    await remplirEtValider(page, MOT_DE_PASSE)
    await expect(page).toHaveURL(new RegExp(`${PAGE_DU_GUICHETIER}$`))
  })

  test("un mot de passe erroné affiche une erreur et laisse sur l'écran de connexion", async ({ page }) => {
    await page.goto('/login')
    await remplirEtValider(page, 'pas-le-bon-mot-de-passe')
    await expect(page.locator('.alert-error')).toBeVisible()
    await expect(page).toHaveURL(/\/login$/)
  })

  test("une page réservée renvoie vers l'écran de connexion quand personne n'est connecté", async ({ page }) => {
    await page.goto(PAGE_DU_GUICHETIER)
    await expect(page).toHaveURL(/\/login$/)
  })
})
