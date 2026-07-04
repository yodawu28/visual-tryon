const state = {
  apiBase: resolveDefaultApiBase(),
  garmentId: localStorage.getItem("kioskGarmentId") || "",
  garmentName: localStorage.getItem("kioskGarmentName") || "",
  garmentRecord: null,
  sizeChartId: localStorage.getItem("kioskSizeChartId") || "",
  sizeCharts: [],
  sessionId: localStorage.getItem("kioskSessionId") || "",
  captureSource: localStorage.getItem("kioskCaptureSource") || "",
  cameraStream: null,
  cameraFiles: {
    front: null,
    side: null,
  },
  captureMetadata: {
    front: null,
    side: null,
  },
  cameraBusy: false,
  cameraSequenceRunning: false,
  captureUploaded: localStorage.getItem("kioskCaptureUploaded") === "true",
  capturePassed: localStorage.getItem("kioskCapturePassed") === "true",
  fitReady: localStorage.getItem("kioskFitReady") === "true",
  previewKey: localStorage.getItem("kioskPreviewKey") || "",
  jobId: localStorage.getItem("kioskJobId") || "",
  jobStatus: localStorage.getItem("kioskJobStatus") || "",
  warnings: [],
};

const PREVIEW_POLL_INTERVAL_MS = 5000;
const ACTIVE_PREVIEW_JOB_STATUSES = new Set(["queued", "running"]);
let previewPollTimer = null;
let previewPollInFlight = false;

function resolveDefaultApiBase() {
  const storedApiBase = localStorage.getItem("kioskApiBase");
  if (storedApiBase) {
    return storedApiBase;
  }

  const location = window.location;
  const isLocalStaticServer =
    ["localhost", "127.0.0.1"].includes(location.hostname) &&
    ["5173", "5174"].includes(location.port);
  if (location.protocol === "file:" || isLocalStaticServer) {
    return "http://127.0.0.1:8080";
  }

  return window.location.origin || "http://127.0.0.1:8080";
}

const els = {
  apiBase: byId("apiBase"),
  checkApiButton: byId("checkApiButton"),
  resetButton: byId("resetButton"),
  apiStatus: byId("apiStatus"),
  heroSession: byId("heroSession"),
  garmentCategory: byId("garmentCategory"),
  garmentType: byId("garmentType"),
  garmentName: byId("garmentName"),
  sizeChartId: byId("sizeChartId"),
  garmentFile: byId("garmentFile"),
  garmentPreview: byId("garmentPreview"),
  garmentPlaceholder: byId("garmentPlaceholder"),
  uploadGarmentButton: byId("uploadGarmentButton"),
  createSessionButton: byId("createSessionButton"),
  garmentStatus: byId("garmentStatus"),
  frontImage: byId("frontImage"),
  sideImage: byId("sideImage"),
  frontPreview: byId("frontPreview"),
  sidePreview: byId("sidePreview"),
  frontPlaceholder: byId("frontPlaceholder"),
  sidePlaceholder: byId("sidePlaceholder"),
  cameraVideo: byId("cameraVideo"),
  cameraCanvas: byId("cameraCanvas"),
  cameraStage: byId("cameraStage"),
  cameraPlaceholder: byId("cameraPlaceholder"),
  cameraCountdown: byId("cameraCountdown"),
  cameraScanLine: byId("cameraScanLine"),
  startCameraButton: byId("startCameraButton"),
  captureSequenceButton: byId("captureSequenceButton"),
  captureFrontButton: byId("captureFrontButton"),
  captureSideButton: byId("captureSideButton"),
  stopCameraButton: byId("stopCameraButton"),
  cameraStatusText: byId("cameraStatusText"),
  uploadCapturesButton: byId("uploadCapturesButton"),
  analyzeCapturesButton: byId("analyzeCapturesButton"),
  captureStatus: byId("captureStatus"),
  heightCm: byId("heightCm"),
  weightKg: byId("weightKg"),
  preferredFit: byId("preferredFit"),
  fitAnalyzeButton: byId("fitAnalyzeButton"),
  fitStatus: byId("fitStatus"),
  fitResult: byId("fitResult"),
  previewSize: byId("previewSize"),
  useMultimodal: byId("useMultimodal"),
  queuePreviewButton: byId("queuePreviewButton"),
  pollJobButton: byId("pollJobButton"),
  previewStatus: byId("previewStatus"),
  previewFrame: byId("previewFrame"),
  previewOutput: byId("previewOutput"),
  previewPlaceholder: byId("previewPlaceholder"),
  summaryGarment: byId("summaryGarment"),
  summarySizeChart: byId("summarySizeChart"),
  summarySession: byId("summarySession"),
  summaryCaptures: byId("summaryCaptures"),
  summaryFit: byId("summaryFit"),
  summaryJob: byId("summaryJob"),
  warningBox: byId("warningBox"),
  eventLog: byId("eventLog"),
};

init();

