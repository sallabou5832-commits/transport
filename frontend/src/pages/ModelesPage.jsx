import BibliothequeModeles from '../components/BibliothequeModeles.jsx'
import Layout from '../components/Layout.jsx'

/** La bibliothèque de modèles de documents juridiques, ouverte à tous les pôles de la compagnie. */
export default function ModelesPage() {
  return (
    <Layout title="Modèles juridiques">
      <BibliothequeModeles />
    </Layout>
  )
}
