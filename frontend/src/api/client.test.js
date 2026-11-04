import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import {
  apiFetch,
  chargeDuJeton,
  getAccessToken,
  jetonExpire,
  obtenirJetonValide,
  setTokens,
  surSessionExpiree,
} from './client.js'

// Un jeton JWT « de poche » : seul le contenu (payload) compte pour `jetonExpire`, la signature n'est jamais vérifiée côté site.
function fabriquerJeton(expDansSecondes) {
  const base64url = (objet) => btoa(JSON.stringify(objet)).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '')
  return `${base64url({ alg: 'HS256' })}.${base64url({ exp: Math.floor(Date.now() / 1000) + expDansSecondes })}.signature`
}

function reponse(statut, corps = {}) {
  return {
    status: statut,
    ok: statut >= 200 && statut < 300,
    headers: { get: () => 'application/json' },
    json: async () => corps,
  }
}

function installerStockage() {
  const donnees = new Map()
  vi.stubGlobal('localStorage', {
    getItem: (cle) => (donnees.has(cle) ? donnees.get(cle) : null),
    setItem: (cle, valeur) => donnees.set(cle, String(valeur)),
    removeItem: (cle) => donnees.delete(cle),
  })
}

describe('jetonExpire', () => {
  it("un jeton qui vaut encore longtemps n'est pas expiré", () => {
    expect(jetonExpire(fabriquerJeton(600))).toBe(false)
  })

  it('un jeton déjà expiré, ou qui expire dans la marge, est expiré', () => {
    expect(jetonExpire(fabriquerJeton(-5))).toBe(true)
    expect(jetonExpire(fabriquerJeton(5))).toBe(true) // marge de 10 s par défaut : mieux vaut renouveler avant l'échéance
    expect(jetonExpire(fabriquerJeton(5), 0)).toBe(false)
  })

  it('un jeton illisible est traité comme expiré', () => {
    expect(jetonExpire('pas-un-jeton')).toBe(true)
    expect(jetonExpire('a.%%%.c')).toBe(true)
    expect(jetonExpire(`a.${btoa('{}')}.c`)).toBe(true) // pas de champ exp
  })
})

describe('chargeDuJeton', () => {
  it('lit ce que porte le jeton (durée de session et échéance)', () => {
    const base64url = (objet) => btoa(JSON.stringify(objet)).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '')
    const jeton = `${base64url({ alg: 'HS256' })}.${base64url({ exp: 2000000000, duree: 'semaine', vs: 2 })}.signature`
    expect(chargeDuJeton(jeton)).toEqual({ exp: 2000000000, duree: 'semaine', vs: 2 })
  })

  it("rend null pour un jeton illisible plutôt que d'échouer", () => {
    expect(chargeDuJeton('pas-un-jeton')).toBeNull()
    expect(chargeDuJeton('')).toBeNull()
    expect(chargeDuJeton('a.%%%.c')).toBeNull()
  })
})

