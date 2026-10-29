from pathlib import Path
import os
import re
import xml.etree.ElementTree as xml

from .errors import ProbeError


def inspect_mod(mod_path: str, version: str = "1.7") -> dict:
    root = Path(mod_path).resolve()
    if not root.is_dir() or version not in {"1.6", "1.7"}:
        raise ProbeError("invalid_mod_path", "Provide an existing trusted Mod/source directory and version 1.6 or 1.7.")
    candidates = []
    symbols = []
    problems = []
    files_read = total_bytes = 0
    truncated = False
    excluded = {".git", ".venv", "bin", "obj", "assemblies", "node_modules"}
    def paths():
        nonlocal truncated
        visited = entries = 0
        def failed(error):
            nonlocal truncated
            truncated = True
            problems.append({"path": str(error.filename), "error": str(error)[:300]})
        for directory, folders, filenames in os.walk(root, followlinks=False, onerror=failed):
            visited += 1
            if visited > 1000:
                truncated = True
                return
            kept = []
            for folder in sorted(folders):
                if folder.lower() in excluded or folder in {"1.6", "1.7"} and folder != version:
                    continue
                candidate = Path(directory) / folder
                try:
                    if not candidate.is_symlink() and not getattr(candidate.lstat(), "st_file_attributes", 0) & 0x400:
                        kept.append(folder)
                except OSError as error:
                    failed(error)
            folders[:] = kept
            for filename in sorted(filenames):
                entries += 1
                if entries > 12000:
                    truncated = True
                    return
                yield Path(directory) / filename

    for path in paths():
        relative = path.relative_to(root)
        if not path.is_file() or path.is_symlink() or any(part.lower() in excluded for part in relative.parts):
            continue
        if any(part in {"1.6", "1.7"} and part != version for part in relative.parts) or path.suffix.lower() not in {".cs", ".xml"}:
            continue
        if files_read >= 300 or total_bytes >= 8388608:
            truncated = True
            break
        try:
            if path.stat().st_size > 262144:
                truncated = True
                continue
            raw = path.read_bytes()
            files_read += 1
            total_bytes += len(raw)
            text = raw.decode("utf-8-sig")
            if path.suffix.lower() == ".cs":
                for match in list(re.finditer(r"\bclass\s+(\w+)(?:\s*:\s*([^\r\n{]+))?", text))[:24]:
                    symbols.append({"path": str(relative), "line": text[:match.start()].count("\n") + 1,
                                    "class": match.group(1), "bases": (match.group(2) or "").strip()[:200]})
                continue
            document = xml.fromstring(text)
            for node in document:
                name = node.findtext("defName")
                if not name or node.tag not in {"AbilityDef", "ThingDef", "HediffDef", "RecipeDef", "JobDef"}:
                    continue
                candidate = {"def_type": node.tag, "def_name": name, "path": str(relative),
                             "parent": node.get("ParentName"), "classes": sorted({entry.get("Class") for entry in node.iter() if entry.get("Class")})[:16]}
                if node.tag == "AbilityDef":
                    candidate["ability_class"] = node.findtext("abilityClass") or "inherited/default Ability"
                    candidate["declared_hediffs"] = sorted({(entry.text or "").strip() for entry in node.iter("hediffDef") if entry.text})[:16]
                    candidate["test_route"] = "Generate actor/target -> GainAbility -> normal QueueCastingJob/Verb/Job -> assert source-derived effect deltas."
                    candidate["contract_required"] = True
                if node.tag == "ThingDef":
                    candidate["declared_power_comps"] = sorted({entry.text.strip() for entry in node.findall("./comps/li/compClass") if entry.text and "Power" in entry.text})[:16]
                    candidate["declared_ingestible"] = node.find("ingestible") is not None
                    candidate["declared_ingestion_outcomes"] = sorted({entry.get("Class") for entry in node.findall("./ingestible/outcomeDoers/li") if entry.get("Class")})[:16]
                    candidate["test_route"] = "Resolved ingestible Def: item_ingest -> normal Ingest job -> source-derived assertions. Building: normal construction; declared power Comp suggests building_power after source review. ui_info_card: actual Stats drawing only."
                    candidate["contract_required"] = True
                candidates.append(candidate)
        except (OSError, UnicodeError, xml.ParseError) as error:
            problems.append({"path": str(relative), "error": str(error)[:300]})
    return {"ok": True, "mod_path": str(root), "version": version, "files_read": files_read,
            "scan_truncated": truncated or len(candidates) > 100 or len(symbols) > 100,
            "candidates": candidates[:100], "source_symbols": symbols[:100], "problems": problems[:20],
            "next": "Read relevant actual implementation with RimSage/source; submit a matching building_power/ability_cast/item_ingest/ui_info_card contract with explicit intent/source_refs/expect. Other actions need a matching adapter; XML hints do not resolve inheritance.",
            "limits": "Lexical/source hints only, not C# semantic proof; unresolved XML inheritance/patches and compiled-only Mods need live/source inspection. No code executed."}
