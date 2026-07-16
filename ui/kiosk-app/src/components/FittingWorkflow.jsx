import { useRef } from "react";

import { Button } from "./Button.jsx";
import { DashboardIcon, ProductIcon, ScanIcon } from "./icons.jsx";

const workflowSteps = [
  { key: "garment", label: "Garment" },
  { key: "scan", label: "Shopper scan" },
  { key: "review", label: "Review" },
];

const checklistItems = ["Full body visible", "Facing forward", "Good lighting", "Garment area visible"];

const workflowStateLabels = {
  scanNotStarted: "Not started",
  scanReady: "Ready to capture",
  scanning: "Scanning",
  scanComplete: "Scan complete",
  fitLocked: "Locked",
  fitLoading: "Loading",
  fitNeedsMeasurements: "Needs input",
  fitReady: "Ready",
  tryOnLocked: "Locked",
  tryOnGenerating: "Generating",
  tryOnReady: "Ready",
};

export function FittingWorkflow({
  activeStage,
  bodyMeasurements,
  captureLabel,
  garmentLabel,
  onAnalyzeFit,
  onBodyMeasurementChange,
  onCapturePhoto,
  onContinueToReview,
  onContinueToScan,
  onOpenProduct,
  onQueueTryOn,
  onWorkflowViewChange,
  state,
  tryOnLabel,
  workflowView,
}) {
  const workflowState = getWorkflowState(state);
  const activeWorkflowView = resolveWorkflowView(workflowView || activeStage, state);

  return (
    <FittingRoomShell
      activeWorkflowView={activeWorkflowView}
      onWorkflowViewChange={onWorkflowViewChange}
      state={state}
      workflowState={workflowState}
    >
      {/* Only render the active workflow view. */}
      {activeWorkflowView === "garment" && (
        <GarmentStep
          garmentLabel={garmentLabel}
          onContinueToScan={onContinueToScan}
          onOpenProduct={onOpenProduct}
          state={state}
        />
      )}
      {activeWorkflowView === "scan" && (
        <ShopperScanStep
          captureLabel={captureLabel}
          garmentLabel={garmentLabel}
          onCapturePhoto={onCapturePhoto}
          onContinueToReview={onContinueToReview}
          state={state}
          workflowState={workflowState}
        />
      )}
      {activeWorkflowView === "review" && (
        <ReviewStep
          bodyMeasurements={bodyMeasurements}
          garmentLabel={garmentLabel}
          onAnalyzeFit={onAnalyzeFit}
          onBodyMeasurementChange={onBodyMeasurementChange}
          onQueueTryOn={onQueueTryOn}
          state={state}
          tryOnLabel={tryOnLabel}
          workflowState={workflowState}
        />
      )}
    </FittingRoomShell>
  );
}

export function FittingRoomShell({ activeWorkflowView, children, onWorkflowViewChange, state, workflowState }) {
  return (
    <section
      className="operator-workspace-layout grid max-w-full gap-4 overflow-x-hidden"
      data-workspace-shell="fitting-session-workspace"
    >
      <WorkflowHeader
        activeWorkflowView={activeWorkflowView}
        onWorkflowViewChange={onWorkflowViewChange}
        state={state}
        workflowState={workflowState}
      />
      <div className="min-h-[520px]">{children}</div>
    </section>
  );
}

export function WorkflowHeader({ activeWorkflowView, onWorkflowViewChange, state, workflowState }) {
  return (
    <header className="workflow-header border-b border-line/80 pb-3">
      <div className="grid gap-3 xl:grid-cols-[260px_minmax(0,1fr)] xl:items-end">
        <div className="min-w-0">
          <h1 className="text-lg font-semibold tracking-tight text-ink">Fitting Room</h1>
          <p className="mt-1 text-sm font-medium text-muted">{currentStepLabel(activeWorkflowView)}</p>
        </div>
        <WorkflowStepper
          activeWorkflowView={activeWorkflowView}
          onWorkflowViewChange={onWorkflowViewChange}
          state={state}
          workflowState={workflowState}
        />
      </div>
    </header>
  );
}

