// Licensed to the .NET Foundation under one or more agreements.
// The .NET Foundation licenses this file to you under the MIT license.

using System;
using System.Diagnostics;
using System.Reflection;
using System.Reflection.Metadata.Ecma335;
using System.Runtime.InteropServices;
using System.Security.Authentication.ExtendedProtection;
using System.Text;
using System.Text.RegularExpressions;

namespace ILTransform
{
    public class ILRewriter
    {
        private static string[] s_xUnitLines =
        {
            ".assembly extern xunit.core {}",
        };

        private static string[] s_factLines =
        {
            ".custom instance void [xunit.core]Xunit.FactAttribute::.ctor() = (",
            "    01 00 00 00",
            ")",
        };

        private static string[] s_csFactLines =
        {
            "[Fact]",
        };

        private static string[] s_processIsolationLines =
        {
            "<RequiresProcessIsolation>true</RequiresProcessIsolation>",
        };

        // Add 'linesToAdd' to 'lines' at index 'index' with indentation copied from 'modelLine'
        // Returns index of lines after the inserted lines
        private static int InsertIndentedLines(List<string> lines, int index, IEnumerable<string> linesToAdd, string modelLine)
        {
            int indent = TestProject.GetIndent(modelLine);
            string indentString = modelLine.Substring(0, indent);
            int oldCount = lines.Count;
            lines.InsertRange(index, linesToAdd.Select(line => indentString + line));
            return index + lines.Count - oldCount;
        }

        private readonly TestProject _testProject;
        private readonly HashSet<string> _classNameDuplicates;
        private readonly Settings _settings;
        private readonly HashSet<string> _rewrittenFiles;

        public ILRewriter(
            TestProject testProject,
            HashSet<string> classNameDuplicates,
            Settings settings,
            HashSet<string> rewrittenFiles)
        {
            _testProject = testProject;
            _classNameDuplicates = classNameDuplicates;
            _settings = settings;
            _rewrittenFiles = rewrittenFiles;
        }

        public void Rewrite()
        {
            if (!string.IsNullOrEmpty(_testProject.TestClassSourceFile) && _rewrittenFiles.Add(_testProject.TestClassSourceFile))
            {
                RewriteFile(_testProject.TestClassSourceFile);
            }
            if (!_settings.DeduplicateClassNames)
            {
                RewriteProject(_testProject.NewAbsolutePath ?? _testProject.AbsolutePath);
            }
        }

