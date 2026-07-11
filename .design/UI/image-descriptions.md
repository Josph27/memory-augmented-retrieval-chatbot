# Braemon UI — Image Descriptions

**Source**: Google Stitch project "Multi-Tier Memory RAG System" (ID: 17357896729539425790)
**Design System**: Braemon (Dark Theme)
**Generated**: 2026-07-08

---

## Design System: Braemon

### Color Palette

| Role | Name | Hex | Usage |
|------|------|-----|-------|
| Base canvas | Space Indigo | `#22223b` | Page backgrounds, primary container |
| Card surfaces | Dusty Grape | `#4a4e69` | Cards, rows, secondary surfaces |
| Borders/icons | Lilac Ash | `#9a8c98` | 1px borders, icons, disabled states |
| Accent/CTA | Almond Silk | `#c9ada7` | Primary buttons, active states, focus |
| Text | Parchment | `#f2e9e4` | All body text, headlines |
| Deep surface | Near-black | `#131315` | Deepest background layers |
| Surface variant | — | `#353436` | Variant surface for depth |
| Outline variant | — | `#47464d` | Subtle outlines |
| Logo accent | Vibrant Purple | `#6b5b95` | Only saturated element — logo mark |
| Error | — | `#ffb4ab` | Error states |
| Error container | — | `#93000a` | Error backgrounds |

### Typography (All Inter)

| Token | Size | Weight | Line Height | Tracking |
|-------|------|--------|-------------|----------|
| Display | 32px | 600 | 40px | -0.02em |
| Headline LG | 24px | 600 | 32px | -0.01em |
| Headline MD | 20px | 500 | 28px | — |
| Body LG | 16px | 400 | 24px | — |
| Body MD | 14px | 400 | 20px | — |
| Body SM | 13px | 400 | 18px | — |
| Label MD | 12px | 600 | 16px | +0.02em |
| Label SM | 11px | 500 | 14px | — |
| Code | 13px | 400 | 20px | — |

### Spacing (4px Base Grid)

| Token | Value |
|-------|-------|
| xs | 4px |
| sm | 8px |
| md | 12px |
| lg | 16px |
| xl | 24px |
| gutter | 12px |
| margin | 20px |

### Shape

- Corner radius: 4px (sharp/subtle) for buttons, inputs, small widgets
- Max 8px for larger containers
- No shadows — depth via tonal layers + 1px hairline borders
- "Blueprint" or "technical drawing" aesthetic

---

## Core Design Rules

### 1. No Chat Bubbles

Messages are rendered as **left-aligned data logs**, not traditional chat bubbles. Each message row has:

- A **2px vertical "Edge Marker"** on the far left of the row
- User messages: Almond Silk (`#c9ada7`) marker
- System/assistant messages: Lilac Ash (`#9a8c98`) marker
- Messages aligned to a grid, not floating
- No rounded containers around message text

### 2. Tonal Depth (No Shadows)

Depth is communicated through luminance layers, not box-shadows:

- **Level 0 (Base)**: Space Indigo `#22223b`
- **Level 1 (Cards/Rows)**: Dusty Grape `#4a4e69` with 1px Lilac Ash border at 20% opacity
- **Level 2 (Modals/Popovers)**: Dusty Grape `#4a4e69` with 1px Almond Silk border at 30% opacity
- 1px hairlines separate sections
- Hover states: subtle background shift to Dusty Grape

### 3. Navigation — Slim Top Bar or Fixed Side Rail

- No search inputs or profile avatars in the main header
- Metadata and system status in a **bottom "status bar"** using Label-SM typography
- Active page highlighted, others in muted Lilac Ash

### 4. Compact Density

- Rows: max 40px height for single-line content
- 1px dividers in Lilac Ash at 10% opacity between rows
- Components prioritize horizontal stacking
- Thin vertical footprints to maximize visible rows

### 5. Buttons

- Compact: 8px top/bottom, 16px left/right padding
- **Primary**: Almond Silk (`#c9ada7`) fill, Space Indigo text
- **Secondary**: Lilac Ash outline, transparent background
- 4px border radius

### 6. Input Fields

- 1px border (Lilac Ash for default)
- Focus: border shifts to Almond Silk
- Background slightly darker than parent ("inset" feel)
- Rectangular, 4px radius

### 7. Logo

- 32×32 pixel perfect square
- Vibrant Purple `#6b5b95` — the ONLY high-saturation element
- Acts as a visual anchor in the dark interface

---

## Screens

### Screen 1: Braemon Home — Unified Header

**Purpose**: Landing page with new chat creation

**Layout**:

- Unified header at top (present on all screens)
- Central area: empty state with logo + "New Chat" button
- No sidebar visible when no active chats exist

**Key Elements**:

- Logo cube (32×32, `#6b5b95`)
- "Braemon" title in Headline LG
- "New Chat" primary button (Almond Silk)
- Navigation links in the unified header: Home, Chats, Documents, Memories