export function WorkflowStepper({ activeWorkflowView, onWorkflowViewChange, state, workflowState }) {
  return (
    <ol aria-label="Fitting progress" className="grid gap-2 sm:grid-cols-3">
      {workflowSteps.map((step, index) => {
        const status = stepStatus(step.key, activeWorkflowView, state, workflowState);
        const locked = status === "locked";

        return (
          <li key={step.key}>
            <button
              aria-current={status === "current" ? "step" : undefined}
              aria-disabled={locked}
              aria-label={`${step.label}: ${status}`}
              className={[
                "workflow-step flex min-h-10 w-full min-w-0 items-center gap-2 rounded-md px-2.5 py-2 text-left transition",
                status === "available" && "text-slate-600 hover:bg-slate-50",
                status === "complete" && "workflow-step-complete text-emerald-700 hover:bg-emerald-50",
                status === "current" && "workflow-step-current bg-brand-50 text-brand-700",
                status === "locked" && "workflow-step-disabled cursor-not-allowed text-slate-400",
              ]
                .filter(Boolean)
                .join(" ")}
              disabled={locked}
              onClick={() => onWorkflowViewChange?.(step.key)}
              type="button"
            >
              <span
                className={[
                  "grid h-6 w-6 shrink-0 place-items-center rounded-full border text-xs font-semibold",
                  status === "complete" && "border-emerald-500 bg-emerald-500 text-white",
                  status === "current" && "border-brand-600 bg-brand-600 text-white",
                  status === "available" && "border-slate-300 bg-white text-slate-600",
                  status === "locked" && "border-slate-200 bg-slate-50 text-slate-400",
                ]
                  .filter(Boolean)
                  .join(" ")}
              >
                {status === "complete" ? "✓" : index + 1}
              </span>
              <span className="truncate text-sm font-medium leading-5">{step.label}</span>
            </button>
          </li>
        );
      })}
    </ol>
  );
}

export function GarmentStep({ garmentLabel, onContinueToScan, onOpenProduct, state }) {
  const garmentSelected = Boolean(state.garmentId);

  return (
    <div className="grid gap-4 xl:grid-cols-[minmax(0,0.96fr)_minmax(360px,0.54fr)]">
      <section className="rounded-lg bg-white p-5 shadow-[0_1px_2px_rgba(15,23,42,0.05)] ring-1 ring-line/80">
        <div className="grid gap-5 lg:grid-cols-[220px_minmax(0,1fr)]">
          <div className="product-preview-surface grid min-h-[320px] place-items-center rounded-lg bg-slate-100 p-4 ring-1 ring-line/70">
            {state.garmentPreviewUrl ? (
              <img
                alt="Selected garment"
                className="max-h-[300px] w-full rounded-md object-contain"
                src={state.garmentPreviewUrl}
              />
            ) : (
              <div className="grid place-items-center gap-3 text-center">
                <div className="grid h-14 w-14 place-items-center rounded-md bg-white text-slate-500 ring-1 ring-line/80">
                  <ProductIcon className="h-7 w-7" />
                </div>
                <p className="text-sm font-semibold text-ink">No garment selected</p>
              </div>
            )}
          </div>

          <div className="grid content-between gap-5">
            <div>
              <h2 className="text-xl font-semibold tracking-tight text-ink">Choose garment</h2>
              <p className="mt-2 max-w-2xl text-sm leading-6 text-muted">
                Select the product image and size chart before scanning the shopper.
              </p>
              <div className="mt-5">
                <SelectedGarmentSummary garmentLabel={garmentLabel} state={state} />
              </div>
            </div>

            <div className="flex flex-col gap-2 sm:flex-row">
              <Button className="w-full sm:w-auto" onClick={onOpenProduct} variant={garmentSelected ? "secondary" : "primary"}>
                {garmentSelected ? "Change product" : "Upload product"}
              </Button>
              <Button className="w-full sm:w-auto" disabled={!garmentSelected} onClick={onContinueToScan}>
                Continue to shopper scan
              </Button>
            </div>
          </div>
        </div>
      </section>

      <aside className="grid content-start gap-3 rounded-lg bg-white p-4 shadow-[0_1px_2px_rgba(15,23,42,0.05)] ring-1 ring-line/80">
        <h3 className="text-sm font-semibold text-ink">Garment details</h3>
        <DetailRow label="Product" value={garmentSelected ? garmentLabel : "Waiting for upload"} />
        <DetailRow label="Category" value={garmentSelected ? formatCategoryLabel(state.garmentCategory || "tops") : "Not selected"} />
        <DetailRow label="Garment type" value={state.garmentType ? state.garmentType.replaceAll("_", " ") : "Not provided"} />
        <DetailRow label="Size chart status" value={getSizeChartLabel(state)} valueTone={state.sizeChartId ? "text-emerald-700" : "text-amber-700"} />
      </aside>
    </div>
  );
}

