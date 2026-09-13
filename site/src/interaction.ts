import type { Segment, CheckName } from "./types";
import { byId } from "./dom";

const CHECK_LABELS: Record<CheckName, string> = {
  geometry: "Geometry",
  topology: "Topology",
  semantic: "Semantic",
};

type Listener = (id: number | null) => void;

/** Cross-links the map SVG and the table: hovering either highlights both. */
export class Highlighter {
  private pathsBySegment = new Map<number, SVGPolylineElement[]>();
  private segmentsById = new Map<number, Segment>();
  private listeners: Listener[] = [];
  private tooltip = byId<HTMLDivElement>("tooltip");

  reset(segments: Segment[]) {
    this.pathsBySegment.clear();
    this.segmentsById.clear();
    segments.forEach((s) => this.segmentsById.set(s.id, s));
  }

  registerPaths(id: number, els: SVGPolylineElement[]) {
    this.pathsBySegment.set(id, els);
  }

  onChange(fn: Listener) {
    this.listeners.push(fn);
  }

  highlight(id: number, evt?: MouseEvent) {
    this.pathsBySegment.forEach((els, sid) => {
      const on = sid === id;
      els.forEach((el) => {
        el.classList.toggle("hot", on);
        el.classList.toggle("dimmed", !on);
      });
    });
    this.listeners.forEach((fn) => fn(id));
    const seg = this.segmentsById.get(id);
    if (evt && seg) {
      this.tooltip.textContent = this.segmentLabel(seg);
      this.tooltip.style.opacity = "1";
      this.moveTooltip(evt);
    }
  }

  clear() {
    this.pathsBySegment.forEach((els) => els.forEach((el) => {
      el.classList.remove("hot");
      el.classList.remove("dimmed");
    }));
    this.listeners.forEach((fn) => fn(null));
    this.tooltip.style.opacity = "0";
  }

  moveTooltip(evt: MouseEvent) {
    this.tooltip.style.left = `${evt.clientX + 14}px`;
    this.tooltip.style.top = `${evt.clientY + 14}px`;
  }

  private segmentLabel(seg: Segment): string {
    const checks = seg.checks.length ? seg.checks.map((c) => CHECK_LABELS[c]).join(", ") : "none";
    return `segment ${seg.id}\nstatus: ${seg.status}  risk: ${seg.risk}/3\nchecks: ${checks}`;
  }
}
