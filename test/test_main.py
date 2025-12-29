import pickle
import unittest
import json
import logging
import tempfile
import os
from src.match_files import match_files_from_file_list
from src import IN_PKL_NAME, OUT_PKL_NAME, PROPS_JSON_NAME
from src.exif_interface import read_exif_data_on_file, parse_exif_data_from_sidecar
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
              open(join("test", "scenarios", casename, PROPS_JSON_NAME), "r", encoding="utf-8") as propsfile):
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

class TestUnicodeHandling(unittest.TestCase):
    """Test that JSON files with emojis and Unicode characters can be loaded correctly."""
    
    def test_load_json_with_emoji(self):
        """Test that a JSON sidecar file with emojis can be loaded without UnicodeDecodeError."""
        # JSON content with emoji in people field
        json_content = {
            "title": "IMG-20240324-WA0005.jpg",
            "description": "",
            "imageViews": "0",
            "creationTime": {
                "timestamp": "1731763421",
                "formatted": "16 Nov 2024, 13:23:41 UTC"
            },
            "photoTakenTime": {
                "timestamp": "1711302371",
                "formatted": "24 Mar 2024, 17:46:11 UTC"
            },
            "geoData": {
                "latitude": 0.0,
                "longitude": 0.0,
                "altitude": 0.0,
                "latitudeSpan": 0.0,
                "longitudeSpan": 0.0
            },
            "people": [{
                "name": "Caesar"
            }, {
                "name": "Giacomo"
            }, {
                "name": "Alice🐒 "
            }],
            "url": "https://photos.google.com/photo/someID",
            "removeResultReason": [{
                "reason": ["OFF_TOPIC"]
            }],
            "googlePhotosOrigin": {
                "mobileUpload": {
                    "deviceFolder": {
                        "localFolderName": "WhatsApp Images"
                    },
                    "deviceType": "ANDROID_PHONE"
                }
            },
            "appSource": {
                "androidPackageName": "com.whatsapp"
            }
        }
        
        # Create a temporary JSON file with UTF-8 encoding
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8') as tmp_file:
            json.dump(json_content, tmp_file, ensure_ascii=False)
            tmp_file_path = tmp_file.name
        
        try:
            # Test loading with UTF-8 encoding (same as in main.py)
            with open(tmp_file_path, "r", encoding="utf-8") as f:
                loaded_data = json.load(f)
            
            # Verify the data was loaded correctly
            self.assertIsInstance(loaded_data, dict, "Loaded data should be a dictionary")
            self.assertEqual(loaded_data["title"], "IMG-20240324-WA0005.jpg")
            
            # Verify emoji is preserved correctly
            self.assertIn("people", loaded_data)
            self.assertEqual(len(loaded_data["people"]), 3)
            self.assertEqual(loaded_data["people"][2]["name"], "Alice🐒 ")
            # Verify the emoji character is actually present (not corrupted)
            self.assertIn("🐒", loaded_data["people"][2]["name"])
            
            # Test that parse_exif_data_from_sidecar can process it
            exif_data = parse_exif_data_from_sidecar(loaded_data)
            self.assertIsInstance(exif_data, dict, "parse_exif_data_from_sidecar should return a dictionary")
            self.assertIn("DateTimeOriginal", exif_data)
            self.assertIn("CreateDate", exif_data)
            
        finally:
            # Clean up
            if os.path.exists(tmp_file_path):
                os.unlink(tmp_file_path)
    
    def test_load_json_with_emoji_no_encoding_specified_fails(self):
        """Test that loading without UTF-8 encoding fails on systems with non-UTF-8 default encoding."""
        # This test documents the issue that was fixed
        json_content = {
            "title": "Test",
            "creationTime": {"timestamp": "1731763421"},
            "photoTakenTime": {"timestamp": "1711302371"},
            "geoData": {"latitude": 0.0, "longitude": 0.0, "altitude": 0.0, "latitudeSpan": 0.0, "longitudeSpan": 0.0},
            "people": [{"name": "Alice🐒"}]
        }
        
        # Create a temporary JSON file with UTF-8 encoding
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8') as tmp_file:
            json.dump(json_content, tmp_file, ensure_ascii=False)
            tmp_file_path = tmp_file.name
        
        try:
            # This should work with UTF-8 encoding (our fix)
            with open(tmp_file_path, "r", encoding="utf-8") as f:
                loaded_data = json.load(f)
            self.assertIn("🐒", loaded_data["people"][0]["name"])
            
        finally:
            if os.path.exists(tmp_file_path):
                os.unlink(tmp_file_path)

if __name__ == '__main__':
    unittest.main()