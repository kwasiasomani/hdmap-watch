import type { RegionBundle } from "./types";
import pit from "../data/pit.json";
import mia from "../data/mia.json";

// Insertion order is display order — Pittsburgh first (the original log),
// Miami second (the first city added when this scaled past one region).
// Adding a tenth region is: run scripts/build_viz_data.py, drop the json
// in site/data/, add one line here.
export const REGIONS: Record<string, RegionBundle> = {
  pit: pit as RegionBundle,
  mia: mia as RegionBundle,
};

export const DEFAULT_REGION = "pit";
