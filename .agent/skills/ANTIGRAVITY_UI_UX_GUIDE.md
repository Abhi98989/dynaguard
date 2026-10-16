# DynaGuard — Antigravity UI/UX Implementation Guide

> Project instruction file for the coding agent. Read before changing dashboard UI.
> This is a project design contract, not a claim that an external “UI UX Pro Max” skill is installed.

## 1. Mission and priority

Act as a senior product designer and frontend engineer. Make DynaGuard a calm, compact, professional QA workspace. Users should quickly understand the selected product, tested build, run status, failures, evidence, and next action.

User preferences are mandatory: minimal visual noise, consistent components, restrained shadows and corner radii, practical spacing, and no unnecessary widgets or empty areas. Minimal does not mean tiny text or crowded controls.

Read AGENTS.md, README.md, docs/SENIOR_QA.md, and relevant implementation files first. Follow repository instructions. Preserve existing authentication, API contracts, request protections, target restrictions, and truthful result semantics.

If an installed UI/UX skill is available, use its relevant guidance subject to this file and user instructions. Do not install a skill or dependency merely because its name resembles this document.

## 2. Current code and implementation approach

The inspected dashboard uses Next.js App Router, React, TypeScript, and plain CSS. Start with:

- `dashboard/app/page.tsx`
- `dashboard/app/style.css`
- `dashboard/app/engine-panel.tsx`
- `dashboard/app/qa-panel.tsx`
- `dashboard/app/layout.tsx`
- `dashboard/package.json`

Verify the current repository before editing; it may have changed. Reuse its stack. Do not migrate frameworks, add a UI framework, or introduce global state libraries solely for this redesign.

Current improvement targets include broad global element styles, a tall introductory section, stacked configuration panels, raw JSON as a primary interaction, and page-level state handling. Refactor incrementally without breaking working actions.

## 3. Visual direction

Use near-white surfaces, dark readable text, thin neutral borders, and one cobalt-blue action accent. Preserve the existing logo. No gradients, glass effects, neumorphism, decorative glows, oversized illustrations, or floating card stacks.

Use emphasis in this order: placement, typography, spacing, border, then color. Shadows are for overlays only. Do not wrap every group in a card. Prefer section headings and dividers for related content.

### Initial design tokens

Define these centrally as CSS custom properties; do not scatter near-identical values across components. These are starting values, not a substitute for browser contrast checks.

```css
:root {
  --canvas: #f8fafc;
  --surface: #ffffff;
  --surface-muted: #f1f5f9;
  --text: #0f172a;
  --text-secondary: #475569;
  --border: #e2e8f0;
  --control-border: #64748b;
  --accent: #1d4ed8;
  --accent-hover: #1e40af;
  --accent-subtle: #eff6ff;
  --success-text: #166534;
  --success-bg: #f0fdf4;
  --warning-text: #92400e;
  --warning-bg: #fffbeb;
  --danger-text: #b91c1c;
  --danger-bg: #fef2f2;
  --space-1: 4px;
  --space-2: 8px;
  --space-3: 12px;
  --space-4: 16px;
  --space-5: 20px;
  --space-6: 24px;
  --space-8: 32px;
  --radius-control: 6px;
  --radius-panel: 8px;
  --radius-badge: 4px;
  --shadow-overlay: 0 8px 24px rgb(15 23 42 / 12%);
}
```

- Default font: existing system sans-serif stack. No remote font dependency needed.
- Body and controls: 14–16px; secondary metadata: 12–13px; page title: 24–28px; section title: 16–18px.
- Body line height: approximately 1.5. Use 400, 500, and 600 weights consistently.
- Never use faint gray text for important status or instructions.
- Keep visible keyboard focus: approximately 2px outline with 2px offset.
- Use monospace for IDs, code, paths, and evidence only.
- Do not use pill shapes for every button and label.

## 4. Layout and density

- Desktop shell: compact navigation approximately 224px wide and a flexible content area with `min-width: 0`.
- Header: roughly 56–64px minimum height, allowed to grow when text wraps.
- Content padding: 24px desktop, 16px narrow screens.
- Panel padding: usually 16px; 20–24px only where content warrants it.
- Related control gaps: 8–12px. Section gaps: 20–24px.
- Avoid fixed content heights, huge minimum heights, spacer elements, and empty grid columns.
- Use content-driven sizing. Do not force every panel into equal heights.
- Full-height application shell is acceptable; individual sections must not use `100vh`.
- Use available width for data tables. Limit long prose and forms to readable line lengths.
- Keep project, environment, and build context visible near run actions.
- Replace the large dashboard hero with a concise page title, optional one-line description, and primary action.
- Summary metrics must answer a useful question and use real data. Do not add decorative counters or charts.

