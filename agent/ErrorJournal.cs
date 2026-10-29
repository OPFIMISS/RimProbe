using System.Runtime.Serialization;

namespace RimProbe.Agent;

[DataContract]
public sealed class ErrorEntry
{
    [DataMember(Name = "sequence")] public long Sequence { get; set; }
    [DataMember(Name = "text")] public string Text { get; set; } = "";
}

public static class ErrorJournal
{
    private static readonly object gate = new();
    private static readonly Queue<ErrorEntry> entries = new();
    private static long sequence;

    public static long Sequence { get { lock (gate) { return sequence; } } }

    public static void Record(string text)
    {
        lock (gate)
        {
            sequence++;
            entries.Enqueue(new ErrorEntry { Sequence = sequence, Text = (text ?? "").Length > 1000 ? text!.Substring(0, 1000) : text ?? "" });
            while (entries.Count > 16)
            {
                entries.Dequeue();
            }
        }
    }

    public static ErrorEntry[] Snapshot()
    {
        lock (gate)
        {
            return entries.ToArray();
        }
    }
}
