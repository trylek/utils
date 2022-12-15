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
        internal static int EndIndexOf(this string thisString, string value)
        {
            int index = thisString.IndexOf(value);
            if (index == -1) return -1;
            return index + value.Length;
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
            projectList!.Add(project);
        }

        internal static void AddToNestedMultiMap<TKey>(
            Dictionary<TKey, Dictionary<DebugOptimize, List<TestProject>>> nestedMultiMap,
            TKey key,
            TestProject project)
            where TKey: notnull
        {
            if (!nestedMultiMap.TryGetValue(key, out Dictionary<DebugOptimize, List<TestProject>>? multiMap))
            {
                multiMap = new Dictionary<DebugOptimize, List<TestProject>>();
                nestedMultiMap.Add(key, multiMap);
            }
            Utils.AddToMultiMap(multiMap, project.DebugOptimize, project);
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
    }
}