export function ShopperScanStep({ captureLabel, garmentLabel, onCapturePhoto, onContinueToReview, state, workflowState }) {
  return (
    <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_320px]">
      <CameraCapturePanel
        captureLabel={captureLabel}
        onCapturePhoto={onCapturePhoto}
        onContinueToReview={onContinueToReview}
        state={state}
        workflowState={workflowState}
      />

      <aside className="grid content-start gap-3">
        <SelectedGarmentSummary compact garmentLabel={garmentLabel} state={state} />

        <section className="rounded-lg bg-white p-4 shadow-[0_1px_2px_rgba(15,23,42,0.05)] ring-1 ring-line/80">
          <div className="flex items-start gap-3">
            <div className="grid h-9 w-9 shrink-0 place-items-center rounded-md bg-brand-50 text-brand-700">
              <ScanIcon className="h-5 w-5" />
            </div>
            <div>
              <h2 className="text-sm font-semibold text-ink">Scan status</h2>
              <p className="mt-1 text-sm leading-5 text-muted">{getScanGuidance(workflowState)}</p>
            </div>
          </div>
        </section>

        <section className="rounded-lg bg-white p-4 shadow-[0_1px_2px_rgba(15,23,42,0.05)] ring-1 ring-line/80">
          <CaptureChecklist checked={workflowState.scan === "scanComplete"} />
        </section>
      </aside>
    </div>
  );
}

