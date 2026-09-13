import type { RegionBundle, Segment, CheckName, Status } from "./types";
import { byId } from "./dom";
import type { Highlighter } from "./interaction";

const CHECK_LABELS: Record<CheckName, string> = {
  geometry: "Geometry",
  topology: "Topology",
  semantic: "Semantic",
};
const CHECK_KEYS: CheckName[] = ["geometry", "topology", "semantic"];

type SortKey = "id" | "risk";
type StatusFilter = "all" | Status;

interface TableState {
  sortKey: SortKey;
  sortDir: 1 | -1;
  statusFilter: StatusFilter;
  searchTerm: string;
}

const state: TableState = { sortKey: "risk", sortDir: -1, statusFilter: "all", searchTerm: "" };

export function resetTableFilters(): void {
  state.statusFilter = "all";
  state.searchTerm = "";
  byId<HTMLInputElement>("search").value = "";
  document.querySelectorAll<HTMLButtonElement>(".filter-btn").forEach((b) => {
    b.setAttribute("aria-pressed", b.dataset["filter"] === "all" ? "true" : "false");
  });
}

export function renderTable(data: RegionBundle, highlighter: Highlighter): void {
  const tbody = byId<HTMLTableSectionElement>("queue-body");
  const rows = [...data.segments].sort((a, b) => {
    const av = state.sortKey === "id" ? a.id : a.risk;
    const bv = state.sortKey === "id" ? b.id : b.risk;
    return av < bv ? -1 * state.sortDir : av > bv ? 1 * state.sortDir : 0;
  });

  tbody.innerHTML = "";
  let rank = 0;
  rows.forEach((seg: Segment) => {
    const visible =
      (state.statusFilter === "all" || seg.status === state.statusFilter) &&
      (!state.searchTerm || String(seg.id).includes(state.searchTerm));
    rank += 1;

    const tr = document.createElement("tr");
    tr.dataset["id"] = String(seg.id);
    if (!visible) tr.classList.add("hidden");

    const pipClass = seg.status === "REVIEW" ? "review" : "pass";
    const pips = [0, 1, 2]
      .map((i) => `<span class="pip ${i < seg.risk ? "on " + pipClass : ""}"></span>`)
      .join("");
    const tags = CHECK_KEYS.map(
      (k) => `<span class="check-tag ${seg.checks.includes(k) ? "fired-" + k : ""}" title="${CHECK_LABELS[k]}">${k[0]!.toUpperCase()}</span>`,
    ).join("");

    tr.innerHTML = `
      <td class="rank-cell mono">${rank}</td>
      <td class="id-cell">${seg.id}</td>
      <td><span class="risk-pips">${pips}</span></td>
      <td><span class="status-chip ${pipClass}">${seg.status}</span></td>
      <td><span class="check-tags">${tags}</span></td>`;

    tr.addEventListener("mouseenter", () => highlighter.highlight(seg.id));
    tr.addEventListener("mouseleave", () => highlighter.clear());
    tbody.appendChild(tr);
  });
}

export function wireTableControls(onChange: () => void): void {
  document.querySelectorAll<HTMLButtonElement>(".th-sort").forEach((btn) => {
    btn.addEventListener("click", () => {
      const key = btn.dataset["sort"] as SortKey;
      if (state.sortKey === key) {
        state.sortDir = state.sortDir === 1 ? -1 : 1;
      } else {
        state.sortKey = key;
        state.sortDir = key === "risk" ? -1 : 1;
      }
      document.querySelectorAll<HTMLButtonElement>(".th-sort").forEach((b) => {
        const active = b === btn;
        b.dataset["active"] = String(active);
        const arrow = b.querySelector(".arrow");
        if (arrow) arrow.textContent = active ? (state.sortDir === 1 ? "▲" : "▼") : "▲";
      });
      onChange();
    });
  });

  document.querySelectorAll<HTMLButtonElement>(".filter-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      state.statusFilter = btn.dataset["filter"] as StatusFilter;
      document.querySelectorAll<HTMLButtonElement>(".filter-btn").forEach((b) => {
        b.setAttribute("aria-pressed", String(b === btn));
      });
      onChange();
    });
  });

  byId<HTMLInputElement>("search").addEventListener("input", (e) => {
    state.searchTerm = (e.target as HTMLInputElement).value.trim();
    onChange();
  });
}

export function highlightRow(id: number | null): void {
  document.querySelectorAll<HTMLTableRowElement>("#queue-body tr").forEach((tr) => {
    tr.classList.toggle("hot", id !== null && tr.dataset["id"] === String(id));
  });
}
