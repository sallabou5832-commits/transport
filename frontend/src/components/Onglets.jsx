/**
 * Onglets d'une page dense : `onglets` = [{ id, label, pole? }], `actif` l'id affiché, `onChoix` reçoit l'id choisi. `pole` donne à
 * l'onglet la couleur de ce pôle (le guide).
 */
export default function Onglets({ onglets, actif, onChoix }) {
  return (
    <div className="onglets" role="tablist">
      {onglets.map((onglet) => (
        <button
          key={onglet.id}
          type="button"
          role="tab"
          aria-selected={actif === onglet.id}
          data-pole={onglet.pole}
          className={`onglet${actif === onglet.id ? ' onglet-actif' : ''}`}
          onClick={() => onChoix(onglet.id)}
        >
          {onglet.label}
        </button>
      ))}
    </div>
  )
}
