// Prospects (public, no auth): submit contact details and a resume.
import Link from "next/link";

import { LeadForm } from "@/components/LeadForm";

export default function HomePage() {
  return (
    <main className="mx-auto flex min-h-screen max-w-xl flex-col justify-center px-4 py-12">
      <div className="mb-8 space-y-2">
        <p className="text-sm font-semibold tracking-wide text-zinc-500 uppercase">Alma</p>
        <h1 className="text-3xl font-semibold tracking-tight">Get an assessment of your case</h1>
        <p className="text-zinc-600">
          Share a few details and your resume. An attorney will review your information and reach out by
          email.
        </p>
      </div>
      <div className="rounded-xl border border-zinc-200 bg-white p-6 shadow-sm sm:p-8">
        <LeadForm />
      </div>
      <div className="mt-2 mb-8 space-y-2">
        <p className="text-sm font-light tracking-tight">
          Not a client?{" "}
          <Link href="/login" className="font-medium text-zinc-900 underline underline-offset-4 hover:text-zinc-600">
            Sign in as an attorney
          </Link>
          .
        </p>
      </div>
    </main>
  );
}
