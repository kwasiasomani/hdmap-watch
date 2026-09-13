import type { RegionBundle, CheckName } from "./types";
import { byId, cssVar } from "./dom";

const NS = "http://www.w3.org/2000/svg";
const CHECK_LABELS: Record<CheckName, string> = {
  geometry: "Geometry",
  topology: "Topology",
  semantic: "Semantic",
};
const CHECK_KEYS: CheckName[] = ["geometry", "topology", "semantic"];
const CHECK_COLOR_VAR: Record<CheckName, string> = {
  geometry: "--cat-geometry",
  topology: "--cat-topology",
  semantic: "--cat-semantic",
};

function svgEl<K extends keyof SVGElementTagNameMap>(tag: K): SVGElementTagNameMap[K] {
  return document.createElementNS(NS, tag) as SVGElementTagNameMap[K];
}

export function renderDonut(data: RegionBundle): void {
  const svg = byId<SVGSVGElement>("donut-svg");
  svg.innerHTML = "";

  const reviewFrac = data.summary.total > 0 ? data.summary.review / data.summary.total : 0;
  const r = 54;
  const circumference = 2 * Math.PI * r;

  const track = svgEl("circle");
  track.setAttribute("cx", "70");
  track.setAttribute("cy", "70");
  track.setAttribute("r", String(r));
  track.setAttribute("fill", "none");
  track.setAttribute("stroke", cssVar("--pass"));
  track.setAttribute("stroke-width", "18");
  svg.appendChild(track);

  const reviewArc = svgEl("circle");
  reviewArc.setAttribute("cx", "70");
  reviewArc.setAttribute("cy", "70");
  reviewArc.setAttribute("r", String(r));
  reviewArc.setAttribute("fill", "none");
  reviewArc.setAttribute("stroke", cssVar("--review"));
  reviewArc.setAttribute("stroke-width", "18");
  reviewArc.setAttribute("stroke-dasharray", `${(circumference * reviewFrac).toFixed(1)} ${circumference.toFixed(1)}`);
  reviewArc.setAttribute("transform", "rotate(-90 70 70)");
  svg.appendChild(reviewArc);

  const figure = svgEl("text");
  figure.setAttribute("x", "70");
  figure.setAttribute("y", "68");
  figure.setAttribute("text-anchor", "middle");
  figure.setAttribute("class", "donut-figure");
  figure.textContent = `${Math.round(reviewFrac * 100)}%`;
  svg.appendChild(figure);

  const caption = svgEl("text");
  caption.setAttribute("x", "70");
  caption.setAttribute("y", "84");
  caption.setAttribute("text-anchor", "middle");
  caption.setAttribute("class", "donut-caption");
  caption.textContent = "REVIEW";
  svg.appendChild(caption);

  byId("donut-pass-n").textContent = String(data.summary.pass);
  byId("donut-review-n").textContent = String(data.summary.review);
}

export function renderRiskBars(data: RegionBundle): void {
  const counts: [number, number, number, number] = [0, 0, 0, 0];
  data.segments.forEach((s) => { counts[s.risk] += 1; });
  const max = Math.max(...counts, 1);
  const colors = [cssVar("--pass"), cssVar("--risk-1"), cssVar("--risk-2"), cssVar("--risk-3")];

  const wrap = byId("risk-bars");
  wrap.innerHTML = "";
  counts.forEach((count, risk) => {
    const row = document.createElement("div");
    row.className = "bar-row";
    row.innerHTML = `<span>risk ${risk}</span><span class="bar-track"><span class="bar-fill" style="width:${(count / max) * 100}%;background:${colors[risk]}"></span></span><span class="count mono">${count}</span>`;
    wrap.appendChild(row);
  });
}

export function renderCheckBars(data: RegionBundle): void {
  const entries: [CheckName, number][] = [
    ["geometry", data.summary.geometry_flagged],
    ["topology", data.summary.topology_flagged],
    ["semantic", data.summary.semantic_flagged],
  ];
  const max = Math.max(...entries.map(([, c]) => c), 1);

  const wrap = byId("check-bars");
  wrap.innerHTML = "";
  entries.forEach(([key, count]) => {
    const color = cssVar(CHECK_COLOR_VAR[key]);
    const row = document.createElement("div");
    row.className = "bar-row";
    row.innerHTML = `<span>${CHECK_LABELS[key]}</span><span class="bar-track"><span class="bar-fill" style="width:${(count / max) * 100}%;background:${color}"></span></span><span class="count mono">${count}</span>`;
    wrap.appendChild(row);
  });

  const legend = byId("check-legend");
  legend.innerHTML = CHECK_KEYS.map(
    (k) => `<span class="legend-row"><span class="swatch" style="background:${cssVar(CHECK_COLOR_VAR[k])}"></span>${CHECK_LABELS[k]}</span>`,
  ).join("");
}
