import { Button } from "./Button.jsx";

function HeaderStatus({ children }) {
  return (
    <span className="inline-flex h-8 min-w-0 items-center justify-center rounded-md bg-slate-50 px-2.5 text-xs font-semibold text-slate-700 ring-1 ring-line/80 sm:px-3">
      <span className="truncate">{children}</span>
    </span>
  );
}

export function AppHeader(props) {
  return <TopBar {...props} />;
}

export function TopBar({
  activeStage,
  garmentSelected,
  onNewSession,
  onOpenDiagnostics,
  onOpenProduct,
  sessionLabel,
}) {
  const productAction = garmentSelected ? "Change product" : "Select product";
  const sessionStatus = sessionLabel === "Active" ? "Session active" : "New session";

  return (
    <header className="sticky top-0 z-30 border-b border-line/80 bg-white/95 px-4 py-2.5 backdrop-blur-xl sm:px-6">
      <div className="mx-auto flex w-full max-w-[1720px] flex-col gap-2 lg:flex-row lg:items-center lg:justify-between">
        <div className="min-w-0">
          <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-muted">Current workflow</p>
          <h2 className="truncate text-lg font-semibold tracking-tight text-ink">Visual Fitting Room</h2>
        </div>

        <div className="grid w-full grid-cols-2 items-center gap-2 sm:flex sm:w-auto sm:justify-end">
          <HeaderStatus>{sessionStatus}</HeaderStatus>
          <Button className="min-w-0 w-full sm:w-auto" onClick={onOpenProduct} size="sm" variant="secondary">
            <span className="sm:hidden">Product</span>
            <span className="hidden sm:inline">{productAction}</span>
          </Button>
          <Button className="min-w-0 w-full sm:w-auto" onClick={onNewSession} size="sm" variant="secondary">
            <span className="sm:hidden">New</span>
            <span className="hidden sm:inline">New session</span>
          </Button>
          <Button
            aria-label={`Open tools for ${activeStage}`}
            className="min-w-0 w-full sm:w-auto"
            onClick={onOpenDiagnostics}
            size="sm"
            variant="ghost"
          >
            Tools
          </Button>
        </div>
      </div>
    </header>
  );
}
