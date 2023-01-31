using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;

namespace ILTransform
{
    public static class IL
    {
        public static List<string> SpecialTokens() => new List<string> {
            "add", "and", "br", "brtrue", "brfalse", "ble", "blt", "beq",    "bge", "bgt", "call", "ceq", "cgt", "ckfinite", "clt", "cpblk", "div",
            "dup", "initblk", "jmp", "ldobj", "ldtoken", "mul", "neg", "nop", "rem", "ret", "sub", "xor", "callvirt",
            "castclass", "cpobj", "initobj", "isinst", "switch"
        };
    }
}
