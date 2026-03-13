import { NextRequest, NextResponse } from "next/server";

// Local dev: set `ANALYZER_BASE_URL` in `apps/web/.env.local`.
// Example: `ANALYZER_BASE_URL=http://localhost:8000`
const ANALYZER_BASE_URL = process.env.ANALYZER_BASE_URL;

type AnalyzeRequest = {
  chain_id: number;
  address: string;
};

type ErrorPayload = {
  error: {
    code: string;
    message: string;
  };
};

function isAnalyzeRequest(value: unknown): value is AnalyzeRequest {
  if (typeof value !== "object" || value === null) {
    return false;
  }

  const candidate = value as Record<string, unknown>;
  return typeof candidate.chain_id === "number" && typeof candidate.address === "string";
}

function backendUnavailableResponse() {
  return NextResponse.json(
    {
      error: {
        code: "backend_unavailable",
        message: "Analyzer service is unavailable",
      },
    },
    { status: 503 },
  );
}

export async function POST(req: NextRequest) {
  if (!ANALYZER_BASE_URL) {
    return backendUnavailableResponse();
  }

  let body: unknown;
  try {
    body = await req.json();
  } catch {
    return NextResponse.json(
      {
        error: {
          code: "invalid_request",
          message: "Request body must be valid JSON",
        },
      },
      { status: 400 },
    );
  }

  if (!isAnalyzeRequest(body)) {
    return NextResponse.json(
      {
        error: {
          code: "invalid_request",
          message: "chain_id and address are required",
        },
      },
      { status: 400 },
    );
  }

  try {
    const upstream = await fetch(`${ANALYZER_BASE_URL}/analyze`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        chain_id: body.chain_id,
        address: body.address,
      }),
      cache: "no-store",
    });

    let data: unknown;
    try {
      data = await upstream.json();
    } catch {
      data = {
        error: {
          code: "backend_unavailable",
          message: "Analyzer service is unavailable",
        },
      } satisfies ErrorPayload;
    }

    return NextResponse.json(data, { status: upstream.status });
  } catch {
    return backendUnavailableResponse();
  }
}
