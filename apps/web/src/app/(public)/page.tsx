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
    </main>
  );
}
