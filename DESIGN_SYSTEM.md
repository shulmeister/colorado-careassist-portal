# 🎨 Colorado CareAssist Portal - Design System

**Last Updated**: November 13, 2025  
**Version**: 2.0 - Databox-Style

---

## 📐 Overview

This design system defines the **Databox-inspired dashboard layout** used across all dashboards in the Colorado CareAssist Portal. The goal is **maximum data density** with **minimal scrolling** - everything critical should be **above the fold**.

---

## 🏗️ Layout Architecture

### Grid Foundation
```css
display: grid;
grid-template-columns: repeat(6, 1fr);
gap: 10px;
```

**Why 6 columns?**
- Flexible enough for varied card sizes
- Allows for: single (1 col), double (2 col), triple (3 col), full-width (6 col)
- Mimics Databox's asymmetric, information-dense layout

---

## 📦 Card Types & Patterns

### 1. **HERO METRICS** (Row 1)
**Purpose**: Highlight 3 most important KPIs  
**Size**: `grid-column: span 2` (2 columns each = 3 cards)  
**Height**: ~120px  

```html
<div style="grid-column: span 2; background: rgba(30, 41, 59, 0.95); border: 1px solid rgba(51, 65, 85, 0.7); border-radius: 10px; padding: 24px 20px;">
    <div style="font-size: 10px; color: #64748b; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 12px;">METRIC NAME</div>
    <div style="font-size: 42px; font-weight: 700; color: #f8fafc; line-height: 1;" id="metricValue">—</div>
    <div style="font-size: 11px; color: #94a3b8; margin-top: 8px;">Last 30 days</div>
</div>
```