export function CameraCapturePanel({ captureLabel, onCapturePhoto, onContinueToReview, state, workflowState }) {
  const fileInputRef = useRef(null);
  const captureSourceRef = useRef("file_upload");
  const scanComplete = workflowState.scan === "scanComplete";
  const scanStarted = workflowState.scan === "scanning" || scanComplete;
  const cameraStatus = getCameraStatus(workflowState);
  const disabled = !state.garmentId || state.scanBusy || state.fitLoading;

  function openCapturePicker(captureSource) {
    captureSourceRef.current = captureSource;
    fileInputRef.current?.click();
  }

  function handleFileChange(event) {
    const file = event.target.files?.[0];
    if (file) {
      onCapturePhoto?.(file, captureSourceRef.current);
    }
    event.target.value = "";
  }

  return (
    <section className="scan-workspace rounded-lg bg-white shadow-[0_1px_2px_rgba(15,23,42,0.05)] ring-1 ring-line/80">
      <div className="scan-panel-header flex flex-col gap-2 px-4 py-3 sm:flex-row sm:items-center sm:justify-between sm:px-5">
        <div className="min-w-0">
          <h2 className="text-xl font-semibold tracking-tight text-ink">Shopper scan</h2>
          <p className="mt-1 text-sm text-muted">Capture or upload a front-facing shopper photo for fit analysis.</p>
        </div>
        <StatusBadge sourceText={cameraStatus} tone={scanComplete ? "success" : "neutral"}>
          <span className="scan-panel-status">{cameraStatus}</span>
        </StatusBadge>
      </div>

      <div className="px-4 pb-4 sm:px-5">
        <div className="scan-stage relative grid h-[360px] overflow-hidden rounded-lg bg-slate-950 text-white shadow-soft sm:h-[420px] xl:h-[440px]">
          <input
            accept="image/*"
            className="sr-only"
            onChange={handleFileChange}
            ref={fileInputRef}
            type="file"
          />
          <div className="absolute inset-0 bg-[radial-gradient(circle_at_50%_18%,rgba(148,163,184,0.16),transparent_32%),linear-gradient(180deg,rgba(15,23,42,0.98),rgba(2,6,23,1))]" />
          <div className="absolute inset-x-4 top-4 z-10 flex items-center justify-between gap-3">
            <StatusBadge tone={scanComplete ? "success" : "dark"}>{captureLabel || cameraStatus}</StatusBadge>
            <span className="rounded-md bg-white/10 px-2 py-1 text-xs font-medium text-white/70">Camera frame</span>
          </div>

          <div className="relative mx-auto my-10 w-[min(64vw,320px)] rounded-[22px] border border-white/14 bg-white/[0.025]">
            <div className="pointer-events-none absolute inset-0 rounded-[24px] bg-[linear-gradient(rgba(255,255,255,0.08)_1px,transparent_1px),linear-gradient(90deg,rgba(255,255,255,0.08)_1px,transparent_1px)] bg-[length:58px_58px]" />
            <div className="pointer-events-none absolute inset-y-7 left-1/2 w-px -translate-x-1/2 bg-white/12" />
            <div className="pointer-events-none absolute inset-x-7 top-1/3 h-px bg-white/12" />
            <div className="pointer-events-none absolute inset-x-7 top-2/3 h-px bg-white/12" />

            <div className="relative mx-auto h-[260px] w-full sm:h-[314px]">
              <div className="absolute left-1/2 top-7 h-[52px] w-[52px] -translate-x-1/2 rounded-full border border-white/28 bg-white/10" />
              <div className="absolute left-1/2 top-[92px] h-[150px] w-[108px] -translate-x-1/2 rounded-b-[26px] rounded-t-[56px] border border-white/28 bg-white/[0.06]" />
              <div className="absolute left-1/2 top-[116px] h-[94px] w-[158px] -translate-x-1/2 rounded-[38px] border border-dashed border-white/25" />
              <div className="absolute bottom-8 left-1/2 h-[66px] w-[84px] -translate-x-1/2 rounded-b-[36px] border border-white/20 bg-white/[0.035]" />
              <div className="absolute left-8 right-8 top-[156px] h-px bg-emerald-200/70 shadow-[0_0_24px_rgba(167,243,208,0.7)]" />
            </div>
          </div>

          <div className="absolute bottom-3 left-3 right-3 z-10 flex flex-col gap-2 rounded-lg bg-black/32 px-3 py-2 backdrop-blur sm:flex-row sm:items-center sm:justify-between">
            <div>
              <p className="text-sm font-semibold text-white">{scanStarted ? cameraStatus : "Ready to capture"}</p>
              <p className="mt-0.5 text-xs text-white/68">Keep head, torso, and garment area inside the guide.</p>
            </div>
            <div className="scan-action-row grid grid-cols-2 gap-2 sm:flex sm:shrink-0">
              <Button className="h-9 min-w-28 px-3 text-sm" disabled={disabled} onClick={() => openCapturePicker("guided_scan")}>
                {state.scanBusy || state.fitLoading ? "Analyzing..." : scanComplete ? "Retake scan" : "Start scan"}
              </Button>
              <Button className="h-9 min-w-28 px-3 text-sm" disabled={disabled} onClick={() => openCapturePicker("file_upload")} variant="secondary">
                Upload photo
              </Button>
              {scanComplete && (
                <Button className="col-span-2 h-9 min-w-32 px-3 text-sm sm:col-span-1" onClick={onContinueToReview} variant="secondary">
                  Continue to review
                </Button>
              )}
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

export function CaptureChecklist({ checked }) {
  return (
    <aside className="quality-checklist grid content-start gap-2">
      <div>
        <h3 className="text-sm font-semibold text-ink">Capture checklist</h3>
      </div>
      <div className="grid gap-1.5">
        {checklistItems.map((label) => (
          <ChecklistItem checked={checked} key={label} label={label} />
        ))}
      </div>
    </aside>
  );
}

export function ChecklistItem({ checked, label }) {
  return (
    <div className="flex min-h-8 items-center gap-2 rounded-md bg-slate-50 px-2.5 py-1.5">
      <span
        className={[
          "grid h-5 w-5 shrink-0 place-items-center rounded-full border text-[10px] font-bold",
          checked ? "border-emerald-500 bg-emerald-500 text-white" : "border-slate-300 bg-white text-transparent",
        ].join(" ")}
      >
        ✓
      </span>
      <span className="text-sm font-medium text-ink">{label}</span>
    </div>
  );
}

export function ReviewStep({ bodyMeasurements, garmentLabel, onAnalyzeFit, onBodyMeasurementChange, onQueueTryOn, state, tryOnLabel, workflowState }) {
  return (
    <div className="grid gap-4">
      <SelectedGarmentSummary compact garmentLabel={garmentLabel} state={state} />
      <div className="review-output-grid grid gap-4 xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
        <SizeRecommendationPanel
          bodyMeasurements={bodyMeasurements}
          onAnalyzeFit={onAnalyzeFit}
          onBodyMeasurementChange={onBodyMeasurementChange}
          state={state}
          workflowState={workflowState}
        />
        <TryOnPreviewPanel onQueueTryOn={onQueueTryOn} state={state} tryOnLabel={tryOnLabel} workflowState={workflowState} />
      </div>
      <ReviewActions onQueueTryOn={onQueueTryOn} state={state} workflowState={workflowState} />
    </div>
  );
}

export function SizeRecommendationPanel({ bodyMeasurements, onAnalyzeFit, onBodyMeasurementChange, state, workflowState }) {
  const recommendation = state.fitRecommendation || {};
  const recommendedSize = recommendation.recommended_size;
  const confidence = formatConfidence(recommendation.confidence);
  const fitIntent = recommendation.preferred_fit || "regular";
  const needsMeasurements = workflowState.fit === "fitNeedsMeasurements";
  const fitLocked = workflowState.fit === "fitLocked";
  const fitLoading = workflowState.fit === "fitLoading";
  const hasBasicMeasurements = Boolean(bodyMeasurements?.heightCm && bodyMeasurements?.weightKg);
  const canUpdate = Boolean(state.capturePassed && state.garmentId && !state.fitLoading);
  const candidates = Array.isArray(recommendation.candidates) ? recommendation.candidates.slice(0, 3) : [];

  return (
    <section className="fit-recommendation-panel rounded-lg bg-white p-5 shadow-[0_1px_2px_rgba(15,23,42,0.05)] ring-1 ring-line/80">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.12em] text-muted">Fit result</p>
          <h2 className="mt-1 text-xl font-semibold tracking-tight text-ink">Size recommendation</h2>
        </div>
        <StatusBadge tone={recommendedSize ? "success" : needsMeasurements || fitLoading ? "neutral" : "locked"}>
          {recommendedSize ? `Size ${recommendedSize}` : needsMeasurements ? "Needs measurements" : fitLoading ? "Loading" : "Locked"}
        </StatusBadge>
      </div>

      <div className="mt-5 grid gap-3 sm:grid-cols-3">
        <MetricBlock label="Recommended size" value={recommendedSize ? `Size ${recommendedSize}` : "Not ready"} />
        <MetricBlock label="Confidence" value={confidence} />
        <MetricBlock label="Fit intent" value={fitIntent} />
      </div>

      <p className="mt-4 rounded-md bg-slate-50 px-3 py-2 text-sm font-medium leading-5 text-ink">
        {state.fitRecommendationLabel || recommendation.reason || "Run the shopper scan and add measurements if needed to produce a deterministic recommendation."}
      </p>

      <div className="mt-4 grid gap-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.12em] text-muted">Key measurements or deltas</p>
          <div className="mt-2 grid gap-2">
            {candidates.length ? (
              candidates.map((candidate) => (
                <div className="flex min-h-9 items-center justify-between gap-3 border-b border-line/70 py-1.5 last:border-b-0" key={candidate.size}>
                  <span className="text-sm font-medium text-ink">Size {candidate.size}</span>
                  <span className="text-sm text-muted">{formatConfidence(candidate.confidence)} match</span>
                </div>
              ))
            ) : (
              <p className="rounded-md bg-slate-50 px-3 py-2 text-sm leading-5 text-muted">
                Candidate deltas appear after a size chart and shopper measurements overlap.
              </p>
            )}
          </div>
        </div>

        <div className="grid gap-2">
          <p className="text-xs font-semibold uppercase tracking-[0.12em] text-muted">Shopper measurements</p>
          <div className="grid grid-cols-2 gap-2">
            <label className="grid gap-1 text-xs font-semibold text-muted" htmlFor="fit-height-cm">
              Height
              <input
                className="h-9 rounded-md border border-line bg-white px-2 text-sm font-medium text-ink outline-none focus:border-brand-500 focus:ring-2 focus:ring-brand-100"
                id="fit-height-cm"
                inputMode="decimal"
                min="1"
                onChange={(event) => onBodyMeasurementChange?.("heightCm", event.target.value)}
                placeholder="cm"
                type="number"
                value={bodyMeasurements?.heightCm || ""}
              />
            </label>
            <label className="grid gap-1 text-xs font-semibold text-muted" htmlFor="fit-weight-kg">
              Weight
              <input
                className="h-9 rounded-md border border-line bg-white px-2 text-sm font-medium text-ink outline-none focus:border-brand-500 focus:ring-2 focus:ring-brand-100"
                id="fit-weight-kg"
                inputMode="decimal"
                min="1"
                onChange={(event) => onBodyMeasurementChange?.("weightKg", event.target.value)}
                placeholder="kg"
                type="number"
                value={bodyMeasurements?.weightKg || ""}
              />
            </label>
          </div>
          <Button
            className="h-9 justify-center px-3 text-sm"
            disabled={!canUpdate || fitLocked || !hasBasicMeasurements}
            onClick={onAnalyzeFit}
            size="sm"
            variant={needsMeasurements ? "primary" : "secondary"}
          >
            {fitLoading ? "Updating..." : "Update recommendation"}
          </Button>
        </div>
      </div>
    </section>
  );
}

export function TryOnPreviewPanel({ onQueueTryOn, state, tryOnLabel, workflowState }) {
  const previewReady = workflowState.tryOn === "tryOnReady";
  const tryOnGenerating = workflowState.tryOn === "tryOnGenerating";
  const fitReady = workflowState.fit === "fitReady";
  const canRequestTryOn = fitReady && !tryOnGenerating;

  return (
    <section className="tryon-review-panel rounded-lg bg-white p-5 shadow-[0_1px_2px_rgba(15,23,42,0.05)] ring-1 ring-line/80">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.12em] text-muted">Try-on review</p>
          <h2 className="mt-1 text-xl font-semibold tracking-tight text-ink">{tryOnLabel}</h2>
        </div>
        <StatusBadge tone={previewReady ? "success" : tryOnGenerating ? "neutral" : "locked"}>
          {workflowStateLabels[workflowState.tryOn]}
        </StatusBadge>
      </div>

      <div className="tryon-result-stage mt-5 grid min-h-[420px] place-items-center rounded-lg bg-slate-100 p-4 ring-1 ring-line/70">
        {previewReady ? (
          state.previewImageUrl ? (
            <img
              alt="Generated try-on preview"
              className="max-h-[390px] w-full rounded-md object-contain"
              src={state.previewImageUrl}
            />
          ) : (
            <div className="grid gap-2 text-center">
              <div className="mx-auto grid h-24 w-16 place-items-end rounded-b-lg rounded-t-full bg-gradient-to-b from-slate-200 to-slate-700 p-1">
                <span className="h-4 w-full rounded bg-emerald-100 text-[10px] font-semibold text-emerald-700">Ready</span>
              </div>
              <p className="text-sm font-semibold text-ink">Try-on preview ready</p>
            </div>
          )
        ) : (
          <div className="max-w-[280px] text-center">
            <DashboardIcon className="mx-auto h-6 w-6 text-slate-400" />
            <p className="mt-3 text-sm font-semibold text-ink">
              {tryOnGenerating ? "Generating try-on preview" : state.tryOnError || "Preview unlocks after fit result."}
            </p>
            {fitReady && <p className="mt-1 text-sm leading-5 text-muted">Generate the visual review from the current recommendation.</p>}
          </div>
        )}
      </div>

      <div className="mt-4 flex flex-col gap-2 sm:flex-row">
        <Button
          className="w-full sm:w-auto"
          disabled={!canRequestTryOn}
          onClick={onQueueTryOn}
          size="sm"
          variant={canRequestTryOn ? "primary" : "secondary"}
        >
          {tryOnGenerating ? "Generating..." : previewReady ? "Regenerate try-on" : "Generate try-on"}
        </Button>
      </div>
    </section>
  );
}

