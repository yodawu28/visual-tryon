export function resolveDefaultApiBase() {
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

export function trimTrailingSlash(value) {
  return String(value || "").replace(/\/+$/, "");
}

export class ApiRequestError extends Error {
  constructor(message, status) {
    super(message);
    this.name = "ApiRequestError";
    this.status = status;
  }
}

const SIZE_CHARTS_PATH = "/api/v1/kiosk/size-charts";
const GARMENTS_PATH = "/api/v1/kiosk/garments";
const SESSIONS_PATH = "/api/v1/kiosk/sessions";
const CAPTURES_PATH = "captures";
const CAPTURE_ANALYZE_PATH = "captures/analyze";
const FIT_ANALYZE_PATH = "fit/analyze";
const VISUAL_PREVIEW_JOBS_PATH = "visual-preview/jobs";
const JOBS_PATH = "/api/v1/kiosk/jobs";

export async function request(apiBase, path, options = {}) {
  const response = await fetch(`${apiBase}${path}`, options);
  const contentType = response.headers.get("content-type") || "";
  const payload = contentType.includes("application/json")
    ? await response.json()
    : await response.text();

  if (!response.ok) {
    const detail = payload && typeof payload === "object" ? payload.detail || payload.message : payload;
    throw new ApiRequestError(detail || `HTTP ${response.status}`, response.status);
  }

  return payload;
}

export async function checkReadiness(apiBase) {
  try {
    const readiness = await request(apiBase, "/api/v1/readiness");
    const ready = readiness.ready === true || readiness.status === "ready" || readiness.status === "ok";
    return {
      label: ready ? "Ready" : "Not ready",
      payload: readiness,
    };
  } catch (error) {
    if (error.status === 503) {
      return {
        label: "Not ready",
        payload: { error: error.message, status: error.status },
      };
    }
    return {
      label: "Offline",
      payload: { error: error.message, status: error.status || "network" },
    };
  }
}

export async function listSizeCharts(apiBase, filters = {}) {
  const params = new URLSearchParams();
  if (filters.category) params.set("category", filters.category);
  if (filters.countryCode) params.set("country_code", filters.countryCode);
  const query = params.toString();
  return request(apiBase, `${SIZE_CHARTS_PATH}${query ? `?${query}` : ""}`);
}

export async function uploadGarment(apiBase, formData) {
  return request(apiBase, GARMENTS_PATH, {
    method: "POST",
    body: formData,
  });
}

export async function listGarments(apiBase, filters = {}) {
  const params = new URLSearchParams();
  if (filters.limit) params.set("limit", String(filters.limit));
  const query = params.toString();
  return request(apiBase, `${GARMENTS_PATH}${query ? `?${query}` : ""}`);
}

export async function createSession(apiBase, garmentId) {
  return request(apiBase, SESSIONS_PATH, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ garment_id: garmentId }),
  });
}

export async function uploadCapture(apiBase, sessionId, frontImage, captureSource = "file_upload") {
  const formData = new FormData();
  formData.append("front_image", frontImage);
  formData.append("capture_source", captureSource);
  return request(apiBase, `${SESSIONS_PATH}/${sessionId}/${CAPTURES_PATH}`, {
    method: "POST",
    body: formData,
  });
}

export async function analyzeCapture(apiBase, sessionId) {
  return request(apiBase, `${SESSIONS_PATH}/${sessionId}/${CAPTURE_ANALYZE_PATH}`, {
    method: "POST",
  });
}

export async function analyzeFit(apiBase, sessionId, bodyMeasurements = {}, preferredFit = "regular") {
  return request(apiBase, `${SESSIONS_PATH}/${sessionId}/${FIT_ANALYZE_PATH}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      preferred_fit: preferredFit,
      body_measurements: bodyMeasurements,
      use_ai_analysis: false,
    }),
  });
}

export async function enqueueVisualPreviewJob(apiBase, sessionId) {
  return request(apiBase, `${SESSIONS_PATH}/${sessionId}/${VISUAL_PREVIEW_JOBS_PATH}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      use_multimodal_analysis: false,
      size: "1024x1024",
      max_attempts: 1,
    }),
  });
}

export async function getKioskJob(apiBase, jobId) {
  return request(apiBase, `${JOBS_PATH}/${jobId}`);
}

export function visualPreviewImageUrl(apiBase, personalizedTryonKey) {
  return `${apiBase}/api/v1/kiosk/visual-previews/${encodeURIComponent(personalizedTryonKey)}/image`;
}
