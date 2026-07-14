import { useEffect, useState } from "react";

import { AppHeader } from "./components/AppHeader.jsx";
import { AppSidebar } from "./components/AppSidebar.jsx";
import { Button } from "./components/Button.jsx";
import { FittingWorkflow } from "./components/FittingWorkflow.jsx";
import { Input, Select } from "./components/Input.jsx";
import { Modal } from "./components/Modal.jsx";
import {
  DashboardIcon,
  ProductIcon,
  ScanIcon,
  SettingsIcon,
  TryOnIcon,
} from "./components/icons.jsx";
import { checkReadiness, resolveDefaultApiBase, trimTrailingSlash } from "./lib/api.js";
import {
  displayCaptureLabel,
  displayGarmentLabel,
  displaySessionLabel,
  displayTryOnLabel,
} from "./lib/displayLabels.js";

const appNavItems = [
  { key: "sessions", label: "Sessions", icon: DashboardIcon },
  { key: "products", label: "Products", icon: ProductIcon },
  { key: "fitting-room", label: "Fitting Room", icon: ScanIcon },
  { key: "history", label: "History", icon: TryOnIcon },
  { key: "settings", label: "Settings", icon: SettingsIcon },
];

const initialSessionState = {
  garmentId: "local-demo-garment",
  garmentName: "T-Shirt",
  captureUploaded: false,
  capturePassed: false,
  visualPreviewReady: false,
  fitReady: false,
  previewKey: "",
  jobId: "",
  jobStatus: "",
};

