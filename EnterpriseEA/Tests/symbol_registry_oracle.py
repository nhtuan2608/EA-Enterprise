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
