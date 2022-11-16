// See https://aka.ms/new-console-template for more information

using System.Text.RegularExpressions;

bool verbose = false;
int argIndex = 0;
if (args[argIndex] == "-v")
{
    verbose = true;
    argIndex++;
}
string filename = args[argIndex++];

if (verbose) Console.WriteLine("file: {0}", filename);

List<string> lines = File.ReadAllLines(filename).ToList();

Regex mainRegex = new Regex("static *(?:unsafe *)?(?:int|void) *Main *(\\() *(?:s|S)tring *\\[ *\\] *([^ )]+) *(\\))");
int mainLineIndex = lines.FindIndex(line => mainRegex.Match(line).Success);

if (verbose) Console.WriteLine("main line {0}", mainLineIndex);

if (mainLineIndex == -1)
{
    return 0;
}

string mainLine = lines[mainLineIndex];
Match mainMatch = mainRegex.Match(mainLine);
int mainMatchIndex = mainMatch.Index;
int mainOpenParamsIndex = mainMatch.Groups[1].Index;
string argsName = mainMatch.Groups[2].Value;
int mainCloseParamsIndex = mainMatch.Groups[3].Index;
int argsLength = argsName.Length;

if (verbose) Console.WriteLine("main arg name {0}", argsName);

int lineNumber = mainLineIndex;
int column = mainMatch.Index + mainMatch.Length;

bool inQuote = false; // assume Main declaration not in quotes...
bool hasOpened = false;
int open = 0;

for (; lineNumber < lines.Count; lineNumber++, column = 0)
{
    string line = lines[lineNumber];
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

        if ((line.Count() >= column + argsLength) && MemoryExtensions.Equals(line.AsSpan(column, argsLength), argsName, StringComparison.Ordinal))
        {
            if (verbose) Console.WriteLine("found use on line #{0}: {1}", lineNumber, line);
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
    Console.WriteLine($"newLineAtEnd={newLineAtEnd}");
}

using (var sw = new StreamWriter(filename))
{
    for (int i = 0; i < lines.Count; ++i)
    {
        string line = lines[i];
        if (i == mainLineIndex)
        {
            sw.Write(line.AsSpan(0, mainOpenParamsIndex + 1));
            sw.Write(line.AsSpan(mainCloseParamsIndex));
        }
        else
        {
            sw.Write(line);
        }
        if (i < lines.Count() - 1 || newLineAtEnd) sw.WriteLine();
    }
}

return 0;
