/* Minimal SVG chart library following the dataviz mark specs:
   2px lines with round joins, ≥8px end markers with 2px surface rings,
   10%-opacity area washes, hairline solid gridlines, crosshair + tooltip
   listing every series at the snapped X, textContent-only labels. */

const SURFACE = "#1a1a19";
const GRID = "#2c2c2a";
const BASELINE = "#383835";
const MUTED = "#898781";

const SVG_NS = "http://www.w3.org/2000/svg";

function el(name, attrs = {}) {
  const node = document.createElementNS(SVG_NS, name);
  for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, v);
  return node;
}

export function fmtUSD(v, compact = false) {
  if (v == null || Number.isNaN(v)) return "—";
  if (compact && Math.abs(v) >= 100000) return "$" + (v / 1000).toFixed(0) + "K";
  if (compact && Math.abs(v) >= 10000) return "$" + (v / 1000).toFixed(1) + "K";
  return "$" + Math.round(v).toLocaleString("en-US");
}

export function fmtPct(v, signed = true) {
  if (v == null || Number.isNaN(v)) return "—";
  const s = signed && v > 0 ? "+" : "";
  return s + v.toFixed(1) + "%";
}

function niceTicks(min, max, count = 4) {
  const span = max - min || 1;
  const step = Math.pow(10, Math.floor(Math.log10(span / count)));
  const err = span / count / step;
  const mult = err >= 7.5 ? 10 : err >= 3.5 ? 5 : err >= 1.5 ? 2 : 1;
  const s = mult * step;
  const ticks = [];
  for (let t = Math.ceil(min / s) * s; t <= max + 1e-9; t += s) ticks.push(t);
  return ticks;
}

function fmtTick(v) {
  if (Math.abs(v) >= 1000) return (v / 1000).toLocaleString("en-US") + "K";
  return v.toLocaleString("en-US");
}

function fmtDateShort(iso) {
  const d = new Date(iso + "T00:00:00Z");
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric", timeZone: "UTC" });
}

/* lineChart(container, {
     series: [{name, color, points: [{date, value}], dashed}],
     bands:  [{name, color, points: [{date, lower, upper}]}],
     height, yFmt, legend }) */