export function ReviewActions({ onQueueTryOn, state, workflowState }) {
  const previewReady = workflowState.tryOn === "tryOnReady";
  const tryOnGenerating = workflowState.tryOn === "tryOnGenerating";
  const fitReady = workflowState.fit === "fitReady";
  const canRegenerate = fitReady && !tryOnGenerating;

  return (
    <section className="flex flex-col gap-2 rounded-lg bg-white px-4 py-3 shadow-[0_1px_2px_rgba(15,23,42,0.05)] ring-1 ring-line/80 sm:flex-row sm:items-center sm:justify-between">
      <div>
        <h3 className="text-sm font-semibold text-ink">Review actions</h3>
        <p className="mt-1 text-sm text-muted">
          {previewReady ? "Approve the output or regenerate the try-on with the current session data." : "Generate the try-on once the recommendation is ready."}
        </p>
      </div>
      <div className="flex flex-col gap-2 sm:flex-row">
        <Button disabled={!previewReady} size="sm" variant="secondary">
          Approve result
        </Button>
        <Button disabled={!canRegenerate || Boolean(state.scanBusy)} onClick={onQueueTryOn} size="sm" variant={previewReady ? "secondary" : "primary"}>
          {tryOnGenerating ? "Generating..." : previewReady ? "Regenerate try-on" : "Generate try-on"}
        </Button>
      </div>
    </section>
  );
}

