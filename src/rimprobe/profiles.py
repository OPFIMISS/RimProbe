import hashlib
import os
from pathlib import Path
import xml.etree.ElementTree as xml

from .errors import ProbeError


def default_mods_config() -> Path:
    home = os.environ.get("USERPROFILE")
    if not home:
        raise ProbeError("profile_source_missing", "Specify --mods-config; the default Windows player profile cannot be located.")
    return Path(home) / "AppData" / "LocalLow" / "Ludeon Studios" / "RimWorld by Ludeon Studios" / "Config" / "ModsConfig.xml"


def plan_profile(mode: str, additions: list[str], source: Path | None = None) -> dict:
    if mode not in {"inherit", "minimal"}:
        raise ProbeError("invalid_profile_mode", "Use inherit (default) or explicitly request minimal.")
    original = []
    provenance = {"mode": mode, "source": None, "source_sha256": None, "original_mods": [], "added_mods": [],
                  "player_config_modified": False, "settings_cloned": False, "dlc_policy": "Preserve enabled entries; no licensing/source filtering."}
    if mode == "inherit":
        source = (source or default_mods_config()).resolve()
        try:
            if source.stat().st_size > 8388608:
                raise ProbeError("profile_too_large", "ModsConfig exceeds 8 MiB.")
            raw = source.read_bytes()
            root = xml.fromstring(raw)
            original = [(item.text or "").strip().lower() for item in root.findall("activeMods/li")]
        except (OSError, xml.ParseError) as error:
            raise ProbeError("profile_source_missing", f"Cannot read {source}; specify --mods-config or explicitly select minimal. {error}") from error
        if not original or any(not item for item in original) or len(original) != len(set(original)):
            raise ProbeError("invalid_profile", "Source activeMods is empty, contains blank IDs or duplicates; no automatic repair was applied.")
        provenance.update(source=str(source), source_sha256=hashlib.sha256(raw).hexdigest(), original_mods=list(original))
    else:
        original = ["brrainz.harmony", "ludeon.rimworld"]
    mods = list(original)
    if "ludeon.rimworld" not in mods:
        raise ProbeError("invalid_profile", "Source profile does not enable Core; refusing to silently reconstruct its load order.")
    if "brrainz.harmony" not in mods:
        mods.insert(0, "brrainz.harmony")
        provenance["added_mods"].append("brrainz.harmony")
    for package_id in [*additions, "rimprobe.agent"]:
        normalized = package_id.strip().lower()
        if normalized not in mods:
            mods.append(normalized)
            provenance["added_mods"].append(normalized)
    provenance["requested_mods"] = mods
    return provenance
