// Essais de bout en bout dans un vrai navigateur, contre une vraie API et une base jetable.
//
//   npm run e2e                 prépare la base, lance l'API et le site compilé, joue tous les scénarios
//   npm run e2e -- --garder     laisse la base et les serveurs (port 8010 / 4173) pour les regarder à la main
//   npm run e2e -- smoke        ne joue que les scénarios dont le nom contient « smoke » (plusieurs : « jeu,caisse »)
//
// Prérequis : Python et PostgreSQL du backend (voir transpt1/README.md) et un Chrome ou Edge installé. Rien n'est
// téléchargé, aucun service extérieur n'est appelé (les SMS sont simulés).
//
// La même pile (base jetable + API + site) sert aux essais Playwright Test : voir `npm run e2e:pw` et pile.setup.mjs.
import fs from 'node:fs'
import path from 'node:path'
import { chromium } from 'playwright-core'
import { BACKEND, FRONTEND, URL_API, URL_WEB, demarrerPile, detruirePile, navigateur } from './lib.mjs'
import { scenarios } from './scenarios.mjs'

const args = process.argv.slice(2)
const garder = args.includes('--garder')
const filtre = args.find((a) => !a.startsWith('--'))
const CAPTURES = path.join(FRONTEND, 'e2e', 'captures')

async function main() {
  const { env, py } = await demarrerPile()

  // Une capture ouverte dans un visualiseur verrouille le dossier sous Windows : on réessaie avant d'abandonner.
  fs.rmSync(CAPTURES, { recursive: true, force: true, maxRetries: 10, retryDelay: 300 })
  fs.mkdirSync(CAPTURES, { recursive: true })

  const chrome = await chromium.launch({ executablePath: navigateur(), headless: true })
  const contexte = { chrome, URL_WEB, URL_API, CAPTURES, BACKEND, py, env }
  let echecs = 0
  const lignes = []
  try {
    for (const scenario of scenarios.filter((s) => !filtre || filtre.split(',').some((f) => s.nom.includes(f)))) {
      const debut = Date.now()
      try {
        const details = (await scenario.jouer(contexte)) || []
        lignes.push({ nom: scenario.nom, ok: true, ms: Date.now() - debut, details })
      } catch (erreur) {
        echecs += 1
        lignes.push({ nom: scenario.nom, ok: false, ms: Date.now() - debut, details: [String(erreur.message || erreur)] })
      }
    }
  } finally {
    await chrome.close()
  }

  console.log('\nRésultats')
  for (const ligne of lignes) {
    console.log(`${ligne.ok ? 'OK  ' : 'ÉCHEC'} ${ligne.nom} (${(ligne.ms / 1000).toFixed(1)} s)`)
    for (const detail of ligne.details) console.log(`      ${detail}`)
  }
  console.log(`\n${lignes.length - echecs}/${lignes.length} scénario(s) réussi(s). Captures : ${CAPTURES}`)
  return echecs
}

let echecs = 1
try {
  echecs = await main()
} catch (erreur) {
  console.error(erreur.message || erreur)
} finally {
  if (garder && echecs === 0) {
    console.log(`\nServeurs laissés en marche : ${URL_WEB} (site) et ${URL_API} (API). Ctrl+C pour arrêter.`)
    await new Promise(() => {})
  }
  detruirePile()
}
process.exit(echecs === 0 ? 0 : 1)
