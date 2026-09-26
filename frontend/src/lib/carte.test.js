import { describe, expect, it } from 'vitest'
import { appliquerPousse, fusionnerPositions } from './carte.js'

const voiture = (idVehicule, releveLe) => ({
  vehicule: idVehicule,
  immatriculation: `CI-000${idVehicule}-AA`,
  releve_le: releveLe,
  vitesse_kmh: 50,
})

describe('appliquerPousse', () => {
  it('ajoute une position pour un véhicule pas encore connu', () => {
    const table = appliquerPousse({}, { vehicule: 7, vitesse_kmh: 60 })
    expect(table).toEqual({ 7: { vehicule: 7, vitesse_kmh: 60 } })
  })

  it('remplace la position précédente du même véhicule sans toucher aux autres', () => {
    const avant = { 7: { vehicule: 7, vitesse_kmh: 60 }, 9: { vehicule: 9, vitesse_kmh: 10 } }
    const apres = appliquerPousse(avant, { vehicule: 7, vitesse_kmh: 80 })
    expect(apres).toEqual({ 7: { vehicule: 7, vitesse_kmh: 80 }, 9: { vehicule: 9, vitesse_kmh: 10 } })
    expect(avant[7].vitesse_kmh).toBe(60) // immuable : l'ancienne table n'a pas bougé
  })
})

describe('fusionnerPositions', () => {
  it('sans rien de poussé : renvoie la liste HTTP telle quelle', () => {
    const http = [voiture(1, '2026-09-24T10:00:00Z')]
    expect(fusionnerPositions(http, {})).toEqual(http)
  })

  it('une position poussée plus récente remplace celle du chargement HTTP', () => {
    const http = [voiture(1, '2026-09-24T10:00:00Z')]
    const poussees = { 1: { vehicule: 1, vitesse_kmh: 90, releve_le: '2026-09-24T10:05:00Z' } }

    const [resultat] = fusionnerPositions(http, poussees)

    expect(resultat.vitesse_kmh).toBe(90)
    expect(resultat.releve_le).toBe('2026-09-24T10:05:00Z')
    expect(resultat.immatriculation).toBe('CI-0001-AA') // les champs non poussés restent ceux du HTTP
  })

  it('une position poussée plus ancienne (arrivée en retard) ne remplace pas la plus récente', () => {
    const http = [voiture(1, '2026-09-24T10:05:00Z')]
    const poussees = { 1: { vehicule: 1, vitesse_kmh: 10, releve_le: '2026-09-24T10:00:00Z' } }

    const [resultat] = fusionnerPositions(http, poussees)

    expect(resultat.vitesse_kmh).toBe(50)
  })

  it('un véhicule sans position poussée garde la sienne', () => {
    const http = [voiture(1, '2026-09-24T10:00:00Z'), voiture(2, '2026-09-24T10:00:00Z')]
    const poussees = { 1: { vehicule: 1, vitesse_kmh: 99, releve_le: '2026-09-24T10:05:00Z' } }

    const resultat = fusionnerPositions(http, poussees)

    expect(resultat[0].vitesse_kmh).toBe(99)
    expect(resultat[1].vitesse_kmh).toBe(50)
  })

  it('un véhicule dont le trajet est terminé (absent du HTTP) ne réapparaît pas malgré une position poussée', () => {
    const http = [voiture(1, '2026-09-24T10:00:00Z')]
    const poussees = { 2: { vehicule: 2, vitesse_kmh: 99, releve_le: '2026-09-24T10:05:00Z' } }

    const resultat = fusionnerPositions(http, poussees)

    expect(resultat).toHaveLength(1)
    expect(resultat[0].vehicule).toBe(1)
  })
})
