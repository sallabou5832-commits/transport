import { useMemo } from 'react'
import { apiFetch } from '../api/client.js'
import useChargement from '../api/useChargement.js'
import useFluxCarte from '../api/useFluxCarte.js'
import { fusionnerPositions } from '../lib/carte.js'
import Alert from './Alert.jsx'

const LARGEUR = 760
const HAUTEUR = 380
const MARGE = 50
const COULEURS = { vert: '#15803d', orange: '#d97706', rouge: '#b91c1c', neutre: '#6b7280' }

/** Projection simple (equirectangulaire corrigée de la latitude) des points sur un cadre, marges comprises. */
function projeter(points) {
  const latitudes = points.map((p) => Number(p.latitude))
  const longitudes = points.map((p) => Number(p.longitude))
  const latMin = Math.min(...latitudes)
  const latMax = Math.max(...latitudes)
  const lonMin = Math.min(...longitudes)
  const lonMax = Math.max(...longitudes)
  const facteur = Math.cos(((latMin + latMax) / 2) * (Math.PI / 180))
  const largeurGeo = Math.max((lonMax - lonMin) * facteur, 0.0001)
  const hauteurGeo = Math.max(latMax - latMin, 0.0001)
  const echelle = Math.min((LARGEUR - 2 * MARGE) / largeurGeo, (HAUTEUR - 2 * MARGE) / hauteurGeo)
  const decalageX = (LARGEUR - largeurGeo * echelle) / 2
  const decalageY = (HAUTEUR - hauteurGeo * echelle) / 2
  return (point) => ({
    x: decalageX + (Number(point.longitude) - lonMin) * facteur * echelle,
    y: HAUTEUR - decalageY - (Number(point.latitude) - latMin) * echelle,
  })
}

/**
 * Carte schématique du réseau, en temps réel : les gares (vert, orange ou rouge selon la ponctualité du jour), les lignes
 * qui les relient et les cars en route à leur dernière position connue. Sans fond de carte : aucun service extérieur, elle
 * fonctionne partout où le site s'ouvre.
 *
 * La position de chaque car affiché se rafraîchit dès qu'il en envoie une nouvelle (`useFluxCarte`, flux poussé par
 * WebSocket) ; la liste des cars en route elle-même (lesquels sont affichés) vient du rafraîchissement périodique
 * ci-dessous, un filet de sécurité qui rattrape aussi un flux poussé resté silencieux (voir `fusionnerPositions`,
 * `lib/carte.js`).
 */
export default function CarteReseau() {
  const { data, error } = useChargement(() => apiFetch('/dashboard/carte/'), { intervalleMs: 60000 })
  const positionsPoussees = useFluxCarte()
  const vehicules = useMemo(
    () => (data ? fusionnerPositions(data.vehicules, positionsPoussees) : []),
    [data, positionsPoussees]
  )

  if (!data) return <Alert>{error}</Alert>

  const gares = data.gares.filter((g) => g.latitude !== null && g.longitude !== null)
  const sansCoordonnees = data.gares.length - gares.length
  const points = [...gares, ...vehicules]
  if (points.length === 0) {
    return <p className="muted">Aucune gare n’a de coordonnées et aucun car n’est suivi : la carte est vide.</p>
  }

  const projection = projeter(points)
  const garesParId = Object.fromEntries(gares.map((g) => [g.id, g]))
  // Des gares très proches (deux gares d'une même ville) se chevauchent : on empile leurs étiquettes au lieu de les superposer.
  const decalageEtiquette = {}
  const placees = []
  for (const gare of gares) {
    const { x, y } = projection(gare)
    decalageEtiquette[gare.id] = placees.filter((p) => Math.hypot(p.x - x, p.y - y) < 60).length
    placees.push({ x, y })
  }

  return (
    <div>
      <svg
        viewBox={`0 0 ${LARGEUR} ${HAUTEUR}`}
        className="carte"
        role="img"
        aria-label={`Carte du réseau : ${gares.length} gare(s), ${vehicules.length} car(s) en route`}
      >
        <rect x="0" y="0" width={LARGEUR} height={HAUTEUR} fill="#f8fafc" rx="8" />
        {data.lignes.map((ligne) => {
          const depart = garesParId[ligne.gare_depart]
          const arrivee = garesParId[ligne.gare_arrivee]
          if (!depart || !arrivee) return null
          const a = projection(depart)
          const b = projection(arrivee)
          return <line key={ligne.id} x1={a.x} y1={a.y} x2={b.x} y2={b.y} stroke="#cbd5e1" strokeWidth="3" strokeDasharray="6 4" />
        })}
        {gares.map((gare) => {
          const { x, y } = projection(gare)
          return (
            <g key={`gare-${gare.id}`}>
              <circle cx={x} cy={y} r="11" fill={COULEURS[gare.couleur]}>
                <title>
                  {gare.nom} — {gare.ponctualite_pourcent === null ? 'pas de départ mesurable' : `${gare.ponctualite_pourcent} % à l’heure`} (
                  {gare.departs_du_jour} départ(s) aujourd’hui)
                </title>
              </circle>
              <text x={x} y={y - 16 - decalageEtiquette[gare.id] * 15} textAnchor="middle" fontSize="13" fontWeight="600" fill="#1f2933">
                {gare.nom}
              </text>
            </g>
          )
        })}
        {vehicules.map((car) => {
          const { x, y } = projection(car)
          return (
            <g key={`car-${car.vehicule}`}>
              <rect
                x={x - 8}
                y={y - 6}
                width="16"
                height="12"
                rx="3"
                fill="#f77f00"
                stroke={car.fatigue ? '#b91c1c' : car.en_direct ? '#ffffff' : '#9ca3af'}
                strokeWidth="3"
                strokeDasharray={car.en_direct ? undefined : '3 2'}
              >
                <title>
                  {car.immatriculation} — {car.ligne} — {car.chauffeur_nom}
                  {car.vitesse_kmh !== null ? ` — ${car.vitesse_kmh} km/h` : ''}
                  {car.en_direct ? '' : ` — dernière position il y a ${Math.round(car.age_secondes / 60)} min`}
                  {car.fatigue ? ' — conducteur fatigué' : ''}
                </title>
              </rect>
              <text x={x + 13} y={y + 4} fontSize="11" fill="#374151">
                {car.immatriculation}
              </text>
            </g>
          )
        })}
      </svg>
      <p className="muted carte-legende">
        <span style={{ color: COULEURS.vert }}>●</span> gare ≥ 90 % à l’heure · <span style={{ color: COULEURS.orange }}>●</span> ≥ 70 % ·{' '}
        <span style={{ color: COULEURS.rouge }}>●</span> en dessous · <span style={{ color: '#f77f00' }}>■</span> car en route (liseré rouge :
        conducteur fatigué, pointillé : position ancienne).
        {sansCoordonnees > 0 && ` ${sansCoordonnees} gare(s) sans coordonnées ne figurent pas sur la carte.`}
      </p>
    </div>
  )
}
