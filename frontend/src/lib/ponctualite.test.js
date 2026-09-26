import { describe, expect, it } from 'vitest'
import cas from './ponctualite.cas.json'
import { retardMinutes, statutFeuille } from './ponctualite.js'

// Les mêmes cas sont rejoués côté serveur (transpt1/dashboard/tests/test_parite_ponctualite.py) : la règle de
// ponctualité existe en deux exemplaires (web et serveur), ce fichier commun garantit qu'ils donnent le même verdict.
describe('règle de ponctualité (cas partagés avec le serveur)', () => {
  it.each(cas)('$cas', ({ prevue, reelle, maintenant, statut, retard_minutes: retard }) => {
    const feuille = { heure_depart_prevue: prevue, heure_depart_reelle: reelle }
    expect(statutFeuille(feuille, new Date(maintenant))).toBe(statut)
    expect(retardMinutes(feuille, new Date(maintenant))).toBe(retard)
  })
})