**Visual Characteristics**:
- **Label**: 10px, uppercase, gray (#64748b)
- **Value**: 42px, bold, white (#f8fafc)
- **Subtitle**: 11px, light gray (#94a3b8)

---

### 2. **MEDIUM METRICS with CHARTS** (Row 2)
**Purpose**: Key metrics with trend visualization  
**Size**: `grid-column: span 2` (3 cards)  
**Height**: ~150px  

```html
<div style="grid-column: span 2; background: rgba(30, 41, 59, 0.95); border: 1px solid rgba(51, 65, 85, 0.7); border-radius: 10px; padding: 18px;">
    <div style="font-size: 10px; color: #64748b; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 10px;">METRIC NAME</div>
    <div style="font-size: 32px; font-weight: 700; color: #f8fafc; line-height: 1; margin-bottom: 14px;" id="metricValue">—</div>
    <div style="height: 65px; position: relative;">
        <canvas id="metricChart"></canvas>
    </div>
</div>
```

**Visual Characteristics**:
- **Label**: 10px, uppercase
- **Value**: 32px, bold
- **Chart**: 65px height, line or area chart
- **Padding**: 18px

---

### 3. **COMPACT SINGLE METRICS** (Rows 3, 5)
**Purpose**: Quick-glance single-value KPIs  
**Size**: `grid-column: span 1` (1 column = 6 per row)  
**Height**: ~85px  

```html
<div style="background: rgba(30, 41, 59, 0.95); border: 1px solid rgba(51, 65, 85, 0.7); border-radius: 10px; padding: 18px;">
    <div style="font-size: 9px; color: #64748b; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 10px;">METRIC</div>
    <div style="font-size: 26px; font-weight: 700; color: #f8fafc; line-height: 1;" id="metricValue">—</div>
</div>
```

**Visual Characteristics**:
- **Label**: 9px, uppercase
- **Value**: 26px, bold
- **Padding**: 18px
- **Minimal footprint**: Pack as many as needed

---

### 4. **LARGE CHART PANELS** (Row 4)
**Purpose**: Detailed trend analysis  
**Size**: `grid-column: span 3` (2 cards side-by-side)  
**Height**: ~190px  

```html
<div style="grid-column: span 3; background: rgba(30, 41, 59, 0.95); border: 1px solid rgba(51, 65, 85, 0.7); border-radius: 10px; padding: 18px;">
    <div style="font-size: 10px; color: #64748b; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 6px;">CHART TITLE</div>
    <div style="font-size: 11px; color: #94a3b8; margin-bottom: 14px;">Chart description</div>
    <div style="height: 140px; position: relative;">
        <canvas id="chartId"></canvas>
    </div>
</div>
```

**Visual Characteristics**:
- **Title**: 10px, uppercase
- **Subtitle**: 11px, descriptive
- **Chart**: 140px height
- **Span**: 3 columns (half the width)

---

### 5. **TALL CHART CARDS** (Multi-row)
**Purpose**: Detailed time-series or large datasets  
**Size**: `grid-column: span 2; grid-row: span 2;`  
**Height**: ~320px (spans 2 rows)  

```html
<div style="grid-column: span 2; grid-row: span 2; background: rgba(30, 41, 59, 0.95); border: 1px solid rgba(51, 65, 85, 0.7); border-radius: 10px; padding: 18px;">
    <div style="font-size: 10px; color: #64748b; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 6px;">METRIC</div>
    <div style="font-size: 12px; color: #94a3b8; margin-bottom: 4px;">vs previous period</div>
    <div style="font-size: 26px; font-weight: 700; color: #f8fafc; margin-bottom: 16px;" id="metricValue">—</div>
    <div style="height: 180px; position: relative;">
        <canvas id="tallChart"></canvas>
    </div>
</div>
```

**Visual Characteristics**:
- **Spans 2 rows**: More vertical space
- **Chart**: 180px height
- **Ideal for**: Impressions, sessions, revenue over time

---

### 6. **DATA TABLES** (Full or half width)
**Purpose**: Ranked lists, campaign breakdowns  
**Size**: `grid-column: span 3` or `span 2`  
**Height**: Variable  

```html
<div style="grid-column: span 3; background: rgba(30, 41, 59, 0.95); border: 1px solid rgba(51, 65, 85, 0.7); border-radius: 10px; padding: 18px;">
    <div style="font-size: 10px; color: #64748b; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 14px;">TABLE TITLE</div>
    <div style="display: flex; flex-direction: column; gap: 10px;">
        <!-- Header Row -->
        <div style="display: flex; justify-content: space-between; padding-bottom: 8px; border-bottom: 1px solid rgba(51, 65, 85, 0.5);">
            <div style="font-size: 10px; color: #94a3b8; flex: 1;">Column 1</div>
            <div style="font-size: 10px; color: #94a3b8; flex: 2;">Column 2</div>
            <div style="font-size: 10px; color: #94a3b8; text-align: right; flex: 1;">Column 3</div>
        </div>
        <!-- Data Rows -->
        <div style="display: flex; justify-content: space-between; align-items: center;">
            <div style="font-size: 11px; color: #64748b; flex: 1;">1</div>
            <div style="font-size: 11px; color: #e2e8f0; flex: 2;">Item Name</div>
            <div style="font-size: 11px; color: #e2e8f0; text-align: right; flex: 1;">Value</div>
        </div>
    </div>
</div>
```

**Visual Characteristics**:
- **Header**: 10px, gray, bottom border
- **Rows**: 11px, white/light gray
- **Compact gaps**: 10px between rows
- **Trend indicators**: Use ▲ (green) and ▼ (red)

---

### 7. **MULTI-ROW TABLES** (Account overview style)
**Purpose**: Comparison tables with trend indicators  
**Size**: `grid-column: span 2; grid-row: span 2;`  
**Height**: ~320px  

```html
<div style="grid-column: span 2; grid-row: span 2; background: rgba(30, 41, 59, 0.95); border: 1px solid rgba(51, 65, 85, 0.7); border-radius: 10px; padding: 18px;">
    <div style="font-size: 10px; color: #64748b; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 14px;">ACCOUNT OVERVIEW</div>
    <div style="display: flex; flex-direction: column; gap: 12px;">
        <!-- Header -->
        <div style="display: flex; justify-content: space-between; align-items: center; padding-bottom: 10px; border-bottom: 1px solid rgba(51, 65, 85, 0.5);">
            <div style="font-size: 11px; color: #94a3b8;">Metric</div>
            <div style="display: flex; gap: 20px;">
                <div style="font-size: 11px; color: #94a3b8;">Value</div>
                <div style="font-size: 11px; color: #94a3b8;">vs prev</div>
            </div>
        </div>
        <!-- Row -->
        <div style="display: flex; justify-content: space-between; align-items: center;">
            <div style="font-size: 12px; color: #e2e8f0;">Metric Name</div>
            <div style="display: flex; gap: 20px; align-items: center;">
                <div style="font-size: 13px; font-weight: 600; color: #f8fafc;">1,234</div>
                <div style="font-size: 11px; color: #10b981; font-weight: 600;">▲ 15%</div>
            </div>
        </div>
    </div>
</div>
```

**Trend Colors**:
- **Green** (#10b981): Positive trend ▲
- **Red** (#ef4444): Negative trend ▼
- **Gray** (#64748b): No change or N/A

---

## 🎨 Color Palette

### Backgrounds
```css
--bg-primary: #0f172a;              /* Page background */
--bg-card: rgba(30, 41, 59, 0.95);  /* Card background */
--bg-sidebar: #1e293b;              /* Sidebar background */
```

### Borders
```css
--border-card: rgba(51, 65, 85, 0.7);     /* Card borders */
--border-section: rgba(51, 65, 85, 0.5);  /* Section dividers */
```

### Text
```css
--text-primary: #f8fafc;    /* Main values */
--text-secondary: #e2e8f0;  /* Secondary text */
--text-muted: #94a3b8;      /* Subtitles */
--text-label: #64748b;      /* Labels, dim text */
```

### Accents
```css
--accent-blue: #3b82f6;     /* Primary CTA */
--accent-green: #10b981;    /* Positive trends */
--accent-red: #ef4444;      /* Negative trends */
--accent-yellow: #f59e0b;   /* Warnings */
```

---

## 📏 Spacing & Typography

### Font Sizes (Hierarchy)
```
Hero Value:     42px (bold 700)
Large Value:    32px (bold 700)
Medium Value:   26px (bold 700)
Body Text:      13px (normal 400)
Labels:         10-12px (normal 400, uppercase)
Small Text:     9-11px (normal 400)
```

### Spacing Scale
```
Card Padding:   18-24px
Card Gap:       10px
Section Gap:    12px
Row Gap:        10-12px
Inline Gap:     4-8px
```

### Border Radius
```
Cards:          10px
Buttons:        8px
Small Elements: 6px
```

---

## 🧩 Example Dashboard Layout

```
┌─────────────────────────────────────────────────────────────┐
│  Row 1: HERO METRICS (3 cards, span 2 each)                │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐                   │
│  │ AD SPEND │ │  REACH   │ │  CONV    │                   │
│  │  $1,234  │ │  45.2K   │ │   123    │                   │
│  └──────────┘ └──────────┘ └──────────┘                   │
├─────────────────────────────────────────────────────────────┤
│  Row 2: MEDIUM METRICS WITH CHARTS (3 cards, span 2 each)  │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐                   │
│  │   ROAS   │ │ COST/CNV │ │  IMPR    │                   │
│  │   3.2x   │ │  $12.50  │ │  18.5K   │                   │
│  │ ╱╲╱╲╱╲╱  │ │ ╱╲╱╲╱╲╱  │ │ ╱╲╱╲╱╲╱  │                   │
│  └──────────┘ └──────────┘ └──────────┘                   │
├─────────────────────────────────────────────────────────────┤
│  Row 3: COMPACT METRICS (6 cards, span 1 each)             │
│  ┌───┐┌───┐┌───┐┌───┐┌───┐┌───┐                          │
│  │CTC││CPC││CTR││CVR││ENG││LKS│                          │
│  │456││2.3││4.5││8.2││789││234│                          │
│  └───┘└───┘└───┘└───┘└───┘└───┘                          │
├─────────────────────────────────────────────────────────────┤
│  Row 4: LARGE CHARTS (2 cards, span 3 each)                │
│  ┌─────────────────────────┐┌─────────────────────────┐   │
│  │   SPEND TREND           ││ AD EFFICIENCY           │   │
│  │   ╱╲╱╲╱╲╱╲╱╲╱╲╱╲       ││ ╱╲╱╲╱╲╱╲╱╲╱╲╱╲         │   │
│  └─────────────────────────┘└─────────────────────────┘   │
├─────────────────────────────────────────────────────────────┤
│  Row 5: MIXED (2 tall cards span 2x2, 4 compact span 1)    │
│  ┌──────────┐┌──────────┐┌──────────┐┌───┐┌───┐          │
│  │ TABLE    ││ IMPRESS  ││ SESSIONS ││CAL││DIR│          │
│  │ Clicks   ││  ╱╲╱╲╱╲  ││  ╱╲╱╲╱╲  ││456││123│          │
│  │ CTR      ││  ╱╲╱╲╱╲  ││  ╱╲╱╲╱╲  │└───┘└───┘          │
│  │ CPC      ││  ╱╲╱╲╱╲  ││  ╱╲╱╲╱╲  │┌───┐┌───┐          │
│  │ Purch    ││  ╱╲╱╲╱╲  ││  ╱╲╱╲╱╲  ││WEB││EML│          │
│  └──────────┘└──────────┘└──────────┘│678││234│          │
│                                        └───┘└───┘          │
├─────────────────────────────────────────────────────────────┤
│  Row 6: TABLE + CHART                                       │
│  ┌─────────────────────────┐┌─────────────────────────┐   │
│  │ CAMPAIGNS OVERVIEW      ││  INTERACTIONS           │   │
│  │ 1. Camp A | 13.1K | $177││  ╱╲╱╲╱╲╱╲╱╲╱╲╱╲         │   │
│  │ 2. Camp B |  4.5K | $67 │└─────────────────────────┘   │
│  │ 3. Camp C |  2.5K | $90 │                              │
│  └─────────────────────────┘                              │
└─────────────────────────────────────────────────────────────┘
```

---

## 🚀 Implementation Checklist

### When Creating a New Dashboard Tab:

1. **Start with 6-column grid**
   ```html
   <div style="display: grid; grid-template-columns: repeat(6, 1fr); gap: 10px; margin-top: 10px;">
   ```

2. **Add 3 Hero Metrics** (Row 1)
   - Most important KPIs
   - `grid-column: span 2` each
   - 42px font size

3. **Add 3 Medium Metrics with Charts** (Row 2)
   - Secondary KPIs with trends
   - `grid-column: span 2` each
   - 32px font + 65px chart

4. **Add 6 Compact Metrics** (Row 3)
   - Quick-glance values
   - `grid-column: span 1` each
   - 26px font size

5. **Add 2 Large Chart Panels** (Row 4)
   - Trend analysis
   - `grid-column: span 3` each
   - 140px chart height

6. **Mix Tall Cards + Compact Metrics** (Row 5)
   - Use `grid-row: span 2` for tall cards
   - Fill remaining space with compact metrics

7. **Add Tables or Additional Charts** (Row 6)
   - Campaign breakdowns, rankings
   - `grid-column: span 3` or more

8. **Update JavaScript**
   - Add `renderXXXMetrics()` function
   - Populate all element IDs
   - Initialize all Chart.js instances

9. **Test Responsiveness**
   - Ensure no scrolling on 1920x1080+ displays
   - Check that all data loads correctly

---

## 📋 Chart.js Configuration

### Standard Area Chart (Trend Lines)
```javascript
new Chart(ctx, {
    type: 'line',
    data: {
        labels: dates,
        datasets: [{
            label: 'Metric',
            data: values,
            borderColor: '#3b82f6',
            backgroundColor: 'rgba(59, 130, 246, 0.1)',
            fill: true,
            tension: 0.4,
            borderWidth: 2,
            pointRadius: 0
        }]
    },
    options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: {
            x: { display: false },
            y: { display: false }
        }
    }
});
```

### Multi-Line Chart (Comparisons)
```javascript
datasets: [
    {
        label: 'CPC',
        data: cpcData,
        borderColor: '#10b981',
        yAxisID: 'y'
    },
    {
        label: 'CTR',
        data: ctrData,
        borderColor: '#3b82f6',
        yAxisID: 'y1'
    }
]
```

---

## ✅ Quality Standards

### Must Have:
- ✅ All critical data **above the fold** (no scrolling)
- ✅ Big, readable numbers (26px minimum for values)
- ✅ Consistent spacing (10px gaps)
- ✅ Clean, minimal aesthetic
- ✅ Trend indicators where relevant (▲/▼)
- ✅ Loading states (`—` or "Loading…")
- ✅ Error handling (show placeholder on API failure)

### Must Avoid:
- ❌ Excessive white space
- ❌ Uniform grids (vary card sizes for visual interest)
- ❌ Tiny fonts (<9px)
- ❌ More than 1 screen of scrolling
- ❌ Cluttered charts (hide legends, gridlines)

---

## 📝 Notes for Future Development

### Applying to Sales Dashboard
1. Replace marketing metrics with sales KPIs:
   - Revenue, Deals Closed, Pipeline Value
   - Average Deal Size, Win Rate, Sales Cycle
   - Calls Made, Emails Sent, Meetings Booked

2. Keep the same layout structure:
   - 3 Hero Metrics (Revenue, Deals, Pipeline)
   - 3 Medium with Charts (Win Rate, Avg Deal Size, Cycle Time)
   - 6 Compact (Calls, Emails, Meetings, etc.)
   - 2 Large Charts (Revenue Trend, Sales Funnel)
   - Tables (Top Performers, Deal Breakdown)

### Applying to Other Dashboards
- **Finance**: Revenue, Expenses, Profit, Cash Flow
- **Operations**: Utilization, Response Time, SLA Metrics
- **HR/Recruitment**: Applications, Interviews, Hires, Time-to-Fill

---

## 🎯 Success Criteria

A dashboard following this design system should:
1. **Fit above the fold** on standard 1920x1080 displays
2. **Display 15-20+ KPIs** simultaneously
3. **Be scannable in <10 seconds** - key insights immediately visible
4. **Look professional** - Databox-quality aesthetic
5. **Be reusable** - same patterns across all dashboards

---

**Template Repository**: `/Users/jasonshulman/Documents/GitHub/colorado-careassist-portal`  
**Reference Implementation**: `templates/marketing.html` (tab-overview)  
**Deployed**: https://portal.coloradocareassist.com/marketing

---

*This design system is a living document. Update it as patterns evolve.*


