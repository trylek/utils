namespace ILTransform_Test {
    public class UtilsTests {
        public static List<string> MakeList(params string[] args) => args.ToList();

        public static IEnumerable<object[]> TrimSharedTokensData()
        {
            yield return new object[] { MakeList("A", "B"), MakeList("A", "B") };
            yield return new object[] { MakeList("A", "A-B"), MakeList("", "B") };
            yield return new object[] { MakeList("A-B", "A"), MakeList("B", "") };
            yield return new object[] { MakeList("A", "A-B", "A", "A-C"), MakeList("", "B", "", "C") };
            yield return new object[] { MakeList("A", "B-A"), MakeList("", "B") };
            yield return new object[] { MakeList("B-A", "A"), MakeList("B", "") };
            yield return new object[] { MakeList("A", "B-A", "C-A"), MakeList("", "B", "C") };
            yield return new object[] { MakeList("pre-A-post", "pre-B-post"), MakeList("A", "B") };
        }

        [MemberData(nameof(TrimSharedTokensData))]
        [Theory]
        public void TrimSharedTokens(List<string> inputs, List<string> expectedOutputs)
        {
            List<string> outputs = ILTransform.Utils.TrimSharedTokens(inputs);
            foreach ((string expectedOutput, string output) in expectedOutputs.Zip(outputs))
            {
                Assert.Equal(expectedOutput, output);
            }
        }
    }
}