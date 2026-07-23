import { useRef } from "react";

import { Button } from "./Button.jsx";
import { DashboardIcon, ProductIcon, ScanIcon } from "./icons.jsx";

const workflowSteps = [
  { key: "scan", label: "Scan" },
  { key: "garments", label: "Garments" },
  { key: "review", label: "Review" },
];

const fitIntentOptions = [
  { value: "slim", label: "Slim" },
  { value: "regular", label: "Regular" },
  { value: "relaxed", label: "Relaxed" },
];

const workflowStateLabels = {
  scanNotStarted: "Not started",
  scanReady: "Ready",
  scanning: "Scanning",
  scanComplete: "Scan complete",
  fitLocked: "Locked",
  fitLoading: "Loading",
  fitNeedsMeasurements: "Needs measurements",
  fitReady: "Ready",
  tryOnLocked: "Locked",
  tryOnGenerating: "Generating",
  tryOnReady: "Ready",
};

export function FittingWorkflow({
  activeStage,
  bodyMeasurements,
  captureLabel,
  confirmedProfile,
  fitIntent,
  garmentLabel,
  mockSensorProfile,
  onAnalyzeFit,
  onBodyMeasurementChange,
  onCapturePhoto,
  onConfirmedProfileChange,
  onContinueToReview,
  onDetectProfileFromSensor,
  onFitIntentChange,
  onMockSensorProfileChange,
  onOpenProduct,
  onQueueTryOn,
  onSelectPreparedGarment,
  onToggleOperatorSensor,
  onWorkflowViewChange,
  operatorSensorOpen,
  pendingCaptureFile,
  preparedGarments,
  preparedGarmentsStatus,
  profileEditorOpen,
  state,
  tryOnLabel,
  workflowView,
}) {
  const workflowState = getWorkflowState(state);
  const activeWorkflowView = resolveWorkflowView(workflowView || activeStage, state, confirmedProfile);

  return (
    <FittingRoomShell
      activeWorkflowView={activeWorkflowView}
      confirmedProfile={confirmedProfile}
      onWorkflowViewChange={onWorkflowViewChange}
      state={state}
      workflowState={workflowState}
    >
      {/* Only render the active workflow view. */}
      {activeWorkflowView === "scan" && (
        <ScanFirstFittingWorkflow
          bodyMeasurements={bodyMeasurements}
          captureLabel={captureLabel}
          confirmedProfile={confirmedProfile}
          fitIntent={fitIntent}
          mockSensorProfile={mockSensorProfile}
          onBodyMeasurementChange={onConfirmedProfileChange || onBodyMeasurementChange}
          onCapturePhoto={onCapturePhoto}
          onContinueToReview={onContinueToReview}
          onDetectProfileFromSensor={onDetectProfileFromSensor}
          onFitIntentChange={onFitIntentChange}
          onMockSensorProfileChange={onMockSensorProfileChange}
          onToggleOperatorSensor={onToggleOperatorSensor}
          operatorSensorOpen={operatorSensorOpen}
          pendingCaptureFile={pendingCaptureFile}
          profileEditorOpen={profileEditorOpen}
          state={state}
          workflowState={workflowState}
        />
      )}
      {activeWorkflowView === "garments" && (
        <PreparedGarmentPicker
          confirmedProfile={confirmedProfile}
          garmentLabel={garmentLabel}
          onOpenProduct={onOpenProduct}
          onSelectPreparedGarment={onSelectPreparedGarment}
          pendingCaptureFile={pendingCaptureFile}
          preparedGarments={preparedGarments}
          preparedGarmentsStatus={preparedGarmentsStatus}
          state={state}
        />
      )}
      {activeWorkflowView === "review" && (
        <ReviewStep
          confirmedProfile={confirmedProfile}
          fitIntent={fitIntent}
          garmentLabel={garmentLabel}
          onAnalyzeFit={onAnalyzeFit}
          onFitIntentChange={onFitIntentChange}
          onQueueTryOn={onQueueTryOn}
          onTryAnotherGarment={() => onWorkflowViewChange?.("garments")}
          state={state}
          tryOnLabel={tryOnLabel}
          workflowState={workflowState}
        />
      )}
    </FittingRoomShell>
  );
}

export function FittingRoomShell({
  activeWorkflowView,
  children,
  confirmedProfile,
  onWorkflowViewChange,
  state,
  workflowState,
}) {
  return (
    <section
      className="operator-workspace-layout grid max-w-full gap-4 overflow-x-hidden"
      data-workspace-shell="fitting-session-workspace"
    >
      <WorkflowHeader
        activeWorkflowView={activeWorkflowView}
        confirmedProfile={confirmedProfile}
        onWorkflowViewChange={onWorkflowViewChange}
        state={state}
        workflowState={workflowState}
      />
      <div className="min-h-[500px]">{children}</div>
    </section>
  );
}

