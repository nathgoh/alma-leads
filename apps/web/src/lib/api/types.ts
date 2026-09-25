import type { components } from "./schema";

type Schemas = components["schemas"];

export type LeadState = Schemas["LeadState"];
export type LeadSummary = Schemas["LeadSummary"];
export type LeadDetail = Schemas["LeadDetail"];
export type LeadPage = Schemas["LeadPage"];
export type EmailLog = Schemas["EmailLogOut"];
export type User = Schemas["UserOut"];

/** FastAPI error body: a string, or a list of field errors with `loc` like ["body", "email"]. */
export type ApiErrorBody = {
  detail?: string | { loc: (string | number)[]; msg: string; type?: string }[];
};