        private void RewriteFile(string source)
        {
            List<string> lines = new List<string>(File.ReadAllLines(source));
            bool isILTest = Path.GetExtension(source).ToLower() == ".il";
            bool rewritten = false;

            if (Path.GetFileName(source).Equals("instance.il", StringComparison.OrdinalIgnoreCase))
            {
                Console.WriteLine("RewriteFile: {0}", source);
            }

            if (!string.IsNullOrEmpty(_testProject.MainMethodName) /*&& !_settings.CleanupILModuleAssembly*/)
            {
                int lineIndex = _testProject.LastMainMethodLine;
                if (lineIndex >= 0)
                {
                    int lineInBody = lines.FindIndex(lineIndex, line => line.Contains('{') || (!isILTest && line.Contains("=>")));
                    if (lineInBody == -1)
                    {
                        Console.Error.WriteLine("Opening brace or => for main method not found in file: {0}", source);
                    }

                    if ((lineInBody >= 0) && _settings.AddILFactAttributes && !_testProject.HasFactAttribute)
                    {
                        int indentLine = (isILTest ? lineInBody + 1 : lineIndex);
                        string firstMainBodyLine = lines[indentLine];
                        int indent = TestProject.GetIndent(firstMainBodyLine);
                        string indentString = firstMainBodyLine.Substring(0, indent);
                        if (isILTest)
                        {
                            InsertIndentedLines(lines, lineInBody + 1, s_factLines, firstMainBodyLine);
                        }
                        else
                        {
                            lines[_testProject.MainTokenMethodLine] =
                                ReplaceIdent(lines[_testProject.MainTokenMethodLine], "Main", "TestEntryPoint");
                            lineIndex = InsertIndentedLines(lines, lineIndex, s_csFactLines, firstMainBodyLine);
                        }
                        _testProject.AddedFactAttribute = true;
                        rewritten = true;
                    }

                    if (_settings.UncategorizedCleanup /*&& !_settings.CleanupILModuleAssembly*/)
                    {
                        if (isILTest)
                        {
                            string line = lines[_testProject.FirstMainMethodLine];
                            if (!line.Contains(".method"))
                            {
                                Console.WriteLine("Internal error re-finding .method in {0}", source);
                            }
                            if (TestProject.MakePublic(isILTest: isILTest, ref line, force: true))
                            {
                                lines[_testProject.FirstMainMethodLine] = line;
                                rewritten = true;
                            }
                        }
                        else
                        {
                            string line = lines[_testProject.FirstMainMethodLine];
                            TestProject.MakePublic(isILTest: isILTest, ref line, force: true);
                            lines[_testProject.FirstMainMethodLine] = line;
                            rewritten = true;
                        }

                        foreach (string baseClassName in _testProject.TestClassBases)
                        {
                            for (int index = 0; index < lines.Count; index++)
                            {
                                string line = lines[index];
                                if (index != _testProject.TestClassLine &&
                                    (line.Contains("class") || line.Contains("struct")) &&
                                    line.Contains(baseClassName))
                                {
                                    if (TestProject.MakePublic(isILTest: isILTest, ref line, force: true))
                                    {
                                        lines[index] = line;
                                        rewritten = true;
                                    }
                                    break;
                                }
                            }
                        }
                    }

                    /*
                    int closingParen = line.IndexOf(')', mainPos + MainTag.Length);
                    if (!_settings.DeduplicateClassNames)
                    {
                        string replacement = " Test(";
                        lines[lineIndex] = line.Substring(0, mainPos) + replacement + line.Substring(closingParen);
                        rewritten = true;
                    }
                    lines[lineIndex] = line.Substring(0, mainPos) + replacement + line.Substring(mainPos + MainTag.Length);
                    rewritten = true;
                    */

                    /*
                    for (int privateIndex = lineIndex; privateIndex >= lineIndex - 1 && privateIndex >= 0; privateIndex--)
                    {
                        line = lines[privateIndex];
                        int privatePos = line.IndexOf("private ");
                        if (privatePos >= 0)
                        {
                            if (!_settings.DeduplicateClassNames)
                            {
                                line = line.Substring(0, privatePos) + "public" + line.Substring(privatePos + 7);
                                lines[privateIndex] = line;
                                rewritten = true;
                            }
                            break;
                        }
                        int publicPos = line.IndexOf("public ");
                        if (publicPos >= 0)
                        {
                            break;
                        }
                    }
                    */
                }
            }

            if (_settings.UncategorizedCleanup && _testProject.TestClassLine < 0)
            {
                if (isILTest)
                {
                    string classLine = $".class public auto ansi Test_{Path.GetFileNameWithoutExtension(source)} extends [mscorlib] System.Object {{";
                    lines.Insert(_testProject.FirstMainMethodLine, classLine);
                    lines.Add("}");
                    rewritten = true;
                }
            }
            else if (_settings.UncategorizedCleanup /*&& !_settings.CleanupILModuleAssembly*/)
            {
                string line = lines[_testProject.TestClassLine];
                TestProject.MakePublic(isILTest: isILTest, ref line, force: true);
                lines[_testProject.TestClassLine] = line;
                rewritten = true;
            }

            if (!_settings.DeduplicateClassNames /*&& !_settings.CleanupILModuleAssembly*/)
            {
                bool hasXunitReference = false;
                string testName = _testProject.TestProjectAlias!;
                bool addFactAttribute = _settings.AddILFactAttributes && !_testProject.HasFactAttribute && isILTest;
                if (isILTest)
                {
                    for (int lineIndex = 0; lineIndex < lines.Count; lineIndex++)
                    {
                        string line = lines[lineIndex];
                        if (line.StartsWith(".assembly extern xunit.core"))
                        {
                            hasXunitReference = true;
                            if (!line.Contains('}'))
                            {
                                int endLine = lineIndex;
                                do
                                {
                                    endLine++;
                                }
                                while (!lines[endLine].Contains('}'));
                                lines.RemoveRange(lineIndex + 1, endLine - lineIndex);
                                lines[lineIndex] = s_xUnitLines[0];
                                rewritten = true;
                            }
                            break;
                        }
                    }

                    for (int lineIndex = 0; lineIndex < lines.Count; lineIndex++)
                    {
                        string line = lines[lineIndex];
                        if (line.StartsWith(".assembly"))
                        {
                            while (!lines[lineIndex].Contains('}'))
                            {
                                lineIndex++;
                            }

                            line = lines[++lineIndex];
                            if (addFactAttribute && !hasXunitReference)
                            {
                                lines.InsertRange(lineIndex, s_xUnitLines);
                                rewritten = true;
                            }
                            break;
                        }

                        /*
                        int start = assemblyIndex + AssemblyTag.Length;
                        for (; ;)
                        {
                            int start = assemblyIndex + AssemblyTag.Length;
                            for (; ; )
                            {
                                while (start < line.Length && Char.IsWhiteSpace(line[start]))
                                {
                                    start++;
                                }
                                const string LibraryTag = "library";
                                if (start + LibraryTag.Length <= line.Length && line.Substring(start, LibraryTag.Length) == LibraryTag)
                                {
                                    start += LibraryTag.Length;
                                    continue;
                                }
                                const string LegacyTag = "legacy";
                                if (start + LegacyTag.Length <= line.Length && line.Substring(start, LegacyTag.Length) == LegacyTag)
                                {
                                    start += LegacyTag.Length;
                                    continue;
                                }

                                if (start + 2 <= line.Length && line[start] == '/' && line[start + 1] == '*')
                                {
                                    start += 2;
                                    while (start + 2 <= line.Length && !(line[start] == '*' && line[start + 1] == '/'))
                                    {
                                        start++;
                                    }
                                    continue;
                                }
                                break;
                            }
                            bool quoted = (start < line.Length && line[start] == '\'');
                            if (quoted)
                            {
                                start++;
                            }
                            int end = start;
                            while (end < line.Length && line[end] != '\'' && (quoted || TestProject.IsIdentifier(line[end])))
                            {
                                end++;
                            }
                            string ident = line.Substring(start, end - start);
                            if (ident != testName)
                            {
                                line = line.Substring(0, start) + (quoted ? "" : "'") + testName + (quoted ? "" : "'") + line.Substring(end);
                                lines[lineIndex] = line;
                                rewritten = true;
                                break;
                            }
                        }
                        */
                    }
                }

                if (_settings.UncategorizedCleanup
                    && _testProject.TestClassNamespace == ""
                    && _testProject.DeduplicatedNamespaceName != null)
                {
                    int lineIndex = _testProject.NamespaceLine;
                    lines.Insert(lineIndex, (isILTest ? "." : "") + "namespace " + _testProject.DeduplicatedNamespaceName);
                    lines.Insert(lineIndex + 1, "{");
                    lines.Add("}");
                    for (int i = lineIndex; i < lines.Count; i++)
                    {
                        if (TestProject.GetILClassName(lines[i], out string? className))
                        {
                            string qualifiedClassName = _testProject.DeduplicatedNamespaceName + "." + className!;
                            for (int s = lineIndex; s < lines.Count; s++)
                            {
                                if (s != i)
                                {
                                    lines[s] = ReplaceIdent(lines[s], className!, qualifiedClassName, IdentKind.TypeUse);
                                }
                            }
                        }
                    }

                    rewritten = true;
                }
                else if (_settings.UncategorizedCleanup
                    && _testProject.DeduplicatedNamespaceName != null)
                {
                    if (isILTest)
                    {
                        for (int lineIndex = _testProject.NamespaceLine; lineIndex < lines.Count; lineIndex++)
                        {
                            lines[lineIndex] = ReplaceIdent(lines[lineIndex], _testProject.TestClassNamespace, _testProject.DeduplicatedNamespaceName, IdentKind.Namespace);
                        }
                    }
                    else
                    {
                        lines[_testProject.NamespaceLine] = lines[_testProject.NamespaceLine].Replace(_testProject.TestClassNamespace, _testProject.DeduplicatedNamespaceName);
                    }
                    rewritten = true;
                }

                if (_settings.UncategorizedCleanup && !isILTest)
                {
                    bool usingXUnit = (_testProject.LastUsingLine >= 0 && lines[_testProject.LastUsingLine].Contains("Xunit"));
                    int rewriteLine = _testProject.LastUsingLine;
                    if (rewriteLine == -1)
                    {
                        rewriteLine = _testProject.LastHeaderCommentLine;
                    }
                    rewriteLine++;
                    if (!usingXUnit)
                    {
                        lines.Insert(rewriteLine++, "using Xunit;");
                        rewritten = true;
                    }
                }
            }

            if (_settings.CleanupILModule && isILTest)
            {
                if (lines.RemoveAll(line => line.Contains(".module")) > 0)
                {
                    rewritten = true;
                }
            }

            if (_settings.CleanupILAssembly && isILTest)
            {
                for (int lineIndex = 0; lineIndex < lines.Count; lineIndex++)
                {
                    string line = lines[lineIndex];
                    int assemblyIndex = line.EndIndexOf(".assembly");
                    if (assemblyIndex >= 0)
                    {
                        for (int charIndex = assemblyIndex; charIndex < line.Length; charIndex++)
                        {
                            if (char.IsWhiteSpace(line[charIndex]))
                            {
                                continue;
                            }
                            if (line[charIndex] == '/' && charIndex + 1 < line.Length && line[charIndex + 1] == '*')
                            {
                                charIndex += 2;
                                while (charIndex + 1 < line.Length && !(line[charIndex] == '*' && line[charIndex + 1] == '/'))
                                {
                                    charIndex++;
                                }
                                charIndex++;
                                continue;
                            }
                            int identStart = charIndex;
                            string assemblyName;
                            if (line[charIndex] == '\'')
                            {
                                charIndex++;
                                while (charIndex < line.Length && line[charIndex++] != '\'')
                                {
                                }
                                assemblyName = line.Substring(identStart + 1, charIndex - identStart - 2);
                            }
                            else
                            {
                                while (charIndex < line.Length && TestProject.IsIdentifier(line[charIndex]))
                                {
                                    charIndex++;
                                }
                                assemblyName = line.Substring(identStart, charIndex - identStart);

                                if (assemblyName == "extern")
                                {
                                    break;
                                }
                                if (assemblyName == "legacy" || assemblyName == "library")
                                {
                                    continue;
                                }
                            }
                            int identEnd = charIndex;
                            string sourceName = Path.GetFileNameWithoutExtension(source);
                            if (sourceName != assemblyName)
                            {
                                string end = line.Substring(identEnd);
                                // Check if line was '.assembly foo // as "foo"' and discard it
                                Match asNameMatch = Regex.Match(end, $@"\s*//\s*as\s+(""?){assemblyName}\1\s*$");
                                if (asNameMatch.Success)
                                {
                                    end = end.Substring(0, asNameMatch.Index);
                                }

                                line = line.Substring(0, identStart) + '\'' + sourceName + '\'' + end;
                                lines[lineIndex] = line;
                                rewritten = true;
                            }
                            break;
                        }
                    }
                }
            }

            if (_settings.UncategorizedCleanup && _testProject.DeduplicatedClassName != null)
            {
                for (int lineIndex = 0; lineIndex < lines.Count; lineIndex++)
                {
                    lines[lineIndex] = ReplaceIdent(lines[lineIndex], _testProject.TestClassName, _testProject.DeduplicatedClassName);
                }
                rewritten = true;
            }

            if (rewritten)
            {
                File.WriteAllLines(source, lines);
            }
        }

