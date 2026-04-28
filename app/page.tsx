"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { AddressInput } from "@/components/AddressInput";
import { ChainSelector } from "@/components/ChainSelector";
import { LoadingSteps } from "@/components/LoadingSteps";
import type { AnalyzeErrorResponse, AnalyzeResponse } from "@/lib/types";

export default function HomePage() {
  const router = useRouter();
  const [chainId, setChainId] = useState(1);
  const [address, setAddress] = useState("");
  const [loading, setLoading] = useState(false);
  const [loadingStep, setLoadingStep] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const isLikelyAddress = useMemo(() => /^0x[a-fA-F0-9]{40}$/.test(address), [address]);

  useEffect(() => {
    if (!loading) {
      setLoadingStep(0);
      return;
    }

    const id = setInterval(() => {
      setLoadingStep((prev) => (prev < 3 ? prev + 1 : prev));
    }, 500);

    return () => clearInterval(id);
  }, [loading]);

  const onSubmit = async () => {
    if (!isLikelyAddress) {
      setError("Enter a valid EVM address (0x + 40 hex chars).");
      return;
    }

    setLoading(true);
    setLoadingStep(0);
    setError(null);
    try {
      const res = await fetch("/api/analyze", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ chain_id: chainId, address }),
      });

      const data = (await res.json()) as AnalyzeResponse | AnalyzeErrorResponse;

      if (!res.ok) {
        throw new Error(data && "error" in data ? data.error.message : "Unable to generate playbook");
      }

      sessionStorage.setItem("zm-last-result", JSON.stringify(data));
      router.push("/result");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unexpected error");
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="mx-auto flex min-h-screen w-full max-w-3xl flex-col justify-center px-4 py-10">
      <section className="zm-panel p-6 md:p-8">
        <p className="text-xs uppercase tracking-[0.25em] text-zm-primary">ZeroMinute IR</p>
        <h1 className="mt-2 text-3xl font-bold text-zm-text md:text-4xl">Code-Aware Emergency Runbooks in Minutes</h1>
        <p className="mt-3 text-sm text-zm-muted">
          Paste a verified contract address, inspect emergency controls, and generate a tactical 30-minute response plan.
        </p>

        <div className="mt-6 space-y-4">
          <ChainSelector value={chainId} onChange={setChainId} />
          <AddressInput value={address} onChange={setAddress} />
        </div>

        <button
          onClick={onSubmit}
          disabled={loading || !address || !isLikelyAddress}
          className="mt-6 w-full rounded-lg bg-zm-primary px-4 py-3 text-sm font-bold uppercase tracking-wide text-zm-bg transition hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-60"
        >
          Generate Playbook
        </button>

        {!loading && address && !isLikelyAddress ? (
          <p className="mt-3 text-xs text-zm-warning">Use checksum/raw hex format: `0x` + 40 hex characters.</p>
        ) : null}
        {loading ? <div className="mt-4"><LoadingSteps current={loadingStep} /></div> : null}
        {error ? <p className="mt-4 text-sm text-zm-danger">{error}</p> : null}
      </section>
    </main>
  );
}
