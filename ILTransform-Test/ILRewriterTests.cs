using ILTransform;
using Newtonsoft.Json.Linq;
using System.Formats.Asn1;
using static ILTransform.ILRewriter;

namespace ILTransform_Test {
    public class ILRewriter_Tests
    {
        [InlineData("ldsflda value class Box_Unbox.valClass Box_Unbox::vc",
            "Box_Unbox", "Box_Unbox.Box_Unbox", true, IdentKind.TypeUse,
            "ldsflda value class Box_Unbox.valClass Box_Unbox.Box_Unbox::vc")]
        [Theory]
        public void ReplaceIdent(
            string source,
            string searchIdent,
            string replaceIdent,
            bool isIL,
            IdentKind searchKind,
            string expectedOutput)
        {
            string output = ILRewriter.ReplaceIdent("", source, searchIdent, replaceIdent, isIL, searchKind);
            Assert.Equal(expectedOutput, output);
        }
    }
}