        private void RewriteProject(string path)
        {
            List<string> lines = new List<string>(File.ReadAllLines(path));
            bool rewritten = false;
            bool hasRequiresProcessIsolation = _testProject.HasRequiresProcessIsolation;
            string quotedOldSourceName = '"' + Path.GetFileName(_testProject.SourceInfo.TestClassSourceFile) + '"';
            for (int lineIndex = 0; lineIndex < lines.Count; lineIndex++)
            {
                string line = lines[lineIndex];

                // Add RequiresProcessIsolation to first PropertyGroup.
                // Do this before the OutputType removal, which might remove the first PropertyGroup.
                if (_settings.AddProcessIsolation && _testProject.NeedsRequiresProcessIsolation && !hasRequiresProcessIsolation)
                {
                    if (line.Contains("<PropertyGroup"))
                    {
                        int indent = TestProject.GetIndent(line);
                        int nextIndent = TestProject.GetIndent(lines[lineIndex + 1]);
                        // If there's a line indented with the PropertyGroup, use that.  Otherwise just add 2 spaces.
                        string modelLine = (nextIndent > indent) ? lines[lineIndex + 1] : "  " + line;

                        string commentLine = $"<!-- Needed for {string.Join(", ", _testProject.RequiresProcessIsolationReasons)} -->";
                        List<string> insertLines = new List<string>() { commentLine };
                        insertLines.AddRange(s_processIsolationLines);
                        // "+ 1" to add after the line.  Then "- 1" to reset to the last inserted line
                        // so that the loop's lineIndex++ puts us after the insertion.
                        lineIndex = InsertIndentedLines(lines, lineIndex + 1, insertLines, modelLine) - 1;

                        hasRequiresProcessIsolation = true;
                        rewritten = true;
                        continue;
                    }
                }

                const string outputTypeTag = "<OutputType>Exe</OutputType>";
                bool containsOutputType = line.Contains(outputTypeTag);
                if (_settings.AddILFactAttributes && containsOutputType)
                {
                    lines.RemoveAt(lineIndex--);
                    if ((lines[lineIndex].Trim() == "<PropertyGroup>")
                        && (lines[lineIndex + 1].Trim() == "</PropertyGroup>"))
                    {
                        lines.RemoveAt(lineIndex);
                        lines.RemoveAt(lineIndex--);
                    }
                    rewritten = true;
                    continue;
                }

                const string compileTag = "<Compile Include";
                bool containsCompileTag = line.Contains(compileTag);
                const string quotedMSBuildProjectName = "\"$(MSBuildProjectName).il\"";
                if (_testProject.IsILProject && containsCompileTag && (_testProject.NewTestClassSourceFile != null))
                {
                    bool ilMatchesProj =
                        Path.GetFileNameWithoutExtension(_testProject.NewTestClassSourceFile)
                        == Path.GetFileNameWithoutExtension(_testProject.NewAbsolutePath ?? _testProject.AbsolutePath);
                    string replaced = ilMatchesProj
                        ? line.Replace(quotedOldSourceName, quotedMSBuildProjectName)
                        : line.Replace(quotedOldSourceName, '"' + Path.GetFileName(_testProject.NewTestClassSourceFile) + '"');
                    if (replaced == line)
                    {
                        if (!line.Contains(quotedMSBuildProjectName) || !ilMatchesProj)
                        {
                            Console.WriteLine($"Unrecognized <Compile Include=...> in {_testProject.AbsolutePath}");
                        }
                    }
                    else
                    {
                        lines[lineIndex] = replaced;
                        rewritten = true;
                    }
                }

                /*
                const string testKindTag = "<CLRTestKind>BuildAndRun</CLRTestKind>";
                int testKindIndex = line.IndexOf(testKindTag);
                if (testKindIndex >= 0)
                {
                    lines[lineIndex] = line.Substring(0, testKindIndex) + "<CLRTestKind>BuildOnly</CLRTestKind>";
                    rewritten = true;
                    continue;
                }
                */
            }

            if (rewritten)
            {
                File.WriteAllLines(path, lines);
            }
        }

        private enum IdentKind
        {
            Namespace,
            TypeUse,
            Other
        }

        private enum TokenKind
        {
            _Illegal,
            WhiteSpace,
            Comment,
            Quoted,
            Identifier,
            Other
        }

        private bool IsNamespaceDeclName(List<string> tokens, List<TokenKind> kinds, int index)
            => (index == 3)
            && kinds[0] == TokenKind.Other && tokens[0] == "."
            && kinds[1] == TokenKind.Identifier && tokens[1] == "namespace"
            && kinds[2] == TokenKind.WhiteSpace;

        private bool IsNamespacePrefix(List<string> tokens, List<TokenKind> kinds, int index)
            => (index + 2 < tokens.Count)
            && kinds[index + 1] == TokenKind.Other && tokens[index + 1] == "."
            && kinds[index + 2] == TokenKind.Identifier;

        private bool IsTypePrefix(List<string> tokens, List<TokenKind> kinds, int index)
            => (index + 2 < tokens.Count)
            && kinds[index + 1] == TokenKind.Other
            && ((tokens[index + 1] == "::") || (tokens[index + 1] == "/")) // type::field or type::nestedtype
            && kinds[index + 2] == TokenKind.Identifier;

        private static string[] TypeDefTokens = { "public", "auto", "ansi" };
        private bool IsTypeNameDef(List<string> tokens, List<TokenKind> kinds, int index)
        {
            for (; index >= 2; index -= 2)
            {
                if (kinds[index - 1] != TokenKind.WhiteSpace) break;
                if (kinds[index - 2] != TokenKind.Identifier) break;
                if (tokens[index - 2] == ".class") return true;
                if (!TypeDefTokens.Contains(tokens[index - 2])) break;
            }
            return false;
        }

