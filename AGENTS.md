# RimProbe development rules

- Keep README.md current: architecture, goals, commands, limitations, pitfalls, and validation evidence.
- Distinguish offline tests, real-game assembly compilation, and actual in-game verification.
- Never modify normal player saves or Mod configuration. Use per-run profiles.
- Never expose arbitrary code execution. Game access runs on the game main thread.
- Do not bundle game assemblies or Harmony. Do not invent author or license metadata.
- Support RimWorld 1.6 (Unity/Mono, net472) and 1.7 (Waylith, net10.0) with separate references, outputs, and intermediate directories. Record validation separately for each version.
- Use the installed MCP SDK contract, not remembered FastMCP signatures.
- Run focused tests and compilation after changes. Do not launch the game unless specifically needed for the task.
