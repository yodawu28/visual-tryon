# Minimal Kiosk Sensor Flow Design

## Context

The current kiosk fitting room has been moving toward a three-step production
workflow. Coach feedback sharpened the product direction: garment setup should
feel like operator/catalog work, while the shopper-facing fitting room should
start with the shopper. The shopper should not have to enter height and weight
before scanning, and should not begin by managing product upload details. The
app should feel like an assisted fitting station: stand in the right place,
scan, confirm detected profile, choose prepared garments, then review the fit.

This design keeps the existing app concept, Fit Engine data contract, and local
try-on workflow. It changes the visible UX model and adds a demo-safe sensor
mock layer that can later be replaced by real hardware.

## Product Principle

The visible shopper experience is production direction. The sensor data source
is replaceable.

The operator sees:

1. Products/catalog setup.
2. Garment images, categories, and size chart readiness.
3. Optional mock sensor controls for demo/testing.

The shopper sees:

1. Stand and scan.
2. Confirm detected profile.
3. Choose a prepared garment.
4. Review size recommendation and try-on.
5. Try another prepared garment without rescanning.

The shopper does not see:

1. Height and weight fields before scan.
2. Operator-only mock sensor controls.
3. Product upload/setup forms inside the fitting flow.
4. Technical source labels unless editing or troubleshooting is needed.

## Approved Visual Direction

Use the v5 white-canvas direction:

- White page and white surfaces.
- Thin neutral outlines instead of gray cards.
- Strong near-black text for primary content.
- Minimal secondary gray text.
- One blue action color for primary actions.
- Scan area owns most of the screen.
- Confirmation is a compact receipt, not a dashboard.

Desktop scan layout target:

- Scan area: two-thirds of the workspace.
- Confirm receipt: one-third of the workspace.
- No large dark camera panel for the production baseline.
- Camera guide uses clear outline, center line, body guide, and floor marker.

## UX Flow

### Products / Operator Setup

Products becomes the operator/admin area for garment preparation.

The operator prepares the garment catalog before shopper sessions. This area
owns upload, category, garment type, and size chart readiness. It can show
operational details because it is not the shopper-facing flow.

Products setup is not a primary Fitting Room workflow step.

### Scan

The scan view becomes the main shopper moment.

Visible copy should be short:

- Heading: `Scan shopper`
- Guidance: `Stand on the mark. We will detect your fitting profile before choosing garments.`
- Primary action: `Start scan`

The camera/scan guide should be light and readable:

- White background.
- Thin outline frame.
- Visible body guide.
- Visible floor/standing marker.
- No dark dashboard-style camera frame by default.

After scan succeeds, the UI should show the compact detected profile receipt
beside the scan area.

Detected profile receipt:

- Heading: `Looks ready`
- Supporting text: `Confirm once. Use this profile for every garment in this session.`
- Rows:
  - Height
  - Weight
  - Fit
- Primary action: `Choose garments`
- Secondary action: `Edit profile`

The receipt should be small enough to feel like confirmation, not a form.

### Garment Selection

After scan/profile confirmation, the shopper or operator chooses a garment from
the prepared catalog.

This view should be simple and shopper-facing:

- Show prepared garments as compact tiles.
- Show only shopper-relevant readiness, such as `Size chart ready`.
- Keep setup actions secondary, for example a `Products` shortcut for operators.
- Selecting a garment should run or enable fit analysis and try-on for the
  confirmed scan/profile.

The session should support trying another garment without rescanning.

### Review

The review page remains the place for outputs:

- Left: size recommendation and explanation.
- Right: try-on preview.

Height and weight should not be shown as open input fields by default. If the
shopper edited detected profile values, review can show a compact measurement
source note such as `Profile confirmed`.

Review should include a clear way to try another prepared garment with the same
scan/profile.

## Sensor Mock Model

Use operator-controlled mock sensor values for the current demo phase.

Recommended operator control:

- Hidden keyboard shortcut, for example `Shift + S`.
- Reveals a compact operator-only panel.
- Panel fields:
  - Mock height fallback in cm.
  - Mock weight in kg.
  - Sensor status: ready, reading, unavailable.
  - Apply reading.

The shopper-facing flow should present the result as a detected profile. It
should not expose that weight came from an operator mock unless diagnostics are
open.

## Data Model

Keep the existing Fit Engine payload shape for compatibility:

- `height_cm`
- `weight_kg`
- `preferred_fit`
- selected garment id/category/size chart from the existing catalog/session
  state

Add UI/session metadata around the source:

- `profileSource`: `mock_sensor`, `camera_estimate`, `manual_override`, or
  `unknown`.
- `profileConfirmed`: boolean.
- `profileEditable`: boolean.
- `sensorStatus`: `ready`, `reading`, `detected`, `unavailable`, or `error`.

For the first implementation, height can use the operator fallback or current
scan-derived estimate when available. Weight uses the operator mock value. If
the shopper edits either value, set `profileSource` to `manual_override`.

## Component Direction

Refactor the current scan and fit input UI into smaller focused components:

- `ScanFirstFittingWorkflow`
  - Makes scan the first shopper-facing Fitting Room step.
  - Keeps Products as catalog/operator setup.
- `DetectedProfileReceipt`
  - Read-only compact height, weight, and fit intent summary.
  - Choose garments and Edit profile actions.
- `DetectedProfileEditor`
  - Small edit state shown only after the shopper/operator clicks Edit.
  - Contains height, weight, and fit intent controls.
- `OperatorSensorPanel`
  - Hidden by default.
  - Provides mock sensor values for demo/testing.
- `LightScanStage`
  - Replaces the dark scan panel with the white-canvas guide.
- `PreparedGarmentPicker`
  - Shows prepared catalog garments after scan/profile confirmation.
  - Keeps upload/setup actions out of the shopper path.

Existing `SizeRecommendationPanel` should stop rendering height and weight
inputs by default. It should consume the confirmed profile from app state.

## Error Handling

If scan succeeds but profile values are missing:

- Show the compact receipt with `Needs confirmation`.
- Primary action remains disabled until values are available or edited.
- Secondary action `Edit` opens the editor.

If sensor mock is unavailable:

- Shopper copy: `Profile needs confirmation.`
- Operator/debug copy can mention sensor unavailable.

If Fit Engine returns insufficient measurements:

- Review page should show the recommendation issue.
- Provide a small `Edit profile` action rather than exposing fields inline.

If no prepared garments exist:

- Fitting Room should show a concise empty state after scan confirmation.
- Primary operator action should route to Products.
- It should not ask the shopper to upload a garment in the fitting flow.

## Accessibility And Readability

- Primary body text should be readable at kiosk distance.
- Avoid low-contrast gray on gray.
- Do not rely on color alone for status.
- Buttons should have stable dimensions.
- Confirmation values should use labels and explicit units.
- Mobile layout stacks scan above profile receipt.

## Testing

Frontend/static tests should verify:

- Height and weight fields are not visible by default in the review panel.
- Detected profile receipt appears after scan success.
- Edit opens height, weight, and fit intent controls.
- Operator sensor panel is hidden by default.
- Mock sensor values populate the Fit Engine payload.
- Fitting Room starts with scan, not garment upload.
- Garment setup/upload remains in Products/operator area.
- Prepared garment picker appears only after scan/profile confirmation.

Interaction tests should verify:

- Scan -> profile confirm -> garment select -> review is the primary path.
- Manual override still sends `height_cm`, `weight_kg`, and `preferred_fit`.
- Review can re-run fit recommendation after profile edits.
- A confirmed scan/profile can be reused to try another prepared garment.

Visual QA should verify:

- Desktop 1440px uses the 2:1 scan-to-confirm balance.
- Text remains readable on the white-canvas layout.
- Mobile stacks without overflow.

## Out Of Scope

This design does not implement real weight hardware, calibrated height
estimation, or a new measurement model. Those can replace the mock sensor source
later without changing the shopper-facing flow.
