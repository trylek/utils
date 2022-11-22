using System.Text.RegularExpressions;
using static System.Net.Mime.MediaTypeNames;

Stats stats = new Stats();
bool printStats = false;
bool verbose = false;
bool onlySearchForJmp = false;

int argIndex = 0;
bool doneArgs = false;
while (!doneArgs && argIndex < args.Length)
{
    switch (args[argIndex])
    {
        case "-v":
            verbose = true;
            argIndex++;
            break;
        case "-s":
            printStats = true;
            argIndex++;
            break;
        case "-j":
            printStats = true;
            onlySearchForJmp = true;
            argIndex++;
            break;
        default:
            doneArgs = true;
            break;
    }
}

string filespec = args[argIndex++];
int error = 0;

if (File.Exists(filespec))
{
    error = ProcessFile(filespec, verbose, onlySearchForJmp, ref stats);
}
else if (Directory.Exists(filespec))
{
    foreach (string file in Directory.GetFiles(filespec, "*.il", SearchOption.AllDirectories))
    {
        error = Math.Max(error, ProcessFile(file, verbose, onlySearchForJmp, ref stats));
    }
}
else
{
    Console.WriteLine("*** not found {0}", filespec);
    return 1;
}

if (printStats)
{
    Console.WriteLine("Number of IL files: {0}", stats.Files);
    Console.WriteLine("Number of .entrypoint: {0}", stats.EntryPoints);
    foreach (var kvp in stats.EntryPointNames)
    {
        Console.WriteLine("   {0}:", kvp.Key);
        for (int i = 0; i < Math.Min(kvp.Value.Count, 5); ++i)
        {
            Console.WriteLine("        {0}", kvp.Value[i]);
        }
    }
    Console.WriteLine("Number with arg: {0}", stats.HasArg);
    foreach (var kvp in stats.ArgNames)
    {
        Console.WriteLine("   {0}:", kvp.Key);
        for (int i = 0; i < Math.Min(kvp.Value.Count, 5); ++i)
        {
            Console.WriteLine("        {0}", kvp.Value[i]);
        }
    }
    Console.WriteLine("Number with arg removed: {0}", stats.ArgRemoved);
    Console.WriteLine("Number with jmp: {0}", stats.FoundJmp);
}

return error;

