import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import {
  anciennete,
  estAujourdhui,
  etatEcheance,
  formatDuree,
  formatFCFA,
  identifiantPropose,
  nouvellesAlertesCritiques,
  indexParId,
  isoAujourdhui,
  joursRestants,
} from './format.js'

describe('formatFCFA', () => {
  it('arrondit et sépare les milliers', () => {
    expect(formatFCFA(5000)).toContain('5')
    expect(formatFCFA(5000)).toMatch(/000\sFCFA$/)
    expect(formatFCFA('12500.6')).toMatch(/501\sFCFA$/)
  })

  it('traite une valeur absente comme zéro', () => {
    expect(formatFCFA(undefined)).toBe('0 FCFA')
    expect(formatFCFA(null)).toBe('0 FCFA')
    expect(formatFCFA('abc')).toBe('0 FCFA')
  })
})

describe('dates relatives à aujourd’hui', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date(2030, 4, 17, 10, 30)) // 17 mai 2030, heure locale
  })
  afterEach(() => vi.useRealTimers())

  it('isoAujourdhui décale en jours, en heure locale', () => {
    expect(isoAujourdhui()).toBe('2030-05-17')
    expect(isoAujourdhui(-6)).toBe('2030-05-11')
    expect(isoAujourdhui(20)).toBe('2030-06-06')
  })

  it('estAujourdhui ne regarde que le jour', () => {
    expect(estAujourdhui(new Date(2030, 4, 17, 0, 5).toISOString())).toBe(true)
    expect(estAujourdhui(new Date(2030, 4, 17, 23, 55).toISOString())).toBe(true)
    expect(estAujourdhui(new Date(2030, 4, 18, 0, 5).toISOString())).toBe(false)
  })

  it('joursRestants compte les jours pleins, négatifs si la date est passée', () => {
    expect(joursRestants('2030-05-17')).toBe(0)
    expect(joursRestants('2030-05-27')).toBe(10)
    expect(joursRestants('2030-05-10')).toBe(-7)
  })

  it('etatEcheance rappelle une échéance passée ou proche, sans date rien', () => {
    expect(etatEcheance('2030-05-10')).toEqual({ ton: 'rouge', libelle: 'Expirée depuis 7 j' })
    expect(etatEcheance('2030-05-17')).toEqual({ ton: 'orange', libelle: 'Échéance dans 0 j' })
    expect(etatEcheance('2030-07-16')).toEqual({ ton: 'orange', libelle: 'Échéance dans 60 j' })
    expect(etatEcheance('2030-07-17')).toEqual({ ton: 'vert', libelle: 'À jour' })
    expect(etatEcheance('2030-06-01', 10).ton).toBe('vert')
    expect(etatEcheance('')).toBeNull()
    expect(etatEcheance(null)).toBeNull()
  })

  it('anciennete compte les années entières révolues', () => {
    expect(anciennete('2020-05-17')).toBe(10)
    expect(anciennete('2020-05-18')).toBe(9) // l’anniversaire n’est pas encore passé
    expect(anciennete('2031-01-01')).toBe(0) // jamais négative
  })
})

describe('identifiantPropose', () => {
  it('fait un identifiant sans accent ni espace à partir du prénom et du nom', () => {
    expect(identifiantPropose('Awa', 'Koné')).toBe('awa.kone')
    expect(identifiantPropose('Jean-Marc', "N'Guessan Yao")).toBe('jean-marc.n-guessan-yao')
    expect(identifiantPropose('Élodie', '')).toBe('elodie')
    expect(identifiantPropose('', '')).toBe('')
  })
})

describe('nouvellesAlertesCritiques', () => {
  const alertes = [
    { id: 1, gravite: 'critique', lue: false },
    { id: 2, gravite: 'attention', lue: false },
    { id: 3, gravite: 'critique', lue: true },
    { id: 4, gravite: 'critique', lue: false },
  ]

  it('au premier relevé, rien n’est nouveau (on ne sonne pas pour le stock déjà là)', () => {
    expect(nouvellesAlertesCritiques(null, alertes)).toEqual([])
  })

  it('ensuite, seules les critiques non lues jamais relevées', () => {
    expect(nouvellesAlertesCritiques(new Set([1, 2, 3]), alertes).map((a) => a.id)).toEqual([4])
    expect(nouvellesAlertesCritiques(new Set([1, 2, 3, 4]), alertes)).toEqual([])
  })
})

describe('formatDuree', () => {
  it('écrit une durée en heures et minutes', () => {
    expect(formatDuree(45)).toBe('45 min')
    expect(formatDuree(300)).toBe('5 h')
    expect(formatDuree(330)).toBe('5 h 30')
    expect(formatDuree(65)).toBe('1 h 05')
    expect(formatDuree(null)).toBe('—')
    expect(formatDuree(0)).toBe('—')
  })
})

describe('indexParId', () => {
  it('indexe une liste par identifiant', () => {
    const index = indexParId([{ id: 1, nom: 'A' }, { id: 7, nom: 'B' }])
    expect(index[7].nom).toBe('B')
    expect(Object.keys(index)).toEqual(['1', '7'])
  })
})
