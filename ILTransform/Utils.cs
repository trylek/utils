using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Runtime.CompilerServices;
using System.Runtime.ExceptionServices;
using System.Text;
using System.Threading.Tasks;

using Counts = System.Collections.Generic.Dictionary<string, int>;

namespace ILTransform
{
    public static class Utils
    {
        internal static int SkipWhiteSpace(this string thisString, int index = 0)
        {
            while (index < thisString.Length && char.IsWhiteSpace(thisString[index]))
            {
                index++;
            }
            return index;
        }

        internal static int ReverseSkipWhiteSpace(this string thisString, int index = 0)
        {
            while (index >= 0 && char.IsWhiteSpace(thisString[index]))
            {
                index--;
            }
            return index;
        }

        internal static (int, int) ReverseSkipWhiteSpace(this List<string> lines, int lineIndex = 0, int column = 0)
        {
            while (lineIndex >= 0
                && column >= 0
                && char.IsWhiteSpace(lines[lineIndex][column]))
            {
                if (column >= 0)
                {
                    column = lines[lineIndex].ReverseSkipWhiteSpace(column);
                }

                if (column == -1)
                {
                    lineIndex--;
                    if (lineIndex >= 0)
                    {
                        column = lines[lineIndex].Length - 1;
                    }
                    else
                    {
                        column = -1;
                    }
                }
            }

            return (lineIndex, column);
        }

        internal static int SkipNonWhiteSpace(this string thisString, int index = 0)
        {
            while (index < thisString.Length && !char.IsWhiteSpace(thisString[index]))
            {
                index++;
            }
            return index;
        }

        internal static bool IndicesOf(this string thisString, string value, out int foundStart, out int foundEnd)
        {
            int index = thisString.IndexOf(value);
            if (index == -1)
            {
                foundStart = foundEnd = -1;
                return false;
            }
            foundStart = index;
            foundEnd = index + value.Length;
            return true;
        }

        internal static bool IndicesOf(this string thisString, string value, int startIndex, int length, out int foundStart, out int foundEnd)
        {
            int index = thisString.IndexOf(value, startIndex, length);
            if (index == -1)
            {
                foundStart = foundEnd = -1;
                return false;
            }
            foundStart = index;
            foundEnd = index + value.Length;
            return true;
        }

        internal static int EndIndexOf(this string thisString, string value)
        {
            int index = thisString.IndexOf(value);
            if (index == -1) return -1;
            return index + value.Length;
        }

        internal static void AddToNestedMap<TKey1, TKey2, TValue>(
            Dictionary<TKey1, Dictionary<TKey2, TValue>> nestedMap,
            TKey1 key1,
            TKey2 key2,
            TValue value)
            where TKey1 : notnull
            where TKey2 : notnull
        {
            if (!nestedMap.TryGetValue(key1, out Dictionary<TKey2, TValue>? innerMap))
            {
                innerMap = new Dictionary<TKey2, TValue>();
                nestedMap.Add(key1, innerMap);
            }
            innerMap.Add(key2, value);
        }

        internal static void AddToMultiMap<TKey>(
            Dictionary<TKey, List<TestProject>> multiMap,
            TKey key,
            TestProject project)
            where TKey : notnull
        {
            if (!multiMap.TryGetValue(key, out List<TestProject>? projectList))
            {
                projectList = new List<TestProject>();
                multiMap.Add(key, projectList);
            }
            projectList.Add(project);
        }

        internal static void AddToNestedMultiMap<TKey1, TKey2>(
            Dictionary<TKey1, Dictionary<TKey2, List<TestProject>>> nestedMultiMap,
            TKey1 key1,
            TKey2 key2,
            TestProject project)
            where TKey1 : notnull
            where TKey2 : notnull
        {
            if (!nestedMultiMap.TryGetValue(key1, out Dictionary<TKey2, List<TestProject>>? multiMap))
            {
                multiMap = new Dictionary<TKey2, List<TestProject>>();
                nestedMultiMap.Add(key1, multiMap);
            }
            Utils.AddToMultiMap(multiMap, key2, project);
        }