export function SelectedGarmentSummary({ compact = false, garmentLabel, state }) {
  const selected = Boolean(state.garmentId);
  const displayName = selected ? garmentLabel : "No garment selected";
  const categoryLabel = selected ? formatCategoryLabel(state.garmentCategory || "tops") : "Upload a product to start";
  const garmentTypeLabel = state.garmentType ? state.garmentType.replaceAll("_", " ") : "";
  const chartLabel = getSizeChartLabel(state);

  return (
    <section
      className={[
        "selected-garment-context-bar rounded-lg bg-white shadow-[0_1px_2px_rgba(15,23,42,0.05)] ring-1 ring-line/80",
        compact ? "p-3" : "p-4",
      ].join(" ")}
      data-selected-garment-bar="visible-after-upload"
    >
      <div className="flex min-w-0 items-center gap-3">
        <div className={compact ? "grid h-10 w-10 shrink-0 place-items-center rounded-md bg-slate-100 text-slate-700 ring-1 ring-line/80" : "grid h-12 w-12 shrink-0 place-items-center rounded-md bg-slate-100 text-slate-700 ring-1 ring-line/80"}>
          {state.garmentPreviewUrl ? (
            <img
              alt=""
              className={compact ? "h-10 w-10 rounded-md object-cover" : "h-12 w-12 rounded-md object-cover"}
              src={state.garmentPreviewUrl}
            />
          ) : (
            <ProductIcon className={compact ? "h-5 w-5" : "h-6 w-6"} />
          )}
        </div>
        <div className="min-w-0">
          <p className="truncate text-sm font-semibold text-ink">{displayName}</p>
          <div className="mt-1 flex min-w-0 flex-wrap items-center gap-x-2 gap-y-1 text-sm text-muted">
            <span>{categoryLabel}</span>
            {selected && garmentTypeLabel && (
              <>
                <span className="h-1 w-1 rounded-full bg-slate-300" />
                <span className="capitalize">{garmentTypeLabel}</span>
              </>
            )}
          </div>
          <p className={state.sizeChartId ? "mt-1 truncate text-sm text-muted" : "mt-1 truncate text-sm font-medium text-amber-700"}>
            {chartLabel}
          </p>
        </div>
      </div>
    </section>
  );
}

