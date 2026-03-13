export type AnalyzeRequest = {
  chain_id: number;
  address: string;
};

export type Finding = {
  name: string;
  type: string;
  confidence: "confirmed" | "inferred";
  evidence: string;
  source_location?: string;
};

export type AnalyzeErrorResponse = {
  error: {
    code:
      | "invalid_request"
      | "invalid_address"
      | "unsupported_chain"
      | "contract_not_verified"
      | "upstream_fetch_failed"
      | "backend_unavailable";
    message: string;
  };
};

export type AnalyzeResponse = {
  contract: {
    chain_id: number;
    address: string;
    contract_name: string;
    verified: boolean;
  };
  confirmed_functions: Finding[];
  inferred_functions: Finding[];
  confirmed_roles: Finding[];
  inferred_roles: Finding[];
  manual_checks: string[];
  warnings: string[];
  runbook_markdown: string;
  normalized_source_summary?: {
    chain_id: number;
    address: string;
    verified: boolean;
    contract_name: string;
    compiler_version?: string | null;
    source_file_count: number;
    metadata_source?: string;
  };
  analyzer_findings?: {
    confirmed_functions: Finding[];
    inferred_functions: Finding[];
    confirmed_roles: Finding[];
    inferred_roles: Finding[];
    manual_checks: string[];
    warnings: string[];
  };
  runbook_json?: Record<string, unknown>;
};