function FittingRoomApp() {
  const [apiBase, setApiBase] = useState(resolveDefaultApiBase());
  const [apiStatus, setApiStatus] = useState("Checking");
  const [eventLog, setEventLog] = useState(["App loaded"]);
  const [diagnosticsDrawer, setDiagnosticsDrawer] = useState(false);
  const [productModalOpen, setProductModalOpen] = useState(false);
  const [state, setState] = useState(() => ({
    ...initialSessionState,
    garmentId: localStorage.getItem("kioskGarmentId") || initialSessionState.garmentId,
    garmentName: localStorage.getItem("kioskGarmentName") || initialSessionState.garmentName,
  }));

  const hasSession = Boolean(state.garmentId || state.captureUploaded || state.jobId || state.previewKey);
  const sessionLabel = displaySessionLabel(hasSession);
  const garmentLabel = displayGarmentLabel(state);
  const captureLabel = displayCaptureLabel(state);
  const tryOnLabel = displayTryOnLabel(state);
  const activeStage = getActiveStage(state);

  useEffect(() => {
    localStorage.setItem("kioskApiBase", apiBase);
  }, [apiBase]);

  useEffect(() => {
    let cancelled = false;
    checkReadiness(apiBase).then((result) => {
      if (cancelled) return;
      setApiStatus(result.label);
      appendLog(`Readiness: ${result.label}`);
    });
    return () => {
      cancelled = true;
    };
  }, [apiBase]);

  const applicationShell = "product-application-shell min-h-screen overflow-x-hidden bg-canvas text-ink";
  const bottomNavigation = "fixed inset-x-0 bottom-0 z-40 border-t border-line bg-white/95 px-2 py-2 backdrop-blur lg:hidden";

  function appendLog(message) {
    setEventLog((current) => [`${new Date().toLocaleTimeString()} ${message}`, ...current].slice(0, 10));
  }

  function resetSession() {
    localStorage.removeItem("kioskGarmentId");
    localStorage.removeItem("kioskGarmentName");
    setState(initialSessionState);
    appendLog("New fitting session prepared");
  }

  function saveProduct(event) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const garmentName = String(form.get("garmentName") || "Coach demo garment").trim();
    const nextState = {
      ...state,
      garmentId: "local-demo-garment",
      garmentName,
    };
    localStorage.setItem("kioskGarmentId", nextState.garmentId);
    localStorage.setItem("kioskGarmentName", nextState.garmentName);
    setState(nextState);
    setProductModalOpen(false);
    appendLog(`Product selected: ${garmentName}`);
  }

  function simulateCapture() {
    setState((current) => ({
      ...current,
      captureUploaded: true,
      capturePassed: true,
      visualPreviewReady: true,
      fitReady: true,
    }));
    appendLog("Guided scan marked ready");
  }

  function queueTryOn() {
    setState((current) => ({
      ...current,
      jobId: "local-demo-job",
      jobStatus: "running",
    }));
    appendLog("Try-on generation queued");
    window.setTimeout(() => {
      setState((current) => ({
        ...current,
        jobStatus: "succeeded",
        previewKey: "local-demo-preview",
      }));
      appendLog("Try-on preview ready");
    }, 900);
  }

  function handlePrimaryAction() {
    if (!state.garmentId) {
      setProductModalOpen(true);
      return;
    }
    if (!state.capturePassed) {
      simulateCapture();
      return;
    }
    queueTryOn();
  }

  async function checkApi() {
    setApiStatus("Checking");
    const result = await checkReadiness(apiBase);
    setApiStatus(result.label);
    appendLog(`Manual readiness check: ${result.label}`);
  }

  function handleNavigationAction(destination) {
    if (destination === "products") {
      setProductModalOpen(true);
      return;
    }
    if (destination === "settings") {
      setDiagnosticsDrawer(true);
      return;
    }
    if (destination !== "fitting-room") {
      appendLog(`Navigation selected: ${destination}`);
    }
  }

  return (
    <AppShell
      bottomNavigation={
        <nav aria-label="Mobile navigation" className={bottomNavigation}>
          <div className="grid grid-cols-5 gap-1">
            {appNavItems.map((item) => {
              const active = item.key === "fitting-room";

              return (
                <button
                  className={[
                    "grid min-h-14 place-items-center gap-1 rounded-xl px-1 text-xs font-semibold transition",
                    active ? "bg-slate-100 text-brand-700" : "text-slate-500",
                  ].join(" ")}
                  key={item.key}
                  onClick={() => handleNavigationAction(item.key)}
                  type="button"
                >
                  <item.icon className="h-5 w-5" />
                  <span className="truncate">{item.label.split(" ")[0]}</span>
                </button>
              );
            })}
          </div>
        </nav>
      }
      className={applicationShell}
      header={
          <AppHeader
            activeStage={activeStage}
            garmentSelected={Boolean(state.garmentId)}
            onNewSession={resetSession}
            onOpenDiagnostics={() => setDiagnosticsDrawer((open) => !open)}
            onOpenProduct={() => setProductModalOpen(true)}
            sessionLabel={sessionLabel}
          />
      }
      sidebar={<AppSidebar onSelect={handleNavigationAction} />}
    >
      <main className="mx-auto w-full max-w-[1680px] px-4 py-4 sm:px-5 lg:py-5">
            <FittingWorkflow
              activeStage={activeStage}
              captureLabel={captureLabel}
              garmentLabel={garmentLabel}
              onOpenProduct={() => setProductModalOpen(true)}
              onQueueTryOn={queueTryOn}
              onRunScan={simulateCapture}
              state={state}
              tryOnLabel={tryOnLabel}
            />
      </main>

      <DiagnosticsDrawer
        apiBase={apiBase}
        apiStatus={apiStatus}
        diagnosticsDrawer={diagnosticsDrawer}
        eventLog={eventLog}
        onApiBaseChange={(value) => setApiBase(trimTrailingSlash(value))}
        onCheckApi={checkApi}
        onClose={() => setDiagnosticsDrawer(false)}
      />

      <ProductModal onClose={() => setProductModalOpen(false)} onSubmit={saveProduct} open={productModalOpen} />
    </AppShell>
  );
}

function AppShell({ bottomNavigation, children, className, header, sidebar }) {
  return (
    <div className={className} data-app-shell="virtual-fitting-app">
      <div className="flex min-h-screen">
        {sidebar}
        <div className="min-w-0 max-w-full flex-1 overflow-x-hidden pb-24 lg:pb-0">
          {header}
          {children}
        </div>
      </div>
      {bottomNavigation}
    </div>
  );
}

