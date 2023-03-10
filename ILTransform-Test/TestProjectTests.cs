using ILTransform;

namespace ILTransform_Test {
    public class TestProjectTests {
        [InlineData("aaa", "aaa")]
        [InlineData("1aaa", "_1aaa")]
        [InlineData("%aa%a", "__aa__a")]
        [InlineData("aa-a", "aa_a")]
        [InlineData("a_@_$_`1_a", "a_@_$_`1_a")]
        [Theory]
        public void SanitizeILIdentifier(string input, string expectedOutput)
        {
            string output = TestProject.SanitizeIdentifier(input, isIL: true);
            Assert.Equal(expectedOutput, output);
        }

        [InlineData("aaa", "aaa")]
        [InlineData("1aaa", "_1aaa")]
        [InlineData("%aa%a", "__aa__a")]
        [InlineData("aa-a", "aa_a")]
        [InlineData("a_@_$_`1_a", "a_________1_a")]
        [Theory]
        public void SanitizeCSIdentifier(string input, string expectedOutput)
        {
            string output = TestProject.SanitizeIdentifier(input, isIL: false);
            Assert.Equal(expectedOutput, output);
        }

        public static List<string> MakeList(params string[] args) => args.ToList();

        public static IEnumerable<object?[]> DedupSuffixDirProjData()
        {
            yield return new object?[] { MakeList("A", "B"), null };
            yield return new object?[] { MakeList("A", "A\\B"), MakeList("", "B") };
            yield return new object?[] { MakeList("A\\B", "A"), MakeList("B", "") };
            yield return new object?[] { MakeList("A", "A\\B", "A", "A\\C"), MakeList("", "B", "", "C") };
            yield return new object?[] { MakeList("A", "B\\A"), null };
            yield return new object?[] { MakeList("B\\A", "A"), null };
            yield return new object?[] { MakeList("A", "B\\A", "C\\A"), null };
            yield return new object?[] { MakeList("pre\\A\\post", "pre\\B\\post"), null };
        }

        [MemberData(nameof(DedupSuffixDirProjData))]
        [Theory]
        public void DedupSuffixDirProj(List<string> inputs, List<string>? expectedOutputs)
        {
            List<string>? outputs = TestProjectStore.DedupSuffixDirProj(inputs);
            Assert.Equal(outputs == null, expectedOutputs == null);
            if (outputs == null) return;
            foreach ((string expectedOutput, string output) in expectedOutputs!.Zip(outputs))
            {
                Assert.Equal(expectedOutput, output);
            }
        }
    }
}

