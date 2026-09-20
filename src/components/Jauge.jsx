export default function Jauge({ vendues, capacite }) {
  const total = capacite || 0
  const pourcentage = total > 0 ? Math.min(100, Math.round((vendues / total) * 100)) : 0
  const plein = total > 0 && vendues >= total

  return (
    <div className="jauge">
      <div className="jauge-barre">
        <div
          className={`jauge-remplissage${plein ? ' jauge-pleine' : ''}`}
          style={{ width: `${pourcentage}%` }}
        />
      </div>
      <span className="jauge-texte">
        {vendues} / {total} places ({pourcentage}%)
      </span>
    </div>
  )
}
