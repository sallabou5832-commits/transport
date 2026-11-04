import { describe, expect, it } from 'vitest'
import { posteAffiche, tachesParMoment } from './guide.js'

const GUIDE = {
  mon_poste: 'guichetier',
  poles: [
    { pole: 'direction', postes: [{ poste: 'pdg' }] },
    { pole: 'exploitation', postes: [{ poste: 'chef_gare' }, { poste: 'guichetier' }] },
  ],
}

describe('posteAffiche', () => {
  it("ouvre le poste demandé dans l'adresse", () => {
    expect(posteAffiche(GUIDE, 'pdg')).toBe('pdg')
  })

  it('ouvre sinon le poste du lecteur', () => {
    expect(posteAffiche(GUIDE, null)).toBe('guichetier')
    expect(posteAffiche(GUIDE, 'inconnu')).toBe('guichetier')
  })

  it("ouvre le premier poste pour un lecteur qui n'a pas de fiche", () => {
    expect(posteAffiche({ ...GUIDE, mon_poste: 'superadmin' }, null)).toBe('pdg')
  })
})

describe('tachesParMoment', () => {
  const moments = [
    { code: 'debut', libelle: 'En début de journée' },
    { code: 'journee', libelle: 'Au fil de la journée' },
    { code: 'fin', libelle: 'En fin de journée' },
  ]

  it("range les tâches dans l'ordre de la journée et omet les moments vides", () => {
    const taches = [
      { titre: 'Clôturer', moment: 'fin' },
      { titre: 'Vendre', moment: 'journee' },
      { titre: 'Vendre au téléphone', moment: 'journee' },
    ]

    expect(tachesParMoment(taches, moments).map((m) => [m.code, m.taches.map((t) => t.titre)])).toEqual([
      ['journee', ['Vendre', 'Vendre au téléphone']],
      ['fin', ['Clôturer']],
    ])
  })
})
