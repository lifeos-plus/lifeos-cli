// Common, cross-domain API types
import type { components } from "@/services/api/generated/schema";

type PersonSummaryTransport = components["schemas"]["PersonSummaryResponse"];
type PersonTagSummary = PersonSummaryTransport["tags"][number];
export type PersonSummary = Pick<PersonSummaryTransport, "id"> &
  Partial<Omit<PersonSummaryTransport, "id" | "tags">> & {
    tags?: Array<Pick<PersonTagSummary, "category" | "entity_type" | "id" | "name"> &
      Partial<Omit<PersonTagSummary, "category" | "entity_type" | "id" | "name">>>;
  };
