import importlib
import json
import sys
from pathlib import Path

from fastapi.testclient import TestClient


def test_kiosk_ui_is_served_from_fastapi(monkeypatch):
    app = _load_main_app(monkeypatch)
    client = TestClient(app)

    response = client.get("/kiosk/")

    assert response.status_code == 200
    assert "Visual Fitting Room" in response.text


def test_kiosk_ui_static_asset_is_served_from_fastapi(monkeypatch):
    app = _load_main_app(monkeypatch)
    client = TestClient(app)

    response = client.get("/kiosk/app.js")

    assert response.status_code == 200
    assert "javascript" in response.headers["content-type"]
    assert "FittingRoomApp" in response.text


def test_kiosk_ui_has_react_tailwind_source_app():
    package_json = json.loads(Path("ui/kiosk-app/package.json").read_text("utf-8"))
    app_source = Path("ui/kiosk-app/src/App.jsx").read_text("utf-8")
    tailwind_config = Path("ui/kiosk-app/tailwind.config.js").read_text("utf-8")

    assert package_json["dependencies"]["@vitejs/plugin-react"]
    assert package_json["dependencies"]["react"]
    assert package_json["dependencies"]["react-dom"]
    assert package_json["dependencies"]["tailwindcss"]
    assert "function FittingRoomApp" in app_source
    assert "AppSidebar" in app_source
    assert "AppHeader" in app_source
    assert "FittingWorkflow" in app_source
    assert "content: [\"./index.html\", \"./src/**/*.{js,jsx}\"]" in tailwind_config


def test_kiosk_ui_defines_reusable_component_surface():
    components_dir = Path("ui/kiosk-app/src/components")
    component_names = {path.stem for path in components_dir.glob("*.jsx")}

    assert {
        "Badge",
        "AppHeader",
        "AppSidebar",
        "Button",
        "Card",
        "FittingWorkflow",
        "Input",
        "Modal",
        "Table",
    }.issubset(component_names)


def test_kiosk_ui_mount_preserves_api_routes(monkeypatch):
    app = _load_main_app(monkeypatch)
    paths = {route.path for route in app.routes}

    assert "/api/v1/readiness" in paths
    assert "/kiosk" in paths


def test_kiosk_ui_uses_same_origin_default_for_runpod():
    app_js = Path("ui/kiosk-app/src/lib/api.js").read_text("utf-8")

    assert "resolveDefaultApiBase" in app_js
    assert "window.location.origin" in app_js
    assert "127.0.0.1:8080" in app_js


def test_kiosk_ui_loads_size_charts_for_product_selection():
    app_js = Path("ui/kiosk-app/src/App.jsx").read_text("utf-8")
    api_js = Path("ui/kiosk-app/src/lib/api.js").read_text("utf-8")
    workflow_source = Path("ui/kiosk-app/src/components/FittingWorkflow.jsx").read_text("utf-8")

    assert "listSizeCharts" in api_js
    assert '"/api/v1/kiosk/size-charts"' in api_js
    assert "uploadGarment" in api_js
    assert '"/api/v1/kiosk/garments"' in api_js
    assert "createSession" in api_js
    assert '"/api/v1/kiosk/sessions"' in api_js
    assert "sizeChartId" in app_js
    assert "sizeChartName" in app_js
    assert "setSizeCharts" in app_js
    assert "sizeChartId" in workflow_source
    assert "chartLabel" in workflow_source
    assert '"Size chart attached"' not in workflow_source


def test_kiosk_ui_wires_scan_upload_and_fit_analysis_to_backend():
    app_js = Path("ui/kiosk-app/src/App.jsx").read_text("utf-8")
    api_js = Path("ui/kiosk-app/src/lib/api.js").read_text("utf-8")
    workflow_source = Path("ui/kiosk-app/src/components/FittingWorkflow.jsx").read_text("utf-8")

    assert "uploadCapture" in api_js
    assert 'captures"' in api_js
    assert "analyzeCapture" in api_js
    assert 'captures/analyze"' in api_js
    assert "analyzeFit" in api_js
    assert 'fit/analyze"' in api_js
    assert "handleCapturePhoto" in app_js
    assert "capture_source" in api_js
    assert "size_recommendation" in app_js
    assert "onCapturePhoto" in workflow_source
    assert "fileInputRef" in workflow_source