## 5. Information architecture

Organize the experience around these tasks, using existing routes or incremental navigation:

1. Select a project and environment.
2. Configure tests or a QA plan.
3. Start an available test execution.
4. Monitor runs and open results.
5. Inspect findings and evidence.
6. Retest fixes and compare outcomes.

Suggested destinations: Overview, Runs, Findings, QA Coverage, and Settings. Add a destination only when it contains a real working feature. Keep legacy fixture tooling in a clearly labeled secondary area.

Use progressive disclosure for advanced configuration and raw reports. Build structured forms for supported configuration fields while retaining an advanced JSON editor where necessary. Do not silently discard advanced fields when switching between form and JSON modes.

## 6. Reusable component contract

Create a small shared component set, adapting existing components first. Suggested location: `dashboard/components/ui/`; feature components may remain near their routes.

| Component | Required behavior |
| --- | --- |
| Button | Primary, secondary, ghost, danger; consistent size; loading and disabled states; explicit button type |
| Field | Visible label, help text, validation message, associated input ID |
| Input / Select / Textarea | Shared border, radius, font, focus, disabled, invalid behavior |
| StatusBadge | Text label plus semantic styling; no color-only meaning |
| SectionHeader | Title, optional short description, contextual actions |
| DataTable | Real table semantics, readable alignment, loading/empty/error states |
| EmptyState | Specific explanation and one relevant next action |
| InlineAlert | Actionable message; appropriate status or alert semantics |
| Dialog / Drawer | Accessible title, focus management, dismissal, focus restoration |
| EvidenceViewer | Masked content, wrapping/scrolling, safe copy and download when supported |

### Buttons and controls

- One visually dominant primary action per active task area.
- Use verbs: “Run tests”, “Create QA plan”, “View evidence”, “Retest fix”.
- Standard desktop controls: 36–40px minimum height; touch controls: at least 44px as a project target.
- Height must grow for wrapping text or enlarged fonts. Never clip labels.
- Horizontal button padding: usually 12–16px. Do not use oversized full-width desktop buttons without purpose.
- Icons: consistent family, 16–20px, with matching stroke weight. Avoid emoji as UI icons.
- Icon-only buttons require an accessible name and discoverable explanation.
- Pending buttons keep their width, show progress, and prevent duplicate submissions.
- Explain why an action is unavailable when the reason is not obvious.
- Confirm consequential destructive actions; do not add confirmation to routine navigation or saving.

### Tables and widgets

- Prefer rows for runs, findings, and coverage; cards only when content needs them.
- Align numbers consistently; render timestamps consistently with timezone context.
- Support long project names, IDs, URLs, and translated labels.
- Truncation must have an accessible way to reveal the full value; never hide critical error messages.
- Filters, pagination, sorting, and counts must operate on real data and accurately reflect their scope.
- No fake progress, sample charts presented as live data, dead buttons, or placeholder success states.

## 7. State management and data flow

Separate server data, local interaction state, form drafts, and shareable navigation state.

- Use local React state for local controls and drafts.
- Use URL state for shareable filters, selected detail views, or tabs when appropriate. Never put secrets in URLs.
- Extract typed data hooks and an API client where repeated logic warrants it.
- Use a reducer for complex related transitions; avoid conflicting booleans for one operation.
- Do not introduce Redux, Zustand, or a query library unless a demonstrated need justifies it.
- Every request-driven view needs explicit loading, success, empty, error, and refresh behavior.
- Keep mutation pending state per action or resource. One running test must not freeze unrelated navigation.
- Abort obsolete fetches or ignore their results using a request identity. A response for project A must not overwrite project B.
- On project change, clear or correctly scope dependent selections, evidence, errors, and subscriptions.
- Scope cached data by project, environment, and relevant filters. Clear sensitive data on logout.
- Preserve form input after recoverable failures; avoid overwriting dirty forms during polling.
- Poll only when useful, at bounded intervals; prevent overlapping requests, stop on unmount, and slow or pause when hidden as appropriate.
- Back off after failures and show stale/disconnected state. Keep prior data visible during background refresh when safe.
- Never optimistically mark a run successful, a finding fixed, or a release approved.
- Derive counts and status summaries from authoritative results rather than duplicating them in independent state.
- Surface expired authentication clearly; preserve only non-sensitive recoverable drafts.
- Display readable, sanitized API errors, never raw stack traces or credentials.

