import { Button } from "./Button.jsx";
import { DashboardIcon, ProductIcon, ScanIcon, TryOnIcon } from "./icons.jsx";

const workflowSteps = [
  { key: "product", label: "Garment" },
  { key: "capture", label: "Shopper scan" },
  { key: "fit", label: "Fit result" },
  { key: "tryon", label: "Try-on" },
];

const checklistItems = ["Full body visible", "Facing forward", "Good lighting", "Garment area visible"];

const workflowStateLabels = {
  scanNotStarted: "Not started",
  scanReady: "Ready to capture",
  scanning: "Scanning",
  scanComplete: "Scan complete",
  fitLocked: "Locked",
  fitLoading: "Loading",
  fitReady: "Ready",
  tryOnLocked: "Locked",
  tryOnGenerating: "Generating",
  tryOnReady: "Ready",
};

export function FittingWorkflow({
  activeStage,
  captureLabel,
  garmentLabel,
  onOpenProduct,
  onQueueTryOn,
  onRunScan,
  state,
  tryOnLabel,
}) {
  const workflowState = getWorkflowState(state);

  return (
    <section
      className="operator-workspace-layout grid max-w-full gap-3 overflow-x-hidden"
      data-workspace-shell="fitting-session-workspace"
    >
      <WorkflowHeader activeStage={activeStage} state={state} />
      <SelectedGarmentBar garmentLabel={garmentLabel} onOpenProduct={onOpenProduct} state={state} />

      <div className="fitting-console-grid fitting-workflow-layout grid items-start gap-3 xl:grid-cols-[minmax(0,68fr)_minmax(320px,32fr)]">
        <ScanWorkspace
          captureLabel={captureLabel}
          onRunScan={onRunScan}
          state={state}
          workflowState={workflowState}
        />
        <OperatorGuidancePanel
          onQueueTryOn={onQueueTryOn}
          state={state}
          tryOnLabel={tryOnLabel}
          workflowState={workflowState}
        />
      </div>
    </section>
  );
}

export function WorkflowHeader({ activeStage, state }) {
  return (
    <header className="workflow-header border-b border-line/80 pb-2">
      <div className="grid gap-2 xl:grid-cols-[240px_minmax(0,1fr)] xl:items-end">
        <div className="min-w-0">
          <h1 className="text-lg font-semibold tracking-tight text-ink">Fitting Room</h1>
          <p className="mt-1 text-sm font-medium text-muted">{currentStepLabel(activeStage, state)}</p>
        </div>
        <WorkflowStepper activeStage={activeStage} state={state} />
      </div>
    </header>
  );
}

export function WorkflowStepper({ activeStage, state }) {
  return (
    <ol aria-label="Fitting progress" className="grid gap-2 sm:grid-cols-4">
      {workflowSteps.map((step, index) => {
        const status = stepStatus(step.key, activeStage, state);

        return (
          <li
            aria-label={`${step.label}: ${status}`}
            className={[
              "workflow-step flex min-w-0 items-center gap-2 rounded-md px-2 py-1.5",
              status === "complete" && "workflow-step-complete text-emerald-700",
              status === "current" && "workflow-step-current bg-brand-50 text-brand-700",
              status === "disabled" && "workflow-step-disabled text-slate-400",
            ]
              .filter(Boolean)
              .join(" ")}
            key={step.key}
          >
            <span
              className={[
                "grid h-6 w-6 shrink-0 place-items-center rounded-full border text-xs font-semibold",
                status === "complete" && "border-emerald-500 bg-emerald-500 text-white",
                status === "current" && "border-brand-600 bg-brand-600 text-white",
                status === "disabled" && "border-slate-200 bg-slate-50 text-slate-400",
              ]
                .filter(Boolean)
                .join(" ")}
            >
              {status === "complete" ? "✓" : index + 1}
            </span>
            <span className="truncate text-sm font-medium leading-5">{step.label}</span>
          </li>
        );
      })}
    </ol>
  );
}