def test_kiosk_ui_presents_mobile_first_virtual_fitting_app_shell():
    index_html = Path("ui/kiosk-demo/index.html").read_text("utf-8")
    app_source = Path("ui/kiosk-app/src/App.jsx").read_text("utf-8")

    assert 'data-app-shell="virtual-fitting-app"' in index_html
    assert 'id="root"' in index_html
    assert "applicationShell" in app_source
    assert "bottomNavigation" in app_source
    assert "diagnosticsDrawer" in app_source
    assert 'class="operator-workspace"' not in index_html
    assert 'class="session-dossier"' not in index_html


def test_kiosk_ui_has_screen_navigation_state_contract():
    app_js = Path("ui/kiosk-app/src/App.jsx").read_text("utf-8")

    assert "activeStage" in app_js
    assert "handleNavigationAction" in app_js
    assert "kioskActiveScreen" not in app_js
    assert "setActiveScreen" not in app_js
    assert "screenPanels" not in app_js
    assert "SettingsPanel" not in app_js
    assert "handlePrimaryAction" in app_js
    assert "kioskActiveStep" not in app_js
    assert 'garmentId: "local-demo-garment"' in app_js
    assert 'garmentName: "T-Shirt"' in app_js


def test_kiosk_ui_keeps_diagnostics_out_of_primary_surface():
    app_source = Path("ui/kiosk-app/src/App.jsx").read_text("utf-8")

    assert "diagnosticsDrawer" in app_source
    assert "apiBase" in app_source
    assert "eventLog" in app_source
    assert "<DiagnosticsDrawer" in app_source


def test_kiosk_ui_first_viewport_is_visual_fitting_room_not_status_dashboard():
    app_source = Path("ui/kiosk-app/src/App.jsx").read_text("utf-8")
    workflow_source = Path("ui/kiosk-app/src/components/FittingWorkflow.jsx").read_text("utf-8")
    combined_source = app_source + workflow_source

    assert 'data-workspace-shell="fitting-session-workspace"' in combined_source
    assert "FittingWorkflow" in combined_source
    assert "SelectedGarmentBar" in combined_source
    assert "ScanWorkspace" in combined_source
    assert "OperatorGuidancePanel" in combined_source
    assert "EmptyPreview" in combined_source
    assert "WorkflowStepper" in combined_source
    assert "Garment" in combined_source
    assert "Shopper scan" in combined_source
    assert "Fit result" in combined_source
    assert "Try-on" in combined_source
    assert "fitting-console-grid" in combined_source
    assert "Run a polished virtual fitting room" not in app_source
    assert "Application settings" not in app_source
    assert "Configure local development" not in app_source
    assert "Fitting performance" not in app_source
    assert "Recent sessions" not in app_source
    assert "overview-grid" not in app_source


def test_kiosk_ui_reads_as_product_application_not_operator_console():
    app_source = Path("ui/kiosk-app/src/App.jsx").read_text("utf-8")
    sidebar_source = Path("ui/kiosk-app/src/components/AppSidebar.jsx").read_text("utf-8")
    workflow_source = Path("ui/kiosk-app/src/components/FittingWorkflow.jsx").read_text("utf-8")
    tailwind_config = Path("ui/kiosk-app/tailwind.config.js").read_text("utf-8")

    assert "product-application-shell" in app_source
    assert "Application navigation" in sidebar_source
    assert "ProductStrip" in workflow_source
    assert "MainFittingCanvas" in workflow_source
    assert "OperatorGuidancePanel" in workflow_source
    assert "OutputStatusList" in workflow_source
    assert "fitting-console-grid fitting-workflow-layout grid items-start gap-3 xl:grid-cols-[minmax(0,68fr)_minmax(320px,32fr)]" in workflow_source
    assert "Try-on preview" in workflow_source
    assert "Session flow" not in sidebar_source
    assert "Keep product, scan" not in sidebar_source
    assert "xl:grid-cols-[300px_minmax(0,1fr)_360px]" not in workflow_source
    assert 'indigo: {' in tailwind_config
    assert 'cyan: {' in tailwind_config
    assert 'canvas: "#F8FAFC"' in tailwind_config