export function WorkflowHeader({ activeWorkflowView, confirmedProfile, onWorkflowViewChange, state, workflowState }) {
  return (
    <header className="workflow-header border-b border-line/80 pb-3">
      <div className="grid gap-3 xl:grid-cols-[240px_minmax(0,1fr)] xl:items-end">
        <div className="min-w-0">
          <p className="text-xs font-semibold uppercase tracking-[0.14em] text-muted">{currentStepNumberLabel(activeWorkflowView)}</p>
          <h1 className="mt-1 text-lg font-semibold tracking-tight text-ink">Fitting Room</h1>
          <p className="mt-1 text-sm font-medium text-muted">{currentStepLabel(activeWorkflowView)}</p>
        </div>
        <WorkflowStepper
          activeWorkflowView={activeWorkflowView}
          confirmedProfile={confirmedProfile}
          onWorkflowViewChange={onWorkflowViewChange}
          state={state}
          workflowState={workflowState}
        />
      </div>
    </header>
  );
}

export function WorkflowStepper({ activeWorkflowView, confirmedProfile, onWorkflowViewChange, state, workflowState }) {
  return (
    <ol aria-label="Fitting progress" className="grid gap-2 sm:grid-cols-3">
      {workflowSteps.map((step, index) => {
        const status = stepStatus(step.key, activeWorkflowView, state, workflowState, confirmedProfile);
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
                  status === "locked" && "border-slate-200 bg-white text-slate-400",
                ]
                  .filter(Boolean)
                  .join(" ")}
              >
                {status === "complete" ? "Done" : index + 1}
              </span>
              <span className="truncate text-sm font-medium leading-5">{step.label}</span>
            </button>
          </li>
        );
      })}
    </ol>
  );
}

function ScanFirstFittingWorkflow({
  bodyMeasurements,
  captureLabel,
  confirmedProfile,
  fitIntent,
  mockSensorProfile,
  onBodyMeasurementChange,
  onCapturePhoto,
  onContinueToReview,
  onDetectProfileFromSensor,
  onFitIntentChange,
  onMockSensorProfileChange,
  onToggleOperatorSensor,
  operatorSensorOpen,
  pendingCaptureFile,
  profileEditorOpen,
  state,
  workflowState,
}) {
  return (
    <div className="grid gap-4 xl:grid-cols-[minmax(0,2fr)_minmax(280px,1fr)]">
      <LightScanStage
        captureLabel={captureLabel}
        confirmedProfile={confirmedProfile}
        onCapturePhoto={onCapturePhoto}
        onContinueToReview={onContinueToReview}
        pendingCaptureFile={pendingCaptureFile}
        state={state}
        workflowState={workflowState}
      />

      <aside className="grid content-start gap-3">
        <DetectedProfileReceipt
          confirmedProfile={confirmedProfile}
          pendingCaptureFile={pendingCaptureFile}
          workflowState={workflowState}
        />
        <DetectedProfileEditor
          bodyMeasurements={bodyMeasurements}
          confirmedProfile={confirmedProfile}
          fitIntent={fitIntent}
          onBodyMeasurementChange={onBodyMeasurementChange}
          onFitIntentChange={onFitIntentChange}
          profileEditorOpen={profileEditorOpen}
        />
        <OperatorSensorPanel
          mockSensorProfile={mockSensorProfile}
          onChange={onMockSensorProfileChange}
          onClose={onToggleOperatorSensor}
          onDetectProfileFromSensor={onDetectProfileFromSensor}
          operatorSensorOpen={operatorSensorOpen}
        />
      </aside>
    </div>
  );
}

