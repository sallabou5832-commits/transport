/** Onglets d'une page dense : `onglets` = [{ id, label }], `actif` l'id affiché, `onChoix` reçoit l'id choisi. */
export default function Onglets({ onglets, actif, onChoix }) {
  return (
    <div className="onglets" role="tablist">
      {onglets.map((onglet) => (
        <button
          key={onglet.id}
          type="button"
          role="tab"
          aria-selected={actif === onglet.id}
          className={`onglet${actif === onglet.id ? ' onglet-actif' : ''}`}
          onClick={() => onChoix(onglet.id)}
        >
          {onglet.label}
        </button>
      ))}
    </div>
  )
}
