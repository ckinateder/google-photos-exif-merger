import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pickle
import unittest
from src.main import match_files_from_file_list
from os.path import join

class TestMatching(unittest.TestCase):
    def test_scene_1(self):
        dirlist = pickle.load(open(join("tests", "cases", "case1_i.pkl"), "rb"))
        expected_matched = pickle.load(open(join("tests", "cases", "case1_o.pkl"), "rb"))
        matched_files, missing_files, ambiguous_files = match_files_from_file_list(dirlist)
        self.assertTrue(len(missing_files) == 0)
        self.assertTrue(len(ambiguous_files) == 0)
        self.assertTrue(len(matched_files) == 3019)
        self.assertListEqual(matched_files, expected_matched)


if __name__ == '__main__':
    unittest.main()