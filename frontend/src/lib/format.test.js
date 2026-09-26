import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import {
  anciennete,
  estAujourdhui,
  formatFCFA,
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

  it('anciennete compte les années entières révolues', () => {
    expect(anciennete('2020-05-17')).toBe(10)
    expect(anciennete('2020-05-18')).toBe(9) // l’anniversaire n’est pas encore passé
    expect(anciennete('2031-01-01')).toBe(0) // jamais négative
  })
})

describe('indexParId', () => {
  it('indexe une liste par identifiant', () => {
    const index = indexParId([{ id: 1, nom: 'A' }, { id: 7, nom: 'B' }])
    expect(index[7].nom).toBe('B')
    expect(Object.keys(index)).toEqual(['1', '7'])
  })
})
