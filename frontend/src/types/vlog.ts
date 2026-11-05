export type VlogMediaType = "image" | "video";
export interface VlogMedia {
  id: string;
  media_type: VlogMediaType;
  filename: string;
  content_type: string;
  size_bytes: number;
  url: string;
  created_at: string;
}
export interface Vlog {
  id: string;
  pet_id: string;
  caption: string | null;
  occurred_on: string;
  media: VlogMedia[];
  created_at: string;
  updated_at: string;
}
export interface VlogFilter {
  pet_id?: string;
  from_date?: string;
  to_date?: string;
}
export interface VlogUpdateInput {
  caption?: string | null;
  occurred_on?: string;
}