function LightScanStage({
  captureLabel,
  confirmedProfile,
  onCapturePhoto,
  onContinueToReview,
  pendingCaptureFile,
  state,
  workflowState,
}) {
  const fileInputRef = useRef(null);
  const captureSourceRef = useRef("file_upload");
  const scanComplete = workflowState.scan === "scanComplete";
  const cameraStatus = getCameraStatus(workflowState);
  const profileReady = Boolean(confirmedProfile?.profileConfirmed);
  const canChooseGarments = scanComplete && profileReady && Boolean(pendingCaptureFile);
  const disabled = Boolean(state.scanBusy || state.fitLoading);

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
    <section className="scan-workspace rounded-lg bg-white shadow-[0_1px_2px_rgba(15,23,42,0.04)] ring-1 ring-line/80">
      <div className="scan-panel-header flex flex-col gap-2 px-4 py-3 sm:flex-row sm:items-center sm:justify-between sm:px-5">
        <div className="min-w-0">
          <h2 className="text-xl font-semibold tracking-tight text-ink">Scan shopper</h2>
          <p className="mt-1 text-sm text-muted">Stand on the mark and keep the full body inside the guide.</p>
        </div>
        <StatusBadge sourceText={cameraStatus} tone={scanComplete ? "success" : "neutral"}>
          <span className="scan-panel-status">{cameraStatus}</span>
        </StatusBadge>
      </div>

      <div className="px-4 pb-4 sm:px-5">
        <div className="scan-stage relative grid h-[390px] overflow-hidden rounded-lg bg-white ring-1 ring-line/80 sm:h-[430px] xl:h-[455px]">
          <input
            accept="image/*"
            className="sr-only"
            onChange={handleFileChange}
            ref={fileInputRef}
            type="file"
          />

          <div className="absolute inset-x-4 top-4 z-10 flex items-center justify-between gap-3">
            <StatusBadge tone={scanComplete ? "success" : "neutral"}>{captureLabel || cameraStatus}</StatusBadge>
            <span className="rounded-md border border-line bg-white px-2 py-1 text-xs font-medium text-muted">
              Camera frame
            </span>
          </div>

          <div className="relative mx-auto my-12 w-[min(70vw,330px)] rounded-[20px] border border-slate-200 bg-white">
            <div className="pointer-events-none absolute inset-y-7 left-1/2 w-px -translate-x-1/2 bg-slate-200" />
            <div className="pointer-events-none absolute inset-x-7 top-1/3 h-px bg-slate-200" />
            <div className="pointer-events-none absolute inset-x-7 top-2/3 h-px bg-slate-200" />
            <div className="relative mx-auto h-[270px] w-full sm:h-[322px]">
              <div className="absolute left-1/2 top-7 h-[54px] w-[54px] -translate-x-1/2 rounded-full border-2 border-slate-500 bg-white" />
              <div className="absolute left-1/2 top-[94px] h-[154px] w-[112px] -translate-x-1/2 rounded-b-[28px] rounded-t-[58px] border-2 border-slate-500 bg-white" />
              <div className="absolute left-1/2 top-[118px] h-[96px] w-[162px] -translate-x-1/2 rounded-[38px] border border-dashed border-slate-400" />
              <div className="absolute bottom-8 left-1/2 h-[68px] w-[86px] -translate-x-1/2 rounded-b-[36px] border-2 border-slate-500 bg-white" />
              <div className="absolute left-8 right-8 top-[158px] h-0.5 bg-brand-500" />
            </div>
          </div>

          <div className="absolute bottom-3 left-3 right-3 z-10 flex flex-col gap-2 rounded-md border border-line bg-white px-3 py-2 shadow-sm sm:flex-row sm:items-center sm:justify-between">
            <div>
              <p className="text-sm font-semibold text-ink">{scanComplete ? "Looks ready" : "Ready to capture"}</p>
              <p className="mt-0.5 text-xs text-muted">Height and weight are detected after capture.</p>
            </div>
            <div className="scan-action-row grid grid-cols-2 gap-2 sm:flex sm:shrink-0">
              <Button className="h-9 min-w-28 px-3 text-sm" disabled={disabled} onClick={() => openCapturePicker("kiosk_webcam")}>
                {state.scanBusy || state.fitLoading ? "Analyzing..." : scanComplete ? "Retake scan" : "Start scan"}
              </Button>
              <Button className="h-9 min-w-28 px-3 text-sm" disabled={disabled} onClick={() => openCapturePicker("file_upload")} variant="secondary">
                Upload photo
              </Button>
              {canChooseGarments && (
                <Button className="col-span-2 h-9 min-w-32 px-3 text-sm sm:col-span-1" onClick={onContinueToReview} variant="secondary">
                  Choose garments
                </Button>
              )}
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

function DetectedProfileReceipt({ confirmedProfile, pendingCaptureFile, workflowState }) {
  const profileReady = Boolean(confirmedProfile?.profileConfirmed);
  const scanComplete = workflowState.scan === "scanComplete";

  return (
    <section
      className="detected-profile-receipt rounded-lg bg-white p-4 shadow-[0_1px_2px_rgba(15,23,42,0.04)] ring-1 ring-line/80"
      data-detected-profile-receipt="true"
    >
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="text-sm font-semibold text-ink">Detected profile</h3>
          <p className="mt-1 text-sm leading-5 text-muted">
            {profileReady ? "Profile confirmed" : scanComplete ? "Confirm once before choosing garments." : "Scan unlocks the shopper profile."}
          </p>
        </div>
        <StatusBadge tone={profileReady ? "success" : "neutral"}>
          {profileReady ? "Looks ready" : workflowStateLabels[workflowState.scan]}
        </StatusBadge>
      </div>
      <div className="mt-4 grid grid-cols-2 gap-2">
        <MetricBlock label="Height" value={confirmedProfile?.heightCm ? `${confirmedProfile.heightCm} cm` : "-"} />
        <MetricBlock label="Weight" value={confirmedProfile?.weightKg ? `${confirmedProfile.weightKg} kg` : "-"} />
      </div>
      <p className="mt-3 text-xs font-medium text-muted">
        {pendingCaptureFile ? "Shopper image ready for garment selection." : "Capture is required before product selection."}
      </p>
    </section>
  );
}

function DetectedProfileEditor({
  bodyMeasurements,
  confirmedProfile,
  fitIntent,
  onBodyMeasurementChange,
  onFitIntentChange,
  profileEditorOpen,
}) {
  const heightValue = bodyMeasurements?.heightCm || confirmedProfile?.heightCm || "";
  const weightValue = bodyMeasurements?.weightKg || confirmedProfile?.weightKg || "";

  return (
    <section className="rounded-lg bg-white p-4 shadow-[0_1px_2px_rgba(15,23,42,0.04)] ring-1 ring-line/80">
      <div className="flex items-center justify-between gap-3">
        <h3 className="text-sm font-semibold text-ink">Edit profile</h3>
        <span className="text-xs font-semibold text-muted">{profileEditorOpen ? "Open" : "Confirm once"}</span>
      </div>
      <div className="mt-3 grid grid-cols-2 gap-2">
        <label className="grid gap-1 text-xs font-semibold text-muted" htmlFor="profile-height-cm">
          Height
          <input
            className="h-9 rounded-md border border-line bg-white px-2 text-sm font-medium text-ink outline-none focus:border-brand-500 focus:ring-2 focus:ring-brand-100"
            id="profile-height-cm"
            inputMode="decimal"
            min="1"
            onChange={(event) => onBodyMeasurementChange?.("heightCm", event.target.value)}
            placeholder="cm"
            type="number"
            value={heightValue}
          />
        </label>
        <label className="grid gap-1 text-xs font-semibold text-muted" htmlFor="profile-weight-kg">
          Weight
          <input
            className="h-9 rounded-md border border-line bg-white px-2 text-sm font-medium text-ink outline-none focus:border-brand-500 focus:ring-2 focus:ring-brand-100"
            id="profile-weight-kg"
            inputMode="decimal"
            min="1"
            onChange={(event) => onBodyMeasurementChange?.("weightKg", event.target.value)}
            placeholder="kg"
            type="number"
            value={weightValue}
          />
        </label>
      </div>
      <div className="mt-3">
        <FitIntentSelect disabled={false} onChange={onFitIntentChange} value={fitIntent || confirmedProfile?.fitIntent || "regular"} />
      </div>
    </section>
  );
}

function ProfileInput({ label, onChange, suffix, value }) {
  return (
    <label className="grid gap-1 text-xs font-semibold text-muted">
      {label}
      <span className="flex h-9 items-center gap-2 rounded-md border border-line bg-white px-2 text-sm font-medium text-ink">
        <input
          className="min-w-0 flex-1 bg-transparent outline-none"
          inputMode="decimal"
          onChange={(event) => onChange?.(event.target.value)}
          type="number"
          value={value}
        />
        <span className="text-xs font-semibold text-muted">{suffix}</span>
      </span>
    </label>
  );
}

function OperatorSensorPanel({ mockSensorProfile, onChange, onClose, onDetectProfileFromSensor, operatorSensorOpen }) {
  if (!operatorSensorOpen) {
    return null;
  }

  return (
    <section className="rounded-lg bg-white p-4 shadow-[0_1px_2px_rgba(15,23,42,0.04)] ring-1 ring-line/80">
      <div className="flex items-start justify-between gap-3">
        <div className="grid h-9 w-9 shrink-0 place-items-center rounded-md bg-slate-50 text-slate-700 ring-1 ring-line">
          <ScanIcon className="h-5 w-5" />
        </div>
        <div className="min-w-0">
          <h3 className="text-sm font-semibold text-ink">Operator sensor mock</h3>
          <p className="mt-1 text-sm leading-5 text-muted">
            Shift+S uses the mock sensor profile: {mockSensorProfile?.heightCm || "-"} cm, {mockSensorProfile?.weightKg || "-"} kg.
          </p>
          <p className="mt-1 text-xs font-medium text-muted">Sensor status: {mockSensorProfile?.sensorStatus || "ready"}</p>
        </div>
        <button className="text-sm font-semibold text-brand-700" onClick={onClose} type="button">
          Close
        </button>
      </div>
      <div className="mt-3 grid gap-2">
        <ProfileInput
          label="Mock height"
          onChange={(value) => onChange?.("heightCm", value)}
          suffix="cm"
          value={mockSensorProfile?.heightCm || ""}
        />
        <ProfileInput
          label="Mock weight"
          onChange={(value) => onChange?.("weightKg", value)}
          suffix="kg"
          value={mockSensorProfile?.weightKg || ""}
        />
      </div>
      <Button className="mt-3 w-full" onClick={() => onDetectProfileFromSensor?.("mock_sensor")} size="sm" variant="secondary">
        Detect profile
      </Button>
    </section>
  );
}

function PreparedGarmentPicker({
  confirmedProfile,
  garmentLabel,
  onOpenProduct,
  onSelectPreparedGarment,
  pendingCaptureFile,
  preparedGarments = [],
  preparedGarmentsStatus,
  state,
}) {
  const canChoose = Boolean(confirmedProfile?.profileConfirmed && pendingCaptureFile && !state.scanBusy && !state.fitLoading);
  const loading = preparedGarmentsStatus === "Loading";

  return (
    <section className="prepared-garment-picker rounded-lg bg-white p-5 shadow-[0_1px_2px_rgba(15,23,42,0.04)] ring-1 ring-line/80">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <p className="text-xs font-semibold uppercase tracking-[0.14em] text-muted">Choose garments</p>
          <h2 className="mt-1 text-xl font-semibold tracking-tight text-ink">Prepared products</h2>
          <p className="mt-1 max-w-2xl text-sm leading-6 text-muted">
            Select a product after the shopper scan. The backend session is created only for the chosen garment.
          </p>
        </div>
        <div className="grid gap-2 sm:min-w-[220px]">
          <DetectedProfileMini confirmedProfile={confirmedProfile} />
          <Button onClick={onOpenProduct} size="sm" variant="secondary">
            Products
          </Button>
        </div>
      </div>

      {!preparedGarments.length && !loading ? (
        <div className="mt-5 grid min-h-[260px] place-items-center rounded-lg border border-dashed border-line bg-white p-6 text-center">
          <div>
            <ProductIcon className="mx-auto h-7 w-7 text-slate-400" />
            <p className="mt-3 text-sm font-semibold text-ink">Prepared products appear here</p>
            <p className="mt-1 text-sm text-muted">Add products in the Products area before shopper sessions.</p>
          </div>
        </div>
      ) : (
        <div className="mt-5 grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {preparedGarments.map((garment) => {
            const selected = state.garmentId === garment.garment_id;
            const chartReady = Boolean(garment.size_chart_id || garment.size_chart?.length || garment.size_chart_name);
            const name = garment.name || "Prepared garment";
            const categoryLabel = formatCategoryLabel(garment.category || "tops");

            return (
              <button
                className={[
                  "grid min-h-[168px] gap-3 rounded-lg border bg-white p-4 text-left transition",
                  selected ? "border-brand-500 ring-2 ring-brand-100" : "border-line hover:border-slate-300 hover:bg-slate-50",
                  !canChoose && "cursor-not-allowed opacity-60",
                ]
                  .filter(Boolean)
                  .join(" ")}
                disabled={!canChoose}
                key={garment.garment_id}
                onClick={() => onSelectPreparedGarment?.(garment)}
                type="button"
              >
                <div className="flex min-w-0 items-start gap-3">
                  <div className="grid h-12 w-12 shrink-0 place-items-center rounded-md bg-slate-50 text-slate-600 ring-1 ring-line">
                    <ProductIcon className="h-6 w-6" />
                  </div>
                  <div className="min-w-0">
                    <p className="truncate text-sm font-semibold text-ink">{name}</p>
                    <p className="mt-1 text-sm text-muted">{categoryLabel}</p>
                  </div>
                </div>
                <div className="grid gap-1 text-sm">
                  <span className={chartReady ? "font-semibold text-emerald-700" : "font-semibold text-amber-700"}>
                    {chartReady ? "Size chart ready" : "Size chart missing"}
                  </span>
                  <span className="text-muted">{garment.size_chart_sizes || garmentLabel || "Select to start fitting"}</span>
                </div>
              </button>
            );
          })}
        </div>
      )}
    </section>
  );
}

