using System;
using System.Linq;
using System.Security.Cryptography.X509Certificates;
using System.Xml;

namespace TestRunXmlDiff
{
    public class TestCase
    {
        public readonly string Name;
        public readonly TimeSpan Time;
        public readonly string Result;

        public TestCase(string name, TimeSpan time, string result)
        {
            Name = name;
            Time = time;
            Result = result;
        }
    }

    /*
    public class TestAssembly
    {
        public readonly string Name;
        public readonly Dictionary<string, TestCase> TestCases = new Dictionary<string, TestCase>();

        public TestAssembly(string name)
        {
            Name = name;
        }
    }
    */

    public class TestResults
    {
        //public readonly Dictionary<string, TestAssembly> TestAssemblies = new Dictionary<string, TestAssembly>();
        public readonly Dictionary<string, TestCase> TestCases = new Dictionary<string, TestCase>();
    }

    internal class Program
    {
        private TestResults _leftResults = new TestResults();
        private TestResults _rightResults = new TestResults();

        static void Main(string[] args)
        {
            new Program().TryMain(args);
        }

        private void TryMain(string[] args)
        {
            TestResults target = _leftResults;
            string sideName = "left";

            foreach (string arg in args)
            {
                if (arg == "|")
                {
                    target = _rightResults;
                    sideName = "right";
                }
                else
                {
                    LoadResultsMulti(arg, target, sideName);
                }
            }

            SummaryResults(_leftResults, "Left");
            SummaryResults(_rightResults, "Right");
            DiffResults(_leftResults, _rightResults);
        }

        private void LoadResultsMulti(string fileNameOrMask, TestResults target, string sideName)
        {
            foreach (string matchingFile in Directory.EnumerateFiles(Path.GetDirectoryName(fileNameOrMask)!, Path.GetFileName(fileNameOrMask)))
            {
                LoadResults(matchingFile, target, sideName);
            }
        }

        private void LoadResults(string fileName, TestResults target, string sideName)
        {
            Console.WriteLine("Loading {0} file: {1}", sideName, fileName);
            XmlDocument document = new XmlDocument();
            document.Load(fileName);
            XmlNode assembliesNode = document["assemblies"]!;
            foreach (XmlNode assemblyNode in assembliesNode.ChildNodes)
            {
                if (assemblyNode.Name != "assembly")
                {
                    continue;
                }
                string? assemblyName = assemblyNode.Attributes?["name"]?.Value;
                if (assemblyName is null)
                {
                    continue;
                }
                foreach (XmlNode collectionNode in assemblyNode.ChildNodes)
                {
                    if (collectionNode.Name != "collection")
                    {
                        continue;
                    }

                    foreach (XmlNode testNode in collectionNode.ChildNodes)
                    {
                        if (testNode.Name != "test")
                        {
                            continue;
                        }
                        string testName = SanitizeTestName(testNode.Attributes!["name"]!.Value);
                        TimeSpan time = TimeSpan.FromSeconds(double.Parse(testNode.Attributes["time"]!.Value));
                        string result = testNode.Attributes["result"]!.Value;
                        if (target.TestCases.TryGetValue(testName, out TestCase? testCase))
                        {
                            target.TestCases[testName] = new TestCase(testName, testCase.Time + time, testCase.Result == result ? result : "<multiple>");
                        }
                        else
                        {
                            target.TestCases.Add(testName, new TestCase(testName, time, result));
                        }
                    }
                }
            }
        }

        private void SummaryResults(TestResults results, string sideName)
        {
            int totalTests = results.TestCases.Count;
            TimeSpan totalTime = TimeSpan.FromTicks(results.TestCases.Values.Sum(tc => tc.Time.Ticks));
            int passedTests = results.TestCases.Values.Where(tc => tc.Result == "Pass").Count();
            int failedTests = results.TestCases.Values.Where(tc => tc.Result == "Fail").Count();
            int skippedTests = results.TestCases.Values.Where(tc => tc.Result == "Skip").Count();
            int others = totalTests - passedTests - failedTests - skippedTests;
            Console.WriteLine("{0} side summary:", sideName);
            Console.WriteLine(new string('-', 14 + sideName.Length));
            Console.WriteLine("Total tests:   {0}", totalTests);
            Console.WriteLine("Passed tests:  {0}", passedTests);
            Console.WriteLine("Failed tests:  {0}", failedTests);
            Console.WriteLine("Skipped tests: {0}", skippedTests);
            Console.WriteLine("Other tests:   {0}", others);
            Console.WriteLine("Total time:    {0:F6} seconds", totalTime.TotalSeconds);
            Console.WriteLine();
        }

        private void DiffResults(TestResults left, TestResults right)
        {
            HashSet<string> leftTests = new HashSet<string>(left.TestCases.Keys);
            leftTests.ExceptWith(right.TestCases.Keys);

            PrintTestDiff(left, right, leftTests, "Left-only tests");

            HashSet<string> rightTests = new HashSet<string>(right.TestCases.Keys);
            rightTests.ExceptWith(left.TestCases.Keys);

            PrintTestDiff(left, right, rightTests, "Right-only tests");

            HashSet<string> commonTests = new HashSet<string>(left.TestCases.Keys);
            commonTests.IntersectWith(right.TestCases.Keys);

            PrintTestDiff(left, right, commonTests, "Tests in both");
        }

        private void PrintTestDiff(TestResults left, TestResults right, IEnumerable<string> tests, string title)
        {
            string titleLine = $"{title} ({tests.Count()} total):";
            Console.WriteLine(titleLine);
            Console.WriteLine(new string('-', titleLine.Length));

            foreach (string testName in tests.OrderBy(t => t))
            {
                Console.WriteLine(testName);
            }

            Console.WriteLine();
        }

        private static string SanitizeTestName(string name)
        {
            string result = name.Replace("\\\\", "\\");
            result = RemoveSuffix(result, ".dll");
            result = RemoveSuffix(result, ".cmd");
            return result;
        }

        private static string RemoveSuffix(string name, string suffix)
        {
            if (name.EndsWith(suffix))
            {
                return name.Substring(0, name.Length - suffix.Length);
            }
            return name;
        }
    }
}