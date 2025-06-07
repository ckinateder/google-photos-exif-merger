import pickle
import unittest
import json
import logging
from src.match_files import match_files_from_file_list
from src import IN_PKL_NAME, OUT_PKL_NAME, PROPS_JSON_NAME
from os.path import join
from parameterized import parameterized

class TestMatching(unittest.TestCase):
    @parameterized.expand([
        ("case0",),
        ("case1",),
        ("case2",),
        ("case3",),
        ("case4",),
    ])
    def test_scenario(self, casename):
        with (open(join("test", "scenarios", casename, IN_PKL_NAME), "rb") as infile, 
              open(join("test", "scenarios", casename, OUT_PKL_NAME), "rb") as outfile, 
              open(join("test", "scenarios", casename, PROPS_JSON_NAME), "r") as propsfile):
            dirlist = pickle.load(infile)
            expected_matched = pickle.load(outfile)
            props = json.load(propsfile)
            
            # suppress logging
            logging.getLogger().setLevel(logging.ERROR)
            matched_files, missing_files, ambiguous_files = match_files_from_file_list(dirlist)
            logging.getLogger().setLevel(logging.INFO)

            self.assertTrue(len(missing_files) == props["missing_files_length"])
            self.assertTrue(len(ambiguous_files) == props["ambiguous_files_length"])
            self.assertTrue(len(matched_files) == props["matched_files_length"])
            self.assertListEqual(matched_files, expected_matched)

if __name__ == '__main__':
    unittest.main()