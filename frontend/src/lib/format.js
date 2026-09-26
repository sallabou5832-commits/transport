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