## 8. Truthful QA and security UX

The interface must preserve these distinctions:

| Situation | UI treatment |
| --- | --- |
| QA plan generated | “Plan created · tests not run” |
| Adapter unavailable | “Not implemented” or “Unavailable” with reason |
| Execution completed | Show actual check outcomes; completed does not mean passed |
| No findings | Explain coverage and incomplete checks; never imply the whole product is secure |
| Suspected issue | Clearly labeled as needing verification |
| Confirmed defect | Link to reproducible, masked evidence |
| Retest succeeds | Describe the specific tested fix and build |
| Required checks missing | Release status remains unevaluated or blocked according to implemented policy |

Keep run lifecycle, check outcome, finding severity, and finding lifecycle separate. Use backend states rather than inventing replacement semantics. Preserve queued, running, failed, passed, blocked, skipped, incomplete, cancelled, and not-run distinctions wherever supported.

Never display secrets from configuration, source scans, network traces, screenshots, or evidence. Client-side hiding alone does not secure data; preserve backend redaction and authorization.

## 9. Responsive and accessible interaction

- Design for narrow screens as well as desktop. Validate around 360, 768, 1280, and 1440px widths.
- Collapse navigation into an accessible menu/drawer when space is insufficient.
- Let toolbars wrap in a logical order. Do not squeeze controls into unreadable widths.
- Wide tables may scroll inside a labeled container; avoid whole-page horizontal overflow.
- Use semantic landmarks, a logical heading order, native controls, and keyboard navigation.
- Ensure visible focus, associated field labels, and programmatically connected validation messages.
- Use readable contrast; validate text, controls, status labels, and focus indicators rather than assuming token choices pass.
- Dialogs must manage focus correctly and restore focus to their trigger. Avoid nested dialogs.
- Announce relevant action results politely; do not announce every polling update.
- Essential actions must not depend on hover alone.
- Support 200% zoom and reduced motion. Do not use animation that delays actions.
- Transitions may be subtle, around 120–180ms; omit decorative motion and pulsing backgrounds.

## 10. Implementation workflow

1. Inspect the existing UI and working flows before editing.
2. Identify the concrete hierarchy, consistency, spacing, and state problems.
3. Define tokens and shared primitives first.
4. Refactor the application shell and one representative run/results flow.
5. Apply the same patterns to remaining screens; do not create a separate design language per page.
6. Preserve backend behavior and all working actions.
7. Add meaningful tests for changed interaction or state behavior, not tests that merely mirror CSS values.
8. Run the repository's available build and type checks.
9. Launch the UI and inspect it in a browser when available; capture representative desktop and mobile screenshots.
10. Report implemented changes, verification performed, and any unverified behavior honestly.

Do not stop with a mockup when implementation is requested. Do not claim browser verification if only the build ran. Do not remove a working capability to simplify the screenshot.

## 11. Acceptance checklist

### Visual consistency

- [ ] Shared tokens govern color, typography, spacing, radii, and control sizes.
- [ ] No decorative shadows, gradients, oversized hero, or nested card stacks.
- [ ] Buttons, fields, badges, tables, and dialogs follow shared contracts.
- [ ] Every visible widget has a clear user task or information purpose.
- [ ] Layout remains useful with both little data and many rows.

### Behavior and state

- [ ] Sign-in/out, project selection, configuration, runs, cancellation, findings, and retests still work where previously supported.
- [ ] Loading, empty, validation, failure, retry, and disabled states are intentional.
- [ ] Fast project switching cannot show another project's stale results.
- [ ] Repeated clicks cannot accidentally submit duplicate operations.
- [ ] Refreshing data does not erase an active form draft.
- [ ] Planned or unexecuted checks never appear passed.

### Browser verification

- [ ] Desktop and narrow-screen layouts inspected with long content.
- [ ] Keyboard-only navigation and visible focus checked.
- [ ] Zoom, contrast, dialogs, and form labels checked.
- [ ] No unexpected page overflow, clipped text, or inaccessible actions.
- [ ] No new console errors or broken requests in exercised flows.
- [ ] Build and TypeScript checks pass, or blockers are explicitly reported.

## 12. Agent start instruction

Read this file and repository instructions. Inspect the current dashboard, then implement the UI improvements directly using the existing stack. Prioritize the shell, shared components, run list, result details, and QA planning form. Keep the design minimal, compact, consistent, accessible, and honest about actual testing coverage. Validate working interactions and provide a concise change summary with screenshots when browser access is available.
