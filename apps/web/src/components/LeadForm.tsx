"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { Controller, useForm } from "react-hook-form";

import { browserApi } from "@/lib/api/browser";
import { parseApiError } from "@/lib/api/errors";
import {
  EMAIL_MAX,
  type LeadFormInput,
  type LeadFormValues,
  MAX_RESUME_BYTES,
  NAME_MAX,
  RESUME_ACCEPT,
  leadSchema,
} from "@/lib/validation/lead";

import { Alert, Button, Field, inputClass } from "./ui";

const FIELDS = ["firstName", "lastName", "email", "resume"] as const;

function toFormData(values: LeadFormValues): FormData {
  const fd = new FormData();
  fd.set("firstName", values.firstName);
  fd.set("lastName", values.lastName);
  fd.set("email", values.email);
  fd.set("website", values.website ?? "");
  fd.set("resume", values.resume, values.resume.name);
  return fd;
}

export function LeadForm() {
  const [submitted, setSubmitted] = useState(false);
  const [generalError, setGeneralError] = useState<string | null>(null);
  const {
    register,
    control,
    handleSubmit,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<LeadFormInput, unknown, LeadFormValues>({
    resolver: zodResolver(leadSchema),
    mode: "onTouched",
    defaultValues: { firstName: "", lastName: "", email: "", website: "" },
  });

  const onSubmit = handleSubmit(async (values) => {
    setGeneralError(null);
    try {
      const { error, response } = await browserApi.POST("/api/v1/leads", {
        // Multipart: the typed body is replaced by real FormData (with the File) on the wire.
        body: values as never,
        bodySerializer: () => toFormData(values),
      });
      if (response.ok) {
        setSubmitted(true);
        return;
      }
      const { fields, general } = parseApiError(response.status, error);
      for (const name of FIELDS) {
        if (fields[name]) setError(name, { type: "server", message: fields[name] }, { shouldFocus: true });
      }
      setGeneralError(general);
    } catch {
      setGeneralError("Couldn't send your information. Check your connection and try again.");
    }
  });

  if (submitted) {
    return (
      <div role="status" className="space-y-2 text-center">
        <h2 className="text-lg font-semibold">Thank you!</h2>
        <p className="text-sm text-zinc-600">
          We received your information. Check your inbox for a confirmation — an attorney will be in touch
          soon.
        </p>
      </div>
    );
  }

  const describedBy = (name: string, hint = false) =>
    errors[name as keyof typeof errors] ? `${name}-error` : hint ? `${name}-hint` : undefined;

  return (
    <form onSubmit={onSubmit} noValidate className="space-y-5" aria-label="Lead form">
      {generalError && <Alert>{generalError}</Alert>}

      <div className="grid gap-5 sm:grid-cols-2">
        <Field id="firstName" label="First name" error={errors.firstName?.message}>
          <input
            id="firstName"
            autoComplete="given-name"
            maxLength={NAME_MAX}
            aria-invalid={!!errors.firstName}
            aria-describedby={describedBy("firstName")}
            className={inputClass(!!errors.firstName)}
            {...register("firstName")}
          />
        </Field>
        <Field id="lastName" label="Last name" error={errors.lastName?.message}>
          <input
            id="lastName"
            autoComplete="family-name"
            maxLength={NAME_MAX}
            aria-invalid={!!errors.lastName}
            aria-describedby={describedBy("lastName")}
            className={inputClass(!!errors.lastName)}
            {...register("lastName")}
          />
        </Field>
      </div>

      <Field id="email" label="Email" error={errors.email?.message}>
        <input
          id="email"
          type="email"
          autoComplete="email"
          maxLength={EMAIL_MAX}
          aria-invalid={!!errors.email}
          aria-describedby={describedBy("email")}
          className={inputClass(!!errors.email)}
          {...register("email")}
        />
      </Field>

      <Field
        id="resume"
        label="Resume / CV"
        error={errors.resume?.message}
        hint={`PDF, DOC, or DOCX — up to ${MAX_RESUME_BYTES / (1024 * 1024)} MB`}
      >
        <Controller
          control={control}
          name="resume"
          render={({ field: { onChange, onBlur, name, ref } }) => (
            <input
              id="resume"
              name={name}
              ref={ref}
              type="file"
              accept={RESUME_ACCEPT}
              aria-invalid={!!errors.resume}
              aria-describedby={describedBy("resume", true)}
              onBlur={onBlur}
              onChange={(e) => onChange(e.target.files?.[0])}
              className="block w-full text-sm text-zinc-700 file:mr-3 file:rounded-md file:border-0 file:bg-zinc-100 file:px-3 file:py-2 file:text-sm file:font-medium hover:file:bg-zinc-200"
            />
          )}
        />
      </Field>

      {/* Honeypot: hidden from people and assistive tech; bots fill every field. */}
      <div aria-hidden="true" className="absolute -left-[10000px] h-px w-px overflow-hidden">
        <label htmlFor="website">Website</label>
        <input id="website" tabIndex={-1} autoComplete="off" {...register("website")} />
      </div>

      <Button type="submit" disabled={isSubmitting} className="w-full">
        {isSubmitting ? "Submitting…" : "Submit"}
      </Button>
    </form>
  );
}
