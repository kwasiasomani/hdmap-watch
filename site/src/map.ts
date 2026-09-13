import type { RegionBundle, Segment } from "./types";
import { byId } from "./dom";
import type { Highlighter } from "./interaction";

const NS = "http://www.w3.org/2000/svg";
const PAD = 18;
const VIEW_W = 640;

function pathLength(points: [number, number][]): number {
  let total = 0;
  for (let i = 1; i < points.length; i++) {
    const [x1, y1] = points[i - 1]!;
    const [x2, y2] = points[i]!;
    total += Math.hypot(x2 - x1, y2 - y1);
  }
  return total;
}

const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

export function renderMap(data: RegionBundle, highlighter: Highlighter): void {
  const svg = byId<SVGSVGElement>("map-svg");
  svg.innerHTML = "";

  const { bounds } = data;
  const scale = (VIEW_W - PAD * 2) / (bounds.xmax - bounds.xmin);
  const viewH = (bounds.ymax - bounds.ymin) * scale + PAD * 2;
  svg.setAttribute("viewBox", `0 0 ${VIEW_W} ${viewH.toFixed(1)}`);

  function toSvg([x, y]: [number, number]): string {
    const sx = (x - bounds.xmin) * scale + PAD;
    const sy = (bounds.ymax - y) * scale + PAD;
    return `${sx.toFixed(1)},${sy.toFixed(1)}`;
  }

  highlighter.reset(data.segments);

  data.segments.forEach((seg: Segment) => {
    const statusClass = seg.status === "REVIEW" ? "status-review" : "status-pass";
    const els: SVGPolylineElement[] = [];

    ([seg.left, seg.right] as const).forEach((boundary) => {
      const pl = document.createElementNS(NS, "polyline") as SVGPolylineElement;
      pl.setAttribute("points", boundary.map(toSvg).join(" "));
      pl.setAttribute("class", `lane-path ${statusClass}`);
      pl.setAttribute("stroke-width", "2.2");
      pl.dataset["id"] = String(seg.id);

      if (!reduceMotion) {
        const len = pathLength(boundary) * scale;
        pl.style.strokeDasharray = `${len}`;
        pl.style.strokeDashoffset = `${len}`;
        pl.style.transition = "stroke-dashoffset 900ms ease-out, stroke-width 120ms ease, opacity 120ms ease";
        requestAnimationFrame(() => {
          requestAnimationFrame(() => { pl.style.strokeDashoffset = "0"; });
        });
      }

      svg.appendChild(pl);
      els.push(pl);
    });

    highlighter.registerPaths(seg.id, els);
    els.forEach((el) => {
      el.addEventListener("mouseenter", (e) => highlighter.highlight(seg.id, e));
      el.addEventListener("mousemove", (e) => highlighter.moveTooltip(e));
      el.addEventListener("mouseleave", () => highlighter.clear());
      el.addEventListener("click", () => scrollRowIntoView(seg.id));
    });
  });
}

function scrollRowIntoView(id: number): void {
  const row = document.querySelector<HTMLTableRowElement>(`#queue-body tr[data-id="${id}"]`);
  row?.scrollIntoView({ block: "center", behavior: "smooth" });
}
