import pickle
import unittest
import json
import logging
import tempfile
import os
from src.match_files import match_files_from_file_list
from src import IN_PKL_NAME, OUT_PKL_NAME, PROPS_JSON_NAME
from src.exif_interface import read_exif_data_on_file
from src.util import run_command
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

class TestExifTool(unittest.TestCase):
    """Test that exiftool is installed and working correctly."""
    
    def test_exiftool_installed(self):
        """Test that exiftool command is available and can be executed."""
        out, err, rc = run_command("exiftool -ver")
        self.assertEqual(rc, 0, f"exiftool command failed with return code {rc}. Error: {err}")
        self.assertIsNotNone(out, "exiftool version command should return output")
        # Version should be a string that can be parsed (contains numbers)
        self.assertTrue(any(c.isdigit() for c in out.strip()), 
                       f"exiftool version output should contain numbers, got: {out}")
    
    def test_exiftool_reads_exif_data(self):
        """Test that exiftool can read EXIF data from a file."""
        # Create a temporary test file (a simple text file)
        # Note: exiftool can read metadata from any file, even if it's not an image
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as tmp_file:
            tmp_file.write("Test content for exiftool")
            tmp_file_path = tmp_file.name
        
        try:
            # Test that we can read EXIF data (even if minimal) from the file
            exif_data = read_exif_data_on_file(tmp_file_path)
            # Should return a dict (even if empty for non-image files)
            self.assertIsInstance(exif_data, dict, 
                                "read_exif_data_on_file should return a dictionary")
            # For any file, exiftool should at least return file metadata
            self.assertIn("File", exif_data, 
                         "exiftool should return at least File metadata")
        finally:
            # Clean up
            if os.path.exists(tmp_file_path):
                os.unlink(tmp_file_path)
    
    def test_exiftool_json_output(self):
        """Test that exiftool can output JSON format correctly."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as tmp_file:
            tmp_file.write("Test content")
            tmp_file_path = tmp_file.name
        
        try:
            # Test the raw exiftool command with JSON output
            command = f"exiftool -a -u -g1 -j {repr(tmp_file_path)}"
            out, err, rc = run_command(command)
            self.assertEqual(rc, 0, f"exiftool JSON command failed: {err}")
            # Should be valid JSON
            parsed = json.loads(out)
            self.assertIsInstance(parsed, list, "exiftool JSON output should be a list")
            self.assertGreater(len(parsed), 0, "exiftool JSON output should contain at least one entry")
        finally:
            if os.path.exists(tmp_file_path):
                os.unlink(tmp_file_path)

if __name__ == '__main__':
    unittest.main()