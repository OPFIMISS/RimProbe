import difflib
from pathlib import Path
import re
import shutil
import subprocess
import sys


def apply_changes(changes):
    sections = []
    for filename, content in changes.items():
        target = Path(filename)
        if target.exists():
            original = target.read_text(encoding="utf-8-sig")
            if original == content:
                continue
            difference = "".join(list(difflib.unified_diff(original.splitlines(True), content.splitlines(True)))[2:])
            sections.append("*** Update File: " + filename + "\n" + re.sub(r"@@[^\n]*\n", "@@\n", difference))
        else:
            sections.append("*** Add File: " + filename + "\n" + "".join("+" + line + "\n" for line in content.splitlines()))
    if not sections:
        return
    wrapper = Path(shutil.which("apply_patch"))
    executable = Path(re.search(r'"([^"]+codex\.exe)"', wrapper.read_text()).group(1).replace("%~dp0", str(wrapper.parent) + "\\")).resolve()
    subprocess.run([str(executable), "--codex-run-as-apply-patch", "*** Begin Patch\n" + "".join(sections) + "*** End Patch"], check=True)


if __name__ == "__main__":
    import json
    apply_changes(json.load(sys.stdin))
