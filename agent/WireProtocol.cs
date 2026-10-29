using System.Runtime.Serialization;
using System.Runtime.Serialization.Json;

namespace RimProbe.Agent;

internal static class WireJson
{
    public static byte[] Serialize<T>(T value)
    {
        using MemoryStream buffer = new();
        new DataContractJsonSerializer(typeof(T)).WriteObject(buffer, value);
        return buffer.ToArray();
    }

    public static T Deserialize<T>(byte[] bytes)
    {
        using MemoryStream buffer = new(bytes);
        return (T)(new DataContractJsonSerializer(typeof(T)).ReadObject(buffer)
            ?? throw new SerializationException("Empty JSON object."));
    }
}

[DataContract]
internal sealed class WireRequest
{
    [DataMember(Name = "protocol")] public int Protocol { get; set; }
    [DataMember(Name = "id")] public string? Id { get; set; }
    [DataMember(Name = "session_id")] public string? SessionId { get; set; }
    [DataMember(Name = "token")] public string? Token { get; set; }
    [DataMember(Name = "command")] public string? Command { get; set; }
    [DataMember(Name = "parameters")] public SuiteOptions? Parameters { get; set; }
}

[DataContract]
internal sealed class WireResponse
{
    [DataMember(Name = "protocol")] public int Protocol { get; set; } = 1;
    [DataMember(Name = "id")] public string? Id { get; set; }
    [DataMember(Name = "session_id")] public string? SessionId { get; set; }
    [DataMember(Name = "ok")] public bool Ok { get; set; }
    [DataMember(Name = "result")] public StateSnapshot? Result { get; set; }
    [DataMember(Name = "error")] public WireError? Error { get; set; }
}

[DataContract]
internal sealed class WireError
{
    [DataMember(Name = "code")] public string? Code { get; set; }
    [DataMember(Name = "message")] public string? Message { get; set; }
}

[DataContract]
internal sealed class BridgeDescriptor
{
    [DataMember(Name = "protocol")] public int Protocol { get; set; } = 1;
    [DataMember(Name = "session_id")] public string? SessionId { get; set; }
    [DataMember(Name = "pid")] public int Pid { get; set; }
    [DataMember(Name = "port")] public int Port { get; set; }
    [DataMember(Name = "agent_version")] public string AgentVersion { get; set; } = "0.1.0";
}

[DataContract]
internal sealed class StateSnapshot
{
    [DataMember(Name = "windows")] public string[] Windows { get; set; } = Array.Empty<string>();
    [DataMember(Name = "quicktest_requested")] public bool QuicktestRequested { get; set; }
    [DataMember(Name = "registered_tests")] public string[] RegisteredTests { get; set; } = Array.Empty<string>();
    [DataMember(Name = "red_error_sequence")] public long RedErrorSequence { get; set; }
    [DataMember(Name = "red_errors")] public ErrorEntry[] RedErrors { get; set; } = Array.Empty<ErrorEntry>();
    [DataMember(Name = "suite")] public SuiteReport? Suite { get; set; }
    [DataMember(Name = "phase")] public string? Phase { get; set; }
    [DataMember(Name = "map_ready")] public bool MapReady { get; set; }
    [DataMember(Name = "long_event_pending")] public bool LongEventPending { get; set; }
    [DataMember(Name = "tick")] public int? Tick { get; set; }
    [DataMember(Name = "paused")] public bool? Paused { get; set; }
    [DataMember(Name = "game_version")] public string? GameVersion { get; set; }
    [DataMember(Name = "map")] public MapSnapshot? Map { get; set; }
    [DataMember(Name = "loaded_mods")] public string[] LoadedMods { get; set; } = Array.Empty<string>();
}

[DataContract]
internal sealed class MapSnapshot
{
    [DataMember(Name = "id")] public int Id { get; set; }
    [DataMember(Name = "width")] public int Width { get; set; }
    [DataMember(Name = "height")] public int Height { get; set; }
}
