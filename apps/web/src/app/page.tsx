"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { createSession } from "@/lib/api";

export default function HomePage() {
  const router = useRouter();
  const [isCreating, setIsCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const onNewSession = async () => {
    try {
      setIsCreating(true);
      setError(null);
      const session = await createSession();
      router.push(`/session/${session.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create session");
    } finally {
      setIsCreating(false);
    }
  };

  return (
    <main className="mx-auto flex min-h-screen max-w-4xl flex-col justify-center px-6 py-12">
      <h1 className="text-4xl font-semibold tracking-tight">CSR Call Assistant</h1>
      <p className="mt-3 text-lg text-slate-300">
        Real-time agent assist for home services
      </p>

      <div className="mt-8">
        <button
          type="button"
          onClick={onNewSession}
          disabled={isCreating}
          className="rounded-md bg-blue-600 px-5 py-3 font-medium text-white transition hover:bg-blue-500 disabled:cursor-not-allowed disabled:bg-blue-800"
        >
          {isCreating ? "Creating..." : "New Session"}
        </button>
        {error ? <p className="mt-3 text-sm text-red-400">{error}</p> : null}
      </div>
    </main>
  );
}
