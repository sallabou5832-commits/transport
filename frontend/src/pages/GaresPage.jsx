import { useState } from 'react'
import { apiFetch } from '../api/client.js'
import useChargement from '../api/useChargement.js'
import Alert from '../components/Alert.jsx'
import FicheGare from '../components/FicheGare.jsx'
import Layout from '../components/Layout.jsx'
import QuaisGare from '../components/QuaisGare.jsx'
import { horairesGare } from '../lib/format.js'

/**
 * Les gares de la compagnie, tenues par la direction sans passer par l'administration : créer une gare, renseigner sa fiche
 * (coordonnées, horaires, position sur la carte), désigner son chef, déclarer ses quais. Une gare ne se supprime pas d'ici :
 * ses départs, ses caisses et ses dépenses y restent rattachés.
 */
export default function GaresPage() {
  const [ouverte, setOuverte] = useState(null)
  const { data, error, loading, recharger } = useChargement(async () => {
    const [gares, chefs, quais] = await Promise.all([apiFetch('/gares/'), apiFetch('/gares/chefs-possibles/'), apiFetch('/quais/')])
    return { gares, chefs, quais }
  })

  if (!data) {
    return (
      <Layout title="Gares et quais">
        <Alert>{error}</Alert>
        {loading && <p>Chargement…</p>}
      </Layout>
    )
  }

  const { gares, chefs, quais } = data
  const gare = gares.find((g) => g.id === ouverte) || null
  const quaisPar = (id) => quais.filter((q) => q.gare === id)

  return (
    <Layout title="Gares et quais">
      <Alert>{error}</Alert>
      <section className="card">
        <h2>Gares ({gares.length})</h2>
        {gares.length === 0 ? (
          <p className="muted">Aucune gare : créez la première ci-dessous.</p>
        ) : (
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>Gare</th>
                  <th>Chef de gare</th>
                  <th>Téléphone</th>
                  <th>Horaires</th>
                  <th>Quais</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {gares.map((g) => (
                  <tr key={g.id}>
                    <td>
                      {g.nom}
                      <div className="muted">{[g.ville, g.adresse].filter(Boolean).join(' — ')}</div>
                    </td>
                    <td>{g.chef_nom || <span className="muted">Aucun</span>}</td>
                    <td>{g.telephone || '—'}</td>
                    <td>{horairesGare(g)}</td>
                    <td>
                      {quaisPar(g.id).filter((q) => q.actif).length} ouvert(s)
                      {quaisPar(g.id).some((q) => !q.actif) && (
                        <div className="muted">{quaisPar(g.id).filter((q) => !q.actif).length} fermé(s)</div>
                      )}
                    </td>
                    <td>
                      <button
                        type="button"
                        className="button-secondary button-small"
                        onClick={() => setOuverte(ouverte === g.id ? null : g.id)}
                      >
                        {ouverte === g.id ? 'Masquer' : 'Modifier'}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {gare && (
        <section className="card card-highlight">
          <h2>Fiche de {gare.nom}</h2>
          <FicheGare key={gare.id} gare={gare} chefs={chefs} onEnregistre={recharger} onSupprime={() => setOuverte(null)} />
          <QuaisGare gare={gare} onChange={recharger} />
        </section>
      )}

      <section className="card">
        <h2>Nouvelle gare</h2>
        <FicheGare key="nouvelle" chefs={chefs} onEnregistre={recharger} />
      </section>
    </Layout>
  )
}