describe('renouvellement des jetons', () => {
  let appels
  let routes
  let sessionsTerminees
  let desabonner

  beforeEach(() => {
    installerStockage()
    appels = []
    routes = {}
    sessionsTerminees = 0
    desabonner = surSessionExpiree(() => {
      sessionsTerminees += 1
    })
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url, options = {}) => {
        const chemin = url.replace(/^.*\/api/, '')
        appels.push({ chemin, autorisation: options.headers?.Authorization })
        const route = routes[chemin]
        if (!route) throw new Error(`route non prévue : ${chemin}`)
        return typeof route === 'function' ? route(options) : route
      }),
    )
  })

  afterEach(() => {
    desabonner()
    vi.unstubAllGlobals()
  })

  const renouvellements = () => appels.filter((appel) => appel.chemin === '/auth/refresh/').length

  describe('obtenirJetonValide', () => {
    it("renvoie le jeton tel quel tant qu'il est valable, sans appel réseau", async () => {
      const jeton = fabriquerJeton(600)
      setTokens(jeton, 'refresh')

      expect(await obtenirJetonValide()).toBe(jeton)
      expect(appels).toHaveLength(0)
    })

    it("renouvelle un jeton expiré et mémorise le nouveau", async () => {
      const neuf = fabriquerJeton(1800)
      setTokens(fabriquerJeton(-60), 'refresh')
      routes['/auth/refresh/'] = reponse(200, { access: neuf })

      expect(await obtenirJetonValide()).toBe(neuf)
      expect(getAccessToken()).toBe(neuf)
    })

    it('renouvellement refusé : session terminée, jetons effacés', async () => {
      setTokens(fabriquerJeton(-60), 'refresh-revoque')
      routes['/auth/refresh/'] = reponse(401, { detail: 'Token is invalid' })

      expect(await obtenirJetonValide()).toBeNull()
      expect(getAccessToken()).toBeNull()
      expect(sessionsTerminees).toBe(1)
    })

    it("sans jeton de renouvellement : null, et rien à terminer s'il n'y a pas de session", async () => {
      expect(await obtenirJetonValide()).toBeNull()
      expect(appels).toHaveLength(0)
    })

    it("réseau coupé pendant le renouvellement : ce n'est pas une fin de session", async () => {
      const ancien = fabriquerJeton(-60)
      setTokens(ancien, 'refresh')
      routes['/auth/refresh/'] = () => {
        throw new TypeError('Failed to fetch')
      }

      expect(await obtenirJetonValide()).toBeNull()
      expect(getAccessToken()).toBe(ancien) // les jetons sont gardés : on pourra réessayer
      expect(sessionsTerminees).toBe(0)
    })
  })

  describe('apiFetch', () => {
    it('un 401 renouvelle le jeton puis rejoue la requête avec le nouveau', async () => {
      const neuf = fabriquerJeton(1800)
      setTokens('ancien', 'refresh')
      routes['/departs/'] = (options) =>
        options.headers.Authorization === `Bearer ${neuf}` ? reponse(200, [{ id: 1 }]) : reponse(401, { detail: 'expiré' })
      routes['/auth/refresh/'] = reponse(200, { access: neuf })

      expect(await apiFetch('/departs/')).toEqual([{ id: 1 }])
      expect(sessionsTerminees).toBe(0)
    })

    it('plusieurs requêtes en 401 en même temps partagent un seul renouvellement', async () => {
      const neuf = fabriquerJeton(1800)
      setTokens('ancien', 'refresh')
      const accepte = (options) =>
        options.headers.Authorization === `Bearer ${neuf}` ? reponse(200, []) : reponse(401, { detail: 'expiré' })
      routes['/departs/'] = accepte
      routes['/vehicules/'] = accepte
      routes['/lignes/'] = accepte
      routes['/auth/refresh/'] = reponse(200, { access: neuf })

      await Promise.all([apiFetch('/departs/'), apiFetch('/vehicules/'), apiFetch('/lignes/')])

      expect(renouvellements()).toBe(1)
    })

    it('renouvellement refusé : la requête échoue en 401 et la session est terminée', async () => {
      setTokens('ancien', 'refresh-revoque')
      routes['/departs/'] = reponse(401, { detail: 'expiré' })
      routes['/auth/refresh/'] = reponse(401, { detail: 'Token is invalid' })

      await expect(apiFetch('/departs/')).rejects.toMatchObject({ status: 401 })
      expect(getAccessToken()).toBeNull()
      expect(sessionsTerminees).toBe(1)
    })

    it('un jeton neuf refusé à son tour (compte suspendu) termine la session', async () => {
      setTokens('ancien', 'refresh')
      routes['/departs/'] = reponse(401, { detail: 'Utilisateur inactif' })
      routes['/auth/refresh/'] = reponse(200, { access: fabriquerJeton(1800) })

      await expect(apiFetch('/departs/')).rejects.toMatchObject({ status: 401 })
      expect(sessionsTerminees).toBe(1)
    })

    it("une panne du serveur de renouvellement (500) ne déconnecte pas l'utilisateur", async () => {
      setTokens('ancien', 'refresh')
      routes['/departs/'] = reponse(401, { detail: 'expiré' })
      routes['/auth/refresh/'] = reponse(500, {})

      await expect(apiFetch('/departs/')).rejects.toMatchObject({ status: 401 })
      expect(getAccessToken()).toBe('ancien')
      expect(sessionsTerminees).toBe(0)
    })

    it("une erreur de connexion (auth: false) ne déclenche ni renouvellement ni fin de session", async () => {
      routes['/auth/login/'] = reponse(401, { detail: 'Identifiants incorrects' })

      await expect(apiFetch('/auth/login/', { method: 'POST', body: {}, auth: false })).rejects.toMatchObject({
        status: 401,
      })
      expect(renouvellements()).toBe(0)
      expect(sessionsTerminees).toBe(0)
    })
  })
})