**Empty State**: Clean, centered layout. The cube logo is the focal point.

---

### Screen 2: Braemon Chat Interface — Unified Header

**Purpose**: Active chat session with messages

**Layout**:

- Unified header (fixed top)
- Left: chat thread sidebar (list of active chats)
- Center: message area — messages as edge-markered data logs
- Bottom: chat input area
- Bottom status bar

**Message Display** (distinct from standard chat):

- Messages are NOT in bubbles
- Each message is a full-width row
- 2px vertical edge marker on the left side
- User messages: Almond Silk (`#c9ada7`) edge marker
- System messages: Lilac Ash (`#9a8c98`) edge marker
- Messages separated by 1px Lilac Ash dividers at 10% opacity
- Typography: Body MD (14px Inter) for message content
- Timestamps in Label SM

**Chat Input**:

- Rectangular input field at the bottom
- 1px Lilac Ash border, dark inset background
- Focus shifts border to Almond Silk
- Send button uses primary button style

**Sidebar**:

- Chat thread list with compact rows (max 40px)
- Active chat highlighted
- Thread titles in Body SM
- 1px dividers between threads

---

### Screen 3: Braemon Cube Logo

**Purpose**: Brand mark

**Specifications**:

- 32×32 pixels
- Color: Vibrant Purple `#6b5b95`
- Perfect square geometry
- SVG format
- Only high-saturation element in the interface

---

### Screen 4: Braemon Chats Library — Unified Header

**Purpose**: Browse and manage chat threads

**Layout**:

- Unified header (fixed top)
- Search bar below header
- Scrollable chat thread list
- Bottom status bar

**Chat List**:

- Compact rows (max 40px)
- Each row: thread title + timestamp + status indicator
- Status indicators: "Active" (Emerald dot) or "Ended" (Slate dot)
- 1px Lilac Ash dividers at 10% opacity between rows
- Hover: subtle background shift to Dusty Grape
- Typography: Body MD for titles, Label SM for timestamps

**Search**: Input field with 1px border, matches input field design rules

---

### Screen 5: Braemon Memory Vault — Unified Header

**Purpose**: Manage long-term memory entries

**Layout**:

- Unified header (fixed top)
- "Add Memory" button (primary, top-right)
- Memory entries as compact rows
- Bottom status bar

**Memory Rows**:

- Each row: memory key + value preview + category tag
- Category tags in Label SM, uppercase, Lilac Ash
- 1px dividers at 10% opacity
- "Delete" action on hover (ghost button with error color)
- Search bar for filtering

**Add Memory Form**:

- Modal (Level 2 depth): Dusty Grape background, Almond Silk 1px border at 30%
- Fields: Key, Value, Category (dropdown), Namespace
- Primary button: "Save"

---

### Screen 6: Braemon Documents Library — Unified Header

**Purpose**: Manage uploaded documents

**Layout**:

- Unified header (fixed top)
- "Upload Document" button (primary, top-right)
- Document list with compact rows
- Bottom status bar

**Document Rows**:

- Each row: document name + file type badge + chunk count + status
- Status: "Active" or "Suppressed"
- Suppressed documents: grayed out with strikethrough
- 1px dividers at 10% opacity
- Actions: "Suppress" and "Delete" as inline ghost buttons

**Upload**: File upload dialog, accepted types: .txt, .md, .pdf

---

## Unified Header Structure

Present on all screens. Contains:

```
┌─────────────────────────────────────────────────────┐
│ [Cube] Braemon    Home  Chats  Docs  Mem  [Profile] │
└─────────────────────────────────────────────────────┘
```

- Fixed position, top of viewport
- Background: Surface container (`#201f21`)
- 1px bottom border: Lilac Ash at 20% opacity
- Height: compact (~48px)
- Logo cube on the left
- Navigation links: active page highlighted in Almond Silk, others in Lilac Ash
- Profile area on the right (minimal — just an icon or initial)
- Typography: Label MD for nav items

## Bottom Status Bar

```
┌─────────────────────────────────────────────────────┐
│ Model: Qwen 3.5 122B    Memory: 127 items    v2.0   │
└─────────────────────────────────────────────────────┘
```

- Fixed position, bottom of viewport
- Background: Surface container
- 1px top border
- Height: compact (~24px)
- Typography: Label SM
- Shows: current model, memory count, version, system status

---

## Design-Specific CSS Variables

```css
:root {
  --color-base: #22223b;
  --color-card: #4a4e69;
  --color-border: #9a8c98;
  --color-accent: #c9ada7;
  --color-text: #f2e9e4;
  --color-surface: #131315;
  --color-surface-variant: #353436;
  --color-outline: #47464d;
  --color-logo: #6b5b95;
  --color-error: #ffb4ab;
  --color-error-container: #93000a;
  --radius: 4px;
  --spacing-base: 4px;
  --font-family: 'Inter', sans-serif;
}
```
