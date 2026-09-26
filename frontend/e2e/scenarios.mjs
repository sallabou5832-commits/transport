// Scénarios de bout en bout. Chaque scénario reçoit le contexte de run.mjs et lève une erreur au premier écart.
// Un scénario se joue avec de vrais comptes de démonstration (transpt1/*/management/commands/seed_demo_*.py).
import path from 'node:path'
import comptes from './comptes.json' with { type: 'json' }
import { executer } from './lib.mjs'

const MOT_DE_PASSE = 'Demo!2024'

/**
 * Ouvre une session neuve (contexte de navigateur isolé) et se connecte par l'écran de connexion. `problemes`
 * recense tout ce qu'un utilisateur ne devrait jamais rencontrer : erreur JavaScript, erreur affichée dans la
 * console, réponse 4xx/5xx de l'API.
 */
export async function connecter(ctx, username, { geolocalisation, ignorer = [] } = {}) {
  const contexteNavigateur = await ctx.chrome.newContext({
    viewport: { width: 1280, height: 900 },
    locale: 'fr-FR',
    // Position simulée de l'appareil (le suivi GPS du chauffeur) : le navigateur d'essai n'a pas de puce GPS.
    ...(geolocalisation ? { geolocation: geolocalisation, permissions: ['geolocation'] } : {}),
  })
  const page = await contexteNavigateur.newPage()
  const problemes = []
  const retenir = (probleme) => {
    // `ignorer` : erreurs que le scénario provoque exprès (ex. le 409 « confirmation requise », que Chrome journalise aussi).
    if (!ignorer.some((motif) => motif.test(probleme))) problemes.push(probleme)
  }
  page.on('console', (message) => {
    if (message.type() === 'error') retenir(`console : ${message.text()}`)
  })
  page.on('pageerror', (erreur) => problemes.push(`erreur JavaScript : ${erreur.message}`))
  page.on('response', (reponse) => {
    if (reponse.status() >= 400 && reponse.url().startsWith(ctx.URL_API)) {
      retenir(`HTTP ${reponse.status()} ${reponse.request().method()} ${reponse.url().replace(ctx.URL_API, '')}`)
    }
  })
  // Un changement de réseau de la machine (Wi-Fi qui se reconnecte) interrompt la navigation, même vers localhost : on réessaie.
  for (let essai = 1; ; essai++) {
    try {
      await page.goto(`${ctx.URL_WEB}/login`)
      break
    } catch (erreur) {
      if (essai >= 3 || !/ERR_NETWORK_CHANGED|ERR_CONNECTION_RESET|ERR_NETWORK_IO_SUSPENDED/.test(String(erreur.message))) throw erreur
    }
  }
  await page.getByLabel('Identifiant').fill(username)
  await page.getByLabel('Mot de passe').fill(MOT_DE_PASSE)
  await page.getByRole('button', { name: 'Se connecter' }).click()
  return {
    page,
    problemes,
    fermer: async () => {
      // Pour comprendre un échec : E2E_CAPTURE_FIN=1 garde l'écran tel qu'il était quand le scénario s'est arrêté.
      if (process.env.E2E_CAPTURE_FIN) {
        await page.screenshot({ path: path.join(ctx.CAPTURES, `fin-${username}-${Date.now()}.png`), fullPage: true }).catch(() => {})
      }
      await contexteNavigateur.close()
    },
  }
}

/** Appelle l'API comme cet utilisateur (sans passer par l'écran) : pour jouer les actions des AUTRES postes d'un scénario. */
export async function api(ctx, username, chemin, { method = 'GET', body } = {}) {
  const connexion = await fetch(`${ctx.URL_API}/auth/login/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password: MOT_DE_PASSE }),
  })
  const { access } = await connexion.json()
  const reponse = await fetch(`${ctx.URL_API}${chemin}`, {
    method,
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${access}` },
    body: body === undefined ? undefined : JSON.stringify(body),
  })
  const texte = await reponse.text()
  if (!reponse.ok) throw new Error(`${username} ${method} ${chemin} -> ${reponse.status} ${texte.slice(0, 200)}`)
  return texte ? JSON.parse(texte) : null
}

/** Dernier message simulé (SMS) contenant ce texte : le client n'a pas accès au logiciel, c'est par là qu'il reçoit son code. */
export function dernierMessage(ctx, fragment) {
  const sortie = executer(
    ctx.py,
    [
      'manage.py',
      'shell',
      '-c',
      `from notifications.models import NotificationLog as N; m = N.objects.filter(contenu__contains=${JSON.stringify(fragment)}, canal='sms').order_by('-id').first(); print(m.contenu if m else '')`,
    ],
    { cwd: ctx.BACKEND, env: ctx.env, titre: 'lecture du dernier message simulé' },
  )
  return sortie.trim()
}

export async function capturer(ctx, page, nom) {
  await page.screenshot({ path: path.join(ctx.CAPTURES, `${nom}.png`), fullPage: true })
}

/** Attend que la page ait fini de charger ses données (plus aucune requête en cours). */
export async function attendreCalme(page) {
  await page.locator('.topbar').waitFor()
  await page.waitForLoadState('networkidle')
}

export const scenarios = [
  {
    nom: 'smoke : chaque poste se connecte et voit son tableau de bord sans erreur',
    async jouer(ctx) {
      const details = []
      const ecarts = []
      for (const compte of comptes) {
        const { page, problemes, fermer } = await connecter(ctx, compte.username)
        try {
          await page.waitForURL(`**${compte.page}`, { timeout: 15000 })
          await attendreCalme(page)
          // La cloche d'alertes est sur toutes les pages : elle doit s'ouvrir.
          await page.getByRole('button', { name: /^Alertes/ }).click()
          await page.getByRole('region', { name: 'Alertes' }).waitFor({ timeout: 5000 })
          await capturer(ctx, page, compte.username)
          if (problemes.length) ecarts.push(`${compte.username} (${compte.page}) : ${[...new Set(problemes)].join(' ; ')}`)
          else details.push(`${compte.username} -> ${compte.page}`)
        } catch (erreur) {
          await capturer(ctx, page, `${compte.username}-echec`).catch(() => {})
          ecarts.push(`${compte.username} (${compte.page}) : ${String(erreur.message).split('\n')[0]}`)
        } finally {
          await fermer()
        }
      }
      if (ecarts.length) throw new Error(`${ecarts.length} poste(s) en écart :\n      ${ecarts.join('\n      ')}`)
      return [`${details.length} postes vérifiés`]
    },
  },

  {
    nom: 'coordination : le QHSE bloque un départ, le chef de gare en est prévenu, le QHSE le lève',
    async jouer(ctx) {
      const qhse = await connecter(ctx, 'qhse_stc')
      const chef = await connecter(ctx, 'chef_gare_stc')
      try {
        await qhse.page.waitForURL('**/dashboard/qhse')
        await attendreCalme(qhse.page)

        await qhse.page.getByLabel('Véhicule').selectOption({ label: 'CI-1001-AB' })
        await qhse.page.getByLabel('Motif du blocage').fill('Fissure du châssis constatée au contrôle')
        await qhse.page.getByRole('button', { name: 'Bloquer le départ' }).click()
        await qhse.page.getByText('Départ bloqué : le chef de gare').waitFor({ timeout: 10000 })
        await qhse.page.getByText('Fissure du châssis constatée au contrôle').first().waitFor()
        await capturer(ctx, qhse.page, 'coordination-1-qhse-bloque')

        // Le chef de gare de la gare de départ du car est prévenu, sans que personne ne l'appelle.
        await chef.page.waitForURL('**/dashboard/gare')
        await chef.page.reload()
        await attendreCalme(chef.page)
        await chef.page.getByRole('button', { name: /^Alertes/ }).click()
        await chef.page.getByText('Départ bloqué par le QHSE : CI-1001-AB').waitFor({ timeout: 10000 })
        await capturer(ctx, chef.page, 'coordination-2-chef-gare-alerte')

        // Le QHSE lève le blocage : le véhicule redevient disponible.
        await qhse.page.getByLabel('Motif de la levée du blocage de CI-1001-AB').fill('Châssis réparé et contrôlé')
        await qhse.page.getByRole('button', { name: 'Lever le blocage' }).click()
        await qhse.page.getByText('Blocage de CI-1001-AB levé.').waitFor({ timeout: 10000 })
        await capturer(ctx, qhse.page, 'coordination-3-qhse-leve')

        const problemes = [...qhse.problemes, ...chef.problemes]
        if (problemes.length) throw new Error([...new Set(problemes)].join(' ; '))
        return ['blocage posé, alerte reçue par le chef de gare, blocage levé']
      } finally {
        await qhse.fermer()
        await chef.fermer()
      }
    },
  },

  {
    nom: 'colis : le bagagiste enregistre, charge, le car arrive, le client retire avec son code',
    async jouer(ctx) {
      const departs = await api(ctx, 'bagagiste_stc', '/departs/')
      const depart = departs
        .filter((d) => d.statut === 'planifie' && d.chauffeur_nom === 'Awa Kone')
        .sort((a, b) => new Date(a.date_heure) - new Date(b.date_heure))[0]
      if (!depart) throw new Error('aucun départ planifié du chauffeur de démonstration')

      const bagagiste = await connecter(ctx, 'bagagiste_stc')
      try {
        const { page } = bagagiste
        await page.waitForURL('**/dashboard/bagagiste')
        await attendreCalme(page)

        // 1. Enregistrement : le code de retrait part au destinataire, jamais à l'écran.
        await page.getByLabel('Départ', { exact: false }).first().selectOption(String(depart.id))
        await page.getByLabel('Description').fill('Carton de pagnes')
        await page.getByLabel('Poids estimé (kg)').fill('12')
        await page.getByLabel('Frais de fret (FCFA)').fill('2000')
        await page.getByLabel('Expéditeur', { exact: true }).fill('Issa Kone')
        await page.getByLabel('Destinataire', { exact: true }).fill('Mariam Toure')
        await page.getByLabel(/^Téléphone du destinataire/).fill('0700000077')
        await page.getByRole('button', { name: 'Enregistrer et envoyer le code' }).click()
        await page.getByText('le code de retrait a été envoyé au destinataire').waitFor({ timeout: 10000 })
        await capturer(ctx, page, 'colis-1-enregistre')

        const sms = dernierMessage(ctx, 'Code de retrait')
        const code = /Code de retrait : ([A-Z0-9]{6})/.exec(sms)?.[1]
        if (!code) throw new Error(`code de retrait introuvable dans le message : « ${sms} »`)
        if (await page.getByText(code).count()) throw new Error('le code de retrait est affiché à l’écran du bagagiste')

        // 2. Chargement, et plan de chargement de la soute.
        await page.getByRole('button', { name: 'Marquer chargé' }).first().click()
        await page.getByText('chargé.', { exact: false }).first().waitFor({ timeout: 10000 })
        await page.getByText('Poids total', { exact: false }).first().waitFor({ timeout: 10000 })
        await capturer(ctx, page, 'colis-2-charge-plan')

        // 3. Le car part puis arrive (actions du chauffeur, jouées par l'API).
        const feuilles = await api(ctx, 'chauffeur_stc', '/feuilles-de-route/')
        const feuille = feuilles.find((f) => f.depart === depart.id)
        await api(ctx, 'chauffeur_stc', `/feuilles-de-route/${feuille.id}/demarrer/`, { method: 'POST' })
        await api(ctx, 'chauffeur_stc', `/feuilles-de-route/${feuille.id}/arriver/`, { method: 'POST' })

        // 4. Le colis est arrivé : le client se présente avec son code.
        await page.reload()
        await attendreCalme(page)
        const champCode = page.getByLabel(/^Code de retrait de COL-/).first()
        await champCode.waitFor({ timeout: 10000 })
        await champCode.fill('AAAAAA')
        await page.getByRole('button', { name: 'Remettre' }).first().click()
        await page.getByText('Code incorrect', { exact: false }).waitFor({ timeout: 10000 })
        await champCode.fill(code)
        await page.getByLabel(/^Nom de la personne qui retire/).first().fill('Mariam Toure')
        await page.getByRole('button', { name: 'Remettre' }).first().click()
        await page.getByText('remis.', { exact: false }).first().waitFor({ timeout: 10000 })
        await capturer(ctx, page, 'colis-3-remis')

        // Les erreurs 400 attendues (mauvais code) ne sont pas des problèmes ; tout le reste l'est.
        const anormaux = bagagiste.problemes.filter((p) => !p.includes('/retirer/') && !p.includes('400'))
        if (anormaux.length) throw new Error([...new Set(anormaux)].join(' ; '))
        return ['colis enregistré, chargé, arrivé, remis avec le bon code (un mauvais code refusé)']
      } finally {
        await bagagiste.fermer()
      }
    },
  },

  {
    nom: 'jeu : le guichetier vend, accomplit une mission et voit sa progression',
    async jouer(ctx) {
      // La démonstration compte déjà des dizaines de ventes du jour, et la première page du poste vue dans la série
      // (le smoke) a annoncé les missions : on repart d'un poste neuf pour que l'annonce soit bien celle de ce scénario.
      executer(
        ctx.py,
        [
          'manage.py',
          'shell',
          '-c',
          "from gamification.models import MissionAccomplie as M, BadgeObtenu as B; M.objects.filter(agent__username='guichetier_stc').delete(); B.objects.filter(agent__username='guichetier_stc').delete()",
        ],
        { cwd: ctx.BACKEND, env: ctx.env, titre: 'remise à zéro du jeu du guichetier' },
      )
      const departs = await api(ctx, 'guichetier_stc', '/departs/')
      const depart = departs.find((d) => d.statut === 'planifie')
      if (!depart) throw new Error('aucun départ planifié')
      for (let i = 0; i < 5; i++) {
        await api(ctx, 'guichetier_stc', '/tickets/', {
          method: 'POST',
          body: { depart: depart.id, passager_nom: `Passager ${i}`, passager_telephone: '0700000001', prix: '5000', mode_paiement: 'especes' },
        })
      }

      const guichetier = await connecter(ctx, 'guichetier_stc')
      try {
        const { page } = guichetier
        await page.waitForURL('**/dashboard/guichetier')
        // « Mission accomplie » : annoncé une fois, sobrement, pendant 8 secondes seulement : on le guette avant tout le reste.
        await page.getByRole('status').getByText('Mission accomplie', { exact: false }).waitFor({ timeout: 20000 })
        await attendreCalme(page)
        await page.getByRole('button', { name: /^Niveau \d/ }).click()
        await page.getByRole('heading', { name: 'Missions du jour' }).waitFor()
        await page.getByRole('heading', { name: 'Badges' }).waitFor()
        await page.getByText('Première vente').first().waitFor()
        await page.getByText(/Ticket vendu × \d+/).waitFor()  // le ticket de démonstration s'ajoute aux 5 ventes
        await page.getByRole('combobox', { name: 'Classement' }).selectOption('guichetiers')
        await page.getByText(/\d+ pts/).first().waitFor()
        await capturer(ctx, page, 'jeu-guichetier')
        if (guichetier.problemes.length) throw new Error([...new Set(guichetier.problemes)].join(' ; '))
        return ['niveau, missions, badges, classement affichés ; mission accomplie annoncée']
      } finally {
        await guichetier.fermer()
      }
    },
  },

  {
    nom: 'configuration : le chef de gare règle son guichetier (jeu coupé, vente retirée), le serveur applique',
    async jouer(ctx) {
      const chef = await connecter(ctx, 'chef_gare_stc')
      const details = []
      try {
        const { page } = chef
        await page.waitForURL('**/dashboard/gare')
        await attendreCalme(page)
        await page.getByRole('link', { name: 'Configuration' }).click()
        await page.waitForURL('**/configuration')
        await attendreCalme(page)
        const carte = page.locator('section.card', { has: page.getByRole('heading', { name: 'Guichetier', exact: true }) })

        // Un chef de gare ne règle ni son supérieur ni ses pairs : seuls guichetier et bagagiste sont proposés.
        const titres = await page.locator('section.card h2').allTextContents()
        for (const interdit of ['Chef de ligne', 'Directeur exploitation', 'PDG']) {
          if (titres.includes(interdit)) throw new Error(`le chef de gare voit le poste « ${interdit} »`)
        }

        await carte.getByLabel('Gamification').selectOption('aucun')
        await carte.getByLabel('Vendre des tickets').check()
        await carte.getByRole('button', { name: 'Enregistrer' }).click()
        await page.getByText('Poste « Guichetier » enregistré.').waitFor({ timeout: 10000 })
        await capturer(ctx, page, 'configuration-chef-de-gare')

        // Le guichetier ne voit plus le jeu, et le serveur refuse la vente.
        const guichetier = await connecter(ctx, 'guichetier_stc')
        try {
          await guichetier.page.waitForURL('**/dashboard/guichetier')
          await attendreCalme(guichetier.page)
          if ((await guichetier.page.locator('.jeu').count()) !== 0) throw new Error('le guichetier voit encore le jeu')
          const departs = await api(ctx, 'guichetier_stc', '/departs/')
          const depart = departs.find((d) => d.statut === 'planifie')
          await guichetier.page.getByLabel('Départ').selectOption(String(depart.id))
          await guichetier.page.getByLabel('Nom du passager').fill('Passager Test')
          await guichetier.page.getByLabel('Téléphone du passager').fill('0700000009')
          await guichetier.page.getByLabel(/^Prix/).fill('5000')
          await guichetier.page.getByRole('button', { name: 'Vendre le ticket' }).click()
          await guichetier.page.getByText('désactivée pour votre poste', { exact: false }).waitFor({ timeout: 10000 })
          await capturer(ctx, guichetier.page, 'configuration-vente-refusee')
          details.push('jeu coupé et vente refusée au guichetier')
        } finally {
          await guichetier.fermer()
        }
      } finally {
        // On remet le poste dans son état d'origine : les scénarios suivants en dépendent.
        await api(ctx, 'chef_gare_stc', '/configuration/postes/guichetier/', {
          method: 'PUT',
          body: { niveau_automatisation: null, niveau_gamification: null, fonctions_desactivees: [], prefere_vocal: false },
        })
        await chef.fermer()
      }
      return details
    },
  },

  {
    nom: 'caisse : le guichetier clôture sa caisse, le chef de gare est prévenu et la voit clôturée',
    async jouer(ctx) {
      const departs = await api(ctx, 'guichetier_stc', '/departs/')
      const depart = departs.find((d) => d.statut === 'planifie')
      for (let i = 0; i < 2; i++) {
        await api(ctx, 'guichetier_stc', '/tickets/', {
          method: 'POST',
          body: { depart: depart.id, passager_nom: `Caisse ${i}`, passager_telephone: '0700000002', prix: '4000', mode_paiement: i ? 'mobile_money' : 'especes' },
        })
      }

      const guichetier = await connecter(ctx, 'guichetier_stc')
      const chef = await connecter(ctx, 'chef_gare_stc')
      try {
        await guichetier.page.waitForURL('**/dashboard/guichetier')
        await attendreCalme(guichetier.page)
        await guichetier.page.getByText('Ma caisse du jour').waitFor()
        await guichetier.page.getByRole('button', { name: 'Clôturer ma caisse' }).click()
        await guichetier.page.getByText('clôturée : le chef de gare en est prévenu', { exact: false }).waitFor({ timeout: 10000 })
        await capturer(ctx, guichetier.page, 'caisse-1-guichetier')

        await chef.page.waitForURL('**/dashboard/gare')
        await chef.page.reload()
        await attendreCalme(chef.page)
        await chef.page.getByText("Caisses du jour de l'équipe", { exact: false }).waitFor()
        await chef.page.getByText('Clôturée', { exact: true }).first().waitFor({ timeout: 10000 })
        await chef.page.getByRole('button', { name: /^Alertes/ }).click()
        await chef.page.getByText('Caisse clôturée : Rose Kouame', { exact: false }).waitFor({ timeout: 10000 })
        await capturer(ctx, chef.page, 'caisse-2-chef-de-gare')

        const problemes = [...guichetier.problemes, ...chef.problemes]
        if (problemes.length) throw new Error([...new Set(problemes)].join(' ; '))
        return ['caisse clôturée par le guichetier, chef de gare prévenu (alerte + tableau)']
      } finally {
        await guichetier.fermer()
        await chef.fermer()
      }
    },
  },

  {
    nom: 'suivi : le chauffeur active le GPS, la direction voit le car, fatigue, relais puis checklist de reprise',
    async jouer(ctx) {
      // 1. La régulation planifie un trajet (après-demain à 3 h : à plus de 8 h de tout départ des données de démonstration, quelle que soit
      // l'heure à laquelle l'essai est joué) et le chauffeur le démarre.
      const demain = new Date()
      demain.setDate(demain.getDate() + 2)
      demain.setHours(3, 0, 0, 0)
      const dispo = await api(ctx, 'chef_ligne_stc', `/departs/disponibilites/?date_heure=${encodeURIComponent(demain.toISOString())}`)
      const vehicule = dispo.vehicules.find((v) => v.statut === 'disponible')
      const conducteur = ['Moussa Diallo', 'Awa Kone'].map((nom) => dispo.chauffeurs.find((c) => c.nom === nom)).find(Boolean)
      if (!vehicule || !conducteur) throw new Error('aucun véhicule ou conducteur libre pour le trajet d’essai')
      const identifiant = { 'Moussa Diallo': 'chauffeur2_stc', 'Awa Kone': 'chauffeur_stc' }[conducteur.nom]
      const lignes = await api(ctx, 'chef_ligne_stc', '/lignes/')
      const depart = await api(ctx, 'chef_ligne_stc', '/departs/planifier/', {
        method: 'POST',
        body: { ligne: lignes[0].id, vehicule: vehicule.id, chauffeur: conducteur.id, date_heure: demain.toISOString() },
      })
      await api(ctx, identifiant, `/feuilles-de-route/${depart.feuille_de_route}/demarrer/`, { method: 'POST' })

      const chauffeur = await connecter(ctx, identifiant, { geolocalisation: { latitude: 6.9, longitude: -5.2 } })
      const direction = await connecter(ctx, 'pdg_stc')
      const autres = []
      try {
        // 2. Le chauffeur active le suivi : sa première position part aussitôt.
        await chauffeur.page.waitForURL('**/dashboard/chauffeur')
        await attendreCalme(chauffeur.page)
        await chauffeur.page.getByRole('heading', { name: /^Trajet en cours/ }).waitFor({ timeout: 10000 })
        await chauffeur.page.getByRole('button', { name: 'Activer le suivi GPS' }).click()
        await chauffeur.page.getByText('dernière position envoyée', { exact: false }).waitFor({ timeout: 15000 })
        await capturer(ctx, chauffeur.page, 'suivi-1-chauffeur-gps')

        // 3. La direction voit le car sur la carte, sans rien demander à personne (sa page s'était chargée avant le premier relevé).
        await direction.page.waitForURL('**/dashboard/direction')
        await direction.page.reload()
        await attendreCalme(direction.page)
        await direction.page.locator('svg.carte title', { hasText: vehicule.immatriculation }).first().waitFor({ state: 'attached', timeout: 10000 })
        await capturer(ctx, direction.page, 'suivi-2-direction-carte')

        // 4. Cinq heures de conduite (on recule le départ du trajet) : alerte, puis relais.
        executer(
          ctx.py,
          ['manage.py', 'shell', '-c', `import datetime; from django.utils import timezone; from personnel_roulant.models import FeuilleDeRoute as F; F.objects.filter(pk=${depart.feuille_de_route}).update(heure_depart_reelle=timezone.now()-datetime.timedelta(hours=5))`],
          { cwd: ctx.BACKEND, env: ctx.env, titre: 'départ du trajet reculé de cinq heures' },
        )
        await chauffeur.page.reload()
        await attendreCalme(chauffeur.page)
        await chauffeur.page.getByText('Vous conduisez depuis plus de 4 h 30', { exact: false }).waitFor({ timeout: 10000 })
        await chauffeur.page.getByLabel('Conducteur qui reprend').selectOption({ label: 'Salif Ouedraogo' })
        await chauffeur.page.getByLabel('Lieu du relais').fill('Toumodi')
        await chauffeur.page.getByRole('button', { name: 'Passer le relais' }).click()
        await chauffeur.page.getByText('Relais effectué', { exact: false }).waitFor({ timeout: 10000 })
        await capturer(ctx, chauffeur.page, 'suivi-3-relais')

        const nouveau = await api(ctx, 'chauffeur_libre_stc', '/suivi/moi/')
        if (!nouveau.en_cours || nouveau.fatigue.conduite_continue_minutes > 1) throw new Error('le nouveau conducteur n’a pas repris le trajet à zéro')
        const ancien = await api(ctx, identifiant, '/suivi/moi/')
        if (ancien.en_cours) throw new Error('l’ancien conducteur conduit encore')
        if (!nouveau.reprise_a_faire) throw new Error('le nouveau conducteur n’a pas de checklist de reprise à faire')

        // 5. Le nouveau conducteur constate l'état du car : un défaut de freins prévient le QHSE, la checklist disparaît ensuite.
        const libre = await connecter(ctx, 'chauffeur_libre_stc')
        const qhse = await connecter(ctx, 'qhse_stc')
        autres.push(libre, qhse)
        await libre.page.waitForURL('**/dashboard/chauffeur')
        await attendreCalme(libre.page)
        const reprise = libre.page.getByRole('region', { name: 'Checklist de reprise' })
        await reprise.getByText('Vous avez repris le trajet à Toumodi').waitFor({ timeout: 10000 })
        await reprise.locator('fieldset', { hasText: 'Freins' }).getByLabel('Défaut', { exact: true }).check()
        await reprise.getByLabel('Défaut constaté : Freins').fill('Pédale spongieuse')
        await capturer(ctx, libre.page, 'suivi-4-checklist-de-reprise')
        await reprise.getByRole('button', { name: /^Valider la reprise \(1 défaut\)/ }).click()
        await libre.page.getByText('Checklist enregistrée : les défauts constatés', { exact: false }).waitFor({ timeout: 10000 })
        await reprise.waitFor({ state: 'detached', timeout: 10000 })
        await qhse.page.waitForURL('**/dashboard/qhse')
        await qhse.page.reload() // sa page s'était chargée avant l'alerte
        await attendreCalme(qhse.page)
        await qhse.page.getByRole('button', { name: /^Alertes/ }).click()
        await qhse.page.getByText('Défaut à la reprise du trajet : freins', { exact: false }).waitFor({ timeout: 10000 })
        const apres = await api(ctx, 'chauffeur_libre_stc', '/suivi/moi/')
        if (apres.reprise_a_faire) throw new Error('la checklist de reprise est encore à faire')

        const problemes = [...chauffeur.problemes, ...direction.problemes, ...libre.problemes, ...qhse.problemes]
        if (problemes.length) throw new Error([...new Set(problemes)].join(' ; '))
        return [
          'GPS actif, car visible sur la carte de la direction, alerte fatigue, relais à Toumodi, fatigue remise à zéro',
          'checklist de reprise : défaut de freins constaté par le nouveau conducteur, alerte critique au QHSE',
        ]
      } finally {
        await chauffeur.fermer()
        await direction.fermer()
        for (const session of autres) await session.fermer()
      }
    },
  },

  {
    nom: 'contrôle : le contrôleur vérifie les billets à bord, clôture avec constats, signale une infraction au QHSE',
    async jouer(ctx) {
      // 1. Un car part demain soir : la régulation le planifie et le guichetier vend deux billets (le code part par SMS).
      const demain = new Date()
      demain.setDate(demain.getDate() + 1)
      demain.setHours(23, 0, 0, 0)
      const dispo = await api(ctx, 'chef_ligne_stc', `/departs/disponibilites/?date_heure=${encodeURIComponent(demain.toISOString())}`)
      const vehicule = dispo.vehicules.find((v) => v.statut === 'disponible')
      const conducteur = dispo.chauffeurs[0]
      if (!vehicule || !conducteur) throw new Error('aucun véhicule ou conducteur libre pour le trajet à contrôler')
      const lignes = await api(ctx, 'chef_ligne_stc', '/lignes/')
      const depart = await api(ctx, 'chef_ligne_stc', '/departs/planifier/', {
        method: 'POST',
        body: { ligne: lignes[0].id, vehicule: vehicule.id, chauffeur: conducteur.id, date_heure: demain.toISOString() },
      })
      const billets = []
      for (const nom of ['Adjoua Koffi', 'Yao Brou']) {
        billets.push(
          await api(ctx, 'guichetier_stc', '/tickets/', {
            method: 'POST',
            body: { depart: depart.id, passager_nom: nom, passager_telephone: '0700000003', prix: depart.tarif ?? '5000', mode_paiement: 'especes' },
          }),
        )
      }
      const [premier, second] = billets
      const sms = dernierMessage(ctx, 'Code du billet')
      if (!sms.includes(second.code)) throw new Error(`le SMS du voyageur ne porte pas le code de son billet : « ${sms} »`)

      const controleur = await connecter(ctx, 'controleur_stc')
      const qhse = await connecter(ctx, 'qhse_stc')
      try {
        const { page } = controleur
        await page.waitForURL('**/dashboard/controle')
        await attendreCalme(page)

        // 2. Ouverture du contrôle sur ce trajet, puis les billets un à un.
        await page.getByLabel('Trajet à contrôler').selectOption(String(depart.feuille_de_route))
        await page.getByRole('button', { name: 'Ouvrir le contrôle' }).click()
        await page.getByRole('heading', { name: /^Contrôle en cours/ }).waitFor({ timeout: 10000 })

        const verifier = async (code, attendu) => {
          await page.getByLabel('Code du billet').fill(code)
          await page.getByRole('button', { name: 'Vérifier', exact: true }).click()
          await page.getByRole('status').getByText(attendu, { exact: false }).waitFor({ timeout: 10000 })
        }
        await verifier(premier.code, 'Billet valide')
        await verifier(premier.code, 'DÉJÀ UTILISÉ') // le même billet présenté deux fois : fraude
        await verifier('ZZZZZZ', 'INCONNU')
        await verifier(second.code, 'Billet valide')
        await capturer(ctx, page, 'controle-1-verdicts')

        // 3. Clôture : trois voyageurs de plus que de billets vendus. Le rapport le dit sans qu'on le rédige.
        await page.getByLabel('Voyageurs comptés à bord').fill('5')
        await page.getByRole('button', { name: 'Clôturer et générer le rapport' }).click()
        await page.getByRole('heading', { name: 'Rapport du contrôle' }).waitFor({ timeout: 10000 })
        await page.getByText('4 (2 valides, 2 refusés)').first().waitFor()
        await page.getByText('3 voyageur(s) de plus que de billets vendus (2)', { exact: false }).first().waitFor()
        await page.getByText('1 billet(s) déjà utilisé(s)', { exact: false }).first().waitFor()
        await capturer(ctx, page, 'controle-2-rapport')

        // 4. Un billet déjà utilisé ne sert pas deux fois, même après la clôture : l'état est au serveur, pas à l'écran.
        const relu = await api(ctx, 'controleur_stc', '/tickets/')
        if (!relu.find((t) => t.id === premier.id)?.utilise_le) throw new Error('le billet vérifié n’est pas marqué utilisé côté serveur')

        // 5. Deuxième contrôle du même car, avec une infraction grave déclarée : le QHSE est alerté sans intermédiaire.
        await page.getByLabel('Trajet à contrôler').selectOption(String(depart.feuille_de_route))
        await page.getByRole('button', { name: 'Ouvrir le contrôle' }).click()
        await page.getByRole('heading', { name: /^Contrôle en cours/ }).waitFor({ timeout: 10000 })
        await page.getByLabel(/^Infraction grave à signaler/).check()
        await page.getByLabel(/^Motif de l/).fill('Voyageurs debout dans l’allée')
        await page.getByRole('button', { name: 'Clôturer et générer le rapport' }).click()
        await page.getByText('Infraction grave : Voyageurs debout dans l’allée').first().waitFor({ timeout: 10000 })
        await page.locator('tr.row-danger').first().waitFor()
        await capturer(ctx, page, 'controle-3-infraction')

        await qhse.page.waitForURL('**/dashboard/qhse')
        await qhse.page.reload()
        await attendreCalme(qhse.page)
        await qhse.page.getByRole('button', { name: /^Alertes/ }).click()
        await qhse.page.getByText('Infraction grave au contrôle', { exact: false }).first().waitFor({ timeout: 10000 })
        await capturer(ctx, qhse.page, 'controle-4-qhse-alerte')

        const problemes = [...controleur.problemes, ...qhse.problemes]
        if (problemes.length) throw new Error([...new Set(problemes)].join(' ; '))
        return ['billets valide / déjà utilisé / inconnu, rapport avec anomalies, infraction grave alertée au QHSE']
      } finally {
        await controleur.fermer()
        await qhse.fermer()
      }
    },
  },

  {
    nom: 'pouvoirs : le terrain demande la fermeture d’une ligne, la direction arbitre, le PDG décide et suspend un compte',
    async jouer(ctx) {
      const details = []
      const connexion = (username) =>
        fetch(`${ctx.URL_API}/auth/login/`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ username, password: MOT_DE_PASSE }),
        })
      const chefLigne = await connecter(ctx, 'chef_ligne_stc')
      const dirops = await connecter(ctx, 'directeur_exploitation_stc')
      const pdg = await connecter(ctx, 'pdg_stc')
      const sessions = [chefLigne, dirops, pdg]
      try {
        // 1. Le chef de ligne voit la route coupée : il DEMANDE la fermeture, la ligne reste ouverte.
        await chefLigne.page.waitForURL('**/dashboard/ligne')
        await attendreCalme(chefLigne.page)
        await chefLigne.page.getByLabel('Ligne concernée').selectOption({ label: 'Abidjan-Bouaké' })
        await chefLigne.page.getByLabel('Motif de la demande').fill('Route coupée par un éboulement')
        await chefLigne.page.getByRole('button', { name: 'Demander la fermeture' }).click()
        await chefLigne.page.getByText('Demande envoyée : le directeur des opérations en est prévenu', { exact: false }).waitFor({ timeout: 10000 })
        await capturer(ctx, chefLigne.page, 'pouvoirs-1-demande')
        const avant = (await api(ctx, 'guichetier_stc', '/lignes/')).find((l) => l.nom === 'Abidjan-Bouaké')
        if (avant.est_fermee) throw new Error('la ligne est fermée avant la décision du directeur des opérations')

        // 2. Le directeur des opérations la valide : la ligne se ferme, et il arbitre un véhicule entre gares.
        await dirops.page.waitForURL('**/dashboard/exploitation')
        await dirops.page.reload()
        await attendreCalme(dirops.page)
        await dirops.page.getByText('Route coupée par un éboulement').first().waitFor({ timeout: 10000 })
        await dirops.page.getByRole('button', { name: 'Valider', exact: true }).click()
        await dirops.page.getByText('Demande validée : le changement est appliqué.').waitFor({ timeout: 10000 })
        await dirops.page.locator('tr.row-danger', { hasText: 'Abidjan-Bouaké' }).first().waitFor({ timeout: 10000 })
        await dirops.page.getByRole('heading', { name: 'Gares en tension' }).waitFor()
        await dirops.page.locator('table tr', { hasText: 'Gare Adjamé' }).first().waitFor()
        const bus = (await api(ctx, 'directeur_exploitation_stc', '/vehicules/')).find((v) => v.immatriculation === 'CI-1006-AB')
        const adjame = (await api(ctx, 'directeur_exploitation_stc', '/gares/')).find((g) => g.nom === 'Gare Adjamé')
        // La page a aussi un formulaire de planification (« Véhicule ») : on reste dans la carte de l'arbitrage.
        const arbitrage = dirops.page.locator('section.card', { has: dirops.page.getByRole('heading', { name: 'Gares en tension' }) })
        await arbitrage.getByLabel('Véhicule').selectOption(String(bus.id))
        await arbitrage.getByLabel('Nouvelle gare d’attache').selectOption(String(adjame.id))
        await arbitrage.getByLabel('Motif du rattachement').fill('Renfort pour les rotations du matin')
        await arbitrage.getByRole('button', { name: 'Rattacher le véhicule' }).click()
        await dirops.page.getByText('CI-1006-AB est rattaché à Gare Adjamé', { exact: false }).waitFor({ timeout: 10000 })
        await capturer(ctx, dirops.page, 'pouvoirs-2-arbitrage')
        details.push('demande du chef de ligne validée, véhicule rattaché à une autre gare')

        // 3. La fermeture s'impose : plus de billet proposé sur cette ligne, le chef de gare en est prévenu.
        const guichetier = await connecter(ctx, 'guichetier_stc')
        const chefGare = await connecter(ctx, 'chef_gare_stc')
        sessions.push(guichetier, chefGare)
        await guichetier.page.waitForURL('**/dashboard/guichetier')
        await attendreCalme(guichetier.page)
        await guichetier.page.getByText('non proposé(s) : ligne fermée', { exact: false }).waitFor({ timeout: 10000 })
        await chefGare.page.waitForURL('**/dashboard/gare')
        await attendreCalme(chefGare.page)
        await chefGare.page.getByRole('button', { name: /^Alertes/ }).click()
        await chefGare.page.getByText('Ligne fermée : Abidjan-Bouaké').waitFor({ timeout: 10000 })
        await chefGare.page.getByText('Véhicule CI-1006-AB rattaché à Gare Adjamé').waitFor({ timeout: 10000 })
        await capturer(ctx, chefGare.page, 'pouvoirs-3-chef-de-gare-prevenu')
        details.push('billets non proposés sur la ligne fermée, chef de gare prévenu (ligne + véhicule)')

        // 4. Le technique demande un investissement ; le PDG en a deux à décider (celle de la démonstration et la nouvelle).
        const technique = await connecter(ctx, 'directeur_technique_stc')
        sessions.push(technique)
        await technique.page.waitForURL('**/dashboard/technique')
        await attendreCalme(technique.page)
        await technique.page.getByRole('link', { name: 'Investissements' }).click()
        await technique.page.waitForURL('**/investissements')
        await attendreCalme(technique.page)
        await technique.page.getByLabel('Intitulé').fill('Atelier mobile')
        await technique.page.getByLabel('Montant (FCFA)').fill('15000000')
        await technique.page.getByRole('button', { name: 'Envoyer la demande' }).click()
        await technique.page.getByText('Demande envoyée : le PDG en est prévenu et décide.').waitFor({ timeout: 10000 })

        await pdg.page.waitForURL('**/dashboard/direction')
        await attendreCalme(pdg.page)
        await pdg.page.getByRole('link', { name: 'Pilotage' }).click()
        await pdg.page.waitForURL('**/pilotage')
        await attendreCalme(pdg.page)
        await pdg.page.getByText('2 à décider').first().waitFor({ timeout: 10000 })

        // 5. Le PDG rouvre la ligne, en gèle une autre, valide un investissement et en refuse un (avec sa raison).
        const ligneBouake = pdg.page.locator('tr', { hasText: 'Abidjan-Bouaké' }).first()
        await pdg.page.getByLabel('Motif de la réouverture de Abidjan-Bouaké').fill('Route dégagée')
        await ligneBouake.getByRole('button', { name: 'Rouvrir' }).click()
        await pdg.page.getByText('Ligne Abidjan-Bouaké rouverte.').waitFor({ timeout: 10000 })
        await pdg.page.getByLabel('Motif de la fermeture de Yopougon-Yamoussoukro').fill('Grève des transporteurs')
        await pdg.page.locator('tr', { hasText: 'Yopougon-Yamoussoukro' }).first().getByRole('button', { name: 'Fermer' }).click()
        await pdg.page.getByText('Ligne Yopougon-Yamoussoukro fermée', { exact: false }).waitFor({ timeout: 10000 })

        await pdg.page.getByLabel('Commentaire sur Achat de 3 autocars').fill('Budget voté')
        await pdg.page.locator('tr', { hasText: 'Achat de 3 autocars' }).getByRole('button', { name: 'Valider' }).click()
        await pdg.page.getByText('« Achat de 3 autocars » validé', { exact: false }).waitFor({ timeout: 10000 })
        await pdg.page.locator('tr', { hasText: 'Atelier mobile' }).getByRole('button', { name: 'Refuser' }).click()
        await pdg.page.getByText('Indiquez la raison du refus', { exact: false }).waitFor({ timeout: 10000 })
        await pdg.page.getByLabel('Commentaire sur Atelier mobile').fill('À reporter à l’exercice prochain')
        await pdg.page.locator('tr', { hasText: 'Atelier mobile' }).getByRole('button', { name: 'Refuser' }).click()
        await pdg.page.getByText('« Atelier mobile » refusé', { exact: false }).waitFor({ timeout: 10000 })
        await capturer(ctx, pdg.page, 'pouvoirs-4-pdg-decisions')

        await technique.page.reload()
        await attendreCalme(technique.page)
        await technique.page.getByText('Budget voté').waitFor({ timeout: 10000 })
        await technique.page.getByText('À reporter à l’exercice prochain').waitFor({ timeout: 10000 })
        details.push('ligne rouverte et gelée par le PDG, investissement validé et refusé (raison exigée), demandeur informé')

        // 6. Le PDG suspend le compte du guichetier : sa session ouverte est coupée, il ne peut plus se connecter ; puis il le réactive.
        await pdg.page.getByLabel('Rechercher').fill('guichetier_stc')
        const compteRose = pdg.page.locator('tr', { hasText: 'Rose Kouame' })
        await pdg.page.getByLabel('Motif de la suspension de Rose Kouame').fill('Écart de caisse répété')
        await compteRose.getByRole('button', { name: 'Suspendre' }).click()
        await pdg.page.getByText('Compte de Rose Kouame suspendu', { exact: false }).waitFor({ timeout: 10000 })
        await capturer(ctx, pdg.page, 'pouvoirs-5-compte-suspendu')
        await guichetier.page.reload()
        await guichetier.page.waitForURL('**/login', { timeout: 15000 })
        if ((await connexion('guichetier_stc')).status !== 401) throw new Error('le compte suspendu se connecte encore')

        await pdg.page.getByLabel('Suspendus seulement').check()
        await compteRose.getByRole('button', { name: 'Réactiver' }).click()
        await pdg.page.getByText('Compte de Rose Kouame réactivé.').waitFor({ timeout: 10000 })
        if ((await connexion('guichetier_stc')).status !== 200) throw new Error('le compte réactivé ne se connecte pas')
        details.push('compte suspendu (session coupée, connexion refusée) puis réactivé')

        // 7. Les 4xx attendus (le refus sans raison, la session du compte suspendu) mis à part, tout est silencieux. Le
        // navigateur écrit aussi chaque 4xx dans sa console, sans dire lequel : il n'y en a pas plus que d'attendus.
        const attendus = ['/investissements/', '/auth/refresh/', '/auth/me/', '/auth/login/']
        const problemes = sessions.flatMap((s) => s.problemes)
        const http = problemes.filter((p) => p.startsWith('HTTP ') && attendus.some((a) => p.includes(a)))
        const consoleReseau = problemes.filter((p) => p.startsWith('console : Failed to load resource'))
        const anormaux = problemes.filter(
          (p) => !(p.startsWith('HTTP ') && attendus.some((a) => p.includes(a))) && !p.startsWith('console : Failed to load resource'),
        )
        if (consoleReseau.length > http.length) anormaux.push(`${consoleReseau.length - http.length} erreur(s) réseau inattendue(s) dans la console`)
        if (anormaux.length) throw new Error([...new Set(anormaux)].join(' ; '))
        return details
      } finally {
        // On remet l'état d'origine : le compte réactivé, les lignes rouvertes.
        for (const ligne of (await api(ctx, 'pdg_stc', '/lignes/').catch(() => [])).filter((l) => l.est_fermee)) {
          await api(ctx, 'pdg_stc', `/lignes/${ligne.id}/changement/`, { method: 'POST', body: { action: 'rouvrir', motif: 'Remise en état de la démonstration' } }).catch(() => {})
        }
        const suspendus = await api(ctx, 'pdg_stc', '/comptes/?suspendus=1').catch(() => [])
        for (const compte of suspendus) await api(ctx, 'pdg_stc', `/comptes/${compte.id}/reactiver/`, { method: 'POST', body: {} }).catch(() => {})
        for (const session of sessions) await session.fermer()
      }
    },
  },

  {
    nom: 'atelier : entretien préventif, ordre ouvert tout seul, file réordonnée, pièce demandée puis servie',
    async jouer(ctx) {
      const details = []
      const il_y_a = (jours) => {
        const d = new Date()
        d.setDate(d.getDate() - jours)
        return d.toISOString().slice(0, 10)
      }
      const technique = await connecter(ctx, 'directeur_technique_stc')
      const sessions = [technique]
      try {
        // 1. Le directeur technique déclare un plan : contrôle technique tous les 90 jours, fait il y a 80 jours (échéance dans 10 jours).
        await technique.page.waitForURL('**/dashboard/technique')
        await attendreCalme(technique.page)
        await technique.page.getByLabel('Véhicule du plan').selectOption({ label: 'CI-1003-AB' })
        await technique.page.getByLabel('Entretien', { exact: true }).fill('Contrôle technique')
        await technique.page.getByLabel('Tous les (jours)').fill('90')
        await technique.page.getByLabel('Durée estimée (heures)').fill('6')
        await technique.page.getByLabel('Dernier entretien (date)').fill(il_y_a(80))
        await technique.page.getByRole('button', { name: 'Déclarer le plan' }).click()
        await technique.page.getByText('Plan « Contrôle technique » déclaré.').waitFor({ timeout: 10000 })
        await technique.page.locator('tr', { hasText: 'Contrôle technique' }).getByText('Bientôt dû').waitFor({ timeout: 10000 })
        await capturer(ctx, technique.page, 'atelier-1-plan')

        // 2. Le passage automatique (cron) prévient l'atelier et ouvre l'ordre de réparation.
        executer(ctx.py, ['manage.py', 'generer_alertes'], { cwd: ctx.BACKEND, env: ctx.env, titre: 'génération des alertes (entretien préventif)' })
        const file = await api(ctx, 'directeur_technique_stc', '/ordres-reparation/file-attente/')
        const preventif = file.find((o) => o.description.startsWith('Entretien préventif : Contrôle technique'))
        if (!preventif) throw new Error('l’ordre de l’entretien préventif n’a pas été ouvert')
        if (preventif.delai_estime_heures !== 6 || !preventif.retour_estime) throw new Error('le délai estimé du plan n’est pas reporté sur l’ordre')
        const boite = file.find((o) => o.description.startsWith('Remplacement de la boîte'))
        const revision = file.find((o) => o.description.startsWith('Révision moteur'))

        const chefAtelier = await connecter(ctx, 'chef_atelier_stc')
        sessions.push(chefAtelier)
        await chefAtelier.page.waitForURL('**/dashboard/atelier')
        await attendreCalme(chefAtelier.page)
        await chefAtelier.page.getByRole('button', { name: /^Alertes/ }).click()
        await chefAtelier.page.getByText('Entretien à prévoir : Contrôle technique — CI-1003-AB').waitFor({ timeout: 10000 })
        details.push('plan déclaré, ordre d’entretien ouvert par le cron, atelier prévenu')

        // 3. Le directeur technique reclasse : il monte l'entretien devant la révision (même urgence), puis le confie au chef d'atelier.
        await technique.page.reload()
        await attendreCalme(technique.page)
        await technique.page.getByRole('button', { name: `Monter l'ordre ${preventif.id}` }).click()
        await technique.page.getByText('Ordre de la file enregistré', { exact: false }).waitFor({ timeout: 10000 })
        const apres = (await api(ctx, 'directeur_technique_stc', '/ordres-reparation/file-attente/')).map((o) => o.id)
        if (apres.indexOf(preventif.id) > apres.indexOf(revision.id)) throw new Error('l’entretien n’est pas passé devant la révision')
        if (apres[0] !== boite.id) throw new Error('l’urgence haute ne prime plus sur la position')
        const charge = await api(ctx, 'directeur_technique_stc', '/maintenance/charge-mecaniciens/')
        const chef = charge.find((c) => c.role === 'chef_atelier')
        await technique.page.getByLabel(`Intervenant de l'ordre ${preventif.id}`).selectOption(String(chef.id))
        await technique.page.getByText(`Ordre ${preventif.id} confié`, { exact: false }).waitFor({ timeout: 10000 })
        await capturer(ctx, technique.page, 'atelier-2-file')
        details.push('file réordonnée (l’urgence prime), ordre confié au chef d’atelier')

        // 4. Le mécanicien demande deux pièces : l'une en stock, l'autre en rupture proche.
        const mecanicien = await connecter(ctx, 'mecanicien_stc')
        const magasinier = await connecter(ctx, 'magasinier_stc')
        sessions.push(mecanicien, magasinier)
        await mecanicien.page.waitForURL('**/dashboard/mecanicien')
        await attendreCalme(mecanicien.page)
        const carte = mecanicien.page.locator('section.card', { has: mecanicien.page.getByRole('heading', { name: 'Demander une pièce au magasinier' }) })
        const demander = async (piece, quantite, attendu) => {
          await carte.getByLabel('Ordre de réparation').selectOption(String(boite.id))
          await carte.getByLabel('Pièce demandée').selectOption({ label: piece })
          await carte.getByLabel('Quantité demandée').fill(String(quantite))
          await carte.getByText(attendu, { exact: false }).first().waitFor({ timeout: 5000 })
          await carte.getByRole('button', { name: 'Envoyer la demande' }).click()
          await carte.getByText('Demande envoyée', { exact: false }).first().waitFor({ timeout: 10000 })
        }
        await demander('Pneu 22.5 (REF-DEMO-PNEU)', 2, 'Disponible : 20 en stock')
        await demander('Filtre à huile (REF-DEMO-HUILE)', 5, 'Stock insuffisant : 2 en stock')
        await capturer(ctx, mecanicien.page, 'atelier-3-demandes')

        // 5. Le magasinier voit tout de suite ce qui suffit : il sert le pneu (le stock baisse), refuse le filtre en disant pourquoi.
        await magasinier.page.waitForURL('**/dashboard/magasinier')
        await magasinier.page.reload()
        await attendreCalme(magasinier.page)
        await magasinier.page.getByText('2 à traiter').waitFor({ timeout: 10000 })
        const ligneFiltre = magasinier.page.locator('tr', { hasText: '5 × Filtre à huile' })
        const lignePneu = magasinier.page.locator('tr', { hasText: '2 × Pneu 22.5' })
        if (!(await ligneFiltre.getByRole('button', { name: 'Servir' }).isDisabled())) throw new Error('on peut servir une pièce dont le stock ne suffit pas')
        await lignePneu.getByRole('button', { name: 'Servir' }).click()
        await magasinier.page.getByText('sortie enregistrée sur l\'ordre', { exact: false }).waitFor({ timeout: 10000 })
        await ligneFiltre.getByLabel(/^Motif du refus/).fill('Commande en cours, livraison lundi')
        await ligneFiltre.getByRole('button', { name: 'Refuser' }).click()
        await magasinier.page.getByText('Demande refusée', { exact: false }).waitFor({ timeout: 10000 })
        await magasinier.page.getByText('Filtre à huile').first().waitFor()
        await magasinier.page.locator('section.card', { hasText: 'Réapprovisionnement suggéré' }).getByText('Filtre à huile').waitFor({ timeout: 10000 })
        await capturer(ctx, magasinier.page, 'atelier-4-magasin')
        const pneu = (await api(ctx, 'magasinier_stc', '/pieces/')).find((p) => p.reference === 'REF-DEMO-PNEU')
        if (pneu.quantite_stock !== 18) throw new Error(`stock du pneu : ${pneu.quantite_stock} au lieu de 18`)

        await mecanicien.page.reload()
        await attendreCalme(mecanicien.page)
        await mecanicien.page.locator('tr', { hasText: '2 × Pneu 22.5' }).getByText('Servie').waitFor({ timeout: 10000 })
        await mecanicien.page.locator('tr', { hasText: '5 × Filtre à huile' }).getByText('Commande en cours, livraison lundi').waitFor({ timeout: 10000 })
        details.push('pièce servie (stock 20 → 18, sortie sur l’ordre), autre refusée avec son motif, suggestion de commande affichée')

        // 6. Les autres pôles en profitent : la régulation voit le retour estimé du car, la direction le rapport de renouvellement.
        const regulation = await connecter(ctx, 'chef_ligne_stc')
        const pdg = await connecter(ctx, 'pdg_stc')
        sessions.push(regulation, pdg)
        await regulation.page.waitForURL('**/dashboard/ligne')
        await attendreCalme(regulation.page)
        const atelier = regulation.page.locator('section.card', { has: regulation.page.getByRole('heading', { name: "Véhicules à l'atelier" }).first() })
        await atelier.locator('tr', { hasText: 'CI-1005-AB' }).getByText(/\d{2}\/\d{2}\/\d{4}/).waitFor({ timeout: 10000 })
        await pdg.page.waitForURL('**/dashboard/direction')
        await attendreCalme(pdg.page)
        await pdg.page.getByText('640 000 km au compteur', { exact: false }).waitFor({ timeout: 10000 })
        await capturer(ctx, pdg.page, 'atelier-5-renouvellement')

        await technique.page.getByLabel('Véhicule à consulter').selectOption({ label: 'CI-1005-AB' })
        await technique.page.getByText('Remplacement de la boîte de vitesses').last().waitFor({ timeout: 10000 })
        await capturer(ctx, technique.page, 'atelier-6-fiche')
        details.push('retour estimé visible de la régulation, rapport de renouvellement à la direction, fiche véhicule')

        const problemes = sessions.flatMap((s) => s.problemes)
        if (problemes.length) throw new Error([...new Set(problemes)].join(' ; '))
        return details
      } finally {
        for (const session of sessions) await session.fermer()
      }
    },
  },

  {
    nom: 'secrétariat : note de service, agenda, archives, santé de la gare, message à l’équipe, conformité',
    async jouer(ctx) {
      const details = []
      const demain = new Date()
      demain.setDate(demain.getDate() + 1)
      demain.setHours(10, 0, 0, 0)
      const local = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}T10:00`
      const sg = await connecter(ctx, 'secretaire_general_stc')
      const sessions = [sg]
      try {
        // 1. Le secrétaire général diffuse une note de service au pôle technique, sans passer par le PDG.
        await sg.page.waitForURL('**/dashboard/direction')
        await attendreCalme(sg.page)
        await sg.page.getByRole('link', { name: 'Secrétariat' }).click()
        await sg.page.waitForURL('**/secretariat')
        await attendreCalme(sg.page)
        await sg.page.getByLabel('Titre de la note').fill('Port du gilet en atelier')
        await sg.page.getByLabel('Contenu de la note').fill('À partir de lundi, le gilet est obligatoire dans tout l’atelier.')
        await sg.page.getByLabel('Technique & Maintenance').check()
        await sg.page.getByRole('button', { name: 'Diffuser la note' }).click()
        await sg.page.getByText('Note diffusée', { exact: false }).waitFor({ timeout: 10000 })

        // 2. Un rendez-vous de la direction, avec le directeur technique invité.
        await sg.page.getByLabel('Titre du rendez-vous').fill('Comité de direction')
        await sg.page.getByLabel('Début', { exact: true }).fill(local(demain))
        await sg.page.getByLabel('Lieu').fill('Siège, salle B')
        await sg.page.getByLabel('Directeur technique').check()
        await sg.page.getByRole('button', { name: "Ajouter à l'agenda" }).click()
        await sg.page.getByText('Rendez-vous ajouté', { exact: false }).waitFor({ timeout: 10000 })
        await sg.page.getByText('Comité de direction').first().waitFor()

        // 3. Un dossier administratif : classé, retrouvé par un mot, archivé (il ne se supprime pas).
        await sg.page.getByLabel('Titre du dossier').fill('Bail de la gare d’Adjamé')
        await sg.page.getByLabel('Date du document').fill('2026-03-15')
        await sg.page.getByLabel('Référence', { exact: true }).fill('CTR-2026-014')
        await sg.page.getByLabel('Emplacement').fill('Armoire 3, chemise B')
        await sg.page.getByRole('button', { name: 'Classer le dossier' }).click()
        await sg.page.getByText('classé.', { exact: false }).waitFor({ timeout: 10000 })
        await sg.page.getByLabel('Rechercher un dossier').fill('armoire 3')
        const dossier = sg.page.locator('tr', { hasText: 'Bail de la gare d’Adjamé' })
        await dossier.waitFor({ timeout: 10000 })
        await dossier.getByRole('button', { name: 'Archiver' }).click()
        await sg.page.getByText('archivé.', { exact: false }).waitFor({ timeout: 10000 })
        await capturer(ctx, sg.page, 'secretariat-1')
        details.push('note de service diffusée, rendez-vous ajouté, dossier classé puis archivé')

        // 4. Les postes visés la reçoivent dans leur cloche ; le directeur technique est invité au comité.
        const mecanicien = await connecter(ctx, 'mecanicien_stc')
        const technique = await connecter(ctx, 'directeur_technique_stc')
        sessions.push(mecanicien, technique)
        await mecanicien.page.waitForURL('**/dashboard/mecanicien')
        await attendreCalme(mecanicien.page)
        await mecanicien.page.getByRole('button', { name: /^Alertes/ }).click()
        await mecanicien.page.getByText('Note de service : Port du gilet en atelier').waitFor({ timeout: 10000 })
        await technique.page.waitForURL('**/dashboard/technique')
        await attendreCalme(technique.page)
        await technique.page.getByRole('button', { name: /^Alertes/ }).click()
        await technique.page.getByText('Agenda : Comité de direction').waitFor({ timeout: 10000 })
        await technique.page.getByRole('link', { name: 'Notes de service' }).click()
        await technique.page.getByText('Port du gilet en atelier').waitFor({ timeout: 10000 })
        details.push('note reçue par le mécanicien et le directeur technique, invitation à l’agenda')

        // 5. Le chef de gare : santé de sa gare, composition de son équipe, message à l'équipe.
        const chef = await connecter(ctx, 'chef_gare_stc')
        sessions.push(chef)
        await chef.page.waitForURL('**/dashboard/gare')
        await attendreCalme(chef.page)
        await chef.page.getByText('Ponctualité du jour').first().waitFor({ timeout: 10000 })
        await chef.page.getByText('Recettes du jour de la gare').waitFor()
        await chef.page.getByText('Véhicules de la gare').waitFor()
        const equipe = await api(ctx, 'chef_gare_stc', '/affectations-gare/agents-affectables/')
        const bagagiste = equipe.find((a) => a.role === 'bagagiste' && a.gare)
        const ligne = chef.page.locator('tr', { hasText: bagagiste.nom })
        await ligne.getByRole('button', { name: 'Retirer de mon équipe' }).click()
        await chef.page.getByText('ne fait plus partie de l', { exact: false }).waitFor({ timeout: 10000 })
        await chef.page.locator('tr', { hasText: bagagiste.nom }).getByRole('button', { name: 'Affecter à ma gare' }).click()
        await chef.page.getByText('rejoint l', { exact: false }).waitFor({ timeout: 10000 })
        await chef.page.getByLabel('Destinataires du message').selectOption('equipe')
        await chef.page.getByLabel('Texte du message').fill('Le car de 14 h aura 30 minutes de retard.')
        await chef.page.getByRole('button', { name: 'Envoyer le message' }).click()
        await chef.page.getByText('Message envoyé à 2 personne(s)').waitFor({ timeout: 10000 })
        await capturer(ctx, chef.page, 'secretariat-2-chef-de-gare')

        const guichetier = await connecter(ctx, 'guichetier_stc')
        sessions.push(guichetier)
        await guichetier.page.waitForURL('**/dashboard/guichetier')
        await attendreCalme(guichetier.page)
        await guichetier.page.getByRole('button', { name: /^Alertes/ }).click()
        await guichetier.page.getByText('Message du chef de la gare Gare Adjamé').waitFor({ timeout: 10000 })
        details.push('santé de la gare, équipe recomposée, message reçu par le guichetier')

        // 6. Le QHSE lit le tableau de conformité : la visite technique du CI-1002-AB est en retard.
        const qhse = await connecter(ctx, 'qhse_stc')
        sessions.push(qhse)
        await qhse.page.waitForURL('**/dashboard/qhse')
        await attendreCalme(qhse.page)
        await qhse.page.getByText('Conformité de la flotte').first().waitFor({ timeout: 10000 })
        await qhse.page.locator('tr', { hasText: 'CI-1002-AB' }).getByText('Visite technique périodique en retard', { exact: true }).waitFor({ timeout: 10000 })
        await capturer(ctx, qhse.page, 'secretariat-3-conformite')
        details.push('tableau de conformité : obligation en retard signalée')

        const problemes = sessions.flatMap((s) => s.problemes)
        if (problemes.length) throw new Error([...new Set(problemes)].join(' ; '))
        return details
      } finally {
        for (const session of sessions) await session.fermer()
      }
    },
  },

  {
    nom: 'comptabilité : le directeur financier règle budget, dépense et facture, exporte la rentabilité, le PDG lit la situation',
    async jouer(ctx) {
      const details = []
      const iso = (decalage) => {
        const d = new Date()
        d.setDate(d.getDate() + decalage)
        return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
      }
      // Un bloc de la page, retrouvé par un élément qui n'existe que chez lui (les intitulés se répètent d'un bloc à l'autre).
      const bloc = (page, contenu) => page.locator('section.card', { has: contenu })
      const df = await connecter(ctx, 'directeur_financier_stc')
      const sessions = [df]
      try {
        // 1. Son tableau de bord montre la trésorerie ; la comptabilité est à un clic.
        await df.page.waitForURL('**/dashboard/finance')
        await attendreCalme(df.page)
        await df.page.getByText('Solde de caisse').first().waitFor({ timeout: 10000 })
        await df.page.locator('.topbar-nav').getByRole('link', { name: 'Comptabilité' }).click()
        await df.page.waitForURL('**/comptabilite')
        await attendreCalme(df.page)

        // 2. Le budget carburant du mois : une ligne à plus de 80 %, une qui a dépassé.
        const suivi = bloc(df.page, df.page.getByRole('heading', { name: 'Budget carburant par ligne', exact: true }))
        await suivi.locator('tr', { hasText: 'Yopougon-Yamoussoukro' }).getByText('Plus de 80 %').waitFor({ timeout: 10000 })
        await suivi.locator('tr', { hasText: 'Abidjan-Yamoussoukro' }).getByText('Dépassé', { exact: true }).waitFor()

        // 3. Il fixe le solde de départ, puis relève le budget de la ligne d'Abidjan-Bouaké.
        const solde = bloc(df.page, df.page.getByRole('button', { name: 'Enregistrer le solde' }))
        await solde.getByLabel('Nouveau solde de départ (FCFA)').fill('3000000')
        await solde.getByRole('button', { name: 'Enregistrer le solde' }).click()
        await df.page.getByText(/Solde de départ fixé à 3\s000\s000\sFCFA/).waitFor({ timeout: 10000 })
        await df.page.getByText(/Solde de départ : 3\s000\s000\sFCFA/).waitFor({ timeout: 10000 })
        const budget = bloc(df.page, df.page.getByRole('heading', { name: 'Fixer le budget carburant', exact: true }))
        await budget.locator('select').selectOption({ label: 'Abidjan-Bouaké' })
        await budget.getByLabel('Budget (FCFA)').fill('300000')
        await budget.getByRole('button', { name: 'Modifier le budget' }).click()
        await df.page.getByText(/Budget carburant de Abidjan-Bouaké modifié : 300\s000\sFCFA/).waitFor({ timeout: 10000 })
        await suivi.locator('tr', { hasText: 'Abidjan-Bouaké' }).getByText(/300\s000\sFCFA/).first().waitFor({ timeout: 10000 })
        details.push('budget suivi par ligne (80 % et dépassement), solde de départ fixé, budget modifié')

        // 4. Une dépense de carburant sur la ligne déjà dépassée : la finance et le PDG en sont alertés.
        const depenses = bloc(df.page, df.page.getByRole('button', { name: 'Enregistrer la dépense' }))
        await depenses.getByLabel('Libellé').fill('Plein e2e')
        await depenses.getByLabel('Montant (FCFA)').fill('5000')
        await depenses.locator('label', { hasText: 'Ligne concernée' }).locator('select').selectOption({ label: 'Abidjan-Yamoussoukro' })
        await depenses.getByRole('button', { name: 'Enregistrer la dépense' }).click()
        await df.page.getByText('Dépense « Plein e2e » enregistrée.').waitFor({ timeout: 10000 })
        await depenses.locator('tr', { hasText: 'Plein e2e' }).waitFor({ timeout: 10000 })
        await df.page.getByRole('button', { name: /^Alertes/ }).click()
        await df.page.getByText('Budget carburant dépassé : Abidjan-Yamoussoukro').waitFor({ timeout: 10000 })
        await df.page.getByRole('button', { name: /^Alertes/ }).click()

        // 5. Elle règle une facture en retard : la dépense s'enregistre seule, le retard disparaît de la trésorerie.
        const factures = bloc(df.page, df.page.getByRole('heading', { name: 'Fournisseurs, assurances et factures', exact: true }))
        const enRetard = factures.locator('tr', { hasText: 'Plaquettes de frein et filtres' })
        await enRetard.getByText('En retard de 4 j').waitFor({ timeout: 10000 })
        await df.page.locator('section.kpi', { hasText: 'Factures en retard' }).getByText('1 facture(s)').waitFor()
        await enRetard.getByRole('button', { name: 'Payer' }).click()
        await df.page.getByText('Facture « Plaquettes de frein et filtres » payée : la dépense est enregistrée.').waitFor({ timeout: 10000 })
        await enRetard.waitFor({ state: 'detached', timeout: 10000 })
        await df.page.locator('section.kpi', { hasText: 'Factures en retard' }).getByText('0 facture(s)').waitFor({ timeout: 10000 })
        await depenses.locator('tr', { hasText: 'Garage Auto Plus — Plaquettes de frein et filtres' }).waitFor({ timeout: 10000 })

        // 6. Un nouveau fournisseur et sa facture, à payer dans trois jours : elle s'ajoute à l'échéancier.
        await factures.getByLabel('Nom', { exact: true }).fill('Sotra Pièces')
        await factures.getByLabel('Activité').fill('Pièces détachées')
        await factures.getByRole('button', { name: 'Ajouter le fournisseur' }).click()
        await df.page.getByText('Fournisseur « Sotra Pièces » ajouté.').waitFor({ timeout: 10000 })
        await factures.locator('label', { hasText: 'Fournisseur ou assureur' }).locator('select').selectOption({ label: 'Sotra Pièces' })
        await factures.getByLabel('Objet').fill('Pneus arrière')
        await factures.getByLabel('Montant (FCFA)').fill('150000')
        await factures.getByLabel('À payer avant le').fill(iso(3))
        await factures.getByRole('button', { name: 'Enregistrer la facture' }).click()
        await df.page.getByText("Facture « Pneus arrière » enregistrée : elle figure à l'échéancier.").waitFor({ timeout: 10000 })
        await factures.locator('tr', { hasText: 'Pneus arrière' }).getByText('Dans 3 j').waitFor({ timeout: 10000 })
        await capturer(ctx, df.page, 'comptabilite-1')
        details.push('dépense saisie et alerte budget, facture réglée (dépense créée), fournisseur et facture ajoutés')

        // 7. La rentabilité par ligne, et son export CSV pour Excel (téléchargé avec le jeton de connexion).
        const rentabilite = bloc(df.page, df.page.getByRole('heading', { name: 'Rentabilité par ligne et par gare', exact: true }))
        await rentabilite.locator('tr', { hasText: 'Abidjan-Bouaké' }).first().waitFor({ timeout: 10000 })
        const [telechargement] = await Promise.all([
          df.page.waitForEvent('download', { timeout: 15000 }),
          rentabilite.getByRole('button', { name: 'Exporter (Excel / CSV)' }).click(),
        ])
        if (!/^rentabilite-\d{4}-\d{2}-\d{2}-\d{4}-\d{2}-\d{2}\.csv$/.test(telechargement.suggestedFilename())) {
          throw new Error(`nom de fichier inattendu : ${telechargement.suggestedFilename()}`)
        }
        let csv = ''
        for await (const morceau of await telechargement.createReadStream()) csv += morceau.toString('utf-8')
        if (!csv.startsWith('﻿Ligne;Gare de départ;') || !csv.includes('Abidjan-Bouaké;') || !csv.includes('TOTAL;')) {
          throw new Error(`contenu de l'export inattendu : ${csv.slice(0, 200)}`)
        }
        details.push(`rentabilité par ligne et par gare, export ${telechargement.suggestedFilename()}`)

        // 8. Le PDG voit la trésorerie sur son tableau de bord, puis la situation complète, sans pouvoir rien saisir.
        const pdg = await connecter(ctx, 'pdg_stc')
        sessions.push(pdg)
        await pdg.page.waitForURL('**/dashboard/direction')
        await attendreCalme(pdg.page)
        await pdg.page.getByText('Solde de caisse').first().waitFor({ timeout: 10000 })
        await pdg.page.locator('.topbar-nav').getByRole('link', { name: 'Finances' }).click()
        await pdg.page.waitForURL('**/finances')
        await attendreCalme(pdg.page)
        const suiviPdg = bloc(pdg.page, pdg.page.getByRole('heading', { name: 'Budget carburant par ligne', exact: true }))
        await suiviPdg.locator('tr', { hasText: 'Abidjan-Yamoussoukro' }).getByText('Dépassé', { exact: true }).waitFor({ timeout: 10000 })
        const echeancier = bloc(pdg.page, pdg.page.getByRole('heading', { name: 'Échéancier des paiements', exact: true }))
        await echeancier.getByText("Prime d'assurance de la flotte").waitFor({ timeout: 10000 })
        await echeancier.getByText('Pneus arrière').waitFor()
        if ((await echeancier.getByText('Plaquettes de frein et filtres').count()) !== 0) throw new Error('une facture payée figure encore à l’échéancier')
        if ((await pdg.page.getByRole('button', { name: /Enregistrer|Payer|Fixer/ }).count()) !== 0) throw new Error('le PDG voit des boutons de saisie')
        await pdg.page.getByRole('button', { name: /^Alertes/ }).click()
        await pdg.page.getByText('Budget carburant dépassé : Abidjan-Yamoussoukro').waitFor({ timeout: 10000 })
        await capturer(ctx, pdg.page, 'comptabilite-2-pdg')
        details.push('le PDG lit trésorerie, budget et échéancier, reçoit l’alerte de dépassement, ne peut rien saisir')

        const problemes = sessions.flatMap((s) => s.problemes)
        if (problemes.length) throw new Error([...new Set(problemes)].join(' ; '))
        return details
      } finally {
        for (const session of sessions) await session.fermer()
      }
    },
  },

  {
    nom: 'ressources humaines : formations OSER, congé validé après impact, doléance, recrutement, fiche agent',
    async jouer(ctx) {
      const details = []
      const bloc = (page, contenu) => page.locator('section.card', { has: contenu })
      const guichetier = await connecter(ctx, 'guichetier_stc')
      const chauffeur = await connecter(ctx, 'chauffeur_stc')
      const drh = await connecter(ctx, 'drh_stc', {
        ignorer: [/HTTP 409 POST \/conges\/\d+\/approuver\//, /console : Failed to load resource: the server responded with a status of 409/],
      })
      const sessions = [guichetier, chauffeur, drh]
      try {
        // 1. Le guichetier ouvre « Mon espace » : sa demande de congé attend, il n'a aucune formation obligatoire ; il dépose une doléance grave.
        await guichetier.page.waitForURL('**/dashboard/guichetier')
        await attendreCalme(guichetier.page)
        await guichetier.page.locator('.topbar-nav').getByRole('link', { name: 'Mon espace' }).click()
        await guichetier.page.waitForURL('**/espace')
        await attendreCalme(guichetier.page)
        await bloc(guichetier.page, guichetier.page.getByRole('heading', { name: 'Mes congés', exact: true })).getByText('En attente').first().waitFor({ timeout: 10000 })
        await guichetier.page.getByText("Aucune formation obligatoire n'est prévue pour votre poste.").waitFor()
        const mediation = bloc(guichetier.page, guichetier.page.getByRole('heading', { name: 'Médiation sociale', exact: true }))
        await mediation.getByLabel('Objet', { exact: true }).fill('Climatiseur du guichet en panne')
        await mediation.locator('select').selectOption('grave')
        await mediation.getByLabel('Ce qui se passe').fill('Le climatiseur du guichet est en panne depuis un mois, il y fait plus de 38 degrés.')
        await mediation.getByRole('button', { name: 'Déposer la doléance' }).click()
        await guichetier.page.getByText('Doléance déposée : le DRH en est informé.').waitFor({ timeout: 10000 })
        await mediation.locator('tr', { hasText: 'Climatiseur du guichet en panne' }).getByText('Déposée', { exact: true }).waitFor({ timeout: 10000 })

        // 2. Le chauffeur voit ses formations : la sécurité routière à renouveler, la visite médicale à jour.
        await chauffeur.page.waitForURL('**/dashboard/chauffeur')
        await attendreCalme(chauffeur.page)
        await chauffeur.page.locator('.topbar-nav').getByRole('link', { name: 'Mon espace' }).click()
        await chauffeur.page.waitForURL('**/espace')
        await attendreCalme(chauffeur.page)
        const formations = bloc(chauffeur.page, chauffeur.page.getByRole('heading', { name: 'Mes formations obligatoires', exact: true }))
        await formations.locator('tr', { hasText: 'Sécurité routière OSER' }).getByText('À renouveler', { exact: true }).waitFor({ timeout: 10000 })
        await formations.locator('tr', { hasText: "Visite médicale d'aptitude" }).getByText('À jour', { exact: true }).waitFor()
        details.push('espace agent : congé en attente, formations OSER (à renouveler) et visite médicale (à jour), doléance déposée')

        // 3. Le DRH enregistre une session pour un conducteur dont la formation est expirée : elle passe à jour.
        await drh.page.waitForURL('**/dashboard/rh')
        await attendreCalme(drh.page)
        await drh.page.getByRole('tab', { name: 'Formations obligatoires' }).click()
        const expiree = drh.page.locator('tr', { hasText: 'Expirée' }).first()
        await expiree.waitFor({ timeout: 10000 })
        await drh.page.locator('tr', { hasText: 'Manquante' }).first().waitFor()
        const nombreExpirees = await drh.page.locator('tr', { hasText: 'Expirée' }).count()
        await expiree.getByRole('button', { name: 'Enregistrer une session' }).click()
        await drh.page.getByRole('button', { name: 'Enregistrer la session', exact: true }).click()
        await drh.page.getByText('Session enregistrée.').waitFor({ timeout: 10000 })
        await drh.page.waitForFunction((n) => [...document.querySelectorAll('tr')].filter((tr) => tr.textContent.includes('Expirée')).length < n, nombreExpirees, { timeout: 10000 })
        await capturer(ctx, drh.page, 'rh-1-formations')

        // 4. Les congés : le guichetier est seul à son poste (impact critique), le chauffeur a un départ demain (à réaffecter).
        await drh.page.getByRole('tab', { name: 'Congés' }).click()
        const carteGuichetier = bloc(drh.page, drh.page.getByRole('heading', { name: /\(Guichetier\)/ }))
        await carteGuichetier.getByText('Impact critique').waitFor({ timeout: 10000 })
        await carteGuichetier.getByRole('button', { name: /^Approuver le congé de/ }).click()
        await drh.page.getByText('Impact critique sur', { exact: false }).waitFor({ timeout: 10000 })
        await drh.page.getByRole('button', { name: 'Valider malgré tout' }).click()
        await drh.page.getByText(/approuvé : l'agent est prévenu/).waitFor({ timeout: 10000 })
        const carteChauffeur = bloc(drh.page, drh.page.getByRole('heading', { name: /\(Chauffeur principal\)/ }))
        await carteChauffeur.getByText('Départs à réaffecter').waitFor({ timeout: 10000 })
        await carteChauffeur.getByRole('button', { name: /^Approuver le congé de/ }).click()
        await drh.page.getByText('devront être réaffectés', { exact: false }).waitFor({ timeout: 10000 })
        await capturer(ctx, drh.page, 'rh-2-conges')
        await drh.page.getByRole('button', { name: 'Valider malgré tout' }).click()
        await drh.page.getByText(/approuvé : l'agent est prévenu/).waitFor({ timeout: 10000 })
        await guichetier.page.reload()
        await attendreCalme(guichetier.page)
        await guichetier.page.getByRole('button', { name: /^Alertes/ }).click()
        await guichetier.page.getByText('Congé approuvé du', { exact: false }).waitFor({ timeout: 10000 })
        details.push('congés : impact critique et départs à réaffecter demandent confirmation, l’agent est prévenu')

        // 5. La médiation : le DRH instruit la doléance, l'agent voit l'étape (une note interne reste invisible).
        await drh.page.getByRole('tab', { name: 'Médiation sociale' }).click()
        const ligneDoleance = drh.page.locator('tr', { hasText: 'Climatiseur du guichet en panne' })
        await ligneDoleance.getByText('Grave', { exact: true }).waitFor({ timeout: 10000 })
        await ligneDoleance.getByRole('button', { name: 'Instruire' }).click()
        const instruction = drh.page.locator('section.detail-panneau', { hasText: 'Climatiseur du guichet en panne' })
        await instruction.getByLabel('Nouvelle étape').fill('Rencontre avec le chef de gare vendredi à 10 h.')
        await instruction.getByLabel('Faire passer la doléance à').selectOption('en_mediation')
        await instruction.getByRole('button', { name: "Ajouter l'étape" }).click()
        await drh.page.getByText('Étape enregistrée.').waitFor({ timeout: 10000 })
        await instruction.getByLabel('Nouvelle étape').fill('Note interne : dossier à suivre de près.')
        await instruction.getByLabel('Visible du déposant').uncheck()
        await instruction.getByRole('button', { name: "Ajouter l'étape" }).click()
        await instruction.getByText('(note interne)').waitFor({ timeout: 10000 })
        await guichetier.page.goto(`${ctx.URL_WEB}/espace`)
        await attendreCalme(guichetier.page)
        const suiviAgent = mediation.locator('tr', { hasText: 'Climatiseur du guichet en panne' })
        await suiviAgent.getByText('Rencontre avec le chef de gare vendredi à 10 h.').waitFor({ timeout: 10000 })
        await suiviAgent.getByText('En médiation', { exact: true }).waitFor()
        if ((await guichetier.page.getByText('Note interne').count()) !== 0) throw new Error('une note interne du DRH est visible de l’agent')
        details.push('médiation : étape visible de l’agent, statut « en médiation », note interne invisible')

        // 6. Le recrutement : deux candidats retenus pour deux postes, l'offre est pourvue ; la fiche type se personnalise puis se rétablit.
        await drh.page.getByRole('tab', { name: 'Recrutement' }).click()
        const fiches = bloc(drh.page, drh.page.getByRole('heading', { name: 'Fiches de poste', exact: true }))
        await fiches.locator('select').selectOption('guichetier')
        await fiches.getByText('Fiche type', { exact: true }).waitFor({ timeout: 10000 })
        await fiches.getByLabel('Intitulé du poste').fill('Guichetier de nuit')
        await fiches.getByRole('button', { name: 'Enregistrer la fiche' }).click()
        await fiches.getByText('Fiche personnalisée', { exact: true }).waitFor({ timeout: 10000 })
        await fiches.getByRole('button', { name: 'Revenir à la fiche type' }).click()
        await fiches.getByText('Fiche type', { exact: true }).waitFor({ timeout: 10000 })
        const offres = bloc(drh.page, drh.page.getByRole('heading', { name: 'Offres de recrutement', exact: true }))
        await offres.locator('tr', { hasText: "Chauffeur d'autocar" }).getByRole('button', { name: 'Candidatures' }).click()
        await drh.page.getByLabel('Décision pour Yao Kouadio').selectOption('retenue')
        await drh.page.getByText('Yao Kouadio : retenue.').waitFor({ timeout: 10000 })
        await drh.page.getByLabel('Décision pour Awa Traoré').selectOption('retenue')
        await offres.locator('tr', { hasText: "Chauffeur d'autocar" }).locator('.badge', { hasText: 'Pourvue' }).waitFor({ timeout: 10000 })
        details.push('recrutement : fiche type personnalisée puis rétablie, offre pourvue quand les deux candidats sont retenus')

        // 7. La fiche complète d'un agent : contrat, évaluation existante, nouvelle évaluation.
        await drh.page.getByRole('tab', { name: 'Dossiers' }).click()
        await drh.page.locator('tr', { hasText: 'Guichetier' }).getByRole('button', { name: /^Ouvrir la fiche de/ }).first().click()
        const fiche = drh.page.locator('section.detail-panneau', { hasText: 'Fiche de' })
        await fiche.getByText('CDD').first().waitFor({ timeout: 10000 })
        await fiche.getByText('4/5').waitFor()
        await fiche.getByLabel('Note sur 5').selectOption('5')
        await fiche.getByLabel('Commentaire', { exact: true }).fill('Excellente tenue de caisse.')
        await fiche.getByRole('button', { name: "Ajouter l'évaluation" }).click()
        await fiche.getByText('5/5').waitFor({ timeout: 10000 })
        await capturer(ctx, drh.page, 'rh-3-fiche-agent')
        details.push('fiche agent : contrat CDD, évaluation, nouvelle évaluation')

        const problemes = sessions.flatMap((s) => s.problemes)
        if (problemes.length) throw new Error([...new Set(problemes)].join(' ; '))
        return details
      } finally {
        for (const session of sessions) await session.fermer()
      }
    },
  },

  {
    nom: 'juridique : litige social signalé, accident → sinistre, pièces jointes, modèles par pôle, synthèse pour la direction',
    async jouer(ctx) {
      const details = []
      const bloc = (page, contenu) => page.locator('section.card', { has: contenu })
      const pdf = (nom) => ({ name: nom, mimeType: 'application/pdf', buffer: Buffer.from('%PDF-1.4\n1 0 obj\n<<>>\nendobj\n%%EOF') })
      const sessions = []
      try {
        // 1. Une doléance grave a été déposée : le juridique la voit dans les litiges sociaux, sans l'identité du déposant.
        await api(ctx, 'guichetier_stc', '/doleances/', {
          method: 'POST',
          body: { objet: 'Heures de nuit non majorées', description: 'Les heures de nuit ne sont pas majorées depuis trois mois.', gravite: 'grave' },
        })
        const juriste = await connecter(ctx, 'responsable_juridique_stc')
        sessions.push(juriste)
        await juriste.page.waitForURL('**/dashboard/juridique')
        await attendreCalme(juriste.page)
        await juriste.page.getByRole('button', { name: /^Alertes/ }).click()
        await juriste.page.getByText('Risque de litige social (grave) : Heures de nuit non majorées').waitFor({ timeout: 10000 })
        await juriste.page.getByRole('button', { name: /^Alertes/ }).click()
        await juriste.page.getByRole('tab', { name: 'Litiges sociaux' }).click()
        const ligneLitige = juriste.page.locator('tr', { hasText: 'Heures de nuit non majorées' })
        await ligneLitige.getByText('Agent : Guichetier').waitFor({ timeout: 10000 })
        await juriste.page.locator('tr', { hasText: 'Temps de repos entre deux trajets' }).getByText('Délégués du personnel roulant').waitFor()
        details.push('litiges sociaux : doléance grave signalée au juridique (poste de l’auteur, pas son identité), litige syndical')

        // 2. Un chauffeur déclare un accident : le dossier de sinistre s'ouvre tout seul et le juridique est prévenu.
        const moi = await api(ctx, 'chauffeur_stc', '/auth/me/')
        const vehicules = await api(ctx, 'chauffeur_stc', '/vehicules/')
        await api(ctx, 'chauffeur_stc', '/incidents/', {
          method: 'POST',
          body: { vehicule: vehicules[0].id, chauffeur: moi.id, type_incident: 'accident', description: 'Choc à basse vitesse au péage de Yamoussoukro.', gravite: 'grave' },
        })
        await juriste.page.reload()
        await attendreCalme(juriste.page)
        await juriste.page.getByRole('button', { name: /^Alertes/ }).click()
        await juriste.page.getByText('Sinistre à instruire : accident du véhicule', { exact: false }).waitFor({ timeout: 10000 })
        await juriste.page.getByRole('button', { name: /^Alertes/ }).click()
        const ligneSinistre = juriste.page.locator('tr', { hasText: 'Accident déclaré : Choc à basse vitesse au péage de Yamoussoukro.' })
        await ligneSinistre.waitFor({ timeout: 10000 })

        // 3. Le dossier : suivi auprès de l'assureur, pièce jointe (envoi, téléchargement, retrait).
        await ligneSinistre.getByRole('button', { name: /^Dossier du sinistre/ }).click()
        const dossier = juriste.page.locator('section.detail-panneau', { hasText: 'Dossier du sinistre' })
        await dossier.getByLabel("Référence chez l'assureur").fill('NSIA-2026-0042')
        await dossier.getByLabel('Montant estimé (FCFA)').fill('1500000')
        await dossier.getByRole('button', { name: 'Enregistrer le suivi' }).click()
        await juriste.page.getByText('Suivi du sinistre enregistré.').waitFor({ timeout: 10000 })
        await dossier.locator('input[type=file]').setInputFiles(pdf('constat.pdf'))
        await dossier.getByLabel('Libellé de la pièce').fill('Constat amiable')
        await dossier.getByRole('button', { name: 'Joindre la pièce' }).click()
        await juriste.page.getByText('Pièce « constat.pdf » jointe au dossier.').waitFor({ timeout: 10000 })
        await dossier.getByText('Constat amiable').first().waitFor()
        const [telechargement] = await Promise.all([
          juriste.page.waitForEvent('download', { timeout: 15000 }),
          dossier.getByRole('button', { name: 'Télécharger' }).click(),
        ])
        if (telechargement.suggestedFilename() !== 'constat.pdf') throw new Error(`nom de fichier inattendu : ${telechargement.suggestedFilename()}`)
        let contenu = ''
        for await (const morceau of await telechargement.createReadStream()) contenu += morceau.toString('utf-8')
        if (!contenu.startsWith('%PDF-1.4')) throw new Error('le fichier téléchargé n’est pas celui qui a été joint')
        await capturer(ctx, juriste.page, 'juridique-1-sinistre')
        details.push('accident déclaré → sinistre ouvert, suivi assureur, pièce jointe envoyée puis téléchargée à l’identique')

        // 4. La bibliothèque : le juridique publie un modèle réservé aux fonctions supports et joint un fichier à un autre.
        await juriste.page.getByRole('tab', { name: 'Modèles de documents' }).click()
        const gestion = bloc(juriste.page, juriste.page.getByRole('heading', { name: 'Bibliothèque de modèles de documents', exact: true }))
        await gestion.getByLabel('Titre du modèle').fill('Reçu pour solde de tout compte')
        await gestion.getByLabel('Texte du modèle').fill('Je soussigné [nom] reconnais avoir reçu la somme de [montant] au titre du solde de tout compte.')
        await gestion.getByLabel('Fonctions supports').check()
        await gestion.getByRole('button', { name: 'Publier le modèle' }).click()
        await juriste.page.getByText('Modèle « Reçu pour solde de tout compte » publié.').waitFor({ timeout: 10000 })
        await gestion.locator('tr', { hasText: 'Attestation de travail' }).locator('input[type=file]').setInputFiles(pdf('attestation.pdf'))
        await juriste.page.getByText('Fichier « attestation.pdf » joint au modèle.').waitFor({ timeout: 10000 })

        // 5. Les autres pôles consultent : chacun voit les modèles ouverts à son pôle, télécharge le fichier, copie le texte.
        const guichetier = await connecter(ctx, 'guichetier_stc')
        const mecanicien = await connecter(ctx, 'mecanicien_stc')
        const drh = await connecter(ctx, 'drh_stc')
        sessions.push(guichetier, mecanicien, drh)
        for (const [session, page] of [[guichetier, 'guichetier'], [mecanicien, 'mecanicien'], [drh, 'rh']]) {
          await session.page.waitForURL(`**/dashboard/${page}`)
          await attendreCalme(session.page)
          await session.page.locator('.topbar-nav').getByRole('link', { name: 'Modèles juridiques' }).click()
          await session.page.waitForURL('**/modeles')
          await attendreCalme(session.page)
        }
        await guichetier.page.getByRole('heading', { name: 'Attestation de travail' }).waitFor({ timeout: 10000 })
        await guichetier.page.getByRole('heading', { name: "Constat amiable d'accident" }).waitFor()
        for (const interdit of ["Charte de sécurité de l'atelier", 'Reçu pour solde de tout compte']) {
          if ((await guichetier.page.getByRole('heading', { name: interdit }).count()) !== 0) throw new Error(`le guichetier voit « ${interdit} »`)
        }
        await mecanicien.page.getByRole('heading', { name: "Charte de sécurité de l'atelier" }).waitFor({ timeout: 10000 })
        if ((await mecanicien.page.getByRole('heading', { name: 'Reçu pour solde de tout compte' }).count()) !== 0) throw new Error('le mécanicien voit un modèle réservé aux supports')
        await drh.page.getByRole('heading', { name: 'Reçu pour solde de tout compte' }).waitFor({ timeout: 10000 })
        await guichetier.page.getByLabel('Rechercher un modèle').fill('constat')
        await guichetier.page.getByRole('heading', { name: 'Attestation de travail' }).waitFor({ state: 'detached', timeout: 10000 })
        await guichetier.page.getByRole('button', { name: 'Lire le texte' }).click()
        await guichetier.page.getByText('Circonstances', { exact: false }).waitFor()
        await guichetier.page.getByLabel('Rechercher un modèle').fill('attestation')
        const [modele] = await Promise.all([
          guichetier.page.waitForEvent('download', { timeout: 15000 }),
          guichetier.page.getByRole('button', { name: /^Télécharger le fichier/ }).click(),
        ])
        if (modele.suggestedFilename() !== 'attestation.pdf') throw new Error(`nom de modèle inattendu : ${modele.suggestedFilename()}`)
        details.push('bibliothèque : modèles filtrés par pôle (guichetier, mécanicien, DRH), recherche, lecture, téléchargement du fichier')

        // 6. La direction lit la synthèse : situation juridique et gestion RH.
        const pdg = await connecter(ctx, 'pdg_stc')
        sessions.push(pdg)
        await pdg.page.waitForURL('**/dashboard/direction')
        await attendreCalme(pdg.page)
        await pdg.page.locator('.topbar-nav').getByRole('link', { name: 'Synthèse RH et juridique' }).click()
        await pdg.page.waitForURL('**/synthese')
        await attendreCalme(pdg.page)
        await pdg.page.getByText('Points de vigilance', { exact: false }).waitFor({ timeout: 10000 })
        await pdg.page.getByText('assurance expirée', { exact: false }).waitFor()
        await pdg.page.getByText('litige(s) social(aux)', { exact: false }).first().waitFor()
        await pdg.page.getByText('Effectif actif').waitFor()
        await capturer(ctx, pdg.page, 'juridique-2-synthese-direction')
        details.push('synthèse pour la direction : points de vigilance juridiques et chiffres RH')

        const problemes = sessions.flatMap((s) => s.problemes)
        if (problemes.length) throw new Error([...new Set(problemes)].join(' ; '))
        return details
      } finally {
        for (const session of sessions) await session.fermer()
      }
    },
  },
]