function currentStepLabel(activeStage, state) {
  if (!state.garmentId) return "Step 1 of 4 · Garment";
  if (activeStage === "capture") return "Step 2 of 4 · Shopper scan";
  if (activeStage === "fit") return "Step 3 of 4 · Fit result";
  return "Step 4 of 4 · Try-on";
}

function stepStatus(key, activeStage, state) {
  if (key === activeStage) return "current";
  if (isStepComplete(key, state)) return "complete";
  return workflowSteps.findIndex((step) => step.key === key) > workflowSteps.findIndex((step) => step.key === activeStage)
    ? "disabled"
    : "complete";
}

function isStepComplete(key, state) {
  if (key === "product") return Boolean(state.garmentId);
  if (key === "capture") return Boolean(state.capturePassed);
  if (key === "fit") return Boolean(state.fitReady);
  return Boolean(state.previewKey);
}

export function SelectedGarmentBar({ garmentLabel, onOpenProduct, state }) {
  const selected = Boolean(state.garmentId);
  const displayName = selected ? garmentLabel : "T-Shirt";

  return (
    <section
      className="selected-garment-context-bar flex min-h-[52px] max-w-full flex-col gap-2 rounded-lg bg-white px-3 py-2 shadow-[0_1px_2px_rgba(15,23,42,0.05)] ring-1 ring-line/80 sm:flex-row sm:items-center sm:justify-between sm:px-4"
      data-selected-garment-bar="visible-after-upload"
    >
      <div className="flex min-w-0 items-center gap-3">
        <div className="grid h-8 w-8 shrink-0 place-items-center rounded-md bg-slate-100 text-slate-700 ring-1 ring-line/80">
          <ProductIcon className="h-5 w-5" />
        </div>
        <div className="flex min-w-0 flex-wrap items-center gap-x-2 gap-y-1 text-sm">
          <p className="truncate font-semibold text-ink">{displayName}</p>
          <span className="text-muted">Tops</span>
          <span className="h-1 w-1 rounded-full bg-slate-300" />
          <span className="text-muted">Size chart attached</span>
        </div>
      </div>

      <Button className="w-full sm:w-auto" onClick={onOpenProduct} size="sm" variant="ghost">
        Change product
      </Button>
    </section>
  );
}

export function ScanWorkspace({ captureLabel, onRunScan, state, workflowState }) {
  const scanComplete = workflowState.scan === "scanComplete";
  const scanStarted = workflowState.scan === "scanning" || scanComplete;
  const cameraStatus = getCameraStatus(workflowState);

  return (
    <section className="scan-workspace rounded-lg bg-white shadow-[0_1px_2px_rgba(15,23,42,0.05)] ring-1 ring-line/80">
      <div className="scan-panel-header flex flex-col gap-2 px-4 py-2.5 sm:flex-row sm:items-center sm:justify-between sm:px-5">
        <div className="min-w-0">
          <h2 className="text-lg font-semibold tracking-tight text-ink">Capture shopper photo</h2>
          <p className="mt-1 text-sm text-muted">Position the shopper inside the frame, facing forward.</p>
        </div>
        <StatusBadge sourceText={cameraStatus} tone={scanComplete ? "success" : "neutral"}>
          <span className="scan-panel-status">{cameraStatus}</span>
        </StatusBadge>
      </div>

      <div className="px-4 pb-3 sm:px-5">
        <CameraCaptureFrame
          onRunScan={onRunScan}
          scanComplete={scanComplete}
          scanLabel={cameraStatus}
          scanStarted={scanStarted}
          state={state}
        />
      </div>
    </section>
  );
}