function init() {
  els.apiBase.value = state.apiBase;
  els.garmentName.value = state.garmentName || "";

  els.checkApiButton.addEventListener("click", checkApi);
  els.resetButton.addEventListener("click", resetUiState);
  els.apiBase.addEventListener("change", () => {
    state.apiBase = trimTrailingSlash(els.apiBase.value);
    els.apiBase.value = state.apiBase;
    localStorage.setItem("kioskApiBase", state.apiBase);
    loadSizeCharts();
  });

  els.garmentCategory.addEventListener("change", () => {
    syncDefaultGarmentType();
    loadSizeCharts();
    render();
  });
  els.sizeChartId.addEventListener("change", () => {
    state.sizeChartId = els.sizeChartId.value;
    localStorage.setItem("kioskSizeChartId", state.sizeChartId);
    render();
  });
  els.garmentFile.addEventListener("change", () => previewFile(els.garmentFile, els.garmentPreview, els.garmentPlaceholder));
  els.frontImage.addEventListener("change", () => handleCaptureFileInput("front", els.frontImage, els.frontPreview, els.frontPlaceholder));
  els.sideImage.addEventListener("change", () => handleCaptureFileInput("side", els.sideImage, els.sidePreview, els.sidePlaceholder));

  els.uploadGarmentButton.addEventListener("click", uploadGarment);
  els.createSessionButton.addEventListener("click", createSession);
  els.startCameraButton.addEventListener("click", startCamera);
  els.captureSequenceButton.addEventListener("click", captureCameraSequence);
  els.captureFrontButton.addEventListener("click", () => captureCameraPhoto("front"));
  els.captureSideButton.addEventListener("click", () => captureCameraPhoto("side"));
  els.stopCameraButton.addEventListener("click", stopCamera);
  els.uploadCapturesButton.addEventListener("click", uploadCaptures);
  els.analyzeCapturesButton.addEventListener("click", () => analyzeCaptures());
  els.fitAnalyzeButton.addEventListener("click", analyzeFit);
  els.queuePreviewButton.addEventListener("click", queuePreviewJob);
  els.pollJobButton.addEventListener("click", () => pollJob({ auto: false }));

  checkApi();
  loadSizeCharts();
  render();
  restorePreviewPolling();
}

function byId(id) {
  return document.getElementById(id);
}

function apiUrl(path) {
  return `${state.apiBase}${path}`;
}

function trimTrailingSlash(value) {
  return String(value || "").replace(/\/+$/, "");
}

async function request(path, options = {}) {
  const response = await fetch(apiUrl(path), options);
  const contentType = response.headers.get("content-type") || "";
  const payload = contentType.includes("application/json")
    ? await response.json()
    : await response.text();

  if (!response.ok) {
    const detail = payload && typeof payload === "object" ? payload.detail || payload.message : payload;
    throw new Error(detail || `HTTP ${response.status}`);
  }
  return payload;
}

async function checkApi() {
  state.apiBase = trimTrailingSlash(els.apiBase.value);
  els.apiBase.value = state.apiBase;
  localStorage.setItem("kioskApiBase", state.apiBase);
  setStatus(els.apiStatus, "running", "Checking");

  try {
    const readiness = await request("/api/v1/readiness");
    const isReady = readiness.ready === true || readiness.status === "ready" || readiness.status === "ok";
    setStatus(els.apiStatus, isReady ? "ready" : "warning", readiness.status || "Reachable");
    logEvent("Readiness", readiness);
  } catch (error) {
    setStatus(els.apiStatus, "error", "Offline");
    logEvent("Readiness failed", { error: error.message });
  }
}

async function loadSizeCharts() {
  const category = els.garmentCategory.value;
  els.sizeChartId.innerHTML = `<option value="">Loading size charts...</option>`;

  try {
    const payload = await request(`/api/v1/kiosk/size-charts?category=${encodeURIComponent(category)}&limit=100`);
    state.sizeCharts = payload.size_charts || [];
    renderSizeCharts();
    logEvent("Size charts loaded", { category, count: state.sizeCharts.length });
  } catch (error) {
    state.sizeCharts = [];
    els.sizeChartId.innerHTML = `<option value="">No chart available</option>`;
    logEvent("Size chart load failed", { error: error.message });
  }
  render();
}

function renderSizeCharts() {
  const previous = state.sizeChartId;
  els.sizeChartId.innerHTML = "";

  if (state.sizeCharts.length === 0) {
    const option = new Option("No default chart for this category", "");
    els.sizeChartId.add(option);
    state.sizeChartId = "";
    localStorage.removeItem("kioskSizeChartId");
    return;
  }

  for (const chart of state.sizeCharts) {
    const label = `${chart.country_code || "GEN"} - ${chart.name || chart.size_chart_id}`;
    const option = new Option(label, chart.size_chart_id);
    els.sizeChartId.add(option);
  }

  const values = new Set(state.sizeCharts.map((chart) => chart.size_chart_id));
  state.sizeChartId = values.has(previous) ? previous : state.sizeCharts[0].size_chart_id;
  els.sizeChartId.value = state.sizeChartId;
  localStorage.setItem("kioskSizeChartId", state.sizeChartId);
}

function syncDefaultGarmentType() {
  const category = els.garmentCategory.value;
  const defaults = {
    tops: "t-shirt",
    bottoms: "shorts",
    one_pieces: "dress",
    full_outfit: "outfit",
  };
  els.garmentType.value = defaults[category] || "";
}

function previewFile(input, img, placeholder) {
  const file = input.files && input.files[0];
  if (!file) return;
  previewSelectedFile(file, img, placeholder);
  render();
}

function handleCaptureFileInput(slot, input, img, placeholder) {
  state.cameraFiles[slot] = null;
  state.captureMetadata[slot] = null;
  markCapturesDirty();
  if (input.files && input.files[0]) {
    state.captureSource = "file_upload";
    persist();
  }
  previewFile(input, img, placeholder);
}

function previewSelectedFile(file, img, placeholder) {
  if (!file) return;
  if (img.src && img.src.startsWith("blob:")) {
    URL.revokeObjectURL(img.src);
  }
  img.src = URL.createObjectURL(file);
  img.hidden = false;
  placeholder.hidden = true;
}

