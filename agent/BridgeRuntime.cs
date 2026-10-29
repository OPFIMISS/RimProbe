using System.Collections.Concurrent;
using System.Diagnostics;
using System.Net;
using System.Net.Sockets;
using System.Text;
using System.Runtime.Serialization;
using RimWorld;
using Verse;

namespace RimProbe.Agent;

public sealed class BridgeRuntime : IDisposable
{
    private const int ProtocolVersion = 1;
    private const int MaximumMessageBytes = 65536;
    private readonly string directory;
    private readonly string sessionId;
    private readonly byte[] token;
    private readonly TcpListener listener = new(IPAddress.Loopback, 0);
    private readonly ConcurrentQueue<PendingRequest> queue = new();
    private readonly Thread worker;
    private volatile bool disposed;
    private readonly BuildingSuite suites = new();
    private readonly ScenarioSuite scenarioSuite = new();
    private readonly AbilitySuite abilitySuite = new();
    private readonly ItemSuite itemSuite = new();
    private readonly UiSuite uiSuite = new();
    private string contractMode = "building";
    private SuiteReport? ActiveReport => contractMode == "scenario" ? scenarioSuite.Report : contractMode == "item_ingest" ? itemSuite.Report
        : contractMode == "ui_info_card" ? uiSuite.Report : contractMode == "ability_cast" ? abilitySuite.Report : suites.Report;

    public static BridgeRuntime? Instance { get; set; }

    public BridgeRuntime(string directory, string sessionId, string token)
    {
        this.directory = directory;
        this.sessionId = sessionId;
        this.token = Encoding.UTF8.GetBytes(token);
        worker = new Thread(Listen) { IsBackground = true, Name = "RimProbe.LocalBridge" };
    }

    public void Start()
    {
        Directory.CreateDirectory(directory);
        listener.Start(4);
        byte[] descriptor = WireJson.Serialize(new BridgeDescriptor
        {
            SessionId = sessionId,
            Pid = Process.GetCurrentProcess().Id,
            Port = ((IPEndPoint)listener.LocalEndpoint).Port
        });
        string temporary = Path.Combine(directory, "bridge.json.tmp");
        File.WriteAllBytes(temporary, descriptor);
        File.Move(temporary, Path.Combine(directory, "bridge.json"));
        worker.Start();
    }

    public static void Pump()
    {
        BridgeRuntime? runtime = Instance;
        if (runtime == null || runtime.disposed)
        {
            return;
        }

        runtime.suites.Pump();
        runtime.scenarioSuite.Pump();
        runtime.abilitySuite.Pump();
        runtime.itemSuite.Pump();
        runtime.uiSuite.Pump();

        for (int count = 0; count < 4 && runtime.queue.TryDequeue(out PendingRequest? pending); count++)
        {
            lock (pending)
            {
                if (pending.Cancelled || Stopwatch.GetTimestamp() > pending.Deadline)
                {
                    pending.Cancelled = true;
                    pending.Completed.Set();
                    continue;
                }

                try
                {
                    bool starting = pending.Request.Command == "start_building_suite" || pending.Request.Command == "start_contract";
                    string? requestedMode = pending.Request.Command == "start_building_suite" ? "building" : pending.Request.Parameters?.Contract?.Recipe;
                    if (starting && runtime.ActiveReport?.Status == "running"
                        && (runtime.ActiveReport.RunId != pending.Request.Parameters?.RunId || runtime.contractMode != requestedMode))
                    {
                        throw new InvalidOperationException("A suite is already running.");
                    }
                    if (pending.Request.Command == "start_building_suite")
                    {
                        runtime.suites.Start(pending.Request.Parameters);
                        runtime.contractMode = "building";
                    }
                    else if (pending.Request.Command == "start_contract")
                    {
                        string? recipe = pending.Request.Parameters?.Contract?.Recipe;
                        if (recipe == "scenario") runtime.scenarioSuite.Start(pending.Request.Parameters);
                        else if (recipe == "ability_cast") runtime.abilitySuite.Start(pending.Request.Parameters);
                        else if (recipe == "building_power") runtime.suites.Start(pending.Request.Parameters);
                        else if (recipe == "item_ingest") runtime.itemSuite.Start(pending.Request.Parameters);
                        else if (recipe == "ui_info_card") runtime.uiSuite.Start(pending.Request.Parameters);
                        else throw new ArgumentException("Unsupported contract recipe.");
                        runtime.contractMode = recipe;
                    }
                    else if (pending.Request.Command == "cancel_suite")
                    {
                        runtime.suites.Cancel();
                        runtime.scenarioSuite.Cancel();
                        runtime.abilitySuite.Cancel();
                        runtime.itemSuite.Cancel();
                        runtime.uiSuite.Cancel();
                    }
                    pending.Result = Snapshot();
                    pending.Result.Suite = runtime.ActiveReport;
                }
                catch (Exception error)
                {
                    pending.Error = error.ToString();
                }
                finally
                {
                    pending.Completed.Set();
                }
            }
        }
    }

