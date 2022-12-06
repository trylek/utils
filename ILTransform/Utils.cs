using System;
using System.Collections.Generic;
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

    }
}
