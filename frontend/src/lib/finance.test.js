import { describe, expect, it } from 'vitest'
import { dernierJourDuMois, etatEcheance, jourDuMois, moisCourant, premierJourDuMois } from './finance.js'

const le = (annee, mois, jour) => new Date(annee, mois - 1, jour)

describe('mois', () => {
  it('donne le premier et le dernier jour du mois en cours', () => {
    expect(premierJourDuMois(0, le(2026, 9, 21))).toBe('2026-09-01')
    expect(dernierJourDuMois(0, le(2026, 9, 21))).toBe('2026-09-30')
  })

  it('passe au mois précédent, y compris à cheval sur l’année et en février bissextile', () => {
    expect(premierJourDuMois(-1, le(2026, 1, 15))).toBe('2025-12-01')
    expect(dernierJourDuMois(-1, le(2026, 1, 15))).toBe('2025-12-31')
    expect(dernierJourDuMois(-1, le(2024, 3, 10))).toBe('2024-02-29')
    expect(dernierJourDuMois(-1, le(2026, 3, 10))).toBe('2026-02-28')
  })

  it('formate le mois d’un champ mois et le ramène au premier jour', () => {
    expect(moisCourant(le(2026, 9, 21))).toBe('2026-09')
    expect(jourDuMois('2026-09')).toBe('2026-09-01')
  })
})

describe('etatEcheance', () => {
  it('signale un retard en rouge', () => {
    expect(etatEcheance({ en_retard: true, jours_restants: -3 })).toEqual({ libelle: 'En retard de 3 j', ton: 'rouge' })
  })

  it('met en orange ce qui tombe dans la semaine, y compris aujourd’hui', () => {
    expect(etatEcheance({ en_retard: false, jours_restants: 0 })).toEqual({ libelle: "Aujourd'hui", ton: 'orange' })
    expect(etatEcheance({ en_retard: false, jours_restants: 7 })).toEqual({ libelle: 'Dans 7 j', ton: 'orange' })
  })

  it('laisse en vert ce qui est plus lointain', () => {
    expect(etatEcheance({ en_retard: false, jours_restants: 8 })).toEqual({ libelle: 'Dans 8 j', ton: 'vert' })
  })
})
