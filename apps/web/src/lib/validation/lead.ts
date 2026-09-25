// Mirrors the API's rules (apps/api/app/schemas/leads.py, app/leads/files.py) for fast,
// field-level feedback. The API remains the enforcement point.
import { z } from "zod";

export const NAME_MAX = 100;
export const EMAIL_MAX = 254;
export const MAX_RESUME_BYTES = 5 * 1024 * 1024;
export const RESUME_EXTENSIONS = [".pdf", ".doc", ".docx"] as const;
export const RESUME_ACCEPT = [
  ...RESUME_EXTENSIONS,
  "application/pdf",
  "application/msword",
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
].join(",");

const name = (label: string) =>
  z
    .string()
    .trim()
    .min(1, `${label} is required`)
    .max(NAME_MAX, `${label} must be at most ${NAME_MAX} characters`);

export function resumeError(file: File | undefined | null): string | null {
  if (!file) return "Please attach your resume";
  const lower = file.name.toLowerCase();
  if (!RESUME_EXTENSIONS.some((ext) => lower.endsWith(ext))) return "Resume must be a PDF, DOC, or DOCX file";
  if (file.size === 0) return "File is empty";
  if (file.size > MAX_RESUME_BYTES) return `File is too large (max ${MAX_RESUME_BYTES / (1024 * 1024)} MB)`;
  return null;
}

export const leadSchema = z.object({
  firstName: name("First name"),
  lastName: name("Last name"),
  email: z
    .string()
    .trim()
    .min(1, "Email is required")
    .max(EMAIL_MAX, `Email must be at most ${EMAIL_MAX} characters`)
    .pipe(z.email("Enter a valid email address")),
  resume: z.custom<File>((v) => v instanceof File, "Please attach your resume").superRefine((file, ctx) => {
    const message = resumeError(file);
    if (message) ctx.addIssue({ code: "custom", message });
  }),
  website: z.string().optional(), // honeypot
});

export type LeadFormInput = z.input<typeof leadSchema>;
export type LeadFormValues = z.output<typeof leadSchema>;
