# will call exiftool directly
import argparse
import os
import json
import re
import pdb
from typing import Union, List, Tuple

from util import _format_list, _find_in_matched, _remove_from_list

from tqdm import trange, tqdm
from tqdm.contrib.logging import logging_redirect_tqdm

import logging

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


def match_files(directory) -> Union[List[Tuple[str]], List[str], List[Tuple[str, Tuple[str]]]]:
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
    all_json_files = [f for f in os.listdir(directory) if os.path.splitext(f)[1].lower() == JSON_EXTENSION]
    all_media_files = [f for f in os.listdir(directory) if os.path.splitext(f)[1].lower() in MEDIA_EXTENSIONS]
    total_media_files = len(all_media_files)
    total_json_files = len(all_json_files)
    logger.info(f"Found {total_media_files} media files and {total_json_files} json files")

    with logging_redirect_tqdm():
        for file in tqdm(all_media_files, desc="media files", leave=False, dynamic_ncols=True):
            # initialize variables
            fullpath = os.path.join(directory, file)
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
                name = match.group("name")
                counter = match.group("counter")
            
            # start off by searching w/ counters
            if counter: # if it takes the form foo(n).jpg
                # search in all_json_files
                pattern = re.compile(rf"^{name}{media_extension}(?P<suffix>.*){re.escape(counter)}{JSON_EXTENSION}$")
                for f in all_json_files:
                    if pattern.match(f):
                        potential_jsons.append(f)
            else: # if no counters
                # now go through and see if anything basic matches with the media extension
                # if nothing found move forward...
                pattern = re.compile(rf"^{basename}{media_extension}(?P<suffix>.*){JSON_EXTENSION}$")
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
            potential_jsons = list(set(potential_jsons))

            #if basename=="IMG_0356":
            #    pdb.set_trace()

            
            # if less than 1 potential matches, there is a problem. move on
            if len(potential_jsons) < 1:
                missing_files.append(file)
                logger.warn(f"{msg}no match found.")
                continue
            
            if len(potential_jsons) > 1: # we have too many
                # get the media extension and match it that way
                # REMEMBER this could be MP4 too and there may not be a json for it. in that case idk
                ambiguous_files.append((file, potential_jsons))
                logger.warn(f"{msg}{len(potential_jsons)} potential matches found.")
                continue

            # if we are this far, then it matched successfully for this instance
            json_file = potential_jsons[0]
            assert os.path.isfile(os.path.join(directory, json_file))
            matched_files.append((file, json_file))
            logger.info(f"{msg}match found at '{json_file}'!")

    # stage 2: search deeeper for missing files
    logger.info(f"Attempting to fix {len(missing_files)} missing metadata files...")
    recovered = []
    with logging_redirect_tqdm():
        for file in tqdm(missing_files, desc="missing files", leave=False, dynamic_ncols=True):
            # just try a bunch of things
            potential_jsons = []
            basename = os.path.splitext(file)[0]
            ext = os.path.splitext(file)[-1]

            # i don't know why this cutoff is at 46
            if len(basename) >= 47: 
                # just check to see if the cutoff exists.
                cutoff_file = basename[:46] + JSON_EXTENSION 
                if os.path.exists(os.path.join(directory, cutoff_file)):
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

    # print
    #logger.info(f"Matched:\n{_format_list(matched_files)}")
    logger.info(f"Missing:\n{_format_list(missing_files)}")
    logger.info(f"Ambiguous:\n{_format_list(ambiguous_files)}")
    logger.info(f"Matched    {len(matched_files)}/{total_media_files} files")
    logger.info(f"Missing    {len(missing_files)}/{total_media_files} files")
    logger.info(f"Ambiguous  {len(ambiguous_files)}/{total_media_files} files")

    # conservation of mass
    accounted_for_media_files = len(matched_files) + len(missing_files) + len(ambiguous_files)
    assert accounted_for_media_files == total_media_files, f"accounted_for_media_files != total_media_files ({accounted_for_media_files} != {total_media_files})"
    return matched_files, missing_files, ambiguous_files

if __name__ == "__main__":
    logger.info(f"Welcome to google-photos-exif-merger by @ckinateder!\n--")

    parser = argparse.ArgumentParser()
    parser.add_argument("--inputDir", type=str, required=True, help="Input directory")
    parser.add_argument("--outputDir", type=str, required=True, help="Output directory")
    args = parser.parse_args()

    logger.info(f"Input dir:  {args.inputDir}")
    logger.info(f"Output dir: {args.outputDir}")

    matched_files, missing_files, ambiguous_files = match_files(args.inputDir)