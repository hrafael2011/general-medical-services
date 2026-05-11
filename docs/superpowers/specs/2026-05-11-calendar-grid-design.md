# Calendar Grid — Redesign to Calendar Layout

**Date:** 2026-05-11  
**Author:** Brainstorming session with user  
**Status:** Draft  

## Problem

The current `CalendarGrid` renders as a table with **rows = service areas** and **columns = days of the month**. This produces excessive horizontal scroll (up to 31+ columns), and the visual does not resemble a real calendar, making it unintuitive for shift assignment management.

## Solution

Replace the table layout with a **wall-calendar-style CSS Grid**: 7 columns (Mon–Sun), rows = weeks of the month. Each day cell aggregates *all* assignments for that day, color-coded by service area.

## Scope Boundary

**Only the visual layout of CalendarGrid.tsx changes.** Everything listed under "What stays the same" is explicitly out of scope for this spec.

### What stays the same

| Item | File(s) | Why |
|------|---------|-----|
| API shape (`CalendarGridResponse`, `DaySlot`) | `api/calendars.ts` | Data model unchanged |
| All mutations (assign, remove, approve, generate, new-version) | `CalendarGrid.tsx` | Business logic unchanged |
| Modals (`AssignDoctorModal`, `RemoveAssignmentPopover`) | `features/calendars/` | Interaction unchanged |
| Header buttons and status badge | `CalendarGrid.tsx` | Visual/layout only change |
| Doctor data fetching and area mapping | `CalendarGrid.tsx` | Data flow unchanged |
| Gaps / summary display | `CalendarGrid.tsx` | Unchanged |
| Service area logic and CRUD | Everywhere | Not touched |
| Model, migration, backend | Everywhere | Not touched |

### What changes

| File | Change |
|------|--------|
| `frontend/src/features/calendars/CalendarGrid.tsx` | Rewrite the `<table>` render block to a 7-column CSS Grid. Reorganize slot → day grouping logic. |
| `frontend/src/styles.css` | Add calendar grid CSS classes (7-column grid, day cell, area badge, day number, "+ Asignar" link). |

## Design Details

### Layout

```
┌────────────────────────────────────────────────────────────────┐
│ ← Volver  Calendario Mayo 2026 — Versión 1          [Borrador] │
│ [Generar calendario] [Aprobar]                                 │
├────────────────────────────────────────────────────────────────┤
│  Lun    Mar    Mié    Jue    Vie    Sáb    Dom                │
├──────┬──────┬──────┬──────┬──────┬──────┬──────┤
│      │      │      │   1  │   2  │   3  │   4  │
│      │      │      │      │      │      │      │
├──────┼──────┼──────┼──────┼──────┼──────┼──────┤
│   5  │   6  │   7  │   8  │   9  │  10  │  11  │
│      │      │      │      │      │      │      │
├──────┼──────┼──────┼──────┼──────┼──────┼──────┤
│  12  │  13  │  14● │  15  │  16  │  17  │  18  │
│      │      │ CABO │      │      │      │      │
│      │      │ PÉREZ│      │      │      │      │
│      │      │  +   │      │      │      │      │
├──────┼──────┼──────┼──────┼──────┼──────┼──────┤
│  19  │  20  │  21  │  22  │  23  │  24  │  25  │
├──────┼──────┼──────┼──────┼──────┼──────┼──────┤
│  26  │  27  │  28  │  29  │  30  │  31  │      │
└──────┴──────┴──────┴──────┴──────┴──────┴──────┘
```

### Day Cell Anatomy

```
┌─────────────────────┐
│ 14                  │  ← day number (bold ~13px) top-left
│                     │
│ 🔴 SARENTO         │  ← Emergencia (color + doctor)
│    NUÑEZ, ARIANNE   │
│ 🔵 — — —           │  ← Pista (empty area, clickable)
│ 🟢 CABO PÉREZ      │  ← Disponible (color + doctor)
│    JUAN             │
│                     │
│ ─ ─ ─ ─ ─ ─ ─ ─ ─ │  ← dashed separator
│  + Asignar          │  ← opens area picker, then AssignDoctorModal
└─────────────────────┘
```

- **3 area rows per day cell**, one per service area (Emergencia, Pista, Disponible)
- **Area row with assignment:** colored dot + `RANGO APELLIDOS, NOMBRE` — click → `RemoveAssignmentPopover`
- **Area row without assignment:** colored dot + `— — —` — click → `AssignDoctorModal(date=day, area=this_area)`
- **"+ Asignar" at bottom:** opens a small inline area picker (3 options), then opens `AssignDoctorModal` with the selected area and date
- **Area colors:**  
  - Emergencia → 🔴 red dot `#dc2626` / background `#fee2e2`  
  - Pista → 🔵 blue dot `#2563eb` / background `#dbeafe`  
  - Disponible → 🟢 green dot `#16a34a` / background `#d1fae5`
