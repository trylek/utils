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

        public static IEnumerable<object[]> GetUniqueSubsetsData()
        {
            yield return new object[] { MakeList("A"), MakeList("A") };
            yield return new object[] { MakeList("A", "B"), MakeList("A", "B") };
            yield return new object[] { MakeList("A\\B", "A\\C"), MakeList("B", "C") };
            yield return new object[] { MakeList("B\\A", "C\\A"), MakeList("B", "C") };
            yield return new object[] { MakeList("A\\X", "B\\X", "C", "D"), MakeList("A", "B", "C", "D") };
            yield return new object[] { MakeList("A\\X", "B\\X", "C\\X", "C\\Y"), MakeList("A", "B", "X", "Y") };
            yield return new object[] { MakeList("A\\C", "A\\D", "B\\C", "B\\D"), MakeList("A\\C", "A\\D", "B\\C", "B\\D") };
            yield return new object[] {
                MakeList("A\\B\\C\\F\\J", "A\\B\\C\\F\\K", "A\\B\\C\\G\\J", "A\\B\\C\\G\\K", "A\\B\\D\\H","A\\B\\D\\I","A\\B\\E"),
                MakeList(         "F\\J",          "F\\K",          "G\\J",          "G\\K",          "H",         "I",      "E" )
            };
            yield return new object[] { MakeList("1A\\2A\\3", "1B\\2B\\3"), MakeList("2A", "2B") };
            yield return new object[]
            {
                MakeList("1A\\2A\\3A", "1B\\2A\\3B", "1C\\2B\\3A"),
                MakeList("1A", "3B", "2B")
            };
        }

        [MemberData(nameof(GetUniqueSubsetsData))]
        [Theory]
        public void GetUniqueSubsets(List<string> inputs, List<string> expectedOutputs)
        {
            List<string>? outputs = ILTransform.Utils.GetUniqueSubsets(inputs);
            Assert.NotNull(outputs);
            foreach ((string expectedOutput, string output) in expectedOutputs.Zip(outputs))
            {
                Assert.Equal(expectedOutput, output);
            }
        }
    }
}