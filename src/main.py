# will call exiftool directly
import argparse
import os
import re
import pdb
from typing import Union, List, Tuple
from util import _format_list, _find_in_matched, _list_files
from tqdm import trange, tqdm
from tqdm.contrib.logging import logging_redirect_tqdm
from __init__ import *
import logging
import json
import pickle
# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s:%(levelname)s: %(message)s',
    datefmt='%Y-%m-%d_%H:%M:%S'
)
logger = logging.getLogger(__name__)

MEDIA_EXTENSIONS = [".jpg", ".jpeg", ".png", ".heic", ".heif", ".mp4", ".mov", ".avi", ".mkv", ".wmv", ".flv", ".f4v", ".f4p", ".f4a", ".f4b"]
LIVE_PHOTO_EXTENSION = ".mp4"
JSON_EXTENSION = ".json"

def match_files_from_file_list(filenames: List[str]=0) -> Union[List[Tuple[str]], List[str], List[Tuple[str, Tuple[str]]]]:
    """
    This function will match the json metadata files with the images in the same directory. There will be a default matching scheme, but there will be cases for other matching schemes.

    Args:
        directory (str): The directory to match the files in.

    Returns:
        Union[List[Tuple[str]], List[str], List[Tuple[str, Tuple[str]]]]:
            Matched files, missing files, ambiguous files
    """
    # start with getting a list of all the files in the directory that are media files. then check if there is a json file with the same base name
    # if there is a json file with the same base name, then add the tuple to the matched list, if not, add it to the unmatched list
    matched_files = []
    missing_files = []
    ambiguous_files = []

    # stage 1: match the json files with the media files
    all_json_files = [f for f in filenames if os.path.splitext(f)[1].lower() == JSON_EXTENSION]
    all_media_files = [f for f in filenames if os.path.splitext(f)[1].lower() in MEDIA_EXTENSIONS]
    total_media_files = len(all_media_files)
    total_json_files = len(all_json_files)
    logger.info(f"Found {total_media_files} media files and {total_json_files} json files")

    with logging_redirect_tqdm():
        for file in tqdm(all_media_files, desc="media files", leave=False, dynamic_ncols=True):
            # initialize variables
            basename = os.path.splitext(file)[0]
            media_extension = os.path.splitext(file)[1] #.lower()
            msg = f"Checking '{file}'... "
            potential_jsons = []

            # get basename
            # remove -edited suffix if there
            basename = re.sub(r'-edited$', '', basename, flags=re.IGNORECASE)
            
            # get counter if there is one
            pattern = re.compile(r"(?P<name>.*)(?P<counter>\(\d+\))$")
            match = pattern.match(basename)
            name = basename
            counter = None
            if match:
                name = match.group("name") # get the counter out of the name
                counter = match.group("counter")
            
            # start off by searching w/ counters
            if counter: # if it takes the form foo(n).jpg
                # search in all_json_files
                pattern = re.compile(rf"^{name}{media_extension}(?P<suffix>.*){re.escape(counter)}{JSON_EXTENSION}$")
                for f in all_json_files:
                    if pattern.match(f):
                        potential_jsons.append(f)
            else: # if no counters
                # reject any JSONS with counters
                pattern = re.compile(rf"^{basename}{media_extension}(?P<suffix>\.[^()]+){JSON_EXTENSION}$")

                for f in all_json_files:
                    match = pattern.match(f)
                    if match:
                        potential_jsons.append(f)

                if len(potential_jsons) == 0:
                    pattern = re.compile(rf'^{re.escape(basename)}.*?(?P<counter>\(\d+\))?{re.escape(JSON_EXTENSION)}$')
                    for f in all_json_files:
                        match = pattern.match(f)
                        # only if there's no counter add it
                        if match and not match.group("counter"):
                            potential_jsons.append(f)
            
        
            # Handle trailing characters: _, _n, _n-
            if basename.endswith(('_n-', '_n', '_')):
                potential_jsons.append(f"{basename[:-1]}.json")

            # get rid of duplicates
            potential_jsons = sorted(list(set(potential_jsons)))
            
            # if less than 1 potential matches, there is a problem. move on
            if len(potential_jsons) < 1:
                missing_files.append(file)
                logger.debug(f"{msg}no match found.")
                continue
            
            if len(potential_jsons) > 1: # we have too many
                # get the media extension and match it that way
                # REMEMBER this could be MP4 too and there may not be a json for it. in that case idk
                ambiguous_files.append((file, potential_jsons))
                logger.debug(f"{msg}{len(potential_jsons)} potential matches found.")
                continue

            # if we are this far, then it matched successfully for this instance
            json_file = potential_jsons[0]
            matched_files.append((file, json_file))
            logger.debug(f"{msg}match found at '{json_file}'!")

    # stage 2: search deeeper for missing files
    logger.info(f"Attempting to fix {len(missing_files)} missing metadata files...")
    recovered = []
    with logging_redirect_tqdm():
        for file in tqdm(missing_files, desc="missing files", leave=False, dynamic_ncols=True):
            # just try a bunch of things
            potential_jsons = []
            basename = os.path.splitext(file)[0]

            # i don't know why this cutoff is at 46
            if len(basename) >= 47: 
                # just check to see if the cutoff exists.
                cutoff_file = basename[:46] + JSON_EXTENSION 
                if cutoff_file in all_json_files:
                    recovered.append((file, cutoff_file))
                    continue

            # search for anything with the same basename in matched
            existing_match = _find_in_matched(matched_files, basename)
            if existing_match != False:
                logger.debug(f"Found {basename} in matched, falling back.")
                recovered.append((file, existing_match[1]))
                continue
            
            # ------- THE FOLLOWING DOES NOTHING BUT MAY BE USEFUL FOR AMBIGUOUS FILES ------
            # search for anything with same basename minus counter in matched
            pattern = re.compile(r"(?P<name>.*)(?P<counter>\(\d+\))$")
            match = pattern.match(basename)
            if match:
                name = match.group("name")
                counter = match.group("counter")
                basename_no_counter = name
                existing_match = _find_in_matched(matched_files, basename_no_counter)
                if existing_match != False:
                    logger.debug(f"Found {basename} in matched, falling back.")
                    recovered.append((file, existing_match[1]))
                    continue

    # move found files into matched_files
    logger.info(f"Recovered {len(recovered)} missing metadata files.")
    matched_files += recovered
    for f, _ in recovered:
        missing_files.remove(f)
    
    recovered = []

    # stage 3: examine all the ambiguous files
    logger.info(f"Attempting to fix {len(ambiguous_files)} ambiguous metadata files...")
    with logging_redirect_tqdm():
        for file, prospects in tqdm(ambiguous_files, desc="ambiguous files", leave=False, dynamic_ncols=True):
            # check if one of the ambiguous ones has already been matched? and then pick the other one
            basename = os.path.splitext(file)[0]
            media_extension = os.path.splitext(file)[1] #.lower()
            # first easy case: LIVE PHOTO
            if media_extension.lower() == LIVE_PHOTO_EXTENSION:
                # just pick the first one
                recovered.append((file, prospects[0]))

    logger.info(f"Recovered {len(recovered)} ambiguous metadata files.")
    matched_files += recovered

    # remove from list
    recovered_fs, _ = zip(*recovered)
    for i, (f, _) in enumerate(ambiguous_files):
        if f in recovered_fs:
            ambiguous_files[i] = None
    
    ambiguous_files = [x for x in ambiguous_files if x is not None]
    
    # sort by name
    matched_files.sort(key=lambda x: x[0])
    ambiguous_files.sort(key=lambda x: x[0])

    # final counts
    num_matched_files = len(matched_files)
    num_missing_files = len(missing_files)
    num_ambiguous_files = len(ambiguous_files)

    # print
    logger.info(f"Matched {num_matched_files}/{total_media_files} files")
    if num_missing_files > 0:
        logger.warning(f"Ambiguous:\n{_format_list(ambiguous_files)}")
        #logger.warning(f"Missing {num_missing_files}/{total_media_files} files")
    if num_ambiguous_files > 0:
        #logger.warning(f"Missing:\n{_format_list(missing_files)}")
        logger.warning(f"Ambiguous {num_ambiguous_files}/{total_media_files} files")

    # conservation of mass
    accounted_for_media_files = num_matched_files + num_missing_files + num_ambiguous_files
    assert accounted_for_media_files == total_media_files, f"accounted_for_media_files != total_media_files ({accounted_for_media_files} != {total_media_files})"
    return matched_files, missing_files, ambiguous_files

