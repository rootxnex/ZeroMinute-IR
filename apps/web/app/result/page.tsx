"use client";

import { useMemo } from "react";
import Link from "next/link";
import { DownloadButtons } from "@/components/DownloadButtons";
import { FunctionCard } from "@/components/FunctionCard";
import { MarkdownViewer } from "@/components/MarkdownViewer";
import { SummaryCard } from "@/components/SummaryCard";
import { WarningBox } from "@/components/WarningBox";
import type { AnalyzeResponse } from "@/lib/types";

export default function ResultPage() {
  const data = useMemo(() => {
    if (typeof window === "undefined") return null;
    const raw = sessionStorage.getItem("zm-last-result");
    if (!raw) return null;
    return JSON.parse(raw) as AnalyzeResponse;
  }, []);

  if (!data) {
    return (
      <main className="mx-auto flex min-h-screen max-w-3xl items-center justify-center px-4">
        <div className="zm-panel p-6 text-center">
          <p className="text-zm-muted">No analysis result found.</p>
          <Link className="mt-4 inline-block text-zm-primary" href="/">
            Back to input
          </Link>
        </div>
      </main>
    );
  }

  const findings = [...data.confirmed_functions, ...data.inferred_functions];
  const roles = [...data.confirmed_roles, ...data.inferred_roles];

  return (
    <main className="mx-auto w-full max-w-5xl px-4 py-8">
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-2xl font-bold text-zm-text">Incident Runbook</h1>
        <Link href="/" className="text-sm text-zm-primary">New Analysis</Link>
      </div>

      <section className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <SummaryCard title="Contract" value={data.contract.contract_name} />
        <SummaryCard title="Address" value={data.contract.address} />
        <SummaryCard title="Chain" value={String(data.contract.chain_id)} />
        <SummaryCard title="Verified" value={String(data.contract.verified)} />
      </section>

      <section className="mt-6 grid gap-4 lg:grid-cols-2">
        <div className="zm-panel p-4">
          <h2 className="mb-3 text-lg font-semibold">Emergency Functions</h2>
          <div className="space-y-3">
            {findings.map((f) => (
              <FunctionCard key={`${f.name}-${f.confidence}`} finding={f} />
            ))}
          </div>
        </div>

        <div className="zm-panel p-4">
          <h2 className="mb-3 text-lg font-semibold">Required Roles</h2>
          <div className="space-y-3">
            {roles.map((r) => (
              <FunctionCard key={`${r.name}-${r.confidence}`} finding={r} />
            ))}
          </div>
        </div>
      </section>

      <section className="mt-6 space-y-4">
        <WarningBox
          warnings={[
            ...data.warnings,
            "This runbook is an operational aid, not an execution guarantee.",
          ]}
          manualChecks={[
            ...data.manual_checks,
            "Always verify current signer access, proxy/implementation path, target contract state, and timelock or multisig constraints before executing emergency actions.",
          ]}
        />

        <MarkdownViewer markdown={data.runbook_markdown} />
        <DownloadButtons markdown={data.runbook_markdown} />
      </section>
    </main>
  );
}
