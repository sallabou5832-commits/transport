/** Pastille de statut. `ton` : vert, orange, rouge, bleu ou neutre. */
export default function Badge({ ton = 'neutre', children }) {
  return <span className={`badge badge-${ton}`}>{children}</span>
}
