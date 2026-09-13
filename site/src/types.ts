export type CheckName = "geometry" | "topology" | "semantic";
export type Status = "PASS" | "REVIEW";

export interface Segment {
  id: number;
  risk: 0 | 1 | 2 | 3;
  status: Status;
  checks: CheckName[];
  is_intersection: boolean;
  left: [number, number][];
  right: [number, number][];
}

export interface Bounds {
  xmin: number;
  xmax: number;
  ymin: number;
  ymax: number;
}

export interface Summary {
  total: number;
  pass: number;
  review: number;
  geometry_flagged: number;
  topology_flagged: number;
  semantic_flagged: number;
}

export interface RegionBundle {
  log_id: string;
  city: string;
  city_name: string;
  bounds: Bounds;
  summary: Summary;
  segments: Segment[];
}

export type RegionKey = string;
