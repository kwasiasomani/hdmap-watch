import { byId } from "./dom";

export function wireHelpModal(): void {
  const backdrop = byId<HTMLDivElement>("help-backdrop");
  const open = () => { backdrop.hidden = false; };
  const close = () => { backdrop.hidden = true; };

  byId("help-btn").addEventListener("click", open);
  byId("help-close").addEventListener("click", close);
  backdrop.addEventListener("click", (e) => { if (e.target === backdrop) close(); });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && !backdrop.hidden) close();
  });
}
