using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Runtime.CompilerServices;
using System.Text;
using System.Threading.Tasks;

namespace ILTransform
{
    internal static class Utils
    {
        internal static int SkipWhiteSpace(this string thisString, int index = 0)
        {
            while (index < thisString.Length && char.IsWhiteSpace(thisString[index]))
            {
                index++;
            }
            return index;
        }

        internal static int SkipNonWhiteSpace(this string thisString, int index = 0)
        {
            while (index < thisString.Length && !char.IsWhiteSpace(thisString[index]))
            {
                index++;
            }
            return index;
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

        // Idea is to convert [dir1A\dir2A\dir3\foo.txt, dir1B\dir2B\dir3\bar.txt] to [dir2, dir2B].
        // This is broken because is uses the entire dir suffix to look for differences but then
        // only returns the outermost directory names.  Consider
        // [dir1A\dir2A\dir3A\A, dir1B\dir2A\dir3B\B, dir1C\dir2B\dir3A\C]
        // where this will return [dir2A, dir2A, dir2B] but should return either
        // [dir1A, dir1B, dir1C] or [dir2A\dir3A, dir2A\dir3B, dir2B\dir3A].
        internal static List<string>? GetNearestDirectoryWithDifferences(List<string> filenames)
        {
            int depth = 1;
            const int maxDepth = 3;
            do
            {
                HashSet<string> folderCollisions = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
                bool foundCollision = false;
                foreach (string filename in filenames)
                {
                    string dir = Path.GetDirectoryName(filename)!;
                    string dirKey = "";
                    for (int i = 0; i < depth; i++)
                    {
                        dirKey += "/" + Path.GetFileName(dir);
                        dir = Path.GetDirectoryName(dir)!;
                    }
                    if (!folderCollisions.Add(dirKey))
                    {
                        foundCollision = true;
                        break;
                    }
                }
                if (!foundCollision)
                {
                    break;
                }
            }
            while (++depth <= maxDepth);

            // Check that we found one
            if (depth > maxDepth)
            {
                return null;
            }

            // Extract the 'depth'th directory name
            IEnumerable<string> extraRootNameEnum = filenames;
            for (int i = 0; i < depth; ++i)
            {
                extraRootNameEnum = extraRootNameEnum.Select(n => Path.GetDirectoryName(n)!);
            }
            extraRootNameEnum = extraRootNameEnum.Select(n => Path.GetFileName(n));
            return extraRootNameEnum.ToList()!;
        }

        // Reduce ["pre-A-post", pre-B-post"] to ["A", "B"]
        internal static List<string> TrimSharedTokens(List<string> values)
        {
            // Strip matching leading characters - but only at token (by _ or -) boundaries
            int minLength = values.Select(n => n.Length).Min();
            int leadingMatches = 0;
            int leadingTokenMatches = 0;
            while ((leadingMatches < minLength)
                && values.All(n => n[leadingMatches] == values[0][leadingMatches]))
            {
                bool isFullToken = new char[] { '_', '-' }.Contains(values[0][leadingMatches]);
                leadingMatches++;
                if (isFullToken) leadingTokenMatches = leadingMatches;
            }
            values = values.Select(n => n.Substring(leadingTokenMatches)).ToList();

            // Strip matching trailing characters
            minLength = values.Select(n => n.Length).Min();
            int trailingMatches = 0;
            int trailingTokenMatches = 0;
            while ((trailingMatches < minLength)
                && values.All(n => n[n.Length - trailingMatches - 1] == values[0][values[0].Length - trailingMatches - 1]))
            {
                bool isFullToken = new char[] { '_', '-' }.Contains(values[0][leadingMatches]);
                trailingMatches++;
                if (isFullToken) trailingTokenMatches = trailingMatches;
            }
            values = values.Select(n => n.Substring(0, n.Length - trailingTokenMatches)).ToList();

            return values;
        }
    }
}

