export function displaySessionLabel(hasSession) {
  return hasSession ? "Active" : "New fitting";
}

export function displayGarmentLabel(state) {
  if (!state.garmentId) return "Choose garment";
  return state.garmentName || "Product selected";
}

export function displayCaptureLabel(state) {
  if (state.capturePassed && state.visualPreviewReady) return "Scan ready";
  if (state.capturePassed) return "Fit ready, improve scan for try-on";
  if (state.captureUploaded) return "Scan uploaded, check quality";
  return "Scan shopper";
}

export function displayTryOnLabel(state) {
  if (state.previewKey) return "Try-on ready";
  if (!state.jobId) return "View try-on";
  if (["queued", "running"].includes(String(state.jobStatus || "").toLowerCase())) {
    return "Generating try-on";
  }
  if (state.jobStatus === "failed") return "Try-on needs retry";
  return "Try-on queued";
}