export function lineChart(container, opts) {
  container.classList.add("chart");
  container.textContent = "";

  const W = 820, H = opts.height || 300;
  const PAD = { top: 14, right: 60, bottom: 26, left: 8 };
  const series = (opts.series || []).filter((s) => s.points.length > 0);
  const bands = opts.bands || [];
  if (!series.length) {
    const note = document.createElement("div");
    note.className = "empty-note";
    note.textContent = "Not enough data yet.";
    container.appendChild(note);
    return;
  }

  // Unified date domain across series + bands
  const dateSet = new Set();
  for (const s of series) s.points.forEach((p) => dateSet.add(p.date));
  for (const b of bands) b.points.forEach((p) => dateSet.add(p.date));
  const dates = [...dateSet].sort();
  const xOf = new Map(dates.map((d, i) => [d, i]));
  const nX = dates.length;

  let vMin = Infinity, vMax = -Infinity;
  for (const s of series) for (const p of s.points) {
    if (p.value == null) continue;
    vMin = Math.min(vMin, p.value); vMax = Math.max(vMax, p.value);
  }
  for (const b of bands) for (const p of b.points) {
    if (p.lower != null) vMin = Math.min(vMin, p.lower);
    if (p.upper != null) vMax = Math.max(vMax, p.upper);
  }
  const spanPad = (vMax - vMin) * 0.08 || vMax * 0.05 || 1;
  vMin -= spanPad; vMax += spanPad;
  if (opts.zeroFloor && vMin < 0) vMin = 0;

  const px = (i) => PAD.left + (nX === 1 ? 0.5 : i / (nX - 1)) * (W - PAD.left - PAD.right);
  const py = (v) => PAD.top + (1 - (v - vMin) / (vMax - vMin)) * (H - PAD.top - PAD.bottom);

  const svg = el("svg", { viewBox: `0 0 ${W} ${H}`, role: "img" });

  // Gridlines: hairline, solid, recessive
  const ticks = niceTicks(vMin, vMax);
  for (const t of ticks) {
    svg.appendChild(el("line", {
      x1: PAD.left, x2: W - PAD.right, y1: py(t), y2: py(t),
      stroke: GRID, "stroke-width": 1,
    }));
    const label = el("text", {
      x: W - PAD.right + 8, y: py(t) + 4, fill: MUTED,
      "font-size": 11, "font-family": "inherit",
    });
    label.style.fontVariantNumeric = "tabular-nums";
    label.textContent = (opts.yPrefix || "") + fmtTick(t);
    svg.appendChild(label);
  }

  // X labels: first, middle, last
  const xIdx = nX <= 3 ? dates.map((_, i) => i) : [0, Math.floor((nX - 1) / 2), nX - 1];
  for (const i of xIdx) {
    const label = el("text", {
      x: px(i), y: H - 8, fill: MUTED, "font-size": 11,
      "text-anchor": i === 0 ? "start" : i === nX - 1 ? "end" : "middle",
      "font-family": "inherit",
    });
    label.textContent = fmtDateShort(dates[i]);
    svg.appendChild(label);
  }

  // Bands (10% wash)
  for (const b of bands) {
    const pts = b.points.filter((p) => p.lower != null && p.upper != null);
    if (pts.length < 2) continue;
    const up = pts.map((p) => `${px(xOf.get(p.date))},${py(p.upper)}`);
    const lo = pts.slice().reverse().map((p) => `${px(xOf.get(p.date))},${py(p.lower)}`);
    svg.appendChild(el("polygon", {
      points: [...up, ...lo].join(" "),
      fill: b.color, "fill-opacity": 0.1,
    }));
  }

  // Series: lines by default, individual dots for scatter series
  for (const s of series) {
    const pts = s.points.filter((p) => p.value != null);
    if (s.dots) {
      for (const p of pts) {
        svg.appendChild(el("circle", {
          cx: px(xOf.get(p.date)), cy: py(p.value), r: 4,
          fill: s.color, "fill-opacity": 0.85,
          stroke: SURFACE, "stroke-width": 2,
        }));
      }
      continue;
    }
    const path = pts.map((p, i) =>
      `${i ? "L" : "M"}${px(xOf.get(p.date))},${py(p.value)}`).join("");
    const attrs = {
      d: path, fill: "none", stroke: s.color, "stroke-width": 2,
      "stroke-linejoin": "round", "stroke-linecap": "round",
    };
    if (s.dashed) attrs["stroke-dasharray"] = "5 4";
    svg.appendChild(el("path", attrs));
    if (s.wash) {
      const base = py(vMin);
      const area = path +
        `L${px(xOf.get(pts[pts.length - 1].date))},${base}` +
        `L${px(xOf.get(pts[0].date))},${base}Z`;
      svg.appendChild(el("path", { d: area, fill: s.color, "fill-opacity": 0.1 }));
    }
    // Endpoint marker: ≥8px with 2px surface ring
    const last = pts[pts.length - 1];
    svg.appendChild(el("circle", {
      cx: px(xOf.get(last.date)), cy: py(last.value), r: 4,
      fill: s.color, stroke: SURFACE, "stroke-width": 2,
    }));
  }

  // Crosshair + tooltip
  const cross = el("line", {
    y1: PAD.top, y2: H - PAD.bottom, stroke: BASELINE,
    "stroke-width": 1, visibility: "hidden",
  });
  svg.appendChild(cross);
  const hoverDots = series.map((s) => {
    const dot = el("circle", {
      r: 4, fill: s.color, stroke: SURFACE, "stroke-width": 2, visibility: "hidden",
    });
    svg.appendChild(dot);
    return dot;
  });

  const tooltip = document.createElement("div");
  tooltip.className = "chart-tooltip";
  container.appendChild(tooltip);
  container.appendChild(svg);

  const valueAt = (s, date) => {
    if (s.dots) {
      const vals = s.points.filter((q) => q.date === date && q.value != null)
        .map((q) => q.value);
      if (!vals.length) return null;
      if (vals.length === 1) return vals[0];
      vals.sort((a, b) => a - b);
      return vals[Math.floor(vals.length / 2)];  // median of same-day sales
    }
    const p = s.points.find((q) => q.date === date);
    return p ? p.value : null;
  };

  svg.addEventListener("pointermove", (ev) => {
    const rect = svg.getBoundingClientRect();
    const fx = ((ev.clientX - rect.left) / rect.width) * W;
    let best = 0, bestDist = Infinity;
    for (let i = 0; i < nX; i++) {
      const d = Math.abs(px(i) - fx);
      if (d < bestDist) { bestDist = d; best = i; }
    }
    const date = dates[best];
    const x = px(best);
    cross.setAttribute("x1", x); cross.setAttribute("x2", x);
    cross.setAttribute("visibility", "visible");

    tooltip.textContent = "";
    const dt = document.createElement("div");
    dt.className = "tt-date";
    dt.textContent = fmtDateShort(date);
    tooltip.appendChild(dt);

    series.forEach((s, i) => {
      const v = valueAt(s, date);
      const dot = hoverDots[i];
      if (v == null) { dot.setAttribute("visibility", "hidden"); }
      else {
        dot.setAttribute("cx", x); dot.setAttribute("cy", py(v));
        dot.setAttribute("visibility", "visible");
      }
      const row = document.createElement("div");
      row.className = "tt-row";
      const key = document.createElement("span");
      key.className = "tt-key";
      key.style.borderTopColor = s.color;
      if (s.dashed) key.style.borderTopStyle = "dashed";
      const name = document.createElement("span");
      name.className = "tt-name";
      name.textContent = s.name;
      const val = document.createElement("span");
      val.className = "tt-val";
      val.textContent = (opts.yFmt || fmtUSD)(v);
      row.append(key, name, val);
      tooltip.appendChild(row);
    });

    tooltip.style.display = "block";
    const tw = tooltip.offsetWidth;
    const xr = (x / W) * rect.width;
    tooltip.style.left = Math.min(Math.max(xr + 14, 0), rect.width - tw - 4) + "px";
    tooltip.style.top = "12px";
  });
  svg.addEventListener("pointerleave", () => {
    cross.setAttribute("visibility", "hidden");
    hoverDots.forEach((d) => d.setAttribute("visibility", "hidden"));
    tooltip.style.display = "none";
  });

  // Legend (always for ≥2 visual layers)
  if (opts.legend !== false && series.length + bands.length >= 2) {
    const legend = document.createElement("div");
    legend.className = "chart-legend";
    for (const s of series) {
      const item = document.createElement("span");
      item.className = "lg-item";
      let key;
      if (s.dots) {
        key = document.createElement("span");
        key.style.cssText = `width:9px;height:9px;border-radius:50%;background:${s.color}`;
      } else {
        key = document.createElement("span");
        key.className = "lg-line" + (s.dashed ? " dashed" : "");
        key.style.borderTopColor = s.color;
      }
      const name = document.createElement("span");
      name.textContent = s.name;
      item.append(key, name);
      legend.appendChild(item);
    }
    for (const b of bands) {
      const item = document.createElement("span");
      item.className = "lg-item";
      const sw = document.createElement("span");
      sw.className = "lg-swatch";
      sw.style.background = b.color;
      sw.style.opacity = 0.25;
      const name = document.createElement("span");
      name.textContent = b.name;
      item.append(sw, name);
      legend.appendChild(item);
    }
    container.appendChild(legend);
  }
}

