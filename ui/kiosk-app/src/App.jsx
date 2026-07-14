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
import {
  analyzeCapture,
  analyzeFit,
  checkReadiness,
  createSession,
  enqueueVisualPreviewJob,
  getKioskJob,
  listSizeCharts,
  resolveDefaultApiBase,
  trimTrailingSlash,
  uploadCapture,
  uploadGarment,
  visualPreviewImageUrl,
} from "./lib/api.js";
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
  garmentId: "",
  garmentName: "",
  garmentPreviewUrl: "",
  garmentCategory: "tops",
  garmentType: "regular_top",
  sessionId: "",
  sizeChartId: "",
  sizeChartName: "",
  sizeChartSizes: "",
  fitRecommendation: null,
  fitRecommendationLabel: "",
  fitRecommendationStatus: "",
  fitNeedsMeasurements: false,
  scanBusy: false,
  fitLoading: false,
  captureUploaded: false,
  capturePassed: false,
  visualPreviewReady: false,
  fitReady: false,
  previewKey: "",
  previewImageUrl: "",
  jobId: "",
  jobStatus: "",
  tryOnError: "",
};

function FittingRoomApp() {
  const [apiBase, setApiBase] = useState(resolveDefaultApiBase());
  const [apiStatus, setApiStatus] = useState("Checking");
  const [eventLog, setEventLog] = useState(["App loaded"]);
  const [diagnosticsDrawer, setDiagnosticsDrawer] = useState(false);
  const [productModalOpen, setProductModalOpen] = useState(false);
  const [productError, setProductError] = useState("");
  const [productSaving, setProductSaving] = useState(false);
  const [sizeCharts, setSizeCharts] = useState([]);
  const [sizeChartsStatus, setSizeChartsStatus] = useState("Idle");
  const [bodyMeasurements, setBodyMeasurements] = useState({
    heightCm: "",
    weightKg: "",
  });
  const [state, setState] = useState(() => ({
    ...initialSessionState,
    garmentId: storedSessionValue("kioskGarmentId") || initialSessionState.garmentId,
    garmentName: localStorage.getItem("kioskGarmentName") || initialSessionState.garmentName,
    garmentCategory: localStorage.getItem("kioskGarmentCategory") || initialSessionState.garmentCategory,
    garmentType: localStorage.getItem("kioskGarmentType") || initialSessionState.garmentType,
    sessionId: localStorage.getItem("kioskSessionId") || initialSessionState.sessionId,
    sizeChartId: localStorage.getItem("kioskSizeChartId") || initialSessionState.sizeChartId,
    sizeChartName: localStorage.getItem("kioskSizeChartName") || initialSessionState.sizeChartName,
    sizeChartSizes: localStorage.getItem("kioskSizeChartSizes") || initialSessionState.sizeChartSizes,
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
    return () => {
      if (state.garmentPreviewUrl) {
        URL.revokeObjectURL(state.garmentPreviewUrl);
      }
    };
  }, [state.garmentPreviewUrl]);

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

  useEffect(() => {
    if (!productModalOpen) return undefined;

    let cancelled = false;
    setSizeChartsStatus("Loading");
    listSizeCharts(apiBase)
      .then((payload) => {
        if (cancelled) return;
        const charts = Array.isArray(payload.size_charts) ? payload.size_charts : [];
        setSizeCharts(charts);
        setSizeChartsStatus(charts.length ? "Ready" : "Empty");
      })
      .catch((error) => {
        if (cancelled) return;
        setSizeCharts([]);
        setSizeChartsStatus("Unavailable");
        setProductError(`Could not load size charts: ${error.message}`);
      });

    return () => {
      cancelled = true;
    };
  }, [apiBase, productModalOpen]);

  const applicationShell = "product-application-shell min-h-screen overflow-x-hidden bg-canvas text-ink";
  const bottomNavigation = "fixed inset-x-0 bottom-0 z-40 border-t border-line bg-white/95 px-2 py-2 backdrop-blur lg:hidden";

  function appendLog(message) {
    setEventLog((current) => [`${new Date().toLocaleTimeString()} ${message}`, ...current].slice(0, 10));
  }

  function resetSession() {
    clearStoredSessionState();
    if (state.garmentPreviewUrl) {
      URL.revokeObjectURL(state.garmentPreviewUrl);
    }
    setState(initialSessionState);
    setBodyMeasurements({ heightCm: "", weightKg: "" });
    appendLog("New fitting session prepared");
  }

  async function saveProduct(event) {
    event.preventDefault();
    setProductError("");
    setProductSaving(true);
    const form = new FormData(event.currentTarget);
    const garmentImage = form.get("garmentImage");
    const garmentName = String(form.get("garmentName") || "Coach demo garment").trim();
    const garmentCategory = String(form.get("category") || "tops");
    const garmentType = String(form.get("garmentType") || "").trim();
    const sizeChartId = String(form.get("sizeChartId") || "").trim();
    const selectedSizeChart = sizeCharts.find((chart) => chart.size_chart_id === sizeChartId);

    if (!(garmentImage instanceof File) || !garmentImage.name) {
      setProductError("Choose a garment image before saving the product.");
      setProductSaving(false);
      return;
    }

    try {
      const uploadPayload = new FormData();
      uploadPayload.append("file", garmentImage);
      uploadPayload.append("category", garmentCategory);
      uploadPayload.append("name", garmentName);
      if (garmentType) uploadPayload.append("garment_type", garmentType);
      if (sizeChartId) uploadPayload.append("size_chart_id", sizeChartId);

      const garmentResponse = await uploadGarment(apiBase, uploadPayload);
      const garment = garmentResponse.garment;
      const sessionResponse = await createSession(apiBase, garment.garment_id);
      const garmentPreviewUrl = URL.createObjectURL(garmentImage);
      const nextState = {
        ...initialSessionState,
        garmentId: garment.garment_id,
        garmentName: garment.name || garmentName,
        garmentPreviewUrl,
        garmentCategory: garment.category || garmentCategory,
        garmentType: garment.garment_type || garmentType,
        sessionId: sessionResponse.session_id || "",
        sizeChartId: garment.size_chart_id || sizeChartId,
        sizeChartName: selectedSizeChart?.name || "",
        sizeChartSizes: formatSizeRange(selectedSizeChart?.size_chart || garment.size_chart || []),
      };

      persistSessionState(nextState);
      setState((current) => {
        if (current.garmentPreviewUrl) {
          URL.revokeObjectURL(current.garmentPreviewUrl);
        }
        return nextState;
      });
      setProductModalOpen(false);
      appendLog(`Product uploaded: ${nextState.garmentName}`);
    } catch (error) {
      setProductError(error.message || "Could not upload product.");
      appendLog(`Product upload failed: ${error.message || "unknown error"}`);
    } finally {
      setProductSaving(false);
    }
  }

  function simulateCapture() {
    setState((current) => ({
      ...current,
      captureUploaded: true,
      capturePassed: true,
      visualPreviewReady: false,
    }));
    appendLog("Guided scan marked ready");
  }

  async function handleCapturePhoto(file, captureSource = "file_upload") {
    if (!state.sessionId) {
      setProductError("Upload a garment and create a session before scanning the shopper.");
      setProductModalOpen(true);
      return;
    }

    setState((current) => ({
      ...current,
      captureUploaded: true,
      capturePassed: false,
      fitLoading: true,
      fitReady: false,
      fitNeedsMeasurements: false,
      fitRecommendation: null,
      fitRecommendationLabel: "",
      fitRecommendationStatus: "",
      scanBusy: true,
      previewKey: "",
      previewImageUrl: "",
      visualPreviewReady: false,
      jobId: "",
      jobStatus: "",
      tryOnError: "",
    }));
    appendLog("Uploading shopper scan");

    try {
      await uploadCapture(apiBase, state.sessionId, file, captureSource);
      const captureResponse = await analyzeCapture(apiBase, state.sessionId);
      const capturePassed = captureResponse.session?.capture_analysis?.passed !== false;
      setState((current) => ({
        ...current,
        capturePassed,
        scanBusy: false,
      }));
      appendLog(capturePassed ? "Capture analysis passed" : "Capture analysis needs review");

      if (!capturePassed) {
        setState((current) => ({
          ...current,
          fitLoading: false,
          fitNeedsMeasurements: false,
          fitReady: false,
        }));
        return;
      }

      await handleAnalyzeFit();
    } catch (error) {
      setState((current) => ({
        ...current,
        fitLoading: false,
        scanBusy: false,
      }));
      appendLog(`Scan or fit failed: ${error.message || "unknown error"}`);
    }
  }

  async function handleAnalyzeFit() {
    if (!state.sessionId) {
      setProductError("Upload a garment and create a session before running Fit Intelligence.");
      setProductModalOpen(true);
      return;
    }

    setState((current) => ({
      ...current,
      fitLoading: true,
      fitNeedsMeasurements: false,
      fitReady: false,
    }));

    try {
      const fitResponse = await analyzeFit(apiBase, state.sessionId, getBodyMeasurementsPayload(bodyMeasurements));
      const recommendation = fitResponse.size_recommendation || {};
      setState((current) => ({
        ...current,
        ...fitRecommendationState(recommendation),
        fitLoading: false,
      }));
      appendLog(
        recommendation.recommended_size
          ? `Fit recommendation: ${recommendation.recommended_size}`
          : `Fit result: ${recommendation.status || "needs input"}`,
      );
    } catch (error) {
      setState((current) => ({
        ...current,
        fitLoading: false,
      }));
      appendLog(`Fit analysis failed: ${error.message || "unknown error"}`);
    }
  }

  function handleBodyMeasurementChange(field, value) {
    setBodyMeasurements((current) => ({
      ...current,
      [field]: value,
    }));
  }

  async function handleQueueTryOn() {
    if (!state.sessionId || !state.fitReady) {
      appendLog("Try-on generation blocked until fit recommendation is ready");
      return;
    }

    setState((current) => ({
      ...current,
      jobStatus: "queued",
      previewKey: "",
      previewImageUrl: "",
      tryOnError: "",
      visualPreviewReady: false,
    }));
    appendLog("Try-on generation queued");

    try {
      const job = await enqueueVisualPreviewJob(apiBase, state.sessionId);
      setState((current) => ({
        ...current,
        jobId: job.job_id,
        jobStatus: job.status || "queued",
      }));
      pollTryOnJob(job.job_id);
    } catch (error) {
      setState((current) => ({
        ...current,
        jobStatus: "failed",
        tryOnError: error.message || "Could not queue try-on generation.",
      }));
      appendLog(`Try-on queue failed: ${error.message || "unknown error"}`);
    }
  }

  async function pollTryOnJob(jobId, attempt = 0) {
    try {
      const job = await getKioskJob(apiBase, jobId);
      const result = job.result || {};
      const previewKey = result.personalized_tryon_key || "";
      const terminal = ["succeeded", "completed", "failed"].includes(String(job.status || "").toLowerCase());
      setState((current) => ({
        ...current,
        jobId,
        jobStatus: job.status,
        previewKey: previewKey || current.previewKey,
        previewImageUrl: previewKey ? visualPreviewImageUrl(apiBase, previewKey) : current.previewImageUrl,
        visualPreviewReady: Boolean(previewKey) || current.visualPreviewReady,
        tryOnError: job.error || current.tryOnError,
      }));

      if (previewKey) {
        appendLog("Try-on preview ready");
        return;
      }
      if (terminal) {
        appendLog(job.error ? `Try-on generation failed: ${job.error}` : `Try-on job finished without preview: ${job.status}`);
        return;
      }
      if (attempt < 90) {
        window.setTimeout(() => pollTryOnJob(jobId, attempt + 1), 2000);
      }
    } catch (error) {
      setState((current) => ({
        ...current,
        jobStatus: "failed",
        tryOnError: error.message || "Could not load try-on job status.",
      }));
      appendLog(`Try-on status failed: ${error.message || "unknown error"}`);
    }
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
    handleQueueTryOn();
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
              bodyMeasurements={bodyMeasurements}
              captureLabel={captureLabel}
              garmentLabel={garmentLabel}
              onAnalyzeFit={handleAnalyzeFit}
              onBodyMeasurementChange={handleBodyMeasurementChange}
              onCapturePhoto={handleCapturePhoto}
              onOpenProduct={() => setProductModalOpen(true)}
              onQueueTryOn={handleQueueTryOn}
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

      <ProductModal
        error={productError}
        onClose={() => setProductModalOpen(false)}
        onSubmit={saveProduct}
        open={productModalOpen}
        saving={productSaving}
        sizeCharts={sizeCharts}
        sizeChartsStatus={sizeChartsStatus}
      />
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

function getBodyMeasurementsPayload(bodyMeasurements) {
  const payload = {};
  const heightCm = Number.parseFloat(bodyMeasurements.heightCm);
  const weightKg = Number.parseFloat(bodyMeasurements.weightKg);
  if (Number.isFinite(heightCm) && heightCm > 0) payload.height_cm = heightCm;
  if (Number.isFinite(weightKg) && weightKg > 0) payload.weight_kg = weightKg;
  return payload;
}

function fitRecommendationState(recommendation) {
  const recommendedSize = recommendation.recommended_size;
  const status = recommendation.status || "ready";
  return {
    fitNeedsMeasurements: status === "insufficient_measurements",
    fitReady: Boolean(recommendedSize),
    fitRecommendation: recommendation,
    fitRecommendationLabel: recommendedSize
      ? `Recommended size ${recommendedSize}`
      : recommendation.reason || "Fit recommendation needs more shopper measurements.",
    fitRecommendationStatus: status,
  };
}

function persistSessionState(nextState) {
  localStorage.setItem("kioskGarmentId", nextState.garmentId);
  localStorage.setItem("kioskGarmentName", nextState.garmentName);
  localStorage.setItem("kioskGarmentCategory", nextState.garmentCategory);
  localStorage.setItem("kioskGarmentType", nextState.garmentType || "");
  localStorage.setItem("kioskSessionId", nextState.sessionId || "");
  localStorage.setItem("kioskSizeChartId", nextState.sizeChartId || "");
  localStorage.setItem("kioskSizeChartName", nextState.sizeChartName || "");
  localStorage.setItem("kioskSizeChartSizes", nextState.sizeChartSizes || "");
}

function storedSessionValue(key) {
  const value = localStorage.getItem(key);
  if (value === "local-demo-garment") {
    clearStoredSessionState();
    return "";
  }
  return value || "";
}

function clearStoredSessionState() {
  [
    "kioskGarmentId",
    "kioskGarmentName",
    "kioskGarmentCategory",
    "kioskGarmentType",
    "kioskSessionId",
    "kioskSizeChartId",
    "kioskSizeChartName",
    "kioskSizeChartSizes",
  ].forEach((key) => localStorage.removeItem(key));
}

function formatSizeRange(sizeChart) {
  const sizes = Array.isArray(sizeChart) ? sizeChart.map((item) => item?.size).filter(Boolean) : [];
  if (!sizes.length) return "";
  return sizes.length === 1 ? sizes[0] : `${sizes[0]}-${sizes[sizes.length - 1]}`;
}

function ProductModal({ error, onClose, onSubmit, open, saving, sizeCharts, sizeChartsStatus }) {
  const [productCategory, setProductCategory] = useState("tops");
  const visibleSizeCharts = sizeCharts.filter((chart) => chart.category === productCategory);

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
          <Select
            id="category"
            label="Category"
            name="category"
            onChange={(event) => setProductCategory(event.target.value)}
            value={productCategory}
          >
            <option value="tops">Tops</option>
            <option value="bottoms">Bottoms</option>
            <option value="one_pieces">One piece</option>
            <option value="full_outfit">Full outfit</option>
          </Select>
          <Input id="garmentType" label="Garment type" name="garmentType" placeholder="t-shirt" />
        </div>
        <Select
          hint={sizeChartsStatus === "Loading" ? "Loading available charts..." : "Used by Fit Intelligence for deterministic size recommendation."}
          id="sizeChartId"
          label="Size chart"
          name="sizeChartId"
        >
          <option value="">No size chart</option>
          {visibleSizeCharts.map((chart) => (
            <option key={chart.size_chart_id} value={chart.size_chart_id}>
              {chart.name} · {chart.country_code} · {chart.category}
            </option>
          ))}
        </Select>
        <label className="grid min-h-32 cursor-pointer place-items-center rounded-2xl border border-dashed border-line bg-slate-50 p-4 text-center transition hover:bg-brand-50">
          <input accept="image/*" className="sr-only" name="garmentImage" required type="file" />
          <span className="font-semibold text-ink">Choose garment image</span>
          <span className="mt-1 text-sm text-muted">PNG or JPG, clean front product photo</span>
        </label>
        {error && <p className="rounded-lg bg-rose-50 px-3 py-2 text-sm font-medium text-rose-700">{error}</p>}
        <div className="flex justify-end gap-2">
          <Button disabled={saving} onClick={onClose} variant="secondary">
            Cancel
          </Button>
          <Button disabled={saving} type="submit">
            {saving ? "Saving..." : "Save product"}
          </Button>
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