def test_kiosk_ui_guides_real_fitting_workflow_with_product_components():
    app_source = Path("ui/kiosk-app/src/App.jsx").read_text("utf-8")
    sidebar_source = Path("ui/kiosk-app/src/components/AppSidebar.jsx").read_text("utf-8")
    header_source = Path("ui/kiosk-app/src/components/AppHeader.jsx").read_text("utf-8")
    workflow_source = Path("ui/kiosk-app/src/components/FittingWorkflow.jsx").read_text("utf-8")

    for component_name in (
        "AppSidebar",
        "AppHeader",
        "TopBar",
        "WorkflowStepper",
        "SelectedGarmentBar",
        "ScanWorkspace",
        "CameraCaptureFrame",
        "CaptureChecklist",
        "ChecklistItem",
        "OperatorGuidancePanel",
        "EmptyPreview",
        "StatusBadge",
    ):
        assert f"function {component_name}" in app_source + sidebar_source + header_source + workflow_source

    assert "Garment" in workflow_source
    assert "Shopper scan" in workflow_source
    assert "Fit result" in workflow_source
    assert "Try-on" in workflow_source
    assert "Position the shopper inside the frame, facing forward." in workflow_source
    assert "Full body visible" in workflow_source
    assert "Facing forward" in workflow_source
    assert "Good lighting" in workflow_source
    assert "Garment area visible" in workflow_source
    assert "Start scan" in workflow_source
    assert "Upload photo" in workflow_source
    assert "Preview unlocks after fit result." in workflow_source
    assert "fitting-workflow-layout" in workflow_source
    assert "workflow-step-current" in workflow_source
    assert "workflow-step-complete" in workflow_source
    assert "workflow-step-disabled" in workflow_source
    assert "Pending" not in workflow_source


def test_kiosk_ui_prioritizes_scan_workspace_over_demo_dashboard_cards():
    app_source = Path("ui/kiosk-app/src/App.jsx").read_text("utf-8")
    sidebar_source = Path("ui/kiosk-app/src/components/AppSidebar.jsx").read_text("utf-8")
    header_source = Path("ui/kiosk-app/src/components/AppHeader.jsx").read_text("utf-8")
    workflow_source = Path("ui/kiosk-app/src/components/FittingWorkflow.jsx").read_text("utf-8")

    for component_name in (
        "AppShell",
        "Sidebar",
        "TopBar",
        "WorkflowHeader",
        "WorkflowStepper",
        "SelectedGarmentBar",
        "ScanWorkspace",
        "CameraCaptureFrame",
        "CaptureChecklist",
        "OperatorGuidancePanel",
        "OutputStatusList",
        "StatusBadge",
        "EmptyPreview",
    ):
        assert f"function {component_name}" in app_source + sidebar_source + header_source + workflow_source

    assert "Guided fitting session" not in workflow_source
    assert "Step 2 of 4 · Shopper scan" in workflow_source
    assert "operator-workspace-layout" in workflow_source
    assert "selected-garment-context-bar" in workflow_source
    assert "operator-guidance-panel" in workflow_source
    assert "Capture shopper photo" in workflow_source
    assert "Position the shopper inside the frame, facing forward." in workflow_source
    assert "Photo checklist" in workflow_source
    assert "Start a shopper scan to unlock fit recommendation and try-on preview." in workflow_source
    assert "Preview unlocks after fit result." in workflow_source
    assert "Garment: Ready" in workflow_source
    assert "Shopper scan: Not started" in workflow_source
    assert "Fit recommendation: Locked" in workflow_source
    assert "Try-on preview: Locked" in workflow_source
    assert "scanNotStarted" in workflow_source
    assert "scanReady" in workflow_source
    assert "scanning" in workflow_source
    assert "scanComplete" in workflow_source
    assert "fitLocked" in workflow_source
    assert "fitLoading" in workflow_source
    assert "fitReady" in workflow_source
    assert "tryOnLocked" in workflow_source
    assert "tryOnGenerating" in workflow_source
    assert "tryOnReady" in workflow_source
    assert "Sessions" in sidebar_source
    assert "Products" in sidebar_source
    assert "Fitting Room" in sidebar_source
    assert "History" in sidebar_source
    assert "Settings" in sidebar_source
    assert "Fitting workflow" not in sidebar_source
    assert "String(index + 1).padStart" not in sidebar_source
    assert "Fit result will appear here" not in workflow_source
    assert "Preview area" not in workflow_source
    assert "onPrimaryAction" not in workflow_source


