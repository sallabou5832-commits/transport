import { Link, useSearchParams } from 'react-router-dom'
import { apiFetch } from '../api/client.js'
import useChargement from '../api/useChargement.js'
import { useAuth } from '../auth/AuthContext.jsx'
import { DASHBOARD_ROLES, PAGES_ANNEXES } from '../auth/roles.js'
import Alert from '../components/Alert.jsx'
import Badge from '../components/Badge.jsx'
import Layout from '../components/Layout.jsx'
import Onglets from '../components/Onglets.jsx'
import { posteAffiche, tachesParMoment } from '../lib/guide.js'

/** Les écrans de la fiche : un lien vers chaque page que le lecteur peut ouvrir, le téléphone signalé. */
function Ecrans({ ecrans, ouvertes }) {
  return (
    <table className="table">
      <thead>
        <tr>
          <th>Écran</th>
          <th>À quoi il sert</th>
        </tr>
      </thead>
      <tbody>
        {ecrans.map((ecran) => (
          <tr key={`${ecran.support}-${ecran.titre}`}>
            <td>
              {ecran.chemin && ouvertes.has(ecran.chemin) ? <Link to={ecran.chemin}>{ecran.titre}</Link> : ecran.titre}
              {ecran.support === 'mobile' && (
                <>
                  {' '}
                  <Badge ton="bleu">Téléphone</Badge>
                </>
              )}
            </td>
            <td>{ecran.usage}</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

/** Les gestes pas à pas, dans l'ordre d'une journée, avec les postes avec qui chacun se coordonne. */
function Taches({ taches, moments }) {
  return tachesParMoment(taches, moments).map((moment) => (
    <div key={moment.code} className="guide-moment">
      <h4>{moment.libelle}</h4>
      {moment.taches.map((tache) => (
        <article key={tache.titre} className="guide-tache">
          <strong>{tache.titre}</strong>
          {tache.permise === true && <Badge ton="vert">Permis par votre règlement intérieur</Badge>}
          {tache.permise === false && <Badge ton="orange">Non permis par votre règlement intérieur</Badge>}
          <ol>
            {tache.etapes.map((etape) => (
              <li key={etape}>{etape}</li>
            ))}
          </ol>
          {tache.avec?.length > 0 && (
            <p className="muted">
              Avec :{' '}
              {tache.avec.map((poste, rang) => (
                <span key={poste.poste}>
                  {rang > 0 && ', '}
                  <Link to={`/guide?poste=${poste.poste}`}>{poste.libelle}</Link>
                </span>
              ))}
            </p>
          )}
        </article>
      ))}
    </div>
  ))
}

function Listes({ contacts, astuces }) {
  return (
    <>
      {contacts.length > 0 && (
        <>
          <h3>À qui vous adresser</h3>
          <ul>
            {contacts.map((ligne) => (
              <li key={ligne}>{ligne}</li>
            ))}
          </ul>
        </>
      )}
      {astuces.length > 0 && (
        <>
          <h3>Bon à savoir</h3>
          <ul>
            {astuces.map((ligne) => (
              <li key={ligne}>{ligne}</li>
            ))}
          </ul>
        </>
      )}
    </>
  )
}

function Fiche({ fiche, moments, ouvertes, monPoste, pole }) {
  return (
    <section className="card guide-fiche" data-pole={pole}>
      <div className="guide-entete">
        <h2>
          {fiche.libelle} {fiche.poste === monPoste && <Badge ton="vert">Votre poste</Badge>}
        </h2>
        <button type="button" className="button-secondary button-small no-print" onClick={() => window.print()}>
          Imprimer cette fiche
        </button>
      </div>
      <p>{fiche.mission}</p>
      {(fiche.regle_par.length > 0 || fiche.regle.length > 0) && (
        <p className="muted">
          {fiche.regle_par.length > 0 && <>Poste réglé par : {fiche.regle_par.join(', ')}. </>}
          {fiche.regle.length > 0 && <>Règle les postes : {fiche.regle.join(', ')}.</>}
        </p>
      )}

      <h3>Écrans</h3>
      <Ecrans ecrans={fiche.ecrans} ouvertes={ouvertes} />

      <h3>Pas à pas</h3>
      <Taches taches={fiche.taches} moments={moments} />

      {fiche.reglement.length > 0 && (
        <>
          <h3>Ce que le règlement intérieur de votre compagnie permet à ce poste</h3>
          <ul>
            {fiche.reglement.map((regle) => (
              <li key={regle.code}>
                {regle.libelle} :{' '}
                {regle.permis ? <Badge ton="vert">Permis</Badge> : <Badge ton="orange">Non permis</Badge>}{' '}
                <span className="muted">(décidé par : {regle.decide === 'PDG' ? 'PDG' : `${regle.decide} ou PDG`})</span>
              </li>
            ))}
          </ul>
        </>
      )}

      <Listes contacts={fiche.contacts} astuces={fiche.astuces} />
    </section>
  )
}

/**
 * Le guide d'utilisation : la fiche de chaque poste, rangée par pôle — sa mission, ses écrans, ses gestes pas à pas dans l'ordre
 * d'une journée et les postes avec qui il se coordonne. Chacun lit le guide de tous les postes ; le sien s'ouvre d'abord.
 * Le règlement intérieur cité est celui de la compagnie du lecteur.
 */
export default function GuidePage() {
  const { user } = useAuth()
  const { data: guide, error, loading } = useChargement(() => apiFetch('/guides/'))
  const [parametres, setParametres] = useSearchParams()

  if (!guide) {
    return (
      <Layout title="Guide">
        <Alert>{error}</Alert>
        {loading && <p>Chargement…</p>}
      </Layout>
    )
  }

  const ouvertes = new Set(
    Object.entries({ ...DASHBOARD_ROLES, ...PAGES_ANNEXES })
      .filter(([, roles]) => roles.includes(user?.role))
      .map(([chemin]) => chemin),
  )
  const poste = posteAffiche(guide, parametres.get('poste'))
  const pole = guide.poles.find((p) => p.postes.some((fiche) => fiche.poste === poste))
  const fiche = pole.postes.find((f) => f.poste === poste)
  const ouvrir = (code) => setParametres({ poste: code })

  return (
    <Layout title="Guide">
      <Alert>{error}</Alert>
      <div className="no-print">
        <Onglets
          onglets={guide.poles.map((p) => ({
            id: p.pole,
            label: p.pole === guide.mon_pole ? `${p.libelle} (votre pôle)` : p.libelle,
            pole: p.pole,
          }))}
          actif={pole.pole}
          onChoix={(code) => {
            const choisi = guide.poles.find((p) => p.pole === code)
            ouvrir(choisi.postes.some((f) => f.poste === guide.mon_poste) ? guide.mon_poste : choisi.postes[0].poste)
          }}
        />
        <Onglets
          onglets={pole.postes.map((f) => ({ id: f.poste, label: f.libelle, pole: pole.pole }))}
          actif={poste}
          onChoix={ouvrir}
        />
      </div>

      <Fiche fiche={fiche} moments={guide.moments} ouvertes={ouvertes} monPoste={guide.mon_poste} pole={pole.pole} />

      <details className="card guide-communs">
        <summary>
          <strong>Pour tous les postes</strong> — connexion, alertes, congés, doléances, paramètres
        </summary>
        <h3>Écrans</h3>
        <Ecrans ecrans={guide.communs.ecrans} ouvertes={ouvertes} />
        <h3>Pas à pas</h3>
        <Taches taches={guide.communs.taches} moments={guide.moments} />
        <Listes contacts={guide.communs.contacts} astuces={guide.communs.astuces} />
      </details>
    </Layout>
  )
}
