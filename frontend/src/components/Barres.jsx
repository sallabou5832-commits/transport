/**
 * Barres horizontales proportionnelles au plus grand élément.
 * `lignes` : [{ cle, label, valeur }] ; `format` met en forme la valeur affichée.
 */
export default function Barres({ lignes, format = (valeur) => valeur, vide = 'Aucune donnée.' }) {
  if (lignes.length === 0) return <p className="muted">{vide}</p>
  const max = Math.max(...lignes.map((ligne) => ligne.valeur))
  return (
    <ul className="barres">
      {lignes.map((ligne) => (
        <li key={ligne.cle}>
          <span className="barres-label">{ligne.label}</span>
          <span className="barres-piste">
            <span
              className="barres-barre"
              style={{ width: `${max > 0 ? (ligne.valeur / max) * 100 : 0}%` }}
            />
          </span>
          <strong className="barres-valeur">{format(ligne.valeur)}</strong>
        </li>
      ))}
    </ul>
  )
}
