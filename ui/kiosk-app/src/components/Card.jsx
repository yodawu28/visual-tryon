export function Card({ children, className = "", padded = true }) {
  return (
    <section
      className={[
        "rounded-2xl border border-line bg-white shadow-card transition duration-200",
        padded ? "p-5" : "",
        className,
      ].join(" ")}
    >
      {children}
    </section>
  );
}

export function CardHeader({ title, description, action }) {
  return (
    <div className="mb-5 flex items-start justify-between gap-4">
      <div className="min-w-0">
        <h2 className="text-lg font-semibold tracking-tight text-ink">{title}</h2>
        {description ? <p className="mt-1 text-sm leading-6 text-muted">{description}</p> : null}
      </div>
      {action ? <div className="shrink-0">{action}</div> : null}
    </div>
  );
}