function DetectedProfileMini({ confirmedProfile }) {
  return (
    <div className="grid min-w-[220px] gap-1 rounded-md border border-line bg-white px-3 py-2">
      <p className="text-xs font-semibold uppercase tracking-[0.12em] text-muted">Profile confirmed</p>
      <p className="text-sm font-semibold text-ink">
        {confirmedProfile?.heightCm || "-"} cm / {confirmedProfile?.weightKg || "-"} kg
      </p>
    </div>
  );
}

export function ReviewStep({
  confirmedProfile,
  fitIntent,
  garmentLabel,
  onAnalyzeFit,
  onFitIntentChange,
  onQueueTryOn,
  onTryAnotherGarment,
  state,
  tryOnLabel,
  workflowState,
}) {
  return (
    <div className="grid gap-4">
      <SelectedGarmentSummary compact garmentLabel={garmentLabel} state={state} />
      <div className="review-output-grid grid gap-4 xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
        <SizeRecommendationPanel
          confirmedProfile={confirmedProfile}
          fitIntent={fitIntent}
          onAnalyzeFit={onAnalyzeFit}
          onFitIntentChange={onFitIntentChange}
          state={state}
          workflowState={workflowState}
        />
        <TryOnPreviewPanel onQueueTryOn={onQueueTryOn} state={state} tryOnLabel={tryOnLabel} workflowState={workflowState} />
      </div>
      <ReviewActions
        onQueueTryOn={onQueueTryOn}
        onTryAnotherGarment={onTryAnotherGarment}
        state={state}
        workflowState={workflowState}
      />
    </div>
  );
}