export function StatusBadge({ children, sourceText, tone = "neutral" }) {
  const tones = {
    dark: "bg-white/10 text-white ring-white/15",
    locked: "bg-slate-100 text-slate-500 ring-slate-200",
    neutral: "bg-slate-100 text-slate-700 ring-slate-200",
    success: "bg-emerald-50 text-emerald-700 ring-emerald-100",
  };

  if (!sourceText) {
    return <span className={`inline-flex items-center rounded-md px-2 py-1 text-xs font-semibold ring-1 ${tones[tone]}`}>{children}</span>;
  }

  return (
    <span
      className={`inline-flex max-w-[156px] items-center truncate rounded-md px-2 py-1 text-xs font-semibold ring-1 ${tones[tone]}`}
      title={sourceText}
    >
      {children}
    </span>
  );
}

function DetailRow({ label, value, valueTone = "text-ink" }) {
  return (
    <div className="flex min-h-9 items-center justify-between gap-3 border-b border-line/70 py-2 last:border-b-0">
      <span className="text-sm text-muted">{label}</span>
      <span className={`text-right text-sm font-semibold ${valueTone}`}>{value}</span>
    </div>
  );
}

function MetricBlock({ label, value }) {
  return (
    <div className="rounded-md bg-slate-50 px-3 py-2">
      <p className="text-xs font-semibold uppercase tracking-[0.12em] text-muted">{label}</p>
      <p className="mt-1 truncate text-sm font-semibold text-ink">{value}</p>
    </div>
  );
}

