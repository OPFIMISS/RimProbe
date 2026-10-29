import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from mcp.server.mcpserver import MCPServer

from .controller import Controller, validate_game
from .errors import ProbeError
from .runner import TestRunner, capabilities
from .inspection import inspect_mod
from .schema import BehaviorContractInput
from .plans import ScenarioPlanInput


def create_server(game_path: Path, runs_path: Path, advanced_tools: bool = False, mods_config: Path | None = None, diagnostic_mod_mismatch: bool = False) -> MCPServer:
    controller = Controller(game_path, runs_path, mods_config, diagnostic_mod_mismatch)
    runner = TestRunner(controller)

    @asynccontextmanager
    async def lifespan(server):
        try:
            yield {}
        finally:
            await asyncio.to_thread(runner.shutdown)

    server = MCPServer(
        "RimProbe", version="0.1.0", lifespan=lifespan,
        instructions="Local RimWorld 1.6 and 1.7 test sessions only; version-specific Agent assemblies. No arbitrary code execution. "
        "No-error logs or map readiness do not prove functional correctness. cleanup_complete means attempt ended; "
        "require cleanup_status=succeeded and owned_process_exit_verified=true for verified cleanup.",
    )

    async def execute(function, *arguments):
        try:
            return await asyncio.to_thread(function, *arguments)
        except ProbeError as error:
            return error.as_dict()
        except OSError as error:
            return ProbeError("filesystem_error", str(error)).as_dict()

    @server.tool()
    async def rimprobe_doctor() -> dict:
        """Read the configured game version and assembly fingerprints without launching."""
        return await execute(validate_game, game_path)

    @server.tool()
    async def rimprobe_capabilities() -> dict:
        """Read supported suites, versions, limitations and the compact autonomous workflow. No game launch."""
        return capabilities()

    @server.tool()
    async def rimprobe_run_suite(def_name: str = "Wall", stuff_name: str | None = None,
                                extra_mods: list[str] | None = None, timeout_seconds: int = 180,
                                max_ticks: int = 60000, profile_mode: str = "inherit", supply_delay_ticks: int = 0) -> dict:
        """Start an autonomous building test in a private desktop. Returns run_id immediately; poll get_run every 2s. Real vanilla hauling/construction, not direct completion. Unknown functions are unsupported; worker stops automatically."""
        return await execute(runner.run_suite, def_name, stuff_name, extra_mods, timeout_seconds, max_ticks, profile_mode, None, supply_delay_ticks)

    @server.tool()
    async def rimprobe_inspect_mod(mod_path: str, version: str = "1.7") -> dict:
        """Read bounded trusted local source/Def hints without executing code. Not semantic proof. Use implementation knowledge to create an explicit effect contract; unknown action/observer adapters need review."""
        return await execute(inspect_mod, mod_path, version)

    @server.tool()
    async def rimprobe_run_plan(plan: ScenarioPlanInput, extra_mods: list[str] | None = None, profile_mode: str = "inherit") -> dict:
        """Compose <=24 typed steps with run-local handles: fixture, inspect/query, normal cast/ingest/equip/move/build, wait and state assertions. Batch executes in background; no reflection/eval. Declare fixture before actions. Poll get_run(wait_seconds=10) until cleanup_complete. Read capabilities.plans first."""
        return await execute(runner.run_plan, plan.model_dump(exclude_unset=True, by_alias=True), extra_mods, profile_mode)

    @server.tool()
    async def rimprobe_run_contract(contract: BehaviorContractInput, extra_mods: list[str] | None = None, profile_mode: str = "inherit") -> dict:
        """Run schema=1 code-derived contract: building_power, ability_cast, item_ingest, or ui_info_card. Uses normal jobs or the real UI draw loop; never directly writes expected outcomes. Default inherits enabled Mods/DLC. Returns run_id; final report includes actual order."""
        return await execute(runner.run_contract, contract.model_dump(exclude_unset=True, by_alias=True), extra_mods, profile_mode)

    @server.tool()
    async def rimprobe_get_run(run_id: str, wait_seconds: int = 0) -> dict:
        """Read stored progress; wait_seconds=10, bounded 0..15. controller_finished/cleanup_complete mean attempt ended, not cleanup success. Require cleanup_status=succeeded and owned_process_exit_verified=true. Failed cleanup remains queryable."""
        return await execute(runner.get_run, run_id, wait_seconds)

    @server.tool()
    async def rimprobe_cancel_run(run_id: str) -> dict:
        """Request cancellation; after controller_finished with a retained owned session, retry cleanup on that same session only. Poll cleanup_status and owned_process_exit_verified. No player-process scan or attach."""
        return await execute(runner.cancel_run, run_id)

    @server.tool()
    async def rimprobe_get_artifact(run_id: str, name: str) -> dict:
        """Read one bounded named report, startup log diagnosis or cleanup artifact. No arbitrary filesystem access."""
        return await execute(runner.get_artifact, run_id, name)

    if not advanced_tools:
        return server

    @server.tool()
    async def rimprobe_launch(quicktest: bool = True, extra_mods: list[str] | None = None, profile_mode: str = "inherit") -> dict:
        """Launch one owned game using a fresh isolated profile; extra_mods is an ordered packageId list."""
        return await execute(controller.launch, quicktest, extra_mods, profile_mode)

    @server.tool()
    async def rimprobe_get_state() -> dict:
        """Query the live Agent on the game's main thread; returns phase, map readiness and tick."""
        return await execute(controller.status)

    @server.tool()
    async def rimprobe_wait_ready(timeout: float = 180, require_map: bool = True) -> dict:
        """Wait up to 600 seconds for an Agent response or ready map; use get_state for short polls."""
        return await execute(controller.wait_ready, timeout, require_map)

    @server.tool()
    async def rimprobe_read_logs(limit: int = 100) -> dict:
        """Read bounded log tails belonging only to the active isolated run, including early process output."""
        return await execute(controller.logs, limit)

    @server.tool()
    async def rimprobe_stop() -> dict:
        """Terminate only this controller's owned game process; does not save or perform graceful in-game quit."""
        return await execute(controller.stop)

    return server