async function startCamera() {
  if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
    showWarning("Camera capture is not supported in this browser.");
    return;
  }

  try {
    stopCamera();
    const stream = await navigator.mediaDevices.getUserMedia({
      video: {
        facingMode: { ideal: "environment" },
        width: { ideal: 1440 },
        height: { ideal: 1920 },
      },
      audio: false,
    });
    state.cameraStream = stream;
    els.cameraVideo.srcObject = stream;
    els.cameraVideo.hidden = false;
    els.cameraPlaceholder.hidden = true;
    await els.cameraVideo.play();
    els.cameraStatusText.textContent = "Camera ready";
    logEvent("Camera started", { source: "guided_mobile_web" });
  } catch (error) {
    state.cameraStream = null;
    els.cameraStatusText.textContent = "Camera unavailable";
    showWarning(`Camera unavailable: ${error.message}`);
  }
  render();
}

function stopCamera() {
  if (state.cameraStream) {
    for (const track of state.cameraStream.getTracks()) {
      track.stop();
    }
  }
  state.cameraStream = null;
  els.cameraVideo.pause();
  els.cameraVideo.removeAttribute("srcObject");
  els.cameraVideo.srcObject = null;
  els.cameraVideo.hidden = true;
  els.cameraPlaceholder.hidden = false;
  stopCaptureScanUi();
  state.cameraBusy = false;
  state.cameraSequenceRunning = false;
  els.cameraStatusText.textContent = "Start the camera, then use Guided Capture to take front and side photos in sequence.";
  render();
}

async function captureCameraSequence() {
  if (!state.cameraStream || !els.cameraVideo.videoWidth || !els.cameraVideo.videoHeight) {
    showWarning("Start the camera before guided capture.");
    return;
  }
  if (state.cameraBusy || state.cameraSequenceRunning) return;

  state.cameraSequenceRunning = true;
  render();
  try {
    els.cameraStatusText.textContent = "Stand facing the camera for the front photo.";
    await sleep(1100);
    const frontCaptured = await captureCameraPhoto("front", { sequence: true });
    if (!frontCaptured) return;

    els.cameraStatusText.textContent = "Turn sideways. Keep arms relaxed and stay in frame.";
    await sleep(2600);
    const sideCaptured = await captureCameraPhoto("side", { sequence: true });
    if (!sideCaptured) return;

    els.cameraStatusText.textContent = "Front and side photos captured. Upload photos to run quality analysis.";
    logEvent("Guided capture sequence complete", {
      front: Boolean(state.cameraFiles.front),
      side: Boolean(state.cameraFiles.side),
    });
  } finally {
    state.cameraSequenceRunning = false;
    render();
  }
}

async function captureCameraPhoto(slot, options = {}) {
  if (!state.cameraStream || !els.cameraVideo.videoWidth || !els.cameraVideo.videoHeight) {
    showWarning("Start the camera before capturing a photo.");
    return false;
  }
  if (state.cameraBusy) return false;

  state.cameraBusy = true;
  render();
  try {
    await runCaptureCountdown(5);
    const candidates = await captureBurstFrames({ count: 5, intervalMs: 140 });
    const selected = selectBestFrame(candidates);
    if (!selected || !selected.blob) {
      showWarning("Could not capture camera frame.");
      return false;
    }

    const file = new File([selected.blob], `guided-mobile-${slot}-${Date.now()}.jpg`, {
      type: "image/jpeg",
    });
    state.cameraFiles[slot] = file;
    state.captureSource = "guided_mobile_web";
    markCapturesDirty();
    state.captureMetadata[slot] = {
      slot,
      source: state.captureSource,
      protocol_version: "guided-capture-v1",
      capture_mode: "countdown_scan_burst",
      burst_count: candidates.length,
      selected_frame_index: selected.index,
      selected_frame_score: selected.score,
      selected_frame_metrics: selected.metrics,
      video_width: selected.width,
      video_height: selected.height,
      captured_at: new Date().toISOString(),
    };
    persist();

    if (slot === "front") {
      els.frontImage.value = "";
      previewSelectedFile(file, els.frontPreview, els.frontPlaceholder);
    } else {
      els.sideImage.value = "";
      previewSelectedFile(file, els.sidePreview, els.sidePlaceholder);
    }
    if (!options.sequence) {
      els.cameraStatusText.textContent = `${slot === "front" ? "Front" : "Side"} captured from ${candidates.length} frames (score ${Math.round(selected.score * 100)}%)`;
    }
    logEvent("Guided camera burst captured", {
      slot,
      source: state.captureSource,
      size: selected.blob.size,
      selected_frame_score: selected.score,
      selected_frame_metrics: selected.metrics,
    });
    return true;
  } finally {
    stopCaptureScanUi();
    state.cameraBusy = false;
    render();
  }
}

function markCapturesDirty() {
  stopPreviewPolling();
  state.captureUploaded = false;
  state.capturePassed = false;
  state.fitReady = false;
  state.previewKey = "";
  state.jobId = "";
  state.jobStatus = "";
}

async function runCaptureCountdown(seconds) {
  els.cameraCountdown.hidden = false;
  for (let value = seconds; value >= 1; value -= 1) {
    els.cameraCountdown.textContent = String(value);
    els.cameraStatusText.textContent = `Hold still. Capturing in ${value}`;
    await sleep(650);
  }
  els.cameraCountdown.hidden = true;
  els.cameraScanLine.hidden = false;
  els.cameraStage.classList.add("is-scanning");
  els.cameraStatusText.textContent = "Scanning for the clearest frame";
}

