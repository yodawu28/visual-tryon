const variants = {
  primary: "bg-brand-600 text-white shadow-sm hover:bg-brand-700 focus:ring-brand-200",
  secondary: "border border-line bg-white text-ink hover:bg-slate-50 focus:ring-slate-200",
  ghost: "text-muted hover:bg-slate-100 hover:text-ink focus:ring-slate-200",
  danger: "bg-rose-500 text-white hover:bg-rose-700 focus:ring-rose-100",
};

const sizes = {
  sm: "h-9 px-3 text-sm",
  md: "h-11 px-4 text-sm",
  lg: "h-12 px-5 text-base",
};

export function Button({
  children,
  className = "",
  size = "md",
  type = "button",
  variant = "primary",
  ...props
}) {
  return (
    <button
      className={[
        "inline-flex items-center justify-center gap-2 rounded-md font-semibold transition duration-200",
        "focus:outline-none focus:ring-4 disabled:cursor-not-allowed disabled:opacity-50",
        variants[variant],
        sizes[size],
        className,
      ].join(" ")}
      type={type}
      {...props}
    >
      {children}
    </button>
  );
}