def test_kiosk_ui_rebuild_removes_demo_dashboard_fragments():
    app_source = Path("ui/kiosk-app/src/App.jsx").read_text("utf-8")
    header_source = Path("ui/kiosk-app/src/components/AppHeader.jsx").read_text("utf-8")
    sidebar_source = Path("ui/kiosk-app/src/components/AppSidebar.jsx").read_text("utf-8")
    workflow_source = Path("ui/kiosk-app/src/components/FittingWorkflow.jsx").read_text("utf-8")

    assert "data-selected-garment-bar" in workflow_source
    assert "scan-action-row" in workflow_source
    assert "operator-preview-placeholder" in workflow_source
    assert "selected-garment-context-bar" in workflow_source
    assert "Session active" in header_source
    assert "Sessions" in sidebar_source
    assert "Products" in sidebar_source
    assert "Fitting Room" in sidebar_source
    assert "History" in sidebar_source
    assert "Settings" in sidebar_source

    assert "Selected garment context" not in workflow_source
    assert "Guided scan marked ready" in app_source
    assert "Run a polished virtual fitting room" not in app_source
    assert "Fitting performance" not in app_source


def test_kiosk_ui_density_pass_keeps_primary_scan_task_above_the_fold():
    workflow_source = Path("ui/kiosk-app/src/components/FittingWorkflow.jsx").read_text("utf-8")

    assert "scan-panel-header" in workflow_source
    assert "scan-panel-status" in workflow_source
    assert "scan-action-row" in workflow_source
    assert "Photo checklist" in workflow_source
    assert "sticky top-20 grid self-start" in workflow_source
    assert "xl:grid-cols-[minmax(0,68fr)_minmax(320px,32fr)]" in workflow_source
    assert "sm:h-[420px]" in workflow_source
    assert "Preview unlocks after fit result." in workflow_source
    assert workflow_source.count('"Start scan"') == 1

    assert "Quality checklist" not in workflow_source
    assert "Fit recommendation unlocks after a successful scan." not in workflow_source
    assert "2xl:grid-cols-[minmax(0,1fr)_280px]" not in workflow_source
    assert "sm:min-h-[460px]" not in workflow_source
    assert "sm:min-h-[600px]" not in workflow_source
    assert "Preview will appear here after scan." not in workflow_source


def test_kiosk_ui_exposes_tryon_generation_loading_action():
    workflow_source = Path("ui/kiosk-app/src/components/FittingWorkflow.jsx").read_text("utf-8")

    assert "onQueueTryOn" in workflow_source
    assert "Generate try-on" in workflow_source
    assert "Generating..." in workflow_source
    assert "Generating try-on preview" in workflow_source
    assert "tryOnGenerating" in workflow_source
    assert "disabled={!canGenerateTryOn || tryOnGenerating}" in workflow_source


def test_kiosk_ui_hides_technical_identifiers_from_primary_ui():
    app_js = Path("ui/kiosk-app/src/lib/displayLabels.js").read_text("utf-8")

    assert "displaySessionLabel" in app_js
    assert "displayGarmentLabel" in app_js
    assert "displayCaptureLabel" in app_js
    assert 'summarySession.textContent = hasSession ? shortId(state.sessionId)' not in app_js
    assert 'summaryGarment.textContent = hasGarment ? `${state.garmentName || "Garment"} (${shortId(state.garmentId)})`' not in app_js
    assert 'captureSourceLabel' not in app_js


def test_kiosk_ui_distinguishes_unready_api_from_offline():
    app_js = Path("ui/kiosk-app/src/lib/api.js").read_text("utf-8")

    assert "ApiRequestError" in app_js
    assert "error.status === 503" in app_js
    assert "Not ready" in app_js


def _load_main_app(monkeypatch):
    monkeypatch.setenv("DEBUG", "true")
    monkeypatch.setenv("API_PROFILE", "kiosk")
    monkeypatch.setenv("KIOSK_UI_ENABLED", "true")
    monkeypatch.setenv("KIOSK_UI_PATH", "/kiosk")

    for module_name in ("src.main", "src.config.settings"):
        sys.modules.pop(module_name, None)

    settings_module = importlib.import_module("src.config.settings")
    settings_module._settings = None
    main_module = importlib.import_module("src.main")
    return main_module.app