        private bool IsTypeNameUse(List<string> tokens, List<TokenKind> kinds, int index)
            => (index >= 2)
            && kinds[index - 2] == TokenKind.Identifier && (tokens[index - 2] == "class" || tokens[index - 2] == "valuetype")
            && kinds[index - 1] == TokenKind.WhiteSpace;

        private bool IsMethodName(List<string> tokens, List<TokenKind> kinds, int index)
            => (index + 1 < tokens.Count)
            && kinds[index + 1] == TokenKind.Other && tokens[index + 1] == "(";

        private static string[] TypeOperators = { "ldtoken", "box", "initobj", "stobj", "isinst", "castclass", "catch" };
        private bool IsOperatorType(List<string> tokens, List<TokenKind> kinds, int index)
            => !IsNamespacePrefix(tokens, kinds, index)
            && (index >= 2)
            && kinds[index - 2] == TokenKind.Identifier && TypeOperators.Contains(tokens[index - 2])
            && kinds[index - 1] == TokenKind.WhiteSpace;

        private bool IsInheritanceType(List<string> tokens, List<TokenKind> kinds, int index)
        {
            while (--index >= 0)
            {
                if ((kinds[index] == TokenKind.Identifier)
                    && ((tokens[index] == "extends") || (tokens[index] == "implements")))
                {
                    return true;
                }

                if (kinds[index] == TokenKind.Identifier
                    || kinds[index] == TokenKind.WhiteSpace
                    || (kinds[index] == TokenKind.Other && tokens[index] == ","))
                    continue;

                break;
            }

            return false;
        }