export function CameraCaptureFrame({ onRunScan, scanComplete, scanLabel, scanStarted, state }) {
  const disabled = !state.garmentId;

  return (
    <div className="scan-stage relative grid h-[360px] overflow-hidden rounded-lg bg-slate-950 text-white shadow-soft sm:h-[420px] xl:h-[440px]">
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_50%_18%,rgba(148,163,184,0.16),transparent_32%),linear-gradient(180deg,rgba(15,23,42,0.98),rgba(2,6,23,1))]" />
      <div className="absolute inset-x-4 top-4 z-10 flex items-center justify-between gap-3">
        <StatusBadge tone={scanComplete ? "success" : "dark"}>{scanLabel}</StatusBadge>
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
          <p className="text-sm font-semibold text-white">{scanStarted ? scanLabel : "Ready to capture"}</p>
          <p className="mt-0.5 text-xs text-white/68">Keep head, torso, and garment area inside the guide.</p>
        </div>
        <div className="scan-action-row grid grid-cols-2 gap-2 sm:flex sm:shrink-0">
          <Button className="h-9 min-w-28 px-3 text-sm" disabled={disabled} onClick={onRunScan}>
            {scanComplete ? "Retake scan" : "Start scan"}
          </Button>
          <Button className="h-9 min-w-28 px-3 text-sm" disabled={disabled} onClick={onRunScan} variant="secondary">
            Upload photo
          </Button>
        </div>
      </div>
    </div>
  );
}

