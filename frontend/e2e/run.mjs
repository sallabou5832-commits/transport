// Essais de bout en bout dans un vrai navigateur, contre une vraie API et une base jetable.
//
//   npm run e2e                 prépare la base, lance l'API et le site compilé, joue tous les scénarios
//   npm run e2e -- --garder     laisse la base et les serveurs (port 8010 / 4173) pour les regarder à la main
//   npm run e2e -- smoke        ne joue que les scénarios dont le nom contient « smoke » (plusieurs : « jeu,caisse »)
//
// Prérequis : Python et PostgreSQL du backend (voir transpt1/README.md) et un Chrome ou Edge installé. Rien n'est
// téléchargé, aucun service extérieur n'est appelé (les SMS sont simulés).
import fs from 'node:fs'
import path from 'node:path'
import { chromium } from 'playwright-core'
import {
  BACKEND,
  FRONTEND,
  MEDIA_E2E,
  PORT_API,
  PORT_WEB,
  URL_API,
  URL_WEB,
  arreterTout,
  attendre,
  environnementServeur,
  executer,
  lancer,
  navigateur,
  python,
} from './lib.mjs'
import { scenarios } from './scenarios.mjs'

const BASE = process.env.E2E_DB_NAME || 'transport_coord_e2e'
const args = process.argv.slice(2)
const garder = args.includes('--garder')
const filtre = args.find((a) => !a.startsWith('--'))
const CAPTURES = path.join(FRONTEND, 'e2e', 'captures')

const SEEDS = ['seed_demo_users', 'seed_demo_reseau', 'seed_demo_operations', 'seed_demo_tableaux', 'generer_alertes']

async function main() {
  const env = environnementServeur(BASE)
  const py = python()
  fs.rmSync(MEDIA_E2E, { recursive: true, force: true, maxRetries: 10, retryDelay: 300 })

  // Le script de préparation se connecte à la base de développement pour créer l'autre : il garde l'environnement d'origine.
  const envBase = { ...process.env, E2E_DB_NAME: BASE }
  executer(py, ['scripts/base_e2e.py', 'creer'], { cwd: BACKEND, env: envBase, titre: 'création de la base jetable' })
  executer(py, ['manage.py', 'migrate', '--noinput'], { cwd: BACKEND, env, titre: 'migrations' })
  for (const seed of SEEDS) executer(py, ['manage.py', seed], { cwd: BACKEND, env, titre: seed })

  const api = lancer(py, ['manage.py', 'runserver', String(PORT_API), '--noreload'], { cwd: BACKEND, env, nom: 'api' })
  await attendre(`${URL_API}/auth/me/`, { statutsAcceptes: [401], enfant: api })

  executer(process.execPath, ['node_modules/vite/bin/vite.js', 'build', '--outDir', 'dist-e2e', '--emptyOutDir'], {
    cwd: FRONTEND,
    env: { ...process.env, VITE_API_BASE_URL: URL_API },
    titre: 'compilation du site',
  })
  const site = lancer(
    process.execPath,
    ['node_modules/vite/bin/vite.js', 'preview', '--outDir', 'dist-e2e', '--port', String(PORT_WEB), '--strictPort', '--host', 'localhost'],
    { cwd: FRONTEND, env: process.env, nom: 'site' },
  )
  await attendre(URL_WEB, { statutsAcceptes: [200], enfant: site })

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
  arreterTout()
  fs.rmSync(MEDIA_E2E, { recursive: true, force: true, maxRetries: 10, retryDelay: 300 })
  try {
    executer(python(), ['scripts/base_e2e.py', 'detruire'], {
      cwd: BACKEND,
      env: { ...process.env, E2E_DB_NAME: BASE },
      titre: 'suppression de la base jetable',
    })
  } catch (erreur) {
    console.error(erreur.message)
  }
}
process.exit(echecs === 0 ? 0 : 1)
