/** Une tuile par gare, colorée selon sa ponctualité du jour (vert / orange / rouge / neutre). */
export default function TuilesGares({ gares }) {
  if (gares.length === 0) return <p className="muted">Aucune gare enregistrée.</p>
  return (
    <div className="tuiles">
      {gares.map((gare) => (
        <div key={gare.id} className={`tuile tuile-${gare.couleur}`}>
          <h3>{gare.nom}</h3>
          <p className="muted">{gare.ville}</p>
          <p>
            {gare.departs} départ{gare.departs > 1 ? 's' : ''} ·{' '}
            {gare.ponctualite_pourcent === null ? 'ponctualité —' : `${gare.ponctualite_pourcent} % à l'heure`}
          </p>
          <p className="muted">
            Remplissage {gare.remplissage_pourcent === null ? '—' : `${gare.remplissage_pourcent} %`}
          </p>
        </div>
      ))}
    </div>
  )
}