async function captureBurstFrames({ count, intervalMs }) {
  const frames = [];
  for (let index = 0; index < count; index += 1) {
    const frame = await captureScoredFrame(index);
    if (frame) frames.push(frame);
    if (index < count - 1) await sleep(intervalMs);
  }
  return frames;
}

async function captureScoredFrame(index) {
  const canvas = els.cameraCanvas;
  canvas.width = els.cameraVideo.videoWidth;
  canvas.height = els.cameraVideo.videoHeight;
  const context = canvas.getContext("2d", { willReadFrequently: true });
  context.drawImage(els.cameraVideo, 0, 0, canvas.width, canvas.height);
  const imageData = context.getImageData(0, 0, canvas.width, canvas.height);
  const metrics = scoreFrameCandidate(imageData, canvas.width, canvas.height);
  const blob = await new Promise((resolve) => canvas.toBlob(resolve, "image/jpeg", 0.92));
  if (!blob) return null;
  return {
    index,
    blob,
    score: metrics.score,
    metrics,
    width: canvas.width,
    height: canvas.height,
  };
}

function scoreFrameCandidate(imageData, width, height) {
  const data = imageData.data;
  const stride = Math.max(4, Math.floor(Math.min(width, height) / 90));
  let count = 0;
  let lumaTotal = 0;
  let edgeTotal = 0;

  for (let y = stride; y < height; y += stride) {
    for (let x = stride; x < width; x += stride) {
      const offset = (y * width + x) * 4;
      const current = luma(data[offset], data[offset + 1], data[offset + 2]);
      const leftOffset = (y * width + x - stride) * 4;
      const upOffset = ((y - stride) * width + x) * 4;
      const left = luma(data[leftOffset], data[leftOffset + 1], data[leftOffset + 2]);
      const up = luma(data[upOffset], data[upOffset + 1], data[upOffset + 2]);
      lumaTotal += current;
      edgeTotal += Math.abs(current - left) + Math.abs(current - up);
      count += 1;
    }
  }

  const brightness = count ? lumaTotal / count : 0;
  const edgeMean = count ? edgeTotal / (count * 2) : 0;
  const brightnessScore = clamp01(1 - Math.abs(brightness - 155) / 130);
  const sharpnessScore = clamp01(edgeMean / 28);
  const resolutionScore = clamp01((width * height) / (960 * 1280));
  const score = clamp01(sharpnessScore * 0.52 + brightnessScore * 0.28 + resolutionScore * 0.2);

  return {
    score: round4(score),
    brightness: round4(brightness),
    edge_mean: round4(edgeMean),
    sharpness_score: round4(sharpnessScore),
    brightness_score: round4(brightnessScore),
    resolution_score: round4(resolutionScore),
  };
}

function selectBestFrame(frames) {
  return [...frames].sort((left, right) => right.score - left.score)[0] || null;
}

function stopCaptureScanUi() {
  els.cameraCountdown.hidden = true;
  els.cameraScanLine.hidden = true;
  els.cameraStage.classList.remove("is-scanning");
}

function luma(red, green, blue) {
  return red * 0.299 + green * 0.587 + blue * 0.114;
}

function clamp01(value) {
  return Math.min(1, Math.max(0, Number(value) || 0));
}

function round4(value) {
  return Math.round((Number(value) || 0) * 10000) / 10000;
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function uploadGarment() {
  const file = els.garmentFile.files && els.garmentFile.files[0];
  if (!file) {
    showWarning("Choose a garment image before upload.");
    return;
  }

  stopPreviewPolling();
  setStatus(els.garmentStatus, "running", "Uploading");
  const form = new FormData();
  form.append("file", file);
  form.append("category", els.garmentCategory.value);
  form.append("garment_type", els.garmentType.value.trim());
  if (els.garmentName.value.trim()) form.append("name", els.garmentName.value.trim());
  if (els.sizeChartId.value) form.append("size_chart_id", els.sizeChartId.value);

  try {
    const payload = await request("/api/v1/kiosk/garments", {
      method: "POST",
      body: form,
    });
    state.garmentRecord = payload.garment;
    state.garmentId = payload.garment.garment_id;
    state.garmentName = payload.garment.name || els.garmentName.value.trim() || payload.garment.garment_type || "Garment";
    state.sessionId = "";
    state.captureUploaded = false;
    state.capturePassed = false;
    state.fitReady = false;
    state.previewKey = "";
    state.jobId = "";
    state.jobStatus = "";
    persist();
    setStatus(els.garmentStatus, "success", "Uploaded");
    logEvent("Garment uploaded", payload);
  } catch (error) {
    setStatus(els.garmentStatus, "error", "Failed");
    logEvent("Garment upload failed", { error: error.message });
  }
  render();
}

async function createSession() {
  if (!state.garmentId) {
    showWarning("Upload a garment before creating a session.");
    return null;
  }

  stopPreviewPolling();
  try {
    const payload = await request("/api/v1/kiosk/sessions", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ garment_id: state.garmentId }),
    });
    state.sessionId = payload.session_id;
    state.captureUploaded = false;
    state.capturePassed = false;
    state.fitReady = false;
    state.previewKey = "";
    state.jobId = "";
    state.jobStatus = "";
    persist();
    logEvent("Session created", payload);
    render();
    return payload;
  } catch (error) {
    logEvent("Session creation failed", { error: error.message });
    return null;
  }
}

async function ensureSession() {
  if (state.sessionId) return true;
  const created = await createSession();
  return Boolean(created);
}

async function uploadCaptures() {
  const front = state.cameraFiles.front || (els.frontImage.files && els.frontImage.files[0]);
  if (!front) {
    showWarning("Front shopper photo is required.");
    return;
  }
  if (!(await ensureSession())) return;

  stopPreviewPolling();
  setStatus(els.captureStatus, "running", "Uploading");
  const form = new FormData();
  form.append("front_image", front);
  const side = state.cameraFiles.side || (els.sideImage.files && els.sideImage.files[0]);
  if (side) form.append("side_image", side);
  if (state.captureSource) form.append("capture_source", state.captureSource);
  const captureMetadata = buildCaptureMetadataPayload();
  if (captureMetadata) {
    form.append("capture_metadata_json", JSON.stringify(captureMetadata));
  }

  try {
    const payload = await request(`/api/v1/kiosk/sessions/${encodeURIComponent(state.sessionId)}/captures`, {
      method: "POST",
      body: form,
    });
    state.captureUploaded = true;
    state.capturePassed = false;
    state.fitReady = false;
    state.previewKey = "";
    state.jobId = "";
    state.jobStatus = "";
    persist();
    setStatus(els.captureStatus, "success", "Uploaded");
    logEvent("Captures uploaded", payload);
    render();
    await analyzeCaptures({ auto: true });
    return;
  } catch (error) {
    setStatus(els.captureStatus, "error", "Failed");
    logEvent("Capture upload failed", { error: error.message });
  }
  render();
}

function buildCaptureMetadataPayload() {
  const metadata = {};
  if (state.captureMetadata.front) metadata.front = state.captureMetadata.front;
  if (state.captureMetadata.side) metadata.side = state.captureMetadata.side;
  return Object.keys(metadata).length ? metadata : null;
}

async function analyzeCaptures(options = {}) {
  const isAutoRun = options.auto === true;
  if (!state.sessionId || !state.captureUploaded) {
    if (!isAutoRun) showWarning("Upload shopper photos before quality analysis.");
    return;
  }

  setStatus(els.captureStatus, "running", "Analyzing");
  try {
    const payload = await request(`/api/v1/kiosk/sessions/${encodeURIComponent(state.sessionId)}/captures/analyze`, {
      method: "POST",
    });
    const passed = Boolean(payload.capture_analysis && payload.capture_analysis.passed);
    state.capturePassed = passed;
    persist();
    setStatus(els.captureStatus, passed ? "success" : "warning", passed ? "Passed" : "Needs retake");
    state.warnings = collectWarnings(payload.capture_analysis);
    logEvent(isAutoRun ? "Auto capture analysis" : "Capture analysis", payload);
  } catch (error) {
    setStatus(els.captureStatus, "error", "Failed");
    logEvent(isAutoRun ? "Auto capture analysis failed" : "Capture analysis failed", { error: error.message });
  }
  render();
}

async function analyzeFit() {
  if (!state.sessionId || !state.capturePassed) {
    showWarning("Run capture quality check before requesting fit advice.");
    return;
  }

  setStatus(els.fitStatus, "running", "Analyzing");
  const body = {
    preferred_fit: els.preferredFit.value,
    body_measurements: {
      height_cm: numberOrNull(els.heightCm.value),
      weight_kg: numberOrNull(els.weightKg.value),
    },
    use_ai_analysis: false,
    size_chart: [],
  };

  try {
    const payload = await request(`/api/v1/kiosk/sessions/${encodeURIComponent(state.sessionId)}/fit/analyze`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(body),
    });
    state.fitReady = true;
    persist();
    setStatus(els.fitStatus, "success", "Ready");
    renderFitResult(payload);
    logEvent("Fit analysis", payload);
  } catch (error) {
    setStatus(els.fitStatus, "error", "Failed");
    logEvent("Fit analysis failed", { error: error.message });
  }
  render();
}

async function queuePreviewJob() {
  if (!state.sessionId || !state.capturePassed) {
    showWarning("Capture analysis must pass before visual preview.");
    return;
  }

  stopPreviewPolling();
  state.previewKey = "";
  state.jobId = "";
  state.jobStatus = "";
  resetImage(
    els.previewOutput,
    els.previewPlaceholder,
    "Queueing visual preview job.",
  );
  setPreviewLoading("Queueing visual preview job.");
  setStatus(els.previewStatus, "running", "Queueing");
  try {
    const payload = await request(`/api/v1/kiosk/sessions/${encodeURIComponent(state.sessionId)}/visual-preview/jobs`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        use_multimodal_analysis: els.useMultimodal.checked,
        size: els.previewSize.value,
        max_attempts: 1,
      }),
    });
    state.jobId = payload.job_id;
    state.jobStatus = payload.status;
    state.previewKey = "";
    persist();
    setPreviewLoading(previewLoadingMessage(state.jobStatus));
    logEvent("Visual preview job queued", payload);
    startPreviewPolling({ immediate: true });
  } catch (error) {
    stopPreviewPolling();
    els.previewFrame.classList.remove("is-loading");
    setStatus(els.previewStatus, "error", "Failed");
    logEvent("Visual preview queue failed", { error: error.message });
  }
  render();
}

