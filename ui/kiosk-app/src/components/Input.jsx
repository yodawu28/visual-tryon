export function Input({ className = "", label, hint, id, ...props }) {
  return (
    <label className="grid gap-1.5 text-sm font-medium text-slate-700" htmlFor={id}>
      {label}
      <input
        className={[
          "h-11 rounded-xl border border-line bg-white px-3 text-sm text-ink shadow-sm outline-none transition",
          "placeholder:text-slate-400 focus:border-brand-500 focus:ring-4 focus:ring-brand-100",
          className,
        ].join(" ")}
        id={id}
        {...props}
      />
      {hint ? <span className="text-xs font-normal text-muted">{hint}</span> : null}
    </label>
  );
}

export function Select({ children, className = "", label, id, ...props }) {
  return (
    <label className="grid gap-1.5 text-sm font-medium text-slate-700" htmlFor={id}>
      {label}
      <select
        className={[
          "h-11 rounded-xl border border-line bg-white px-3 text-sm text-ink shadow-sm outline-none transition",
          "focus:border-brand-500 focus:ring-4 focus:ring-brand-100",
          className,
        ].join(" ")}
        id={id}
        {...props}
      >
        {children}
      </select>
    </label>
  );
}
