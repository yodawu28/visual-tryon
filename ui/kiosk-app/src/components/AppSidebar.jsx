import { DashboardIcon, ProductIcon, ScanIcon, SettingsIcon, TryOnIcon } from "./icons.jsx";

const appNavigation = [
  { key: "products", label: "Garments", icon: ProductIcon },
  { key: "size-charts", label: "Size charts", icon: TryOnIcon },
  { key: "sessions", label: "Sessions", icon: DashboardIcon },
  { key: "settings", label: "Settings", icon: SettingsIcon },
  { key: "kiosk", label: "Visual Try-on", icon: ScanIcon },
];

export function AppSidebar({ activeKey = "products", onSelect }) {
  return <Sidebar activeKey={activeKey} items={appNavigation} onSelect={onSelect} />;
}

export function Sidebar({ activeKey = "products", items, onSelect }) {
  return (
    <aside className="hidden w-56 shrink-0 border-r border-line/70 bg-white px-3 py-4 lg:flex lg:flex-col">
      <div className="flex items-center gap-2 px-2">
        <div className="grid h-8 w-8 place-items-center rounded-md bg-ink text-xs font-black text-white shadow-sm">
          VF
        </div>
        <div className="min-w-0">
          <p className="text-[11px] font-semibold text-muted">Visual fitting</p>
          <h1 className="truncate text-sm font-semibold tracking-tight text-ink">Management</h1>
        </div>
      </div>

      <nav aria-label="Application navigation" className="mt-6 grid gap-0.5">
        {items.map((item) => {
          const active = item.key === activeKey;

          return (
            <button
              aria-current={active ? "page" : undefined}
              className={[
                "group flex min-h-9 items-center gap-2 rounded-md px-2.5 text-left text-sm font-medium transition",
                active
                  ? "bg-slate-100 text-ink"
                  : "text-slate-600 hover:bg-slate-50 hover:text-ink",
              ].join(" ")}
              key={item.key}
              onClick={() => onSelect(item.key)}
              type="button"
            >
              <item.icon className={active ? "h-4 w-4 text-brand-600" : "h-4 w-4 text-slate-500"} />
              <span className="truncate">{item.label}</span>
            </button>
          );
        })}
      </nav>

      <div className="mt-auto border-t border-line/70 px-2 pt-4">
        <p className="text-xs font-medium text-muted">Current section</p>
        <p className="mt-1 text-sm font-semibold text-ink">Management</p>
      </div>
    </aside>
  );
}
