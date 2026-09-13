import "./style.css";
import { REGIONS, DEFAULT_REGION } from "./regions";
import type { RegionBundle } from "./types";
import { byId } from "./dom";
import { Highlighter } from "./interaction";
import { renderDonut, renderRiskBars, renderCheckBars } from "./charts";
import { renderMap } from "./map";
import { renderTable, wireTableControls, highlightRow, resetTableFilters } from "./table";
import { wireHelpModal } from "./modal";
import { updateNotifyLink } from "./notify";

const highlighter = new Highlighter();
highlighter.onChange(highlightRow);

let currentKey = DEFAULT_REGION;

function currentData(): RegionBundle {
  const data = REGIONS[currentKey];
  if (!data) throw new Error(`unknown region "${currentKey}"`);
  return data;
}

function populateLogSelect(): void {
  const select = byId<HTMLSelectElement>("log-select");
  Object.entries(REGIONS).forEach(([key, data]) => {
    const opt = document.createElement("option");
    opt.value = key;
    opt.textContent = `${data.city_name} (${data.city}) · ${data.log_id.slice(0, 8)}… (${data.summary.total} segments)`;
    select.appendChild(opt);
  });
  select.value = currentKey;
}

function populateRegionChips(): void {
  const wrap = byId("region-chips");
  wrap.innerHTML = "";
  Object.entries(REGIONS).forEach(([key, data]) => {
    const chip = document.createElement("button");
    chip.type = "button";
    chip.className = "region-chip";
    chip.dataset["region"] = key;
    chip.setAttribute("aria-pressed", String(key === currentKey));
    chip.innerHTML = `${data.city_name} <span class="n">${data.summary.total}</span>`;
    chip.addEventListener("click", () => selectRegion(key));
    wrap.appendChild(chip);
  });
}

function syncChipsAndSelect(): void {
  byId<HTMLSelectElement>("log-select").value = currentKey;
  document.querySelectorAll<HTMLButtonElement>(".region-chip").forEach((chip) => {
    chip.setAttribute("aria-pressed", String(chip.dataset["region"] === currentKey));
  });
}

function renderStats(data: RegionBundle): void {
  byId("stat-total").textContent = String(data.summary.total);
  byId("stat-pass").textContent = String(data.summary.pass);
  byId("stat-review").textContent = String(data.summary.review);
  const rate = data.summary.total > 0 ? Math.round((data.summary.review / data.summary.total) * 100) : 0;
  byId("stat-rate").textContent = `${rate}%`;
  byId("stat-regions").textContent = String(Object.keys(REGIONS).length);

  byId("map-sub").textContent = `${data.log_id.slice(0, 8)}… · ${data.city_name} (${data.city})`;
  byId("queue-sub").textContent = `${data.summary.review} of ${data.summary.total} flagged`;
  byId("log-note").textContent = `— ${data.city_name} tile, pulled from the public AV2 bucket, scored, loaded to S3`;
}

function renderAll(): void {
  const data = currentData();
  renderStats(data);
  renderDonut(data);
  renderRiskBars(data);
  renderCheckBars(data);
  renderMap(data, highlighter);
  renderTable(data, highlighter);
  updateNotifyLink(data);
}

function selectRegion(key: string): void {
  currentKey = key;
  resetTableFilters();
  syncChipsAndSelect();
  renderAll();
}

function main(): void {
  populateLogSelect();
  populateRegionChips();

  byId<HTMLSelectElement>("log-select").addEventListener("change", (e) => {
    selectRegion((e.target as HTMLSelectElement).value);
  });

  wireTableControls(() => renderTable(currentData(), highlighter));
  wireHelpModal();

  renderAll();
}

main();
