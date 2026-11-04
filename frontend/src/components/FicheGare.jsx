import { useState } from 'react'
import { apiFetch } from '../api/client.js'
import useActions from '../api/useActions.js'
import Alert from './Alert.jsx'

const VIDE = { nom: '', ville: '', adresse: '', telephone: '', heure_ouverture: '', heure_fermeture: '', chef: '', latitude: '', longitude: '' }

function valeursDe(gare) {
  if (!gare) return VIDE
  return {
    nom: gare.nom,
    ville: gare.ville,
    adresse: gare.adresse,
    telephone: gare.telephone,
    heure_ouverture: gare.heure_ouverture?.slice(0, 5) || '',
    heure_fermeture: gare.heure_fermeture?.slice(0, 5) || '',
    chef: gare.chef ?? '',
    latitude: gare.latitude ?? '',
    longitude: gare.longitude ?? '',
  }
}

/**
 * La fiche d'une gare (`gare` absente : une nouvelle gare). Avec `chefs` (l'annuaire des chefs de gare, que seule la direction
 * reçoit), la fiche est complète : nom, ville, chef, position sur la carte. Sans, c'est ce que le chef de gare tient lui-même :
 * adresse, téléphone et horaires de sa gare.
 */
export default function FicheGare({ gare, chefs, onEnregistre, onSupprime }) {
  const complet = Boolean(chefs)
  const [valeurs, setValeurs] = useState(() => valeursDe(gare))
  const { agir, envoi, message } = useActions(onEnregistre)
  const changer = (champ) => (event) => setValeurs({ ...valeurs, [champ]: event.target.value })

  async function supprimer() {
    // Un élément déjà utilisé (départs, tickets, historique) se garde : le serveur refuse et dit pourquoi.
    if (!window.confirm(`Supprimer la gare « ${gare.nom} » ?`)) return
    await agir(() => apiFetch(`/gares/${gare.id}/`, { method: 'DELETE' }).then(() => onSupprime()), null)
  }

  async function enregistrer(event) {
    event.preventDefault()
    const corps = {
      adresse: valeurs.adresse,
      telephone: valeurs.telephone,
      heure_ouverture: valeurs.heure_ouverture || null,
      heure_fermeture: valeurs.heure_fermeture || null,
    }
    if (complet) {
      Object.assign(corps, {
        nom: valeurs.nom,
        ville: valeurs.ville,
        chef: valeurs.chef === '' ? null : Number(valeurs.chef),
        latitude: valeurs.latitude === '' ? null : Number(valeurs.latitude).toFixed(6),
        longitude: valeurs.longitude === '' ? null : Number(valeurs.longitude).toFixed(6),
      })
    }
    const ok = await agir(
      gare
        ? () => apiFetch(`/gares/${gare.id}/`, { method: 'PATCH', body: corps })
        : () => apiFetch('/gares/', { method: 'POST', body: corps }),
      gare ? `Fiche de la gare ${valeurs.nom || gare.nom} enregistrée.` : `Gare « ${valeurs.nom} » créée.`,
    )
    if (ok && !gare) setValeurs(VIDE)
  }

  return (
    <form onSubmit={enregistrer}>
      <Alert type={message.type || 'error'}>{message.texte}</Alert>
      <div className="form-grid">
        {complet && (
          <>
            <label>
              Nom de la gare
              <input value={valeurs.nom} onChange={changer('nom')} maxLength={255} required />
            </label>
            <label>
              Ville
              <input value={valeurs.ville} onChange={changer('ville')} maxLength={255} required />
            </label>
            <label>
              Chef de gare
              <select value={valeurs.chef} onChange={changer('chef')}>
                <option value="">— Aucun —</option>
                {gare?.chef && !chefs.some((chef) => chef.id === gare.chef) && (
                  // Le chef en place dont le compte est suspendu n'est plus dans l'annuaire : on le montre tel quel.
                  <option value={gare.chef}>{gare.chef_nom} (compte suspendu)</option>
                )}
                {chefs.map((chef) => {
                  const ailleurs = chef.gare && chef.gare.id !== gare?.id
                  return (
                    <option key={chef.id} value={chef.id} disabled={ailleurs}>
                      {chef.nom}
                      {ailleurs ? ` (dirige ${chef.gare.nom})` : ''}
                    </option>
                  )
                })}
              </select>
            </label>
          </>
        )}
        <label>
          Adresse
          <input value={valeurs.adresse} onChange={changer('adresse')} maxLength={255} />
        </label>
        <label>
          Téléphone
          <input type="tel" value={valeurs.telephone} onChange={changer('telephone')} maxLength={30} placeholder="07 00 00 00 00" />
        </label>
        <label>
          Ouverture
          <input type="time" value={valeurs.heure_ouverture} onChange={changer('heure_ouverture')} />
        </label>
        <label>
          Fermeture
          <input type="time" value={valeurs.heure_fermeture} onChange={changer('heure_fermeture')} />
        </label>
        {complet && (
          <>
            <label>
              Latitude (carte)
              <input type="number" step="any" min="-90" max="90" value={valeurs.latitude} onChange={changer('latitude')} />
            </label>
            <label>
              Longitude (carte)
              <input type="number" step="any" min="-180" max="180" value={valeurs.longitude} onChange={changer('longitude')} />
            </label>
          </>
        )}
      </div>
      <div className="fiche-actions">
        <button type="submit" disabled={envoi}>
          {gare ? 'Enregistrer la fiche' : 'Créer la gare'}
        </button>
        {gare && onSupprime && (
          <button type="button" className="button-secondary" disabled={envoi} onClick={supprimer}>
            Supprimer la gare
          </button>
        )}
      </div>
    </form>
  )
}
