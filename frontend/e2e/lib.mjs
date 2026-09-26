// Outils de l'environnement d'essai de bout en bout : processus, attente des serveurs, choix du navigateur.
import { spawn, spawnSync } from 'node:child_process'
import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'

export const FRONTEND = path.resolve(import.meta.dirname, '..')
export const BACKEND = path.resolve(FRONTEND, '..', 'transpt1')

export const PORT_API = Number(process.env.E2E_PORT_API || 8010)
export const PORT_WEB = Number(process.env.E2E_PORT_WEB || 4173)
export const URL_API = `http://localhost:${PORT_API}/api`
export const URL_WEB = `http://localhost:${PORT_WEB}`
// Les pièces jointes des essais (sinistres, modèles de documents) vont dans un dossier jetable, vidé à chaque essai.
export const MEDIA_E2E = path.join(os.tmpdir(), 'transport-coord-e2e-media')

export function python() {
  if (process.env.E2E_PYTHON) return process.env.E2E_PYTHON
  for (const candidat of [
    path.join(BACKEND, 'venv', 'Scripts', 'python.exe'),
    path.join(BACKEND, 'venv', 'bin', 'python'),
  ]) {
    if (fs.existsSync(candidat)) return candidat
  }
  return 'python'
}

/** Navigateur Chromium déjà installé (Chrome ou Edge) : aucun téléchargement de navigateur n'est nécessaire. */
export function navigateur() {
  if (process.env.E2E_BROWSER) return process.env.E2E_BROWSER
  const candidats = [
    'C:/Program Files/Google/Chrome/Application/chrome.exe',
    'C:/Program Files (x86)/Google/Chrome/Application/chrome.exe',
    'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',
    '/usr/bin/google-chrome',
    '/usr/bin/chromium',
    '/usr/bin/chromium-browser',
    '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
  ]
  const trouve = candidats.find((c) => fs.existsSync(c))
  if (!trouve) throw new Error('Aucun Chrome/Edge trouvé : indiquez-le avec la variable E2E_BROWSER.')
  return trouve
}

/** Environnement des commandes du serveur : base jetable, mode développement (les données de démo l'exigent). */
export function environnementServeur(base) {
  return {
    ...process.env,
    DB_NAME: base,
    DJANGO_DEBUG: 'True',
    DJANGO_MEDIA_ROOT: MEDIA_E2E,
    DJANGO_ALLOWED_HOSTS: 'localhost,127.0.0.1',
    CORS_ALLOWED_ORIGINS: URL_WEB,
    NOTIFICATIONS_SIMULATION_MODE: 'True',
    // Une vingtaine de connexions d'affilée depuis la même adresse : sans cela, la limitation les freinerait.
    CONNEXION_LIMITE_COMPTE: '1000/min',
    CONNEXION_LIMITE_ADRESSE: '1000/min',
    PYTHONIOENCODING: 'utf-8',
    PYTHONUTF8: '1',
  }
}

export function executer(commande, args, { cwd, env, titre } = {}) {
  console.log(`> ${titre || [commande, ...args].join(' ')}`)
  const resultat = spawnSync(commande, args, { cwd, env, stdio: ['ignore', 'pipe', 'pipe'], encoding: 'utf-8' })
  if (resultat.status !== 0) {
    console.error(resultat.stdout)
    console.error(resultat.stderr)
    throw new Error(`Échec (${resultat.status}) : ${titre || commande}`)
  }
  return resultat.stdout
}

const processus = []

export function lancer(commande, args, { cwd, env, nom }) {
  console.log(`> [${nom}] ${[commande, ...args].join(' ')}`)
  const enfant = spawn(commande, args, { cwd, env, stdio: ['ignore', 'pipe', 'pipe'] })
  let sortie = ''
  for (const flux of [enfant.stdout, enfant.stderr]) flux.on('data', (morceau) => (sortie = (sortie + morceau).slice(-4000)))
  enfant.journal = () => sortie
  enfant.nom = nom
  processus.push(enfant)
  return enfant
}

export function arreterTout() {
  for (const enfant of processus.splice(0)) {
    if (enfant.exitCode !== null) continue
    if (process.platform === 'win32') spawnSync('taskkill', ['/PID', String(enfant.pid), '/T', '/F'])
    else enfant.kill('SIGTERM')
  }
}

export async function attendre(url, { statutsAcceptes, delaiMs = 60000, enfant } = {}) {
  const limite = Date.now() + delaiMs
  while (Date.now() < limite) {
    if (enfant && enfant.exitCode !== null) throw new Error(`${enfant.nom} s'est arrêté :\n${enfant.journal()}`)
    try {
      const reponse = await fetch(url)
      if (!statutsAcceptes || statutsAcceptes.includes(reponse.status)) return
    } catch {
      // pas encore prêt
    }
    await new Promise((resolve) => setTimeout(resolve, 500))
  }
  throw new Error(`${url} ne répond pas après ${delaiMs / 1000} s${enfant ? `\n${enfant.journal()}` : ''}`)
}
