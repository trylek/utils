string?[] lines = File.ReadAllLines(args[0]);

Dictionary<string, string> batchVars = new Dictionary<string, string>();
Dictionary<string, string> bashVars = new Dictionary<string, string>();

int openPropertyGroup = -1;
int openBatch = -1;
int openBash = -1;
int appendLine = -1;
bool extraPropertyStuff = false;
bool extraScriptStuff = false;

for (int i = 0; i < lines.Length; i++)
{
    string line = lines[i]!.Trim();

    if (openPropertyGroup == -1)
    {
        if (line == "<PropertyGroup>")
        {
            Console.WriteLine($"PropertyGroup at {i}");
            openPropertyGroup = i;
        }
        continue;
    }

    if (line == "</PropertyGroup>")
    {
        Console.WriteLine($"/PropertyGroup at {i} - extraPropertyStuff={extraPropertyStuff}");
        if (!extraPropertyStuff)
        {
            lines[openPropertyGroup] = null;
            lines[i] = null;
        }
        openPropertyGroup = -1;
        openBatch = -1;
        openBash = -1;
        appendLine = -1;
        extraPropertyStuff = false;
        extraScriptStuff = false;
        continue;
    }

    if (openBatch == -1 && openBash == -1)
    {
        if (line == "<CLRTestBatchPreCommands><![CDATA[")
        {
            Console.WriteLine($"Batch at {i}");
            openBatch = i;
            continue;
        }
        if (line == "<BashCLRTestPreCommands><![CDATA[")
        {
            Console.WriteLine($"Bash at {i}");
            openBash = i;
            continue;
        }
        extraPropertyStuff = true;
        continue;
    }

    if (openBatch != -1)
    {
        if (line == "$(CLRTestBatchPreCommands)")
        {
            Console.WriteLine($"Append at {i}");
            appendLine = i;
            continue;
        }

        if (line.StartsWith("set "))
        {
            Console.WriteLine($"set at {i}");
            int varIndex = 4;
            int valueIndex = line.IndexOf("=");
            batchVars[line.Substring(varIndex, valueIndex - varIndex).Trim()] =
                line.Substring(valueIndex + 1).Trim();

            lines[i] = null;
            continue;
        }

        if (line == "]]></CLRTestBatchPreCommands>")
        {
            Console.WriteLine($"/Batch at {i} - extraScriptStuff={extraScriptStuff}");
            if (!extraScriptStuff)
            {
                lines[openBatch] = null;
                lines[i] = null;
                if (appendLine != -1) lines[appendLine] = null;
                extraScriptStuff = false;
            }
            openBatch = -1;
            appendLine = -1;
            continue;
        }

        extraScriptStuff = true;
        continue;
    }

    if (openBash != -1)
    {
        if (line == "$(BashCLRTestPreCommands)")
        {
            appendLine = i;
            continue;
        }

        if (line.StartsWith("export "))
        {
            int varIndex = 7;
            int valueIndex = line.IndexOf("=");
            bashVars[line.Substring(varIndex, valueIndex - varIndex).Trim()] =
                line.Substring(valueIndex + 1).Trim();

            lines[i] = null;
            continue;
        }

        if (line == "]]></BashCLRTestPreCommands>")
        {
            if (!extraScriptStuff)
            {
                lines[openBash] = null;
                lines[i] = null;
                if (appendLine != -1) lines[appendLine] = null;
                extraScriptStuff = false;
            }
            openBash = -1;
            appendLine = -1;
            continue;
        }

        extraScriptStuff = true;
        continue;
    }

    extraPropertyStuff = true;
}

if (batchVars.Count == 0)
{
    Console.WriteLine("No batch vars");
    return 1;
}

if (batchVars.Count != bashVars.Count)
{
    Console.WriteLine($"# of batch/bash vars don't match {batchVars.Count}/{bashVars.Count}");
    return 1;
}

foreach (var entry in batchVars)
{
    if (!bashVars.TryGetValue(entry.Key, out var value))
    {
        Console.WriteLine($"missing {entry.Key} in bash");
        return 1;
    }
    if (entry.Value != value)
    {
        Console.WriteLine($"Key {entry.Key} mismatch value {entry.Value} vs {value}");
        return 1;
    }
}

int endOfLastCompile = -1;

for (int i=lines.Length - 1; i >= 0; --i)
{
    string? line = lines[i];
    if (line == null) continue;
    line = line.Trim();

    if (line.StartsWith("<Compile"))
    {
        if (line.EndsWith("/>"))
        {
            endOfLastCompile = i;
        }
        else
        {
            for (int j = i; j < lines.Length; ++j)
            {
                if (line.Equals("</Compile>"))
                {
                    endOfLastCompile = j;
                    break;
                }

            }
        }
        if (endOfLastCompile != -1) break;
    }
}

if (endOfLastCompile == -1)
{
    Console.WriteLine("No Compile found");
    return 1;
}

bool newLineAtEnd;
using (FileStream fs = File.Open(args[0], FileMode.Open))
{
    fs.Seek(fs.Length - 1, SeekOrigin.Begin);
    int b = fs.ReadByte();
    newLineAtEnd = b == '\n';
    Console.WriteLine($"newLineAtEnd={newLineAtEnd}");
}

using (var sw = new StreamWriter(args[0]))
{
    for (int i = 0; i < lines.Length; ++i)
    {
        string? line = lines[i];
        if (line == null) continue;
        sw.Write(line);
        if (i < lines.Length - 1 || newLineAtEnd) sw.WriteLine();
        if (i == endOfLastCompile)
        {
            sw.WriteLine();
            foreach (var entry in batchVars)
            {
                sw.WriteLine($"    <CLRTestEnvironmentVariable Include=\"{entry.Key}\" Value=\"{entry.Value}\" />");
            }
        }
    }
}

return 0;