export default function Jauge({ vendues, capacite, reservees = 0 }) {
  const total = capacite || 0
  const pourcentage = total > 0 ? Math.min(100, Math.round((vendues / total) * 100)) : 0
  const plein = total > 0 && vendues >= total
  // Places mises de côté pour des ventes hors ligne : pas encore vendues, mais plus
  // vendables par un autre guichet (voir places_reservees dans l'API des départs).
  const pourcentageReserve =
    total > 0 ? Math.min(100 - pourcentage, Math.round((reservees / total) * 100)) : 0

  return (
    <div className="jauge">
      <div className="jauge-barre">
        <div
          className={`jauge-remplissage${plein ? ' jauge-pleine' : ''}`}
          style={{ width: `${pourcentage}%` }}
        />
        {pourcentageReserve > 0 && (
          <div
            className="jauge-reservee"
            style={{ width: `${pourcentageReserve}%` }}
            title={`${reservees} place(s) réservée(s) pour des ventes hors ligne`}
          />
        )}
      </div>
      <span className="jauge-texte">
        {vendues} / {total} places ({pourcentage}%)
        {reservees > 0 && ` · dont ${reservees} réservée${reservees > 1 ? 's' : ''} hors ligne`}
      </span>
    </div>
  )
}
