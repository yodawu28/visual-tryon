import { useEffect, useRef, useState } from "react";

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
  listGarments,
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
  const fitRequestRef = useRef(0);
  const tryOnRequestRef = useRef(0);
  const selectionRequestRef = useRef(0);
  const [apiBase, setApiBase] = useState(resolveDefaultApiBase());
  const [apiStatus, setApiStatus] = useState("Checking");
  const [eventLog, setEventLog] = useState(["App loaded"]);
  const [diagnosticsDrawer, setDiagnosticsDrawer] = useState(false);
  const [productModalOpen, setProductModalOpen] = useState(false);
  const [productError, setProductError] = useState("");
  const [productSaving, setProductSaving] = useState(false);
  const [workflowView, setWorkflowView] = useState("scan");
  const [sizeCharts, setSizeCharts] = useState([]);
  const [sizeChartsStatus, setSizeChartsStatus] = useState("Idle");
  const [preparedGarments, setPreparedGarments] = useState([]);
  const [preparedGarmentsStatus, setPreparedGarmentsStatus] = useState("Idle");
  const [pendingCaptureFile, setPendingCaptureFile] = useState(null);
  const [pendingCaptureSource, setPendingCaptureSource] = useState("kiosk_webcam");
  const [profileEditorOpen, setProfileEditorOpen] = useState(false);
  const [operatorSensorOpen, setOperatorSensorOpen] = useState(false);
  const [mockSensorProfile, setMockSensorProfile] = useState(() => ({
    heightCm: localStorage.getItem("kioskMockHeightCm") || "170",
    weightKg: localStorage.getItem("kioskMockWeightKg") || "68",
    sensorStatus: "ready",
  }));
  const [confirmedProfile, setConfirmedProfile] = useState(() => ({
    heightCm: "",
    weightKg: "",
    fitIntent: normalizeFitIntent(localStorage.getItem("kioskFitIntent") || "regular"),
    profileSource: "unknown",
    profileConfirmed: false,
    sensorStatus: "ready",
  }));
  const [bodyMeasurements, setBodyMeasurements] = useState({
    heightCm: "",
    weightKg: "",
  });
  const [fitIntent, setFitIntent] = useState(() => normalizeFitIntent(localStorage.getItem("kioskFitIntent") || "regular"));
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
  const activeStage = getAvailableWorkflowView(workflowView, state, confirmedProfile);

  useEffect(() => {
    localStorage.setItem("kioskApiBase", apiBase);
  }, [apiBase]);

  useEffect(() => {
    localStorage.setItem("kioskFitIntent", fitIntent);
  }, [fitIntent]);

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
    let cancelled = false;
    setPreparedGarmentsStatus("Loading");
    listGarments(apiBase, { limit: 100 })
      .then((payload) => {
        if (cancelled) return;
        const garments = Array.isArray(payload.garments) ? payload.garments : [];
        setPreparedGarments(garments);
        setPreparedGarmentsStatus(garments.length ? "Ready" : "Empty");
      })
      .catch((error) => {
        if (cancelled) return;
        setPreparedGarments([]);
        setPreparedGarmentsStatus("Unavailable");
        appendLog(`Prepared garments unavailable: ${error.message || "unknown error"}`);
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

  useEffect(() => {
    function handleKeyDown(event) {
      if (event.shiftKey && event.key.toLowerCase() === "s") {
        event.preventDefault();
        setOperatorSensorOpen((open) => !open);
      }
    }

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, []);

  useEffect(() => {
    const nextWorkflowView = getAvailableWorkflowView(workflowView, state, confirmedProfile);
    if (nextWorkflowView !== workflowView) {
      setWorkflowView(nextWorkflowView);
    }
  }, [confirmedProfile.profileConfirmed, state.fitReady, state.fitRecommendation, workflowView]);

  const applicationShell = "product-application-shell min-h-screen overflow-x-hidden bg-canvas text-ink";
  const bottomNavigation = "fixed inset-x-0 bottom-0 z-40 border-t border-line bg-white/95 px-2 py-2 backdrop-blur lg:hidden";

  function appendLog(message) {
    setEventLog((current) => [`${new Date().toLocaleTimeString()} ${message}`, ...current].slice(0, 10));
  }

  function resetSession() {
    fitRequestRef.current += 1;
    tryOnRequestRef.current += 1;
    selectionRequestRef.current += 1;
    clearStoredSessionState();
    if (state.garmentPreviewUrl) {
      URL.revokeObjectURL(state.garmentPreviewUrl);
    }
    setState(initialSessionState);
    setWorkflowView("scan");
    setPendingCaptureFile(null);
    setPendingCaptureSource("kiosk_webcam");
    setProfileEditorOpen(false);
    setConfirmedProfile({
      heightCm: "",
      weightKg: "",
      fitIntent: "regular",
      profileSource: "unknown",
      profileConfirmed: false,
      sensorStatus: "ready",
    });
    setBodyMeasurements({ heightCm: "", weightKg: "" });
    setFitIntent("regular");
    appendLog("New fitting session prepared");
  }

  async function saveProduct(event) {
    event.preventDefault();
    setProductError("");
    setProductSaving(true);
    const form = new FormData(event.currentTarget);
    const garmentImage = form.get("garmentImage");
    const garmentName = String(form.get("garmentName") || "Prepared garment").trim();
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
      const preparedGarment = {
        ...garment,
        size_chart_name: selectedSizeChart?.name || "",
        size_chart_sizes: formatSizeRange(selectedSizeChart?.size_chart || garment.size_chart || []),
      };
      setPreparedGarments((current) => [
        preparedGarment,
        ...current.filter((item) => item.garment_id !== garment.garment_id),
      ]);
      setPreparedGarmentsStatus("Ready");
      setProductModalOpen(false);
      appendLog(`Product prepared: ${garment.name || garmentName}`);
    } catch (error) {
      setProductError(error.message || "Could not upload product.");
      appendLog(`Product upload failed: ${error.message || "unknown error"}`);
    } finally {
      setProductSaving(false);
    }
  }

  function detectProfileFromSensor(source = "mock_sensor") {
    const heightCm = String(mockSensorProfile.heightCm || "").trim();
    const weightKg = String(mockSensorProfile.weightKg || "").trim();
    const nextProfile = {
      heightCm,
      weightKg,
      fitIntent,
      profileSource: source,
      profileConfirmed: Boolean(heightCm && weightKg),
      sensorStatus: heightCm && weightKg ? "detected" : "unavailable",
    };
    setConfirmedProfile(nextProfile);
    setBodyMeasurements({ heightCm, weightKg });
    return nextProfile;
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
    if (!file) {
      return;
    }

    fitRequestRef.current += 1;
    tryOnRequestRef.current += 1;
    selectionRequestRef.current += 1;
    clearStoredSessionState();
    setPendingCaptureFile(file);
    setPendingCaptureSource(captureSource);
    detectProfileFromSensor("mock_sensor");
    setState({
      ...initialSessionState,
      captureUploaded: true,
      capturePassed: true,
      scanBusy: false,
      fitLoading: false,
      fitNeedsMeasurements: false,
      fitReady: false,
      fitRecommendation: null,
      fitRecommendationLabel: "",
      fitRecommendationStatus: "",
      previewKey: "",
      previewImageUrl: "",
      visualPreviewReady: false,
      jobId: "",
      jobStatus: "",
      tryOnError: "",
    });
    setWorkflowView("scan");
    appendLog("Shopper profile detected");
  }

  async function runBackendCaptureAndFit(
    sessionId,
    captureFile = pendingCaptureFile,
    selectionRequestId = selectionRequestRef.current,
    captureSource = pendingCaptureSource,
  ) {
    if (!sessionId || !captureFile) {
      return false;
    }

    setState((current) => ({
      ...current,
      scanBusy: true,
      fitLoading: true,
      fitReady: false,
      fitNeedsMeasurements: false,
    }));

    await uploadCapture(apiBase, sessionId, captureFile, captureSource || "file_upload");
    if (selectionRequestRef.current !== selectionRequestId) {
      return false;
    }
    const captureResponse = await analyzeCapture(apiBase, sessionId);
    if (selectionRequestRef.current !== selectionRequestId) {
      return false;
    }
    const capturePassed = captureResponse.session?.capture_analysis?.passed !== false;
    setState((current) => ({
      ...current,
      capturePassed,
      scanBusy: false,
    }));

    if (!capturePassed) {
      setState((current) => ({
        ...current,
        fitLoading: false,
        fitNeedsMeasurements: false,
        fitReady: false,
      }));
      appendLog("Capture analysis needs review");
      return false;
    }

    return handleAnalyzeFit(sessionId);
  }

  async function handleAnalyzeFit(sessionIdOverride = state.sessionId) {
    if (!sessionIdOverride) {
      appendLog("Choose a prepared garment before running Fit Intelligence.");
      setWorkflowView("garments");
      return;
    }

    const fitRequestId = fitRequestRef.current + 1;
    fitRequestRef.current = fitRequestId;
    setState((current) => ({
      ...current,
      fitLoading: true,
      fitNeedsMeasurements: false,
      fitReady: false,
    }));

    try {
      const fitResponse = await analyzeFit(
        apiBase,
        sessionIdOverride,
        getBodyMeasurementsPayload(confirmedProfile),
        confirmedProfile.fitIntent || fitIntent,
      );
      if (fitRequestRef.current !== fitRequestId) {
        return false;
      }
      const recommendation = fitResponse.size_recommendation || {};
      setState((current) => ({
        ...(current.sessionId === sessionIdOverride ? {
          ...current,
          ...fitRecommendationState(recommendation),
          fitLoading: false,
        } : current),
      }));
      appendLog(
        recommendation.recommended_size
          ? `Fit recommendation: ${recommendation.recommended_size}`
          : `Fit result: ${recommendation.status || "needs input"}`,
      );
      return true;
    } catch (error) {
      if (fitRequestRef.current !== fitRequestId) {
        return false;
      }
      setState((current) => ({
        ...(current.sessionId === sessionIdOverride
          ? { ...current, fitLoading: false }
          : current),
      }));
      appendLog(`Fit analysis failed: ${error.message || "unknown error"}`);
      return false;
    }
  }

  function handleBodyMeasurementChange(field, value) {
    handleConfirmedProfileChange(field, value);
  }

  function handleConfirmedProfileChange(field, value) {
    tryOnRequestRef.current += 1;
    setBodyMeasurements((current) => ({
      ...current,
      [field]: value,
    }));
    setConfirmedProfile((current) => {
      const nextProfile = {
        ...current,
        [field]: value,
        profileSource: "manual_override",
      };
      return {
        ...nextProfile,
        profileConfirmed: Boolean(nextProfile.heightCm && nextProfile.weightKg),
      };
    });
    setState((current) => ({
      ...current,
      fitRecommendation: null,
      fitRecommendationLabel: current.capturePassed ? "Update recommendation for edited profile." : "",
      fitRecommendationStatus: current.capturePassed ? "needs_update" : "",
      fitNeedsMeasurements: Boolean(current.capturePassed),
      fitReady: false,
      previewKey: "",
      previewImageUrl: "",
      visualPreviewReady: false,
      jobId: "",
      jobStatus: "",
      tryOnError: "",
    }));
  }

  function handleFitIntentChange(value) {
    const nextFitIntent = normalizeFitIntent(value);
    tryOnRequestRef.current += 1;
    setFitIntent(nextFitIntent);
    setConfirmedProfile((current) => ({
      ...current,
      fitIntent: nextFitIntent,
      profileSource: current.profileSource === "unknown" ? "manual_override" : current.profileSource,
    }));
    setState((current) => {
      if (!current.fitRecommendation && !current.fitReady && !current.previewKey && !current.jobId) {
        return current;
      }

      return {
        ...current,
        fitRecommendation: null,
        fitRecommendationLabel: current.capturePassed ? "Update recommendation for selected fit intent." : "",
        fitRecommendationStatus: current.capturePassed ? "needs_update" : "",
        fitNeedsMeasurements: Boolean(current.capturePassed),
        fitReady: false,
        previewKey: "",
        previewImageUrl: "",
        visualPreviewReady: false,
        jobId: "",
        jobStatus: "",
        tryOnError: "",
      };
    });
    appendLog(`Fit intent selected: ${nextFitIntent}`);
  }

  function handleMockSensorProfileChange(field, value) {
    setMockSensorProfile((current) => {
      const next = {
        ...current,
        [field]: value,
        sensorStatus: "ready",
      };
      if (field === "heightCm") localStorage.setItem("kioskMockHeightCm", value);
      if (field === "weightKg") localStorage.setItem("kioskMockWeightKg", value);
      return next;
    });
  }

  async function handleSelectPreparedGarment(garment) {
    if (!garment?.garment_id) return;
    if (!confirmedProfile.profileConfirmed) {
      setProfileEditorOpen(true);
      appendLog("Confirm shopper profile before choosing garments");
      return;
    }
    if (!pendingCaptureFile) {
      setWorkflowView("scan");
      appendLog("Scan shopper before choosing garments");
      return;
    }

    const selectionRequestId = selectionRequestRef.current + 1;
    selectionRequestRef.current = selectionRequestId;
    fitRequestRef.current += 1;
    tryOnRequestRef.current += 1;
    const selectedGarmentState = {
      garmentId: garment.garment_id,
      garmentName: garment.name || "Prepared garment",
      garmentPreviewUrl: "",
      garmentCategory: garment.category || "tops",
      garmentType: garment.garment_type || "",
      sizeChartId: garment.size_chart_id || "",
      sizeChartName: garment.size_chart_name || "",
      sizeChartSizes: garment.size_chart_sizes || formatSizeRange(garment.size_chart || []),
    };

    setState((current) => ({
      ...current,
      ...selectedGarmentState,
      fitRecommendation: null,
      fitRecommendationLabel: "",
      fitRecommendationStatus: "",
      fitNeedsMeasurements: false,
      fitReady: false,
      previewKey: "",
      previewImageUrl: "",
      visualPreviewReady: false,
      jobId: "",
      jobStatus: "",
      tryOnError: "",
    }));

    try {
      const sessionResponse = await createSession(apiBase, garment.garment_id);
      if (selectionRequestRef.current !== selectionRequestId) {
        return;
      }
      const sessionId = sessionResponse.session_id || sessionResponse.session?.session_id || "";
      if (!sessionId) {
        throw new Error("Could not create fitting session.");
      }
      setState((current) => ({ ...current, sessionId }));
      persistSessionState({ ...initialSessionState, ...selectedGarmentState, sessionId });
      const backendReady = await runBackendCaptureAndFit(
        sessionId,
        pendingCaptureFile,
        selectionRequestId,
        pendingCaptureSource,
      );
      if (selectionRequestRef.current !== selectionRequestId) {
        return;
      }
      if (!backendReady) return;
      setWorkflowView("review");
      appendLog(`Garment selected: ${garment.name || garment.garment_id}`);
    } catch (error) {
      if (selectionRequestRef.current !== selectionRequestId) {
        return;
      }
      setState((current) => ({ ...current, fitLoading: false, scanBusy: false }));
      appendLog(`Garment selection failed: ${error.message || "unknown error"}`);
    }
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
    const tryOnRequestId = tryOnRequestRef.current + 1;
    tryOnRequestRef.current = tryOnRequestId;
    const sessionId = state.sessionId;

    try {
      const job = await enqueueVisualPreviewJob(apiBase, sessionId);
      if (tryOnRequestRef.current !== tryOnRequestId) {
        return;
      }
      setState((current) => ({
        ...current,
        jobId: job.job_id,
        jobStatus: job.status || "queued",
      }));
      pollTryOnJob(job.job_id, sessionId, tryOnRequestId);
    } catch (error) {
      if (tryOnRequestRef.current !== tryOnRequestId) {
        return;
      }
      setState((current) => ({
        ...current,
        jobStatus: "failed",
        tryOnError: error.message || "Could not queue try-on generation.",
      }));
      appendLog(`Try-on queue failed: ${error.message || "unknown error"}`);
    }
  }

  async function pollTryOnJob(jobId, sessionId, tryOnRequestId, attempt = 0) {
    if (tryOnRequestRef.current !== tryOnRequestId) {
      return;
    }
    try {
      const job = await getKioskJob(apiBase, jobId);
      if (tryOnRequestRef.current !== tryOnRequestId) {
        return;
      }
      const result = job.result || {};
      const previewKey = result.personalized_tryon_key || "";
      const terminal = ["succeeded", "completed", "failed"].includes(String(job.status || "").toLowerCase());
      setState((current) => ({
        ...(current.sessionId === sessionId ? {
          ...current,
          jobId,
          jobStatus: job.status,
          previewKey: previewKey || current.previewKey,
          previewImageUrl: previewKey ? visualPreviewImageUrl(apiBase, previewKey) : current.previewImageUrl,
          visualPreviewReady: Boolean(previewKey) || current.visualPreviewReady,
          tryOnError: job.error || current.tryOnError,
        } : current),
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
        window.setTimeout(() => pollTryOnJob(jobId, sessionId, tryOnRequestId, attempt + 1), 2000);
      }
    } catch (error) {
      if (tryOnRequestRef.current !== tryOnRequestId) {
        return;
      }
      setState((current) => ({
        ...(current.sessionId === sessionId ? {
          ...current,
          jobStatus: "failed",
          tryOnError: error.message || "Could not load try-on job status.",
        } : current),
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
      setWorkflowView("scan");
      return;
    }
    setWorkflowView("review");
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
              confirmedProfile={confirmedProfile}
              fitIntent={fitIntent}
              garmentLabel={garmentLabel}
              mockSensorProfile={mockSensorProfile}
              onAnalyzeFit={handleAnalyzeFit}
              onBodyMeasurementChange={handleBodyMeasurementChange}
              onCapturePhoto={handleCapturePhoto}
              onConfirmedProfileChange={handleConfirmedProfileChange}
              onFitIntentChange={handleFitIntentChange}
              onContinueToReview={() => setWorkflowView("garments")}
              onContinueToScan={() => setWorkflowView("scan")}
              onDetectProfileFromSensor={detectProfileFromSensor}
              onMockSensorProfileChange={handleMockSensorProfileChange}
              onOpenProduct={() => setProductModalOpen(true)}
              onQueueTryOn={handleQueueTryOn}
              onSelectPreparedGarment={handleSelectPreparedGarment}
              onToggleOperatorSensor={() => setOperatorSensorOpen((open) => !open)}
              onWorkflowViewChange={(view) => setWorkflowView(getAvailableWorkflowView(view, state, confirmedProfile))}
              operatorSensorOpen={operatorSensorOpen}
              pendingCaptureFile={pendingCaptureFile}
              preparedGarments={preparedGarments}
              preparedGarmentsStatus={preparedGarmentsStatus}
              profileEditorOpen={profileEditorOpen}
              state={state}
              tryOnLabel={tryOnLabel}
              workflowView={activeStage}
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

function getAvailableWorkflowView(view, state, confirmedProfile = {}) {
  if (view === "review" && !state.fitReady && !state.fitRecommendation) {
    return state.capturePassed && confirmedProfile.profileConfirmed ? "garments" : "scan";
  }
  if (view === "garment") return "garments";
  if (view === "garments" && (!state.capturePassed || !confirmedProfile.profileConfirmed)) return "scan";
  if (view === "scan" || view === "garments" || view === "review") return view;
  return "scan";
}

function getBodyMeasurementsPayload(bodyMeasurements) {
  const payload = {};
  const heightCm = Number.parseFloat(bodyMeasurements.heightCm);
  const weightKg = Number.parseFloat(bodyMeasurements.weightKg);
  if (Number.isFinite(heightCm) && heightCm > 0) payload.height_cm = heightCm;
  if (Number.isFinite(weightKg) && weightKg > 0) payload.weight_kg = weightKg;
  return payload;
}

function normalizeFitIntent(value) {
  return ["slim", "regular", "relaxed"].includes(value) ? value : "regular";
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
    "kioskFitIntent",
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
      description="Use realistic product details so recommendations and try-on output match the prepared catalog."
      onClose={onClose}
      open={open}
      title="Select product"
    >
      <form className="grid gap-4" onSubmit={onSubmit}>
        <Input id="garmentName" label="Display name" name="garmentName" placeholder="Prepared product" />
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