        internal static void AddToMultiMap<TKey>(
            Dictionary<TKey, HashSet<string>> multiMap,
            TKey key,
            string value)
            where TKey : notnull
        {
            if (!multiMap.TryGetValue(key, out HashSet<string>? projectSet))
            {
                projectSet = new HashSet<string>();
                multiMap.Add(key, projectSet);
            }
            projectSet.Add(value);
        }

        internal static void FileMove(string sourceFileName, string destFileName, bool overwrite = false)
        {
            if (sourceFileName == destFileName) return;
            //Console.WriteLine($"Move file: {sourceFileName} => {destFileName}");
            if (string.Equals(sourceFileName, destFileName, StringComparison.OrdinalIgnoreCase))
            {
                Console.WriteLine($"Case-sensitive move from {sourceFileName} to {destFileName}");
            }
            File.Move(sourceFileName, destFileName, overwrite);
        }

        internal static bool HasNewLineAtEnd(string filename)
        {
            using (FileStream fs = File.Open(filename, FileMode.Open))
            {
                fs.Seek(-1, SeekOrigin.End);
                int b = fs.ReadByte();
                return b == '\n';
            }
        }

        internal enum NewLineAtEndSetting
        {
            No,
            Preserve,
            Yes
        }

        internal static void WriteAllLines(string filename, List<string> lines, NewLineAtEndSetting newLineAtEndSetting = NewLineAtEndSetting.Yes)
        {
            bool appendNewLineAtEnd;
            switch (newLineAtEndSetting)
            {
                case NewLineAtEndSetting.No:
                    appendNewLineAtEnd = false;
                    break;

                case NewLineAtEndSetting.Preserve:
                    appendNewLineAtEnd = HasNewLineAtEnd(filename);
                    break;

                case NewLineAtEndSetting.Yes:
                    appendNewLineAtEnd = true;
                    break;

                default:
                    throw new ArgumentException(string.Format("newLineAtEnd = {0}", newLineAtEndSetting));
            }

            using (var writer = new StreamWriter(filename))
            {
                bool first = true;
                foreach (string line in lines)
                {
                    if (first)
                    {
                        first = false;
                    }
                    else
                    {
                        writer.WriteLine();
                    }

                    writer.Write(line);
                }

                if (appendNewLineAtEnd)
                {
                    writer.WriteLine();
                }
            }
        }

        internal static bool AllUnique(this IEnumerable<string> strings)
        {
            var set = new HashSet<string>();

            foreach (string str in strings)
            {
                if (!set.Add(str))
                {
                    return false;
                }
            }

            return true;
        }

        private static string[]?[] GetComponents(List<string[]> individualComponents, bool[] found, int componentLength)
        {
            string[]?[] components = new string[]?[individualComponents.Count];

            for (int i = 0; i < individualComponents.Count; ++i)
            {
                if (found[i]) continue;
                string[] ic = individualComponents[i];
                components[i] =
                    Enumerable.Range(0, ic.Length - componentLength + 1)
                              .Reverse()
                              // The use of '_' is odd here.. the caller wants a single name built from multiple
                              // directory names, but that detail doesn't belong here.
                              .Select(start => string.Join('_', new ArraySegment<string>(ic, start, componentLength)))
                              .ToArray();
            }

            return components;
        }
        private static Counts BuildComponentCounts(IEnumerable<IEnumerable<string>?> components)
            => components.Where(f => f != null).SelectMany(f => f!).GroupBy(c => c).ToDictionary(g => g.Key, g => g.Count());
        private static void ReduceComponentCounts(Counts counts, string[] components)
            => components.ToList().ForEach(c => counts[c]--);