- **Doctor format:** `RANGO APELLIDOS, NOMBRE` (e.g. "CABO NUÑEZ MENDEZ, ARIANNE")
- **Overflow:** If day cell height exceeded, clip with `overflow: hidden` — only 3 areas exist, so overflow should not occur in practice
- **Day number:** Left/top aligned, bold. Days outside month have `color: #d1d5db` (faded)

### Interactions

| Action | Behavior | Same as before? |
|--------|----------|-----------------|
| Click empty area row (`— — —`) | Opens `AssignDoctorModal` with that date + area pre-set | ✅ Same flow |
| Click on doctor/assignment | Opens `RemoveAssignmentPopover` for that assignment | ✅ Same |
| "+ Asignar" click | Opens inline area picker (3 buttons: E / P / D), then `AssignDoctorModal` | 🆕 New |
| Days without any assignments | Show 3 rows of `— — —`, all clickable to assign | 🆕 New |
| "Generar" / "Aprobar" buttons | Unchanged behavior | ✅ Same |
| "← Volver" | Navigate back to calendar list | ✅ Same |

### Technical Implementation

**Data restructuring (in component render, no API change):**

```typescript
// Current: flat slots array
// [{service_date: "2026-05-14", service_area_id: "area1", assignment: {...}}, ...]

// New: grouped by day
interface DayAssignments {
  date: string;
  day: number;        // 1-31
  dayOfWeek: number;  // 0=Sun, 1=Mon, ...
  slots: DaySlot[];   // all slots for this day
}

// Computed from:
// 1. month/year from calendar data
// 2. First day of month (getDay()) to determine offset
// 3. Slots grouped by service_date
```

**CSS Grid layout:**

```css
.calendar-grid {
  display: grid;
  grid-template-columns: repeat(7, 1fr);
  gap: 1px;
  background: #e2e8f0;  /* grid lines */
}

.calendar-day-header {
  background: #f8fafc;
  text-align: center;
  font-weight: 700;
  font-size: 0.78rem;
  padding: 6px;
}

.calendar-cell {
  background: #fff;
  min-height: 90px;
  padding: 4px 6px;
  vertical-align: top;
}
```

**Week computation:**

```typescript
function buildCalendarWeeks(year: number, month: number, slots: DaySlot[]): DayAssignments[][] {
  const daysInMonth = new Date(year, month, 0).getDate();
  const firstDayOfWeek = new Date(year, month - 1, 1).getDay(); // 0=Sun
  // Map JS Sunday=0 to display Monday=0
  const offset = firstDayOfWeek === 0 ? 6 : firstDayOfWeek - 1;
  
  // Build empty grid cells for padding + each day
  // Group slots by date
}
```

### States

| State | Behavior |
|-------|----------|
| Loading | Show "Cargando grilla…" (existing) |
| Error | Show "Error al cargar el calendario." (existing) |
| Empty month (no slots) | Grid with empty day cells, each showing "+ Asignar" (draft) or "—" (approved) |
| Normal (some assignments) | Grid with mixed filled/empty cells |
| Overflow (4+ assign per day) | Show "y +N más" link |
| Approved version | Cells show "—" instead of "+ Asignar", no click interaction on empty cells |

### Error / Edge Cases

| Case | Handling |
|------|----------|
| Day with no slots | Empty cell, shows day number only + "+" or "—" |
| Unknown area ID | Falls back to area ID as text, neutral gray dot |
| Slot without assignment | Treated as empty cell |
| Month with <7 day offset | Empty cells (padded) before day 1 |
| Month ending mid-week | Empty cells after last day |
| Doctor name very long | CSS `overflow: hidden` + `text-overflow: ellipsis` |

### Testing

Tests in `CalendarGrid.test.tsx` need updates:

- Mock data restructured to include getDay/getDate dependency
- Assert grid structure instead of table structure
- Test: 7 day headers rendered
- Test: day numbers in correct positions
- Test: assignments shown in day cells with correct colors
- Test: overflow "y +N más" shown when >3 assignments
- Test: click opens correct modal
- Test: month with variable weekday start (Monday, Wednesday, etc.)
- **No-padding days mix:** months starting on different weekdays exercise offset logic
- **Edge:** 28-day February, 31-day month, month spanning 6 weeks

## Implementation Order

1. Style classes in `styles.css` (calendar grid, day cell, area dot, "+ Asignar" link)
2. Helper functions in `CalendarGrid.tsx` (build weeks, group slots by day)
3. Render swap: `<table>` → CSS Grid
4. Update tests
5. Visual verification

## Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| Breaking existing modal/button interactions | Keep all state, handlers, and onClick wiring unchanged |
| Layout breaks on narrow screens | CSS grid auto-scales; test at 768px+ |
| Performance with many slots | Slots already loaded client-side; aggregation is O(n) |