static int ProcessFile(string filename, bool verbose, bool onlySearchForJmp, ref Stats stats)
{
    if (verbose) Console.WriteLine("file: {0}", filename);

    stats.Files++;

    List<string> lines = File.ReadAllLines(filename).ToList();

    string entrypointString = ".entrypoint";

    int numEntrypoints = lines.Where(line => line.Contains(entrypointString)).Count();
    if (numEntrypoints == 0)
    {
        if (verbose) Console.WriteLine("-V- no entrypoints in {0}", filename);
        return 0;
    }

    if (numEntrypoints > 1)
    {
        Console.WriteLine("*** multiple entrypoints in {0}", filename);
        return 1;
    }
    stats.EntryPoints++;

    int entrypointIndex = lines.FindIndex(line => line.Contains(entrypointString));
    if (verbose) Console.WriteLine("entry point {0}", entrypointIndex);

    int mainIndex;
    for (mainIndex = entrypointIndex; mainIndex >= 0; --mainIndex)
    {
        if (lines[mainIndex].Contains(".method")) break;
    }
    if (mainIndex == -1)
    {
        Console.WriteLine("*** no .method in {0}", filename);
        return 1;
    }

    string mainLine = lines[mainIndex];
    int mainColumn = 0;

    Regex[] mainRegexes =
    {
        new Regex(@"\.method(?:\s+(?:/\*06000002\*/|public|private|privatescope|assembly|hidebysig))*\s+static"),
        new Regex(@"\s+(?:int32|unsigned\s+int32|void)(?:\s+modopt\(\[mscorlib\]System\.Runtime\.CompilerServices\.CallConvCdecl\))?"),
        new Regex(@"\s+(?<main>[^\s(]+)\s*\("),
        new Regex(@"\s*(?:(?<type>class\s+(?:\[(?:mscorlib|'mscorlib')\])?System\.String|string)\s*\[\s*\](?:\s*(?<arg>[0-9a-zA-z_]+))?|(?<arg>[0-9a-zA-z_]+))?"),
        new Regex(@"\s*\)"),
    };
    List<int> mainMatchLineNumbers = new List<int>();
    List<Match> mainMatches = new List<Match>();

    for (int regexIndex = 0; regexIndex < mainRegexes.Length; ++regexIndex)
    {
        Regex mainRegex = mainRegexes[regexIndex];
        Match mainMatch = mainRegex.Match(mainLine, mainColumn);
        if (mainLine.Substring(mainColumn).All(c => char.IsWhiteSpace(c)))
        {
            mainIndex++;
            mainLine = lines[mainIndex];
            mainMatch = mainRegex.Match(mainLine);
        }
        if (!mainMatch.Success)
        {
            Console.WriteLine("*** RE {0} failure on {1} in {2}", regexIndex, mainLine, filename);
            return 1;
        }
        mainMatchLineNumbers.Add(mainIndex);
        mainMatches.Add(mainMatch);
        mainColumn = mainMatch.Index + mainMatch.Length;
    }

    string mainName = mainMatches[2].Groups["main"].Value;
    if (mainName[0] == '\'' && mainName[mainName.Length - 1] == '\'')
    {
        mainName = mainName.Substring(1, mainName.Length - 2);
    }
    stats.EntryPointNames[mainName] = stats.EntryPointNames.GetValueOrDefault(mainName, new List<string>());
    stats.EntryPointNames[mainName].Add(filename);
    string? argName = null;

    if (string.IsNullOrEmpty(mainMatches[3].Groups["type"].Value))
    {
        if (!onlySearchForJmp) return 0;
    }
    else
    {
        stats.HasArg++;
        argName = mainMatches[3].Groups["arg"].Value;
        stats.ArgNames[argName] = stats.ArgNames.GetValueOrDefault(argName, new List<string>());
        stats.ArgNames[argName].Add(filename);
    }

    int lineNumber = mainIndex;
    int column = mainColumn;

    bool inQuote = false; // assume Main declaration not in quotes...
    bool hasOpened = false;
    int open = 0;

    Regex jmpRegex = new Regex(@"^(?:\s*[0-9a-zA-Z_]+:)?\s*jmp\s+");
    Regex ldargRegex = new Regex(@"ldarga?(?:\.s?)?\s*(?<arg>[0-9a-zA-Z_]+)");
    // ldarg.n
    // ldarg n
    // ldarg name
    // ldarga n
    // ldarga.s name
    // regex will catch extras like ldarg0

    bool foundJmp = false;
    bool foundLdarg = false;

    for (; (lineNumber < lines.Count) && (!hasOpened || open > 0); lineNumber++, column = 0)
    {
        string line = lines[lineNumber];

        Match jmpMatch = jmpRegex.Match(line);
        if (jmpMatch.Success)
        {
            Console.WriteLine("found jmp in {0} #{1}: {2}", filename, lineNumber, line);
            foundJmp = true;
        }

        Match ldargMatch = ldargRegex.Match(line);
        if (ldargMatch.Success)
        {
            string matchArgName = ldargMatch.Groups["arg"].Value;
            if ((matchArgName == "0") || ((argName != null) && (matchArgName == argName)))
            {
                Console.WriteLine("found use in {0} #{1}: {2}", filename, lineNumber, line);
                foundLdarg = true;
            }
        }

        for (; column < line.Length; ++column)
        {
            char c = line[column];
            if (c == '"')
            {
                inQuote = !inQuote;
                continue;
            }

            if (inQuote)
            {
                continue;
            }

            if ((column == 0 ||
                line[column - 1] == ' ' ||
                (column > 1 && line[column - 1] == ':' && (line[column - 2] != ':'))) &&
                MemoryExtensions.Equals(line.AsSpan(column, Math.Min("jmp".Length, line.Length - column)), "jmp".AsSpan(), StringComparison.Ordinal))
            {
                Console.WriteLine("found non-pattern jmp in {0} #{1}: {2}", filename, lineNumber, line);
            }

            if (c == '{')
            {
                hasOpened = true;
                open++;
            }
            else if (c == '}')
            {
                open--;
            }

            if (hasOpened && (open == 0))
            {
                break;
            }
        }
    }

    if (foundJmp)
    {
        stats.FoundJmp++;
    }

    if (!foundLdarg && !foundJmp)
    {
        stats.ArgRemoved++;

        if (!onlySearchForJmp)
        {
            bool newLineAtEnd;
            using (FileStream fs = File.Open(filename, FileMode.Open))
            {
                fs.Seek(fs.Length - 1, SeekOrigin.Begin);
                int b = fs.ReadByte();
                newLineAtEnd = b == '\n';
                if (verbose) Console.WriteLine($"newLineAtEnd={newLineAtEnd}");
            }

            using (var sw = new StreamWriter(filename))
            {
                string? prevLine = null;
                for (int i = 0; i < lines.Count; ++i)
                {
                    string line = lines[i];
                    if (i == mainMatchLineNumbers[3])
                    {
                        line = line.Substring(0, mainMatches[3].Index) + line.Substring(mainMatches[3].Index + mainMatches[3].Length);
                        line = line.TrimEnd();
                        if (line == "")
                        {
                            if (((i + 1) < lines.Count) && (prevLine != null))
                            {
                                prevLine += lines[++i].Trim();
                            }
                            continue;
                        }
                    }
                    if (prevLine != null)
                    {
                        sw.WriteLine(prevLine);
                    }
                    prevLine = line;
                }

                if (prevLine != null)
                {
                    sw.Write(prevLine);
                    if (newLineAtEnd)
                    {
                        sw.WriteLine();
                    }
                }
            }
        }
    }

    return 0;
}

struct Stats
{
    public Stats() { }

    public int Files;
    public int EntryPoints;
    public Dictionary<string, List<string>> EntryPointNames = new Dictionary<string, List<string>>();
    public int HasArg;
    public Dictionary<string, List<string>> ArgNames = new Dictionary<string, List<string>>();
    public int ArgRemoved;
    public int FoundJmp;
}
