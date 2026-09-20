/** Indicateur clé : un titre, un grand chiffre et un détail. `ton` colore la carte (vert/orange/rouge). */
export default function Kpi({ titre, valeur, detail, ton }) {
  return (
    <section className={`card kpi${ton ? ` kpi-${ton}` : ''}`}>
      <h2>{titre}</h2>
      <p className="big-number">{valeur}</p>
      {detail && <p className="muted">{detail}</p>}
    </section>
  )
}
