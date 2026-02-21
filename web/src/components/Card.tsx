// Reusable metric card — a label + bold value in a small panel.
// No state or side effects; React just calls this as a function and renders the JSX.
export function Card({ label, value, tooltip }: { label: string; value: string; tooltip?: string }) {
  return (
    <article className="card" title={tooltip ?? `${label}: ${value}`}>
      <p>{label}</p>
      <h3>{value}</h3>
    </article>
  )
}