function currentStepLabel(activeWorkflowView) {
  if (activeWorkflowView === "garment") return "Step 1 of 3 · Garment";
  if (activeWorkflowView === "scan") return "Step 2 of 3 · Shopper scan";
  return "Step 3 of 3 · Review";
}

function stepStatus(key, activeWorkflowView, state, workflowState) {
  if (key === activeWorkflowView) return "current";
  if (isStepComplete(key, state, workflowState)) return "complete";
  if (!isStepAvailable(key, state)) return "locked";
  return "available";
}

function isStepAvailable(key, state) {
  if (key === "garment") return true;
  if (key === "scan") return Boolean(state.garmentId);
  return Boolean(state.capturePassed);
}

function isStepComplete(key, state, workflowState) {
  if (key === "garment") return Boolean(state.garmentId);
  if (key === "scan") return Boolean(state.capturePassed);
  return workflowState.tryOn === "tryOnReady";
}

function resolveWorkflowView(view, state) {
  const normalized = {
    capture: "scan",
    fit: "review",
    product: "garment",
    tryon: "review",
  }[view] || view;

  if (!state.garmentId) return "garment";
  if (normalized === "review" && !state.capturePassed) return "scan";
  if (normalized === "garment" || normalized === "scan" || normalized === "review") return normalized;
  return state.capturePassed ? "review" : "scan";
}

function formatCategoryLabel(category) {
  const labels = {
    bottoms: "Bottoms",
    full_outfit: "Full outfit",
    one_pieces: "One piece",
    tops: "Tops",
  };
  return labels[category] || String(category || "Tops");
}

function getSizeChartLabel(state) {
  if (state.sizeChartName) {
    return `${state.sizeChartName}${state.sizeChartSizes ? ` · ${state.sizeChartSizes}` : ""}`;
  }
  if (state.sizeChartId) {
    return `Chart linked${state.sizeChartSizes ? ` · ${state.sizeChartSizes}` : ""}`;
  }
  if (state.garmentId) return "No chart linked";
  return "Size chart loads after upload";
}

function getCameraStatus(workflowState) {
  if (workflowState.scan === "scanComplete") return workflowStateLabels.scanComplete;
  if (workflowState.scan === "scanning") return workflowStateLabels.scanning;
  return workflowStateLabels.scanReady;
}

function getScanGuidance(workflowState) {
  if (workflowState.scan === "scanComplete") return "Scan succeeded. Continue to review when the operator is ready.";
  if (workflowState.scan === "scanning") return "Capture is being analyzed for fit readiness.";
  return "Start scan or upload a shopper photo. Review outputs stay locked until scan completes.";
}

function formatConfidence(confidence) {
  const numeric = Number.parseFloat(confidence);
  if (!Number.isFinite(numeric) || numeric <= 0) return "Not ready";
  return `${Math.round(numeric * 100)}%`;
}

function getWorkflowState(state) {
  const scan = state.capturePassed ? "scanComplete" : state.scanBusy || state.captureUploaded ? "scanning" : "scanNotStarted";
  const fit = state.fitReady
    ? "fitReady"
    : state.fitLoading
      ? "fitLoading"
      : state.fitNeedsMeasurements || state.fitRecommendationStatus === "insufficient_measurements"
        ? "fitNeedsMeasurements"
        : "fitLocked";
  const tryOn = state.previewKey
    ? "tryOnReady"
    : ["queued", "leased", "running"].includes(String(state.jobStatus || "").toLowerCase())
      ? "tryOnGenerating"
      : "tryOnLocked";

  return { fit, scan, tryOn };
}