async function pollJob({ auto = false } = {}) {
  if (!state.jobId) {
    if (!auto) {
      showWarning("Queue a visual preview job first.");
    }
    stopPreviewPolling();
    return;
  }
  if (previewPollInFlight) {
    return;
  }

  previewPollInFlight = true;
  const previousStatus = state.jobStatus;
  if (!auto) {
    setStatus(els.previewStatus, "running", "Checking");
  }
  try {
    const payload = await request(`/api/v1/kiosk/jobs/${encodeURIComponent(state.jobId)}`);
    state.jobStatus = payload.status;
    if (payload.status === "succeeded" && payload.result) {
      stopPreviewPolling();
      state.previewKey = payload.result.personalized_tryon_key || "";
      state.warnings = payload.result.warnings || [];
      loadPreviewImage();
      setStatus(els.previewStatus, "success", "Ready");
      els.previewFrame.classList.remove("is-loading");
    } else if (payload.status === "failed") {
      stopPreviewPolling();
      els.previewFrame.classList.remove("is-loading");
      setPreviewPlaceholder("Visual preview job failed. Check the worker log.");
      setStatus(els.previewStatus, "error", "Failed");
    } else {
      setPreviewLoading(previewLoadingMessage(payload.status));
      setStatus(els.previewStatus, "running", payload.status || "Running");
    }
    persist();
    if (!auto || payload.status !== previousStatus || isTerminalPreviewJob(payload.status)) {
      logEvent("Visual preview job", payload);
    }
    const diagnostics = buildPreviewDiagnostics(payload.result);
    if (diagnostics) {
      logEvent("Visual preview diagnostics", diagnostics);
    }
  } catch (error) {
    setStatus(els.previewStatus, auto ? "warning" : "error", auto ? "Retrying" : "Check failed");
    logEvent("Visual preview poll failed", { error: error.message });
  } finally {
    previewPollInFlight = false;
  }
  render();
}

function loadPreviewImage() {
  if (!state.previewKey) return;
  const path = `/api/v1/kiosk/visual-previews/${encodeURIComponent(state.previewKey)}/image?ts=${Date.now()}`;
  els.previewFrame.classList.remove("is-loading");
  els.previewOutput.src = apiUrl(path);
  els.previewOutput.hidden = false;
  els.previewPlaceholder.hidden = true;
}

function restorePreviewPolling() {
  if (!state.jobId || state.previewKey || state.jobStatus === "failed") {
    return;
  }
  if (!state.jobStatus || isActivePreviewJob(state.jobStatus)) {
    startPreviewPolling({ immediate: true });
  }
}

function startPreviewPolling({ immediate = false } = {}) {
  if (!state.jobId || state.previewKey) {
    return;
  }
  stopPreviewPolling();
  setPreviewLoading(previewLoadingMessage(state.jobStatus || "queued"));
  previewPollTimer = window.setInterval(() => {
    pollJob({ auto: true });
  }, PREVIEW_POLL_INTERVAL_MS);
  if (immediate) {
    pollJob({ auto: true });
  }
}

function stopPreviewPolling() {
  if (!previewPollTimer) {
    return;
  }
  window.clearInterval(previewPollTimer);
  previewPollTimer = null;
}

function setPreviewLoading(message) {
  els.previewFrame.classList.add("is-loading");
  els.previewOutput.hidden = true;
  setPreviewPlaceholder(message);
}

function setPreviewPlaceholder(message) {
  els.previewPlaceholder.textContent = message;
  els.previewPlaceholder.hidden = false;
}

function previewLoadingMessage(status) {
  const label = status ? String(status).replaceAll("_", " ") : "queued";
  return `Generating visual preview. Job status: ${label}.`;
}

function isActivePreviewJob(status) {
  return ACTIVE_PREVIEW_JOB_STATUSES.has(String(status || "").toLowerCase());
}

function isTerminalPreviewJob(status) {
  return ["succeeded", "failed"].includes(String(status || "").toLowerCase());
}

function renderFitResult(payload) {
  const recommendation = payload.size_recommendation || {};
  const assessment = payload.fit_assessment || {};
  const report = payload.fit_report || {};
  const landmarkSignals = report.landmark_fit_signals || assessment.landmark_fit_signals || {};
  const confidenceBreakdown = payload.confidence_breakdown || report.confidence_breakdown || {};
  const size = recommendation.recommended_size || recommendation.size || "N/A";
  const sizeMatchConfidence = confidenceBreakdown.size_match_confidence ?? recommendation.confidence;
  const overallConfidence = confidenceBreakdown.overall_confidence ?? payload.confidence_score;
  const sizeMatchLabel = sizeMatchConfidence != null ? `${Math.round(sizeMatchConfidence * 100)}%` : "N/A";
  const overallLabel = overallConfidence != null ? `${Math.round(overallConfidence * 100)}%` : "N/A";
  const rationale = recommendation.reason || recommendation.rationale || report.summary || payload.message || "Recommendation generated.";
  const confidenceNote = "Size match is based on the garment size chart. Data confidence reflects measurement quality and stays conservative until detailed measurements or calibrated captures are available.";
  const landmarkHints = Array.isArray(landmarkSignals.body_shape_hints) ? landmarkSignals.body_shape_hints : [];
  const landmarkGuidance = Array.isArray(landmarkSignals.guidance) ? landmarkSignals.guidance : [];
  const landmarkBlock = landmarkSignals.status === "available"
    ? `
      <div class="insight-block">
        <strong>Pose fit signals</strong>
        ${renderInlineList([...landmarkHints, ...landmarkGuidance].slice(0, 4))}
      </div>
    `
    : "";

  els.fitResult.classList.remove("empty");
  els.fitResult.innerHTML = `
    <div class="result-grid">
      <div class="metric">
        <span>Recommended size</span>
        <strong>${escapeHtml(size)}</strong>
      </div>
      <div class="metric">
        <span>Size match</span>
        <strong>${escapeHtml(sizeMatchLabel)}</strong>
      </div>
    </div>
    <p class="helper-text">${escapeHtml(rationale)}</p>
    <p class="helper-text">Data confidence: ${escapeHtml(overallLabel)}. Measurement basis: ${escapeHtml(confidenceBreakdown.measurement_confidence_label || "unknown")}.</p>
    <p class="helper-text">${escapeHtml(confidenceNote)}</p>
    <p class="helper-text">${escapeHtml(assessment.summary || "")}</p>
    ${landmarkBlock}
  `;
}

