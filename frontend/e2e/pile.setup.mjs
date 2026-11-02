// Pile des essais Playwright Test (« npm run e2e:pw ») : la même que « npm run e2e », c'est-à-dire une base jetable
// garnie des comptes de démonstration, l'API Django (port 8010) et le site compilé (port 4173). Elle est montée avant
// la première spec et démontée après la dernière, même en cas d'échec.
//
// E2E_REUTILISER=1 : ne rien monter, viser la pile déjà lancée par « npm run e2e -- --garder » (pratique pour écrire une spec).
import { demarrerPile, detruirePile } from './lib.mjs'

export default async function preparerPile() {
  if (process.env.E2E_REUTILISER) return undefined
  try {
    await demarrerPile()
  } catch (erreur) {
    detruirePile()
    throw erreur
  }
  return detruirePile
}