export function SizeRecommendationPanel({ confirmedProfile, fitIntent, onAnalyzeFit, onFitIntentChange, state, workflowState }) {
  const recommendation = state.fitRecommendation || {};
  const recommendedSize = recommendation.recommended_size;
  const confidence = formatConfidence(recommendation.confidence);
  const selectedFitIntent = fitIntent || recommendation.preferred_fit || confirmedProfile?.fitIntent || "regular";
  const needsMeasurements = workflowState.fit === "fitNeedsMeasurements";
  const fitLocked = workflowState.fit === "fitLocked";
  const fitLoading = workflowState.fit === "fitLoading";
  const canUpdate = Boolean(state.capturePassed && state.garmentId && !state.fitLoading);
  const fitIntentNeedsUpdate = state.fitRecommendationStatus === "needs_update";
  const candidates = Array.isArray(recommendation.candidates) ? recommendation.candidates.slice(0, 3) : [];

  return (
    <section className="fit-recommendation-panel rounded-lg bg-white p-5 shadow-[0_1px_2px_rgba(15,23,42,0.04)] ring-1 ring-line/80">
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
        <FitIntentSelect disabled={!state.capturePassed || fitLoading} onChange={onFitIntentChange} value={selectedFitIntent} />
      </div>

      <div className="mt-4 grid grid-cols-2 gap-2">
        <MetricBlock label="Height" value={confirmedProfile?.heightCm ? `${confirmedProfile.heightCm} cm` : "-"} />
        <MetricBlock label="Weight" value={confirmedProfile?.weightKg ? `${confirmedProfile.weightKg} kg` : "-"} />
      </div>

      <p className="mt-4 rounded-md bg-slate-50 px-3 py-2 text-sm font-medium leading-5 text-ink">
        {state.fitRecommendationLabel || recommendation.reason || "Fit Intelligence uses the confirmed profile and selected garment size chart."}
      </p>

      <div className="mt-4 grid gap-2">
        <p className="text-xs font-semibold uppercase tracking-[0.12em] text-muted">Key measurements or deltas</p>
        {candidates.length ? (
          candidates.map((candidate) => (
            <div className="flex min-h-9 items-center justify-between gap-3 border-b border-line/70 py-1.5 last:border-b-0" key={candidate.size}>
              <span className="text-sm font-medium text-ink">Size {candidate.size}</span>
              <span className="text-sm text-muted">{formatConfidence(candidate.confidence)} match</span>
            </div>
          ))
        ) : (
          <p className="rounded-md bg-slate-50 px-3 py-2 text-sm leading-5 text-muted">
            Candidate deltas appear after the size chart and profile overlap.
          </p>
        )}
      </div>

      <Button
        className="mt-4 h-9 justify-center px-3 text-sm"
        disabled={!canUpdate || fitLocked || (!fitIntentNeedsUpdate && !needsMeasurements && Boolean(recommendedSize))}
        onClick={onAnalyzeFit}
        size="sm"
        variant={needsMeasurements ? "primary" : "secondary"}
      >
        {fitLoading ? "Updating..." : "Update recommendation"}
      </Button>
    </section>
  );
}