function render() {
  const hasGarmentFile = Boolean(els.garmentFile.files && els.garmentFile.files[0]);
  const hasFrontFile = Boolean(state.cameraFiles.front || (els.frontImage.files && els.frontImage.files[0]));
  const hasGarment = Boolean(state.garmentId);
  const hasSession = Boolean(state.sessionId);
  const hasJob = Boolean(state.jobId);
  const previewJobActive = hasJob && !state.previewKey && isActivePreviewJob(state.jobStatus);
  const cameraRunning = Boolean(state.cameraStream);
  const cameraBusy = Boolean(state.cameraBusy || state.cameraSequenceRunning);

  els.uploadGarmentButton.disabled = !hasGarmentFile;
  els.createSessionButton.disabled = !hasGarment;
  els.uploadCapturesButton.disabled = !hasGarment || !hasFrontFile;
  els.analyzeCapturesButton.disabled = !hasSession || !state.captureUploaded;
  els.fitAnalyzeButton.disabled = !hasSession || !state.capturePassed;
  els.queuePreviewButton.disabled = !hasSession || !state.capturePassed || previewJobActive;
  els.pollJobButton.disabled = !hasJob || previewPollInFlight;
  els.queuePreviewButton.textContent = previewJobActive ? "Generating Preview" : "Queue Preview Job";
  els.pollJobButton.textContent = previewJobActive ? "Polling Job" : "Refresh Job";
  els.startCameraButton.disabled = cameraRunning || cameraBusy;
  els.captureSequenceButton.disabled = !cameraRunning || cameraBusy;
  els.captureFrontButton.disabled = !cameraRunning || cameraBusy;
  els.captureSideButton.disabled = !cameraRunning || cameraBusy;
  els.stopCameraButton.disabled = !cameraRunning || cameraBusy;

  if (hasGarment && els.garmentStatus.textContent === "Waiting") {
    setStatus(els.garmentStatus, "success", "Uploaded");
  }
  if (state.capturePassed) setStatus(els.captureStatus, "success", "Passed");
  else if (state.captureUploaded) setStatus(els.captureStatus, "success", "Uploaded");
  if (state.fitReady) setStatus(els.fitStatus, "success", "Ready");
  if (state.previewKey) {
    setStatus(els.previewStatus, "success", "Ready");
    loadPreviewImage();
  } else if (previewJobActive) {
    setPreviewLoading(previewLoadingMessage(state.jobStatus));
    setStatus(els.previewStatus, "running", state.jobStatus || "Running");
  } else if (state.jobStatus) {
    els.previewFrame.classList.remove("is-loading");
    setStatus(els.previewStatus, state.jobStatus === "failed" ? "error" : "running", state.jobStatus);
  }

  els.heroSession.textContent = hasSession ? shortId(state.sessionId) : "None";
  els.summaryGarment.textContent = hasGarment ? `${state.garmentName || "Garment"} (${shortId(state.garmentId)})` : "Not uploaded";
  els.summarySizeChart.textContent = selectedSizeChartLabel();
  els.summarySession.textContent = hasSession ? shortId(state.sessionId) : "Not started";
  const captureSourceLabel = state.captureSource ? ` (${state.captureSource.replaceAll("_", " ")})` : "";
  els.summaryCaptures.textContent = state.capturePassed
    ? `Quality passed${captureSourceLabel}`
    : state.captureUploaded
      ? `Uploaded, not checked${captureSourceLabel}`
      : "Not uploaded";
  els.summaryFit.textContent = state.fitReady ? "Recommendation ready" : "Not analyzed";
  els.summaryJob.textContent = hasJob ? `${shortId(state.jobId)} - ${state.jobStatus || "queued"}` : "Not queued";

  updateWorkflow();
  renderWarnings();
}

function updateWorkflow() {
  const steps = {
    garment: Boolean(state.garmentId),
    captures: Boolean(state.capturePassed),
    fit: Boolean(state.fitReady),
    preview: Boolean(state.previewKey),
  };
  for (const node of document.querySelectorAll("[data-step-indicator]")) {
    const key = node.getAttribute("data-step-indicator");
    node.classList.toggle("done", Boolean(steps[key]));
    node.classList.remove("active");
  }

  const active = !steps.garment
    ? "garment"
    : !steps.captures
      ? "captures"
      : !steps.fit
        ? "fit"
        : "preview";
  const activeNode = document.querySelector(`[data-step-indicator="${active}"]`);
  if (activeNode) activeNode.classList.add("active");
}

function renderWarnings() {
  if (!state.warnings || state.warnings.length === 0) {
    els.warningBox.hidden = true;
    els.warningBox.textContent = "";
    return;
  }
  els.warningBox.hidden = false;
  els.warningBox.innerHTML = state.warnings.map((warning) => `<div>${escapeHtml(String(warning))}</div>`).join("");
}