/* Sparkline: de-emphasis line with an accent end-dot. */
export function sparkline(container, values, { color = "#3987e5", width = 96, height = 30 } = {}) {
  container.textContent = "";
  const vals = (values || []).filter((v) => v != null);
  if (vals.length < 2) return;
  const min = Math.min(...vals), max = Math.max(...vals);
  const span = max - min || 1;
  const P = 3;
  const px = (i) => P + (i / (vals.length - 1)) * (width - 2 * P);
  const py = (v) => P + (1 - (v - min) / span) * (height - 2 * P);
  const svg = el("svg", { viewBox: `0 0 ${width} ${height}`, width, height, "aria-hidden": "true" });
  const path = vals.map((v, i) => `${i ? "L" : "M"}${px(i)},${py(v)}`).join("");
  svg.appendChild(el("path", {
    d: path, fill: "none", stroke: MUTED, "stroke-width": 1.5,
    "stroke-linejoin": "round", "stroke-linecap": "round",
  }));
  svg.appendChild(el("circle", {
    cx: px(vals.length - 1), cy: py(vals[vals.length - 1]), r: 3,
    fill: color, stroke: SURFACE, "stroke-width": 2,
  }));
  container.appendChild(svg);
}

/* Donut: part-to-whole, ≤6 segments, 2px surface gaps, legend carries labels. */
export function donut(container, segments, { size = 180, centerLabel = "" } = {}) {
  container.textContent = "";
  const total = segments.reduce((a, s) => a + s.value, 0);
  if (!total) return;
  const R = size / 2, r = R - 16, cx = R, cy = R;
  const svg = el("svg", { viewBox: `0 0 ${size} ${size}`, width: size, height: size, role: "img" });
  let angle = -Math.PI / 2;
  for (const seg of segments) {
    const frac = seg.value / total;
    const a2 = angle + frac * 2 * Math.PI;
    const large = frac > 0.5 ? 1 : 0;
    const x1 = cx + r * Math.cos(angle), y1 = cy + r * Math.sin(angle);
    const x2 = cx + r * Math.cos(a2), y2 = cy + r * Math.sin(a2);
    const path = el("path", {
      d: `M${cx},${cy} L${x1},${y1} A${r},${r} 0 ${large} 1 ${x2},${y2} Z`,
      fill: seg.color, stroke: SURFACE, "stroke-width": 2,
    });
    const title = el("title");
    title.textContent = `${seg.label}: ${fmtUSD(seg.value)} (${(frac * 100).toFixed(0)}%)`;
    path.appendChild(title);
    svg.appendChild(path);
    angle = a2;
  }
  // Punch the hole
  svg.appendChild(el("circle", { cx, cy, r: r * 0.62, fill: SURFACE }));
  if (centerLabel) {
    const t = el("text", {
      x: cx, y: cy + 5, "text-anchor": "middle", fill: "#ffffff",
      "font-size": 15, "font-weight": 600, "font-family": "inherit",
    });
    t.textContent = centerLabel;
    svg.appendChild(t);
  }
  container.appendChild(svg);
}

export const PALETTE = ["#3987e5", "#199e70", "#c98500", "#008300", "#9085e9", "#e66767"];