function getActiveStage(state) {
  if (!state.garmentId) return "product";
  if (!state.capturePassed) return "capture";
  if (!state.previewKey) return "fit";
  return "tryon";
}

function ProductModal({ onClose, onSubmit, open }) {
  return (
    <Modal
      description="Use realistic product details so the fitting room reads like an operator app, not a demo wrapper."
      onClose={onClose}
      open={open}
      title="Select product"
    >
      <form className="grid gap-4" onSubmit={onSubmit}>
        <Input id="garmentName" label="Display name" name="garmentName" placeholder="Coach demo garment" />
        <div className="grid gap-4 sm:grid-cols-2">
          <Select id="category" label="Category" name="category">
            <option>Tops</option>
            <option>Bottoms</option>
            <option>One piece</option>
            <option>Full outfit</option>
          </Select>
          <Input id="garmentType" label="Garment type" name="garmentType" placeholder="t-shirt" />
        </div>
        <label className="grid min-h-32 cursor-pointer place-items-center rounded-2xl border border-dashed border-line bg-slate-50 p-4 text-center transition hover:bg-brand-50">
          <input className="sr-only" type="file" />
          <span className="font-semibold text-ink">Choose garment image</span>
          <span className="mt-1 text-sm text-muted">PNG or JPG, clean front product photo</span>
        </label>
        <div className="flex justify-end gap-2">
          <Button onClick={onClose} variant="secondary">
            Cancel
          </Button>
          <Button type="submit">Save product</Button>
        </div>
      </form>
    </Modal>
  );
}

function DiagnosticsDrawer({
  apiBase,
  apiStatus,
  diagnosticsDrawer,
  eventLog,
  onApiBaseChange,
  onCheckApi,
  onClose,
}) {
  return (
    <aside
      aria-label="Diagnostics"
      className={[
        "fixed right-4 top-20 z-40 w-[min(420px,calc(100vw-2rem))] rounded-2xl border border-line bg-white p-5 shadow-soft transition",
        diagnosticsDrawer ? "translate-y-0 opacity-100" : "pointer-events-none -translate-y-3 opacity-0",
      ].join(" ")}
    >
      <div className="flex items-start justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold tracking-tight text-ink">Diagnostics</h2>
          <p className="text-sm text-muted">Developer tools stay out of the shopper-facing workflow.</p>
        </div>
        <Button onClick={onClose} size="sm" variant="ghost">
          Close
        </Button>
      </div>
      <div className="mt-4 grid gap-3">
        <div className="rounded-2xl border border-line bg-slate-50 p-4">
          <div className="flex items-start justify-between gap-3">
            <div>
              <p className="text-xs font-bold uppercase tracking-[0.14em] text-muted">Backend</p>
              <p className="mt-1 text-sm font-semibold text-ink">{apiStatus}</p>
            </div>
            <Button onClick={onCheckApi} size="sm" variant="secondary">
              Check
            </Button>
          </div>
          <Input
            defaultValue={apiBase}
            hint="Use same origin on RunPod, or 127.0.0.1:8080 while testing standalone."
            id="api-base-input"
            label="API base"
            onBlur={(event) => onApiBaseChange(event.target.value)}
            type="url"
          />
        </div>
        <div className="rounded-2xl bg-slate-950 p-4">
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">eventLog</p>
          <pre className="mt-2 max-h-52 overflow-auto whitespace-pre-wrap text-xs leading-5 text-slate-100">
            {eventLog.join("\n")}
          </pre>
        </div>
      </div>
    </aside>
  );
}

function StatusTile({ label, value }) {
  return (
    <div className="rounded-2xl border border-line bg-white p-4 shadow-sm">
      <p className="text-xs font-bold uppercase tracking-[0.14em] text-muted">{label}</p>
      <p className="mt-2 break-words text-sm font-semibold text-ink">{value}</p>
    </div>
  );
}

export default FittingRoomApp;