function buildPreviewDiagnostics(result) {
  if (!result) return null;
  const artifacts = result.diagnostic_artifacts || {};
  const qualityGate = result.output_quality_gate || null;
  const generation = result.generation_metadata || {};
  const diagnostics = {
    output_quality_status: qualityGate && qualityGate.status
      ? qualityGate.status
      : null,
    output_quality_issues: qualityGate && Array.isArray(qualityGate.issues)
      ? qualityGate.issues
      : [],
    work_dir: artifacts.work_dir || generation.work_dir || null,
    conditioned_person:
      artifacts.conditioned_person || generation.conditioned_person || null,
    conditioned_garment:
      artifacts.conditioned_garment || generation.conditioned_garment || null,
    leffa_report: artifacts.leffa_report || generation.leffa_report || null,
    input_quality_report:
      artifacts.input_quality_report || generation.input_quality_report || null,
    conditioning_report:
      artifacts.conditioning_report || generation.conditioning_report || null,
  };
  return Object.values(diagnostics).some((value) =>
    Array.isArray(value) ? value.length > 0 : Boolean(value)
  )
    ? diagnostics
    : null;
}

function renderInlineList(items) {
  const cleanItems = items.map((item) => String(item || "").trim()).filter(Boolean);
  if (cleanItems.length === 0) {
    return `<p class="helper-text">No pose-specific guidance.</p>`;
  }
  return `<ul class="inline-list">${cleanItems.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>`;
}

function collectWarnings(analysis) {
  if (!analysis) return [];
  const guidance = Array.isArray(analysis.guidance) ? analysis.guidance : [];
  const issues = Array.isArray(analysis.issues) ? analysis.issues.map((issue) => `Issue: ${issue}`) : [];
  return [...issues, ...guidance];
}

function setStatus(el, type, text) {
  el.className = `status-pill ${type}`;
  el.textContent = text;
}

function selectedSizeChartLabel() {
  const chart = state.sizeCharts.find((item) => item.size_chart_id === state.sizeChartId);
  if (!chart) return state.sizeChartId ? shortId(state.sizeChartId) : "Not selected";
  return `${chart.country_code || "GEN"} - ${chart.name || shortId(chart.size_chart_id)}`;
}

function numberOrNull(value) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function shortId(value) {
  if (!value) return "";
  const text = String(value);
  if (text.length <= 18) return text;
  const parts = text.split(":");
  const suffix = parts[parts.length - 1];
  return `${parts.slice(0, -1).join(":")}:...${suffix.slice(-8)}`;
}

function showWarning(message) {
  state.warnings = [message];
  renderWarnings();
  logEvent("User action blocked", { message });
}

function logEvent(title, payload) {
  const timestamp = new Date().toLocaleTimeString();
  const line = `[${timestamp}] ${title}\n${JSON.stringify(payload, null, 2)}`;
  els.eventLog.textContent = `${line}\n\n${els.eventLog.textContent}`.slice(0, 12000);
}

function persist() {
  setOrRemove("kioskGarmentId", state.garmentId);
  setOrRemove("kioskGarmentName", state.garmentName);
  setOrRemove("kioskSizeChartId", state.sizeChartId);
  setOrRemove("kioskSessionId", state.sessionId);
  setOrRemove("kioskCaptureSource", state.captureSource);
  setOrRemove("kioskJobId", state.jobId);
  setOrRemove("kioskJobStatus", state.jobStatus);
  setOrRemove("kioskPreviewKey", state.previewKey);
  localStorage.setItem("kioskCaptureUploaded", String(state.captureUploaded));
  localStorage.setItem("kioskCapturePassed", String(state.capturePassed));
  localStorage.setItem("kioskFitReady", String(state.fitReady));
}

function setOrRemove(key, value) {
  if (value) localStorage.setItem(key, value);
  else localStorage.removeItem(key);
}

function resetUiState() {
  stopPreviewPolling();
  for (const key of [
    "kioskGarmentId",
    "kioskGarmentName",
    "kioskSizeChartId",
    "kioskSessionId",
    "kioskCaptureSource",
    "kioskCaptureUploaded",
    "kioskCapturePassed",
    "kioskFitReady",
    "kioskJobId",
    "kioskJobStatus",
    "kioskPreviewKey",
  ]) {
    localStorage.removeItem(key);
  }
  Object.assign(state, {
    garmentId: "",
    garmentName: "",
    garmentRecord: null,
    sessionId: "",
    captureSource: "",
    cameraFiles: {
      front: null,
      side: null,
    },
    captureMetadata: {
      front: null,
      side: null,
    },
    cameraBusy: false,
    cameraSequenceRunning: false,
    captureUploaded: false,
    capturePassed: false,
    fitReady: false,
    previewKey: "",
    jobId: "",
    jobStatus: "",
    warnings: [],
  });
  els.garmentFile.value = "";
  els.frontImage.value = "";
  els.sideImage.value = "";
  stopCamera();
  resetImage(els.garmentPreview, els.garmentPlaceholder, "No garment selected");
  resetImage(els.frontPreview, els.frontPlaceholder, "No front photo");
  resetImage(els.sidePreview, els.sidePlaceholder, "No side photo");
  resetImage(els.previewOutput, els.previewPlaceholder, "Visual preview will appear here after the worker completes.");
  els.fitResult.className = "result-box empty";
  els.fitResult.innerHTML = "<strong>No fit result yet</strong><span>Fit advice can run without generating visual preview.</span>";
  setStatus(els.garmentStatus, "neutral", "Waiting");
  setStatus(els.captureStatus, "neutral", "Waiting");
  setStatus(els.fitStatus, "neutral", "Waiting");
  setStatus(els.previewStatus, "neutral", "Optional");
  logEvent("UI state reset", { reset: true });
  render();
}

function resetImage(img, placeholder, text) {
  img.removeAttribute("src");
  img.hidden = true;
  placeholder.textContent = text;
  placeholder.hidden = false;
}

function escapeHtml(value) {
  return String(value || "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}
