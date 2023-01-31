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
    }
}