        // An overly complicated function that extracts unique substrings (subpaths) from a list
        // of paths.  It looks for unique path components, starting from length 1 (so just a single
        // directory name in the path) and growing from there.  For each length, it tries the end
        // of the path first.
        public static List<string> GetUniqueSubsets(List<string> filenames)
        {
            bool[] found = new bool[filenames.Count];

            // Break each path into a list of directories
            List<string[]> individualComponents = filenames.Select(f => f.Split(Path.DirectorySeparatorChar)).ToList();

            List<string?> results = Enumerable.Repeat<string?>(null, filenames.Count).ToList();

            for (int componentLength = 1; !found.All(b =>b); ++componentLength)
            {
                // For each path, get all subpaths of length 'componentLength'
                string[]?[] components = GetComponents(individualComponents, found, componentLength);

                Counts counts = BuildComponentCounts(components);
                bool changed;

                do
                {
                    changed = false;

                    // Search for unique subpaths
                    for (int i = 0; i < components.Length; ++i)
                    {
                        if (found[i]) { continue; }
                        foreach (string component in components[i]!)
                        {
                            if (counts[component] == 1)
                            {
                                changed = true;
                                results[i] = component;
                                break;
                            }
                        }
                    }

                    // AFTER finding all unique subpaths for the current length,
                    // decrement the counts.  This avoids "false unique" answers.
                    // E.g, with [A\C, A\C2, B\C2], we first select C for A\C but
                    // avoid then selecting A for A\C2.  We don't do any checks like
                    // this across sizes.
                    for (int i = 0; i < components.Length; ++i)
                    {
                        if (found[i]) { continue; }
                        if (results[i] == null) { continue; }

                        ReduceComponentCounts(counts, components[i]!);
                        found[i] = true;
                    }
                } while (changed);
            }
            return results!;
        }

        public static bool IsMatchOrOutOfRange(string str1, int index1, string str2, int index2)
            => index1 < 0 || index1 >= str1.Length || index2 < 0 || index2 >= str2.Length || str1[index1] == str2[index2];

        // Reduce ["pre-A-post", pre-B-post"] to ["A", "B"]
        public static List<string> TrimSharedTokens(List<string> values)
        {
            int minLength = values.Select(n => n.Length).Min();
            // Any string longer than 'minLength' (if one exists, else any of them)
            int repStringIndex = values.FindIndex(n => n.Length > minLength);
            if (repStringIndex == -1) repStringIndex = 0;
            string repString = values[repStringIndex];

            // Strip matching leading characters - but only at token (by _ or -) boundaries

            // Search for leading matches and mark the points where we hit the end of a token.
            // Allow it to go one past the end of the shortest string to handle ["a", "a-b", "a-c"]
            int leadingMatches = 0;
            int leadingTokenMatches = 0;
            while ((leadingMatches <= minLength)
                && values.All(n => IsMatchOrOutOfRange(n, leadingMatches, repString, leadingMatches)))
            {
                bool isFullToken = leadingMatches == repString.Length || new char[] { '_', '-' }.Contains(repString[leadingMatches]);
                leadingMatches++;
                if (isFullToken) leadingTokenMatches = leadingMatches;
            }

            values = values.Select(n => n.Substring(Math.Min(n.Length, leadingTokenMatches))).ToList();
            repString = values[repStringIndex];
            minLength = values.Select(n => n.Length).Min();

            // Strip matching trailing characters - but only at token (by _ or -) boundaries

            // Search for trailing matches and mark the points where we hit the start of a token.
            // Allow it to go one past the beginning of the shortest string to handle ["a", "b-a", "c-a"]
            int trailingMatches = 0;
            int trailingTokenMatches = 0;
            while ((trailingMatches <= minLength)
                && values.All(n => IsMatchOrOutOfRange(n, n.Length - trailingMatches - 1, repString, repString.Length - trailingMatches - 1)))
            {
                bool isFullToken = trailingMatches == repString.Length || new char[] { '_', '-' }.Contains(repString[repString.Length - trailingMatches - 1]);
                trailingMatches++;
                if (isFullToken) trailingTokenMatches = trailingMatches;
            }
            values = values.Select(n => n.Substring(0, Math.Max(0, n.Length - trailingTokenMatches))).ToList();

            return values;
        }
    }
}

