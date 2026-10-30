"""Read-only diagnostic comparison. Shared candidates never suppress errors."""
import hashlib
import json
from pathlib import Path
import re

from .errors import ProbeError


def compare_sessions(root: Path, baseline_session_id: str, candidate_session_id: str) -> dict:
    def read(session_id, name):
        if not isinstance(session_id, str) or re.fullmatch(r"[a-f0-9]{32}", session_id) is None:
            raise ProbeError("invalid_session", "Use a session_id returned by get_run; paths are not accepted.")
        path = (root / session_id / name).resolve()
        if not path.is_relative_to(root.resolve()) or not path.is_file() or path.stat().st_size > 262144:
            raise ProbeError("baseline_unavailable", "Missing, escaped or oversized session evidence.")
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (ValueError, UnicodeError) as error:
            raise ProbeError("invalid_evidence", "Invalid session JSON.") from error
        if not isinstance(data, dict):
            raise ProbeError("invalid_evidence", "Expected session evidence object.")
        return data

    if baseline_session_id == candidate_session_id:
        raise ProbeError("invalid_baseline", "Baseline must be an independent run.")
    baseline = read(baseline_session_id, "run.json")
    candidate = read(candidate_session_id, "run.json")
    for manifest, session_id in ((baseline, baseline_session_id), (candidate, candidate_session_id)):
        if manifest.get("session_id") != session_id:
            raise ProbeError("invalid_evidence", "Manifest/session mismatch.")

    # Equal IDs/order do not prove equal target assemblies/assets. Report that limit explicitly.
    fields = ("game", "active_mods", "agent_sha256", "display_profile")
    mismatches = [field for field in fields if baseline.get(field) != candidate.get(field) or baseline.get(field) is None]
    if ("-quicktest" in baseline.get("arguments", [])) != ("-quicktest" in candidate.get("arguments", [])):
        mismatches.append("quicktest")
    if baseline.get("known_expansions") != candidate.get("known_expansions"):
        mismatches.append("known_expansions")
    baseline_profile, candidate_profile = baseline.get("profile", {}), candidate.get("profile", {})
    if baseline_profile.get("mode") != candidate_profile.get("mode") or baseline_profile.get("source_sha256") != candidate_profile.get("source_sha256"):
        mismatches.append("profile")
    diagnostics = [read(session_id, "startup.json") for session_id in (baseline_session_id, candidate_session_id)]
    def fingerprints(data):
        return {hashlib.sha256(re.sub(r"^\d{2}:\d{2}:\d{2} ", "", str(entry.get("line", ""))).encode("utf-8")).hexdigest(): str(entry.get("line", ""))[:400]
                for entry in data.get("error_candidates", [])[:40] if isinstance(entry, dict)}
    left, right = map(fingerprints, diagnostics)
    return {"baseline_session_id": baseline_session_id, "candidate_session_id": candidate_session_id,
            "environment_fields_match": not mismatches, "environment_mismatches": mismatches,
            "coverage_complete": all(not data.get("scan_truncated", True) and bool(data.get("sources")) for data in diagnostics),
            "shared_error_candidates": [{"fingerprint": key, "line": right[key]} for key in sorted(left.keys() & right.keys())],
            "candidate_only_errors": [{"fingerprint": key, "line": right[key]} for key in sorted(right.keys() - left.keys())],
            "attribution": "Shared exact-line candidates after stripping only a leading HH:MM:SS log clock prefix. No suppression, outcome upgrade or Mod blame. Full target/dependency binary and asset provenance is not captured; matching environment fields are not proof of equivalent installations.",
            "outcomes_modified": False}