function FitIntentSelect({ disabled, onChange, value }) {
  return (
    <label className="grid gap-1 rounded-md bg-slate-50 px-3 py-2" htmlFor="fit-intent">
      <span className="text-xs font-semibold uppercase tracking-[0.12em] text-muted">Fit intent</span>
      <select
        className="h-8 rounded-md border border-line bg-white px-2 text-sm font-semibold text-ink outline-none transition focus:border-brand-500 focus:ring-2 focus:ring-brand-100 disabled:cursor-not-allowed disabled:bg-slate-100 disabled:text-slate-400"
        disabled={disabled}
        id="fit-intent"
        onChange={(event) => onChange?.(event.target.value)}
        value={value}
      >
        {fitIntentOptions.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    </label>
  );
}

export function TryOnPreviewPanel({ onQueueTryOn, state, tryOnLabel, workflowState }) {
  const previewReady = workflowState.tryOn === "tryOnReady";
  const tryOnGenerating = workflowState.tryOn === "tryOnGenerating";
  const fitReady = workflowState.fit === "fitReady";
  const canRequestTryOn = fitReady && !tryOnGenerating;

  return (
    <section className="tryon-review-panel rounded-lg bg-white p-5 shadow-[0_1px_2px_rgba(15,23,42,0.04)] ring-1 ring-line/80">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.12em] text-muted">Try-on review</p>
          <h2 className="mt-1 text-xl font-semibold tracking-tight text-ink">Try-on preview</h2>
        </div>
        <StatusBadge tone={previewReady ? "success" : tryOnGenerating ? "neutral" : "locked"}>
          {workflowStateLabels[workflowState.tryOn]}
        </StatusBadge>
      </div>

      <div className="tryon-result-stage mt-5 grid min-h-[420px] place-items-center rounded-lg bg-slate-50 p-4 ring-1 ring-line/70">
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
              <p className="text-sm font-semibold text-ink">{tryOnLabel || "Try-on preview ready"}</p>
            </div>
          )
        ) : (
          <div className="max-w-[280px] text-center">
            <DashboardIcon className="mx-auto h-6 w-6 text-slate-400" />
            <p className="mt-3 text-sm font-semibold text-ink">
              {tryOnGenerating ? "Generating try-on preview" : state.tryOnError || "Generate try-on from the current recommendation."}
            </p>
            {fitReady && <p className="mt-1 text-sm leading-5 text-muted">Create the visual review for this shopper and garment.</p>}
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

export function ReviewActions({ onQueueTryOn, onTryAnotherGarment, state, workflowState }) {
  const previewReady = workflowState.tryOn === "tryOnReady";
  const tryOnGenerating = workflowState.tryOn === "tryOnGenerating";
  const fitReady = workflowState.fit === "fitReady";
  const canRegenerate = fitReady && !tryOnGenerating;
  const canRequestTryOn = canRegenerate && !state.scanBusy;

  return (
    <section className="flex flex-col gap-2 rounded-lg bg-white px-4 py-3 shadow-[0_1px_2px_rgba(15,23,42,0.04)] ring-1 ring-line/80 sm:flex-row sm:items-center sm:justify-between">
      <div>
        <h3 className="text-sm font-semibold text-ink">Review actions</h3>
        <p className="mt-1 text-sm text-muted">
          {previewReady ? "Approve the output or regenerate the try-on with the current session data." : "Generate the try-on once the recommendation is ready."}
        </p>
      </div>
      <div className="flex flex-col gap-2 sm:flex-row">
        <Button onClick={onTryAnotherGarment} size="sm" variant="secondary">
          Try another garment
        </Button>
        <Button disabled={!previewReady} size="sm" variant="secondary">
          Approve result
        </Button>
        <Button disabled={!canRequestTryOn} onClick={onQueueTryOn} size="sm" variant={previewReady ? "secondary" : "primary"}>
          {tryOnGenerating ? "Generating..." : previewReady ? "Regenerate try-on" : "Generate try-on"}
        </Button>
      </div>
    </section>
  );
}

export function SelectedGarmentSummary({ compact = false, garmentLabel, state }) {
  const selected = Boolean(state.garmentId);
  const displayName = selected ? garmentLabel : "No garment selected";
  const categoryLabel = selected ? formatCategoryLabel(state.garmentCategory || "tops") : "Add products before shopper sessions";
  const garmentTypeLabel = state.garmentType ? state.garmentType.replaceAll("_", " ") : "";
  const chartLabel = getSizeChartLabel(state);

  return (
    <section
      className={[
        "selected-garment-context-bar rounded-lg bg-white shadow-[0_1px_2px_rgba(15,23,42,0.04)] ring-1 ring-line/80",
        compact ? "p-3" : "p-4",
      ].join(" ")}
      data-selected-garment-bar="visible-after-selection"
    >
      <div className="flex min-w-0 items-center gap-3">
        <div className={compact ? "grid h-10 w-10 shrink-0 place-items-center rounded-md bg-slate-50 text-slate-700 ring-1 ring-line/80" : "grid h-12 w-12 shrink-0 place-items-center rounded-md bg-slate-50 text-slate-700 ring-1 ring-line/80"}>
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
          <p className={state.sizeChartId ? "mt-1 truncate text-sm text-emerald-700" : "mt-1 truncate text-sm font-medium text-amber-700"}>
            {chartLabel}
          </p>
        </div>
      </div>
    </section>
  );
}

export function StatusBadge({ children, sourceText, tone = "neutral" }) {
  const tones = {
    dark: "bg-slate-900 text-white ring-slate-900",
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

function MetricBlock({ label, value }) {
  return (
    <div className="rounded-md bg-slate-50 px-3 py-2">
      <p className="text-xs font-semibold uppercase tracking-[0.12em] text-muted">{label}</p>
      <p className="mt-1 truncate text-sm font-semibold text-ink">{value}</p>
    </div>
  );
}

function currentStepLabel(activeWorkflowView) {
  if (activeWorkflowView === "scan") return "Scan shopper";
  if (activeWorkflowView === "garments") return "Choose garments";
  return "Review result";
}

function currentStepNumberLabel(activeWorkflowView) {
  if (activeWorkflowView === "scan") return "Step 1 of 3";
  if (activeWorkflowView === "garments") return "Step 2 of 3";
  return "Step 3 of 3";
}

function stepStatus(key, activeWorkflowView, state, workflowState, confirmedProfile) {
  if (key === activeWorkflowView) return "current";
  if (isStepComplete(key, state, workflowState, confirmedProfile)) return "complete";
  if (!isStepAvailable(key, state, confirmedProfile)) return "locked";
  return "available";
}

function isStepAvailable(key, state, confirmedProfile) {
  if (key === "scan") return true;
  if (key === "garments") return Boolean(state.capturePassed && confirmedProfile?.profileConfirmed);
  return Boolean(state.fitReady || state.fitRecommendation);
}

function isStepComplete(key, state, workflowState, confirmedProfile) {
  if (key === "scan") return Boolean(state.capturePassed && confirmedProfile?.profileConfirmed);
  if (key === "garments") return Boolean(state.garmentId);
  return workflowState.tryOn === "tryOnReady";
}

function resolveWorkflowView(view, state, confirmedProfile) {
  const normalized = {
    capture: "scan",
    fit: "review",
    garment: "garments",
    product: "garments",
    tryon: "review",
  }[view] || view;

  if (normalized === "review" && !state.fitReady && !state.fitRecommendation) {
    return state.capturePassed && confirmedProfile?.profileConfirmed ? "garments" : "scan";
  }
  if (normalized === "garments" && (!state.capturePassed || !confirmedProfile?.profileConfirmed)) return "scan";
  if (normalized === "scan" || normalized === "garments" || normalized === "review") return normalized;
  return state.fitReady || state.fitRecommendation
    ? "review"
    : state.capturePassed && confirmedProfile?.profileConfirmed
      ? "garments"
      : "scan";
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
  if (state.sizeChartName && state.sizeChartSizes) return `${state.sizeChartName} (${state.sizeChartSizes})`;
  if (state.sizeChartName) return state.sizeChartName;
  if (state.sizeChartId) return "Size chart ready";
  return "Size chart missing";
}

function formatConfidence(value) {
  if (typeof value !== "number" || Number.isNaN(value)) return "Not ready";
  return `${Math.round(value * 100)}%`;
}

function getCameraStatus(workflowState) {
  if (workflowState.scan === "scanComplete") return workflowStateLabels.scanComplete;
  if (workflowState.scan === "scanning") return workflowStateLabels.scanning;
  if (workflowState.scan === "scanReady") return workflowStateLabels.scanReady;
  return workflowStateLabels.scanNotStarted;
}

function getWorkflowState(state) {
  const scan = state.scanBusy
    ? "scanning"
    : state.capturePassed
      ? "scanComplete"
      : state.captureUploaded
        ? "scanReady"
        : "scanNotStarted";

  const fit = state.fitLoading
    ? "fitLoading"
    : state.fitReady
      ? "fitReady"
      : state.fitNeedsMeasurements
        ? "fitNeedsMeasurements"
        : "fitLocked";

  const tryOn = state.visualPreviewReady || state.previewKey || state.previewImageUrl
    ? "tryOnReady"
    : ["queued", "running", "processing"].includes(String(state.jobStatus || "").toLowerCase())
      ? "tryOnGenerating"
      : "tryOnLocked";

  return { fit, scan, tryOn };
}
