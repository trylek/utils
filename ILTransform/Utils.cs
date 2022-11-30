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
    }
}