    private static StateSnapshot Snapshot()
    {
        bool busy = LongEventHandler.AnyEventNowOrWaiting;
        Game? game = busy ? null : Current.Game;
        Map? map = game?.CurrentMap;
        bool playing = Current.ProgramState == ProgramState.Playing;
        bool mapReady = playing && map != null && !busy;
        return new StateSnapshot
        {
            Windows = busy ? Array.Empty<string>() : Find.WindowStack.Windows.Take(12).Select(window => window.GetType().FullName ?? window.GetType().Name).ToArray(),
            QuicktestRequested = GenCommandLine.CommandLineArgPassed("quicktest"),
            RegisteredTests = RegisteredProbeTests.Keys,
            Phase = busy ? "loading" : mapReady ? "playing" : Current.ProgramState.ToString().ToLowerInvariant(),
            MapReady = mapReady,
            LongEventPending = busy,
            Tick = game?.tickManager?.TicksGame,
            Paused = game?.tickManager?.Paused,
            GameVersion = VersionControl.CurrentVersionStringWithRev,
            Map = map == null ? null : new MapSnapshot { Id = map.uniqueID, Width = map.Size.x, Height = map.Size.z },
            LoadedMods = LoadedModManager.RunningModsListForReading.Select(mod => mod.PackageId).ToArray(),
            RedErrorSequence = ErrorJournal.Sequence,
            RedErrors = ErrorJournal.Snapshot()
        };
    }

    private void Listen()
    {
        while (!disposed)
        {
            try
            {
                using TcpClient client = listener.AcceptTcpClient();
                client.ReceiveTimeout = 2000;
                client.SendTimeout = 2000;
                Handle(client.GetStream());
            }
            catch (Exception error)
            {
                if (!disposed)
                {
                    RecordTransportError(error);
                }
            }
        }
    }

    private void Handle(NetworkStream stream)
    {
        using MemoryStream buffer = new();
        long deadline = Stopwatch.GetTimestamp() + Stopwatch.Frequency * 2;
        while (buffer.Length < MaximumMessageBytes)
        {
            if (Stopwatch.GetTimestamp() > deadline)
            {
                throw new IOException("RimProbe request read deadline expired.");
            }

            int next = stream.ReadByte();
            if (next == -1)
            {
                return;
            }

            if (next == '\n')
            {
                break;
            }

            buffer.WriteByte((byte)next);
        }

        if (buffer.Length >= MaximumMessageBytes)
        {
            throw new IOException("RimProbe request exceeds the size limit.");
        }

        WireRequest request;
        try
        {
            request = WireJson.Deserialize<WireRequest>(buffer.ToArray());
        }
        catch (SerializationException)
        {
            Reply(stream, "", null, "invalid_request", "Malformed request JSON or invalid field types.");
            return;
        }

        string requestId = request.Id ?? "";
        if (request.Protocol != ProtocolVersion || request.SessionId != sessionId)
        {
            Reply(stream, requestId, null, "protocol_mismatch", "Unsupported protocol or session.");
            return;
        }

        byte[] suppliedToken = Encoding.UTF8.GetBytes(request.Token ?? "");
        if (!TokensEqual(suppliedToken, token))
        {
            Reply(stream, requestId, null, "unauthorized", "Invalid session token.");
            return;
        }

        if (request.Command != "get_state" && request.Command != "start_building_suite" && request.Command != "start_contract" && request.Command != "cancel_suite")
        {
            Reply(stream, requestId, null, "unknown_command", "Supported commands: get_state, start_building_suite, start_contract, cancel_suite.");
            return;
        }

        if (queue.Count >= 32)
        {
            Reply(stream, requestId, null, "queue_full", "Main-thread queue is full.");
            return;
        }

        PendingRequest pending = new() { Request = request };
        queue.Enqueue(pending);
        if (!pending.Completed.Wait(3000))
        {
            lock (pending)
            {
                if (!pending.Completed.IsSet)
                {
                    pending.Cancelled = true;
                }
            }
        }

        lock (pending)
        {
            if (pending.Cancelled)
            {
                Reply(stream, requestId, null, "main_thread_timeout", "Game main thread did not service the request in time.");
            }
            else if (pending.Error != null)
            {
                Reply(stream, requestId, null, "snapshot_failed", pending.Error);
            }
            else
            {
                Reply(stream, requestId, pending.Result, null, null);
            }
        }
    }

    private static bool TokensEqual(byte[] supplied, byte[] expected)
    {
        if (supplied.Length != expected.Length)
        {
            return false;
        }

        int difference = 0;
        for (int index = 0; index < expected.Length; index++)
        {
            difference |= supplied[index] ^ expected[index];
        }

        return difference == 0;
    }

    private void Reply(NetworkStream stream, string requestId, StateSnapshot? result, string? code, string? message)
    {
        byte[] payload = WireJson.Serialize(new WireResponse
        {
            Id = requestId,
            SessionId = sessionId,
            Ok = code == null,
            Result = result,
            Error = code == null ? null : new WireError { Code = code, Message = message }
        });
        if (payload.Length > MaximumMessageBytes - 1)
        {
            throw new IOException("RimProbe response exceeds the size limit.");
        }

        stream.Write(payload, 0, payload.Length);
        stream.WriteByte((byte)'\n');
    }

    private void RecordTransportError(Exception error)
    {
        try
        {
            string path = Path.Combine(directory, "agent.log");
            if (!File.Exists(path) || new FileInfo(path).Length < 1048576)
            {
                File.AppendAllText(path, DateTime.UtcNow.ToString("O") + " " + error.GetType().Name + ": " + error.Message + Environment.NewLine);
            }
        }
        catch (Exception)
        {
        }
    }

    public void Dispose()
    {
        disposed = true;
        listener.Stop();
    }

    private sealed class PendingRequest
    {
        public WireRequest Request = new();
        public readonly ManualResetEventSlim Completed = new();
        public readonly long Deadline = Stopwatch.GetTimestamp() + Stopwatch.Frequency * 3;
        public bool Cancelled;
        public StateSnapshot? Result;
        public string? Error;
    }
}