        private bool IsVariableName(List<string> tokens, List<TokenKind> kinds, int index)
            => (index >= 2)
            && kinds[index - 2] == TokenKind.Identifier && tokens[index - 2] == "int"
            && kinds[index - 1] == TokenKind.WhiteSpace;

        private List<(string, TokenKind)> SpecialTokens = new List<(string, TokenKind)>()
        {
            (".class", TokenKind.Identifier),
            (".ctor", TokenKind.Identifier),
            ("::", TokenKind.Other),
            ("(", TokenKind.Other),
            (")", TokenKind.Other),
        };

        private string ReplaceIdent(string source, string searchIdent, string replaceIdent, IdentKind searchKind = IdentKind.Other)
        {
            if (!source.Contains(searchIdent))
            {
                return source;
            }

            var tokens = new List<string>();
            var kinds = new List<TokenKind>();

            for (int index = 0, next; index < source.Length; index = next)
            {
                next = index;
                TokenKind kind = TokenKind._Illegal;

                char c = source[next];
                if (c == '\"')
                {
                    while (++next < source.Length && source[next] != '\"')
                    {
                        // nothing
                    }
                    // next is " or end of line
                    if (next < source.Length)
                    {
                        next++;
                    }
                    kind = TokenKind.Quoted;
                }
                else if (c == '/' && next + 1 < source.Length && source[next + 1] == '/')
                {
                    // Comment - copy over rest of line
                    next = source.Length;
                    kind = TokenKind.Comment;
                }
                else if (char.IsWhiteSpace(c))
                {
                    while (++next < source.Length && char.IsWhiteSpace(source[next]))
                    {
                        // nothing
                    }
                    kind = TokenKind.WhiteSpace;
                }
                else
                {
                    var special = SpecialTokens.FirstOrDefault(
                        candidate => next + candidate.Item1.Length <= source.Length
                        && MemoryExtensions.Equals(source.AsSpan(next, candidate.Item1.Length), candidate.Item1.AsSpan(0), StringComparison.Ordinal));
                    if (special.Item1 != null)
                    {
                        next += special.Item1.Length;
                        kind = special.Item2;
                    }
                }

                if (next == index)
                {
                    if (!TestProject.IsIdentifier(c))
                    {
                        while (++next < source.Length && !TestProject.IsIdentifier(source[next]) && !char.IsWhiteSpace(source[next]))
                        {
                            // nothing
                        }
                        kind = TokenKind.Other;
                    }
                    else
                    {
                        while (++next < source.Length && TestProject.IsIdentifier(source[next]))
                        {
                            // nothing
                        }
                        kind = TokenKind.Identifier;
                    }
                }

                tokens.Add(source.Substring(index, next - index));
                kinds.Add(kind);
            }

            var builder = new StringBuilder();
            for (int i = 0; i < tokens.Count; ++i)
            {
                string token = tokens[i];
                if (kinds[i] == TokenKind.Identifier)
                {
                    if (token == searchIdent)
                    {
                        bool replace = true;
                        if (searchKind == IdentKind.Namespace)
                        {
                            if (IsNamespaceDeclName(tokens, kinds, i)
                                || IsNamespacePrefix(tokens, kinds, i))
                            {
                                // good
                            }
                            else if (IsTypeNameDef(tokens, kinds, i))
                            {
                                replace = false;
                            }
                            else
                            {
                                Console.WriteLine("{0}: Checking for namespace: couldn't determine token kind of token #{1}={2} in",
                                    _testProject.AbsolutePath, i, token);
                                Console.WriteLine(source);
                                replace = false;
                            }
                        }
                        else if (searchKind == IdentKind.TypeUse)
                        {
                            if (IsTypePrefix(tokens, kinds, i)
                                || IsTypeNameUse(tokens, kinds, i)
                                || IsInheritanceType(tokens, kinds, i)
                                || IsOperatorType(tokens, kinds, i))
                            {
                                // good
                            }
                            else if (IsNamespacePrefix(tokens, kinds, i)
                                || IsMethodName(tokens, kinds, i)
                                || IsTypeNameDef(tokens, kinds, i)
                                || IsVariableName(tokens, kinds, i))
                            {
                                replace = false;
                            }
                            else
                            {
                                Console.WriteLine("{0}: Checking for type: couldn't determine token kind of token #{1}={2} in",
                                    _testProject.AbsolutePath, i, token);
                                Console.WriteLine(source);
                                replace = false;
                            }
                        }

                        if (replace)
                        {
                            builder.Append(replaceIdent);
                            continue;
                        }
                    }
                }

                builder.Append(token);
            }
            return builder.ToString();
        }
    }
}
