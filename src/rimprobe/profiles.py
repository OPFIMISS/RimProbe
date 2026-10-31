import hashlib
import os
from pathlib import Path
import xml.etree.ElementTree as xml
from typing import Literal

from .errors import ProbeError

ProfileMode = Literal["inherit", "minimal", "minimal_all_installed_dlc"]
PROFILE_MODES = ("inherit", "minimal", "minimal_all_installed_dlc")


def default_mods_config() -> Path:
    home = os.environ.get("USERPROFILE")
    if not home:
        raise ProbeError("profile_source_missing", "Specify --mods-config; the default Windows player profile cannot be located.")
    return Path(home) / "AppData" / "LocalLow" / "Ludeon Studios" / "RimWorld by Ludeon Studios" / "Config" / "ModsConfig.xml"


def plan_profile(mode: str, additions: list[str], source: Path | None = None,
                 installed_dlc: list[str] | None = None) -> dict:
    if mode not in PROFILE_MODES:
        raise ProbeError("invalid_profile_mode", "Use inherit (default), minimal, or minimal_all_installed_dlc.")
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
        if mode == "minimal_all_installed_dlc":
            if installed_dlc is None:
                raise ProbeError("dlc_inventory_required", "All-DLC mode requires the installed game's About metadata inventory.")
            if any(not isinstance(p, str) or not p.startswith("ludeon.rimworld.") or p != p.strip().lower() for p in installed_dlc):
                raise ProbeError("invalid_dlc_inventory", "DLC inventory must contain exact official package IDs.")
            original.extend(dict.fromkeys(installed_dlc))
            provenance["installed_dlc"] = list(dict.fromkeys(installed_dlc))
            provenance["dlc_policy"] = "All installed DLC About identities; no licensing/source filtering. Never inherit the player Mod list."
    mods = list(original)
    if "ludeon.rimworld" not in mods:
        raise ProbeError("invalid_profile", "Source profile does not enable Core; refusing to silently reconstruct its load order.")
    if "brrainz.harmony" not in mods:
        mods.insert(0, "brrainz.harmony")
        provenance["added_mods"].append("brrainz.harmony")
    # New trusted test packs can reference IProbeTest during assembly loading.
    # Preserve inherited order, but insert a missing Agent BEFORE any appended packs.
    for package_id in ["rimprobe.agent", *additions]:
        normalized = package_id.strip().lower()
        if normalized not in mods:
            mods.append(normalized)
            provenance["added_mods"].append(normalized)
    provenance["requested_mods"] = mods
    return provenance