def find_sidecar_files(directory:str, test_case_dir:str = None):
    files_in_directory = _list_files(directory)
    
    matched_files, missing_files, ambiguous_files = match_files_from_file_list(files_in_directory)
    with logging_redirect_tqdm():
        for media_file, json_file in tqdm(matched_files, desc="validating", leave=False, dynamic_ncols=True):
            full_media_file = os.path.join(directory, media_file)
            assert os.path.isfile(full_media_file), f"{full_media_file} doesn't exist!"
            full_json_file = os.path.join(directory, json_file)
            assert os.path.isfile(full_json_file), f"{full_json_file} doesn't exist!"

    if test_case_dir:
        logger.info(f"Saving test cases to {test_case_dir}...")
        os.makedirs(test_case_dir, exist_ok=True)
        in_path = os.path.join(test_case_dir, IN_PKL_NAME)
        out_path = os.path.join(test_case_dir, OUT_PKL_NAME)
        props_path = os.path.join(test_case_dir, PROPS_JSON_NAME)
        props = {
            "matched_files_length": len(matched_files),
            "missing_files_length": len(missing_files),
            "ambiguous_files_length": len(ambiguous_files),
        }
        with open(in_path, "ab") as infile, open(out_path, "ab") as outfile, open(props_path, "w") as propsfile:
            pickle.dump(files_in_directory, infile)
            pickle.dump(matched_files, outfile)
            json.dump(props, propsfile, indent=2)
            
        logger.info(f"I/O saved to in.pkl, out.pkl, and props.json in {test_case_dir}.")

    return matched_files, missing_files, ambiguous_files

if __name__ == "__main__":
    logger.info(f"Welcome to google-photos-exif-merger by @ckinateder!\n--")

    parser = argparse.ArgumentParser()
    parser.add_argument("--inputDir", type=str, required=True, help="Input directory")
    parser.add_argument("--outputDir", type=str, required=True, help="Output directory")
    parser.add_argument("--logLevel", type=str, default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"], help="Logging level")
    parser.add_argument("--testCaseDir", type=str, required=False, help="Path to save the input and output as a test case")
    args = parser.parse_args()

    # Set log level from command line argument
    logger.setLevel(getattr(logging, args.logLevel))

    logger.info(f"Input dir:  {args.inputDir}")
    logger.info(f"Output dir: {args.outputDir}")

    matched_files, missing_files, ambiguous_files = find_sidecar_files(args.inputDir, args.testCaseDir)