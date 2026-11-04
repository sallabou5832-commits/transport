export function formatFCFA(montant) {
  return `${Math.round(Number(montant) || 0).toLocaleString('fr-FR')} FCFA`
}

export function formatDateHeure(iso) {
  if (!iso) return '—'
  return new Date(iso).toLocaleString('fr-FR', { dateStyle: 'short', timeStyle: 'short' })
}

export function formatHeure(iso) {
  if (!iso) return '—'
  return new Date(iso).toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' })
}

export function formatDate(iso) {
  if (!iso) return '—'
  return new Date(iso).toLocaleDateString('fr-FR')
}

/** « 2025-03-09 » du jour, décalé de `decalageJours` (négatif = passé), en heure locale. */
export function isoAujourdhui(decalageJours = 0) {
  const date = new Date()
  date.setDate(date.getDate() + decalageJours)
  const mois = String(date.getMonth() + 1).padStart(2, '0')
  const jour = String(date.getDate()).padStart(2, '0')
  return `${date.getFullYear()}-${mois}-${jour}`
}

export function estAujourdhui(iso) {
  return new Date(iso).toDateString() === new Date().toDateString()
}

/** Jours entre aujourd'hui et une date « AAAA-MM-JJ » (négatif si la date est passée). */
export function joursRestants(dateIso) {
  const [annee, mois, jour] = dateIso.split('-').map(Number)
  const aujourdhui = new Date()
  aujourdhui.setHours(0, 0, 0, 0)
  return Math.round((new Date(annee, mois - 1, jour) - aujourdhui) / 86400000)
}

/**
 * Où en est une échéance « AAAA-MM-JJ » (autorisation d'exercer, carte de transport) : un rappel à l'écran, rien n'est bloqué.
 * `null` sans date.
 */
export function etatEcheance(dateIso, preavisJours = 60) {
  if (!dateIso) return null
  const jours = joursRestants(dateIso)
  if (jours < 0) return { ton: 'rouge', libelle: `Expirée depuis ${-jours} j` }
  if (jours <= preavisJours) return { ton: 'orange', libelle: `Échéance dans ${jours} j` }
  return { ton: 'vert', libelle: 'À jour' }
}

/** Une durée en minutes, lisible : « 45 min », « 5 h », « 5 h 30 » ; « — » sans valeur. */
export function formatDuree(minutes) {
  if (!minutes) return '—'
  const heures = Math.floor(minutes / 60)
  const reste = minutes % 60
  if (!heures) return `${reste} min`
  return reste ? `${heures} h ${String(reste).padStart(2, '0')}` : `${heures} h`
}

/** Horaires d'ouverture d'une gare : « 05:30 – 22:00 », « dès 05:30 », « jusqu'à 22:00 » ou « — ». */
export function horairesGare(gare) {
  const ouverture = gare.heure_ouverture?.slice(0, 5)
  const fermeture = gare.heure_fermeture?.slice(0, 5)
  if (ouverture && fermeture) return `${ouverture} – ${fermeture}`
  if (ouverture) return `dès ${ouverture}`
  if (fermeture) return `jusqu'à ${fermeture}`
  return '—'
}

/** Ancienneté en années entières à partir d'une date « AAAA-MM-JJ ». */
export function anciennete(dateIso) {
  const debut = new Date(dateIso)
  const maintenant = new Date()
  let annees = maintenant.getFullYear() - debut.getFullYear()
  const anniversairePasse =
    maintenant.getMonth() > debut.getMonth() ||
    (maintenant.getMonth() === debut.getMonth() && maintenant.getDate() >= debut.getDate())
  if (!anniversairePasse) annees -= 1
  return Math.max(0, annees)
}

export function indexParId(liste) {
  return Object.fromEntries(liste.map((element) => [element.id, element]))
}

export const LABELS_VEHICULE = {
  disponible: 'Disponible',
  en_ligne: 'En ligne',
  en_maintenance: 'En maintenance',
  bloque_securite: 'Bloqué sécurité',
}

/** « Awa Koné » → « awa.kone » : l'identifiant de connexion proposé à la création d'un compte (modifiable). */
export function identifiantPropose(prenom, nom) {
  return [prenom, nom]
    .map((partie) =>
      partie
        .normalize('NFD')
        .replace(/\p{Diacritic}/gu, '')
        .toLowerCase()
        .trim()
        .replace(/[^a-z0-9]+/g, '-')
        .replace(/^-+|-+$/g, ''),
    )
    .filter(Boolean)
    .join('.')
}

/**
 * Les alertes critiques non lues apparues depuis le relevé précédent (`dejaVues` : les identifiants déjà relevés), pour prévenir
 * l'agent (son, notification du navigateur) une seule fois par alerte. Au premier relevé (`dejaVues` nul), rien n'est nouveau.
 */
export function nouvellesAlertesCritiques(dejaVues, alertes) {
  if (!dejaVues) return []
  return alertes.filter((alerte) => alerte.gravite === 'critique' && !alerte.lue && !dejaVues.has(alerte.id))
}

// Durées de session proposées à la connexion (« rester connecté ») : sans case cochée, 1 jour comme avant. Le serveur ramène le
// choix au plafond de la compagnie et du poste.
export const LABELS_DUREE_SESSION = {
  jour: '1 jour',
  semaine: '7 jours',
  mois: '30 jours',
  deconnexion: "Jusqu'à la déconnexion",
}

export const LABELS_CLASSE_VEHICULE = { standard: 'Standard', climatise: 'Climatisé', vip: 'VIP' }

export const TON_VEHICULE = {
  disponible: 'vert',
  en_ligne: 'bleu',
  en_maintenance: 'orange',
  bloque_securite: 'rouge',
}

export const LABELS_GRAVITE = { faible: 'Faible', moyenne: 'Moyenne', grave: 'Grave' }
export const TON_GRAVITE = { faible: 'neutre', moyenne: 'orange', grave: 'rouge' }

export const LABELS_TYPE_INCIDENT = {
  panne: 'Panne',
  accident: 'Accident',
  retard: 'Retard',
  cargaison: 'Anomalie de cargaison',
  autre: 'Autre',
}

export const LABELS_DEPART = { planifie: 'Planifié', en_cours: 'En cours', termine: 'Terminé' }

export const TON_COULEUR = { vert: 'vert', orange: 'orange', rouge: 'rouge', neutre: 'neutre' }