export function CaptureChecklist({ checked }) {
  return (
    <aside className="quality-checklist grid content-start gap-2">
      <div>
        <h3 className="text-sm font-semibold text-ink">Photo checklist</h3>
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

export function OperatorGuidancePanel({ onQueueTryOn, state, tryOnLabel, workflowState }) {
  const nextStepText = getNextStepText(workflowState);

  return (
    <aside className="operator-guidance-panel sticky top-20 grid self-start content-start gap-2.5 rounded-lg bg-white p-3 shadow-[0_1px_2px_rgba(15,23,42,0.05)] ring-1 ring-line/80">
      <section className="flex items-start gap-3">
        <div className="grid h-9 w-9 shrink-0 place-items-center rounded-md bg-brand-50 text-brand-700">
          <ScanIcon className="h-5 w-5" />
        </div>
        <div>
          <h2 className="text-sm font-semibold text-ink">Next step</h2>
          <p className="mt-1 text-sm leading-5 text-muted">{nextStepText}</p>
        </div>
      </section>

      <section className="border-t border-line/70 pt-2.5">
        <CaptureChecklist checked={workflowState.scan === "scanComplete"} />
      </section>

      <section className="border-t border-line/70 pt-2.5">
        <h3 className="text-sm font-semibold text-ink">Output status</h3>
        <OutputStatusList workflowState={workflowState} />
      </section>

      <EmptyPreview onQueueTryOn={onQueueTryOn} state={state} tryOnLabel={tryOnLabel} workflowState={workflowState} />
    </aside>
  );
}

export function OutputStatusList({ workflowState }) {
  const rows = [
    { label: "Garment", sourceText: "Garment: Ready", value: "Ready", tone: "success" },
    {
      label: "Shopper scan",
      sourceText: "Shopper scan: Not started",
      value: workflowStateLabels[workflowState.scan],
      tone: workflowState.scan === "scanComplete" ? "success" : "neutral",
    },
    {
      label: "Fit recommendation",
      sourceText: "Fit recommendation: Locked",
      value: workflowStateLabels[workflowState.fit],
      tone: workflowState.fit === "fitReady" ? "success" : workflowState.fit === "fitLoading" ? "neutral" : "locked",
    },
    {
      label: "Try-on preview",
      sourceText: "Try-on preview: Locked",
      value: workflowStateLabels[workflowState.tryOn],
      tone: workflowState.tryOn === "tryOnReady" ? "success" : workflowState.tryOn === "tryOnGenerating" ? "neutral" : "locked",
    },
  ];

  return (
    <div className="mt-2 grid gap-1">
      {rows.map((row) => (
        <StatusRow key={row.label} {...row} />
      ))}
    </div>
  );
}

function StatusRow({ label, sourceText, tone, value }) {
  const title = `${label}: ${value}`;

  return (
    <div className="flex min-h-8 items-center justify-between gap-3 border-b border-line/70 py-1.5 last:border-b-0">
      <span className="truncate text-sm text-muted">{label}</span>
      <StatusBadge sourceText={title || sourceText} tone={tone}>
        {value}
      </StatusBadge>
    </div>
  );
}

export function EmptyPreview({ onQueueTryOn, state, tryOnLabel, workflowState }) {
  const previewReady = workflowState.tryOn === "tryOnReady";
  const tryOnGenerating = workflowState.tryOn === "tryOnGenerating";
  const fitReady = workflowState.fit === "fitReady";
  const canGenerateTryOn = fitReady && !state.previewKey;

  return (
    <section className="border-t border-line/70 pt-2.5">
      <div className="flex items-center justify-between gap-3">
        <h3 className="text-sm font-semibold text-ink">{tryOnLabel}</h3>
        {canGenerateTryOn ? (
          <Button
            className="h-8 px-2.5 text-xs"
            disabled={!canGenerateTryOn || tryOnGenerating}
            onClick={onQueueTryOn}
            size="sm"
            variant={tryOnGenerating ? "secondary" : "primary"}
          >
            {tryOnGenerating ? "Generating..." : "Generate try-on"}
          </Button>
        ) : (
          <TryOnIcon className="h-4 w-4 shrink-0 text-slate-500" />
        )}
      </div>

      <div className="operator-preview-placeholder mt-2 grid min-h-[108px] place-items-center rounded-md bg-slate-50 p-3 text-center ring-1 ring-line/70">
        {previewReady ? (
          <div className="grid gap-2">
            <div className="mx-auto grid h-20 w-14 place-items-end rounded-b-lg rounded-t-full bg-gradient-to-b from-slate-200 to-slate-700 p-1">
              <span className="h-4 w-full rounded bg-emerald-100 text-[10px] font-semibold text-emerald-700">Ready</span>
            </div>
            <p className="text-sm font-semibold text-ink">Try-on preview ready</p>
          </div>
        ) : (
          <div className="max-w-[220px]">
            <DashboardIcon className="mx-auto h-5 w-5 text-slate-400" />
            <p className="mt-2 text-sm font-semibold text-ink">
              {tryOnGenerating ? "Generating try-on preview" : "Preview unlocks after fit result."}
            </p>
            {fitReady && <p className="mt-1 text-sm leading-5 text-muted">Preview generation is available from the session actions.</p>}
          </div>
        )}
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

function getCameraStatus(workflowState) {
  if (workflowState.scan === "scanComplete") return workflowStateLabels.scanComplete;
  if (workflowState.scan === "scanning") return workflowStateLabels.scanning;
  return workflowStateLabels.scanReady;
}

function getNextStepText(workflowState) {
  if (workflowState.tryOn === "tryOnReady") return "Try-on preview is ready for operator review.";
  if (workflowState.fit === "fitReady") return "Fit recommendation is ready. Review outputs before creating the try-on preview.";
  if (workflowState.scan === "scanComplete") return "Scan is complete. Fit recommendation is being prepared.";
  return "Start a shopper scan to unlock fit recommendation and try-on preview.";
}

function getWorkflowState(state) {
  const scan = state.capturePassed ? "scanComplete" : state.captureUploaded ? "scanning" : "scanNotStarted";
  const fit = state.fitReady ? "fitReady" : state.capturePassed ? "fitLoading" : "fitLocked";
  const tryOn = state.previewKey ? "tryOnReady" : state.jobStatus === "running" ? "tryOnGenerating" : "tryOnLocked";

  return { fit, scan, tryOn };
}

function ProductStrip(props) {
  return <SelectedGarmentBar {...props} />;
}

function MainFittingCanvas(props) {
  return <ScanWorkspace {...props} />;
}
