// See https://aka.ms/new-console-template for more information

using System.IO;
using System.Text.RegularExpressions;

Stats stats = new Stats();
bool printStats = false;
bool verbose = false;

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
        default:
            doneArgs = true;
            break;
    }
}

string filespec = args[argIndex++];
int error = 0;

if (File.Exists(filespec))
{
    error = ProcessFile(filespec, verbose, ref stats);
}
else if (Directory.Exists(filespec))
{
    foreach (string file in Directory.GetFiles(filespec, "*.cs", SearchOption.AllDirectories))
    {
        error = Math.Max(error, ProcessFile(file, verbose, ref stats));
    }
}
else
{
    Console.WriteLine("*** not found {0}", filespec);
    return 1;
}

if (printStats)
{
    Console.WriteLine("Number of C# files: {0}", stats.Files);
    Console.WriteLine("Number of Main methods: {0}", stats.Mains);
    Console.WriteLine("Number with arg: {0}", stats.HasArg);
    foreach (var kvp in stats.ArgNames)
    {
        Console.WriteLine("   {0}:", kvp.Key);
        for (int i = 0; i < Math.Min(kvp.Value.Count, 5); ++i)
        {
            Console.WriteLine("        {0}", kvp.Value[i]);
        }
        if (kvp.Value.Count > 5)
        {
            Console.WriteLine("        ...");
        }
    }
    Console.WriteLine("Number with arg removed: {0}", stats.ArgRemoved);
}

return error;

static int ProcessFile(string filename, bool verbose, ref Stats stats)
{
    //if (verbose) Console.WriteLine("file: {0}", filename);

    stats.Files++;

    List<string> lines = File.ReadAllLines(filename).ToList();

    Regex existsMainRegex = new Regex(@"(^| +)Main *($|\()");
    int existsMainLineNumber = lines.FindIndex(line => existsMainRegex.Match(line).Success);
    if (existsMainLineNumber == -1)
    {
        return 0;
    }

    int staticForMainDeclLineNumber = lines.FindLastIndex(existsMainLineNumber, line => line.Contains("static"));
    if (staticForMainDeclLineNumber == -1)
    {
        Console.WriteLine("Couldn't find \"static\" before Main @ {0} in {1}", existsMainLineNumber, filename);
        return 0;
    }
    stats.Mains++;
    if (verbose) Console.WriteLine("main line {0} in {1}", existsMainLineNumber, filename);

    int lineNumber = staticForMainDeclLineNumber;
    string line = lines[lineNumber];
    int column = 0;

    Regex skipRegex = new Regex(@"^\s*(?://.*)?$");
    Regex[] mainRegexes =
    {
        new Regex(@"static"),
        new Regex(@"\s+(?:unsafe\s+)?(?:int|void)"),
        new Regex(@"\s+Main"),
        new Regex(@"(?<open>\() *(?:(?:s|(?:System.)?S)tring *\[ *\] *(?<arg>[0-9a-zA-Z_]+) *)?(?<close>\))")
    };
    const int mainOpenParenIndex = 3;
    const int mainArgIndex = 3;
    const int mainCloseParentIndex = 3;
    List<int> mainMatchLineNumbers = new List<int>();
    List<Match> mainMatches = new List<Match>();

    for (int regexIndex = 0; regexIndex < mainRegexes.Length; ++regexIndex)
    {
        while (skipRegex.Match(line.Substring(column)).Success)
        {
            line = lines[++lineNumber];
            column = 0;
        }
        Regex mainRegex = mainRegexes[regexIndex];
        Match mainMatch = mainRegex.Match(line, column);
        if (!mainMatch.Success)
        {
            Console.WriteLine("Couldn't match RE #{0} for Main at {1}:{2} in {3}", regexIndex, lineNumber, column, filename);
            Console.WriteLine("  {0}", line);
            Console.WriteLine("  {0}^", new string(' ', column));
            return 0;
        }
        mainMatchLineNumbers.Add(lineNumber);
        mainMatches.Add(mainMatch);
        column = mainMatch.Index + mainMatch.Length;
    }

    int mainOpenParenColumn = mainMatches[mainOpenParenIndex].Groups["open"].Index;
    string argsName = mainMatches[mainArgIndex].Groups["arg"].Value;
    int mainCloseParenColumn = mainMatches[mainCloseParentIndex].Groups["close"].Index;
    int argsLength = argsName.Length;

    if (string.IsNullOrEmpty(argsName))
    {
        return 0;
    }
    stats.HasArg++;

    if (verbose) Console.WriteLine("main arg name {0}", argsName);
    stats.ArgNames[argsName] = stats.ArgNames.GetValueOrDefault(argsName, new List<string>());
    stats.ArgNames[argsName].Add(filename);

    lineNumber = mainMatchLineNumbers[mainCloseParentIndex];
    line = lines[lineNumber];
    column = mainMatches[mainCloseParentIndex].Index + mainMatches[mainCloseParentIndex].Length;

    bool inQuote = false; // assume Main declaration not in quotes...
    bool hasOpened = false;
    int open = 0;

    for (; (lineNumber < lines.Count) && (!hasOpened || open > 0); lineNumber++, column = 0)
    {
        line = lines[lineNumber];
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

            if ((line.Count() >= column + argsLength)
                && (column == 0 || !char.IsAsciiLetterOrDigit(line[column - 1])) // avoid matching a partial token, this is not a full check
                && MemoryExtensions.Equals(line.AsSpan(column, argsLength), argsName, StringComparison.Ordinal))
            {
                Console.WriteLine("found use on line #{0} in {1}", lineNumber, filename);
                Console.WriteLine(line);
                return 0;
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

    bool newLineAtEnd;
    using (FileStream fs = File.Open(filename, FileMode.Open))
    {
        fs.Seek(fs.Length - 1, SeekOrigin.Begin);
        int b = fs.ReadByte();
        newLineAtEnd = b == '\n';
    }

    using (var sw = new StreamWriter(filename))
    {
        for (int i = 0; i < lines.Count; ++i)
        {
            line = lines[i];
            if (i == mainMatchLineNumbers[mainOpenParenIndex])
            {
                sw.Write(line.AsSpan(0, mainOpenParenColumn + 1));
                sw.Write(line.AsSpan(mainCloseParenColumn));
            }
            else
            {
                sw.Write(line);
            }
            if (i < lines.Count() - 1 || newLineAtEnd) sw.WriteLine();
        }
    }

    stats.ArgRemoved++;
    return 0;
}

struct Stats
{
    public Stats() { }

    public int Files;
    public int Mains;
    public int HasArg;
    public Dictionary<string, List<string>> ArgNames = new Dictionary<string, List<string>>();
    public int ArgRemoved;
}