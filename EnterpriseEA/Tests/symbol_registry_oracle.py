"""Offline reference resolver for explicit symbol mapping, not MT5 discovery."""


def resolve(canonical: str, entries: list[dict], runtime: dict) -> dict:
    def result(status, reason, **values):
        return {"resolved": status == "RESOLVED", "status": status,
                "reason_code": reason, "canonical_symbol": canonical, **values}

    if not canonical or not runtime.get("configured_broker_server") or not runtime.get("observed_broker_server"):
        return result("BLOCKED", "BROKER_SERVER_IDENTITY_MISSING")
    if runtime["configured_broker_server"] != runtime["observed_broker_server"]:
        return result("BLOCKED", "BROKER_SERVER_IDENTITY_MISMATCH")

    matches = [row for row in entries if row.get("canonical_symbol") == canonical and
               row.get("broker_server") == runtime["observed_broker_server"]]
    if not matches:
        return result("UNRESOLVED", "NO_EXACT_SERVER_MAPPING")
    if len(matches) != 1:
        return result("UNRESOLVED", "AMBIGUOUS_EXACT_MAPPING")
    entry = matches[0]
    common = {"broker_server": entry.get("broker_server", ""),
              "broker_symbol": entry.get("broker_symbol", ""),
              "source_version": entry.get("source_version", ""),
              "metadata_version": entry.get("metadata_version", ""),
              "metadata_fingerprint": entry.get("metadata_fingerprint", "")}
    if entry.get("resolution_status") == "BLOCKED":
        return result("BLOCKED", "REGISTRY_ENTRY_BLOCKED", **common)
    if entry.get("resolution_status") != "RESOLVED" or not entry.get("broker_symbol"):
        return result("UNRESOLVED", "REGISTRY_ENTRY_UNRESOLVED", **common)
    if (entry.get("metadata_quality") != "OK" or not entry.get("source_version") or
            not entry.get("metadata_version") or not entry.get("metadata_fingerprint")):
        return result("UNRESOLVED", "REGISTRY_METADATA_INCOMPLETE", **common)
    if not runtime.get("broker_symbol_enabled"):
        return result("BLOCKED", "BROKER_SYMBOL_DISABLED", **common)
    if runtime.get("observed_broker_symbol") != entry["broker_symbol"]:
        return result("BLOCKED", "BROKER_SYMBOL_IDENTITY_MISMATCH", **common)
    if (runtime.get("metadata_quality") != "OK" or not runtime.get("metadata_version") or
            not runtime.get("metadata_fingerprint")):
        return result("UNRESOLVED", "RUNTIME_METADATA_INCOMPLETE", **common)
    if (runtime["metadata_version"] != entry["metadata_version"] or
            runtime["metadata_fingerprint"] != entry["metadata_fingerprint"]):
        return result("BLOCKED", "MATERIAL_SPEC_CHANGED", **common)
    return result("RESOLVED", "EXACT_MAPPING_AND_METADATA_CONFIRMED", **common)


def suggest(canonical: str, available: list[str]) -> tuple[int, str]:
    """Return advisory prefix/suffix matches only; caller must explicitly map them."""
    if not canonical:
        return 0, ""
    variants = []
    for candidate in available:
        if not candidate or candidate == canonical or len(candidate) <= len(canonical):
            continue
        if candidate.startswith(canonical) or candidate.endswith(canonical):
            if candidate not in variants:
                variants.append(candidate)
    return len(variants), variants[0] if len(variants) == 1 else ""
def normalize_canonical_csv(csv: str, max_symbols: int = 32) -> list[str]:
    if not csv:
        return []
    tokens = [t.strip().upper() for t in csv.split(',')]
    result = []
    for t in tokens:
        if t and t not in result:
            result.append(t)
    if not result or len(result) > max_symbols:
        return []
    return result

def rank_candidate(canonical: str, candidate: dict) -> tuple[int, str] | None:
    if not canonical or not candidate:
        return None
    c_upper = canonical.strip().upper()
    c_name = str(candidate.get("name") or candidate.get("broker_symbol") or candidate.get("symbol") or "").strip().upper()
    if not c_upper or not c_name:
        return None

    ALIASES = {"DXY": ("USDX",), "USOUSD": ("USOIL", "XTIUSD", "WTI"),
               "US500": ("SPCUSD", "SPX500", "SP500", "USA500")}

    tradeable = candidate.get("tradeable", True)
    conversion_only = candidate.get("conversion_only", False)
    rank_value = 5 if (not tradeable or conversion_only) else 0

    if c_name == c_upper:
        return (rank_value if rank_value == 5 else 1, "CONVERSION_ONLY" if conversion_only else "DISABLED" if rank_value == 5 else "EXACT_TRADEABLE")
    if c_name.startswith(c_upper) and len(c_name) > len(c_upper):
        return (rank_value if rank_value == 5 else 2, "CONVERSION_ONLY" if conversion_only else "DISABLED" if rank_value == 5 else "SUFFIX_TRADEABLE")
    if c_name.endswith(c_upper) and len(c_name) > len(c_upper):
        return (rank_value if rank_value == 5 else 2, "CONVERSION_ONLY" if conversion_only else "DISABLED" if rank_value == 5 else "PREFIX_TRADEABLE")
    for alias_target in ALIASES.get(c_upper, ()):
        if c_name == alias_target or c_name.startswith(alias_target) or c_name.endswith(alias_target):
            return (rank_value if rank_value == 5 else 4, "CONVERSION_ONLY" if conversion_only else "DISABLED" if rank_value == 5 else "ALIAS_TRADEABLE")

    return None

def resolve_batch(canonicals: list[str], available: list[dict]) -> list[dict]:
    results = []
    for canonical in canonicals:
        best_rank = 999
        best_candidates = []
        for candidate in available:
            match = rank_candidate(canonical, candidate)
            if match:
                rank_score, rank_reason = match
                if rank_score < best_rank:
                    best_rank = rank_score
                    best_candidates = [(candidate, rank_reason)]
                elif rank_score == best_rank:
                    best_candidates.append((candidate, rank_reason))
        
        c_name = ""
        status = "MISSING"
        reason_code = "NO_MATCHING_CANDIDATE"
        resolved = False

        if not best_candidates:
            pass
        elif best_rank >= 5:
            c_label = best_candidates[0][1]
            status = "DISABLED"
            reason_code = "CONVERSION_ONLY_SYMBOL" if c_label == "CONVERSION_ONLY" else "BROKER_SYMBOL_DISABLED"
        elif len(best_candidates) > 1:
            status = "AMBIGUOUS"
            reason_code = "AMBIGUOUS_BEST_RANK_MATCH"
        else:
            cand, reason = best_candidates[0]
            c_name = str(cand.get("name") or cand.get("broker_symbol") or cand.get("symbol") or "")
            status = "RESOLVED"
            resolved = True
            if reason == "EXACT_TRADEABLE": reason_code = "UNIQUE_EXACT_MATCH"
            elif reason == "SUFFIX_TRADEABLE": reason_code = "UNIQUE_SUFFIX_ROOT_MATCH"
            elif reason == "PREFIX_TRADEABLE": reason_code = "UNIQUE_PREFIX_ROOT_MATCH"
            elif reason == "ALIAS_TRADEABLE": reason_code = "UNIQUE_ALIAS_ROOT_MATCH"

        results.append({
            "canonical_symbol": canonical,
            "broker_symbol": c_name,
            "status": status,
            "resolved": resolved,
            "reason_code": reason_code
        })
    return results
