# Usage:
# python get_tests.py <path to unmerged test> <paths to test groups>
#
# Example:
# python
#   get_tests\get_tests.py
#   d:/r/runtime/artifacts/log/TestRun.xml
#   d:/r/runtime2/artifacts/log/JIT.Regression.Regression_1.testRun.xml
#   d:/r/runtime2/artifacts/log/JIT.Regression.Regression_2.testRun.xml
#   ...

import os
import sys
import xml.etree.ElementTree as ET

def load(file):
    tree = ET.parse(file)
    root = tree.getroot()
    tests = {}
    for test in root.iter('test'):
        attrib = test.attrib

        # Tests are listed a bit differently (.cmd vs .dll, some capitalization).
        # Normalize here.
        name, _ = os.path.splitext(attrib['name'].replace('\\\\','\\'))
        name = name.lower()
        tests[name] = attrib['time']
    print(f"{file} has {len(tests)} entries")
    return tests

def get(files):
    tests1 = load(files[1])
    tests2 = {}
    for file in files[2:]:
        tests = load(file)
        old_size = len(tests2)
        add_size = len(tests)
        tests2.update(tests)
        if old_size + add_size != len(tests2):
            print("no")
    print(f"len(tests1) = {len(tests1)}")
    print(f"len(tests2) = {len(tests2)}")

    # Used to find information about a specific test
    #for name in tests1.keys():
    #    if "b11553" in name:
    #        print(name)
    #for name in tests2.keys():
    #    if "b11553" in name:
    #        print(name)

    # Print differences
    for name in tests1.keys():
        if name not in tests2.keys():
            print(f"only in 1: {name}")
    for name in tests2.keys():
        if name not in tests1.keys():
            print(f"only in 2: {name}")

    # Extend comparison/reporting here

if __name__ == "__main__":
    get(sys.argv)
