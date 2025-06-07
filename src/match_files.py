import os
import re
import pdb
from typing import Union, List, Tuple, Dict
from util import _format_list, _find_in_matched, _list_files
from tqdm import tqdm
from tqdm.contrib.logging import logging_redirect_tqdm
from __init__ import *
import logging
import json
import pickle


logger = logging.getLogger(__name__)

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
    skipped_files = [f for f in filenames if os.path.splitext(f)[1].lower() not in MEDIA_EXTENSIONS and os.path.splitext(f)[1].lower() != JSON_EXTENSION]
    
    if len(skipped_files) > 0:
        logger.info(f"Skipping the following files: {skipped_files}")
    
    total_media_files = len(all_media_files)
    total_json_files = len(all_json_files)
    logger.info(f"Found {total_media_files} media files and {total_json_files} json files")

    with logging_redirect_tqdm():
        for file in tqdm(all_media_files, desc="finding sidecars", leave=LEAVE_TQDM, dynamic_ncols=True):
            basename = os.path.splitext(file)[0]
            media_extension = os.path.splitext(file)[1]
            msg = f"Checking '{file}'... "
            
            # Remove -edited suffix
            basename = re.sub(r'-edited$', '', basename, flags=re.IGNORECASE)
            
            # Check for counter pattern like (1), (2) at the end
            counter_match = re.search(r'(.+)(\(\d+\))$', basename)
            potential_jsons = []
            
            if counter_match:
                # Has counter: look for name.ext.*counter.json
                name = counter_match.group(1)
                counter = counter_match.group(2)
                pattern = f"{re.escape(name)}{re.escape(media_extension)}.*{re.escape(counter)}{re.escape(JSON_EXTENSION)}"
            else:
                # No counter: look for basename.ext.*.json (but exclude files with counters)
                pattern = f"{re.escape(basename)}{re.escape(media_extension)}\\.[^()]+{re.escape(JSON_EXTENSION)}"
            
            # Find matches
            for json_file in all_json_files:
                if re.match(pattern, json_file):
                    potential_jsons.append(json_file)
            
            # Fallback: if no counter and no matches, try loose matching
            if not counter_match and not potential_jsons:
                fallback_pattern = f"^{re.escape(basename)}.*{re.escape(JSON_EXTENSION)}$"
                for json_file in all_json_files:
                    if re.match(fallback_pattern, json_file) and '(' not in json_file:
                        potential_jsons.append(json_file)
            
            # Handle special trailing characters
            if basename.endswith(('_n-', '_n', '_')):
                potential_jsons.append(f"{basename.rstrip('_n-')}.json")
            
            # Remove duplicates
            potential_jsons = sorted(set(potential_jsons))
            
            # Categorize results
            if len(potential_jsons) == 0:
                missing_files.append(file)
                logger.debug(f"{msg}no match found.")
            elif len(potential_jsons) > 1:
                ambiguous_files.append((file, potential_jsons))
                logger.debug(f"{msg}{len(potential_jsons)} potential matches found.")
            else:
                matched_files.append((file, potential_jsons[0]))
                logger.debug(f"{msg}match found at '{potential_jsons[0]}'!")

    # stage 2: search deeeper for missing files
    if len(missing_files) > 0:
        logger.info(f"Attempting to fix {len(missing_files)} missing metadata files...")
        recovered = []
        with logging_redirect_tqdm():
            for file in tqdm(missing_files, desc="fixing missing files", leave=LEAVE_TQDM, dynamic_ncols=True):
                basename = os.path.splitext(file)[0]
        
                # Check for filename cutoff at 46 characters
                if len(basename) >= 47:
                    cutoff_file = basename[:46] + JSON_EXTENSION
                    if cutoff_file in all_json_files:
                        recovered.append((file, cutoff_file))
                        continue
                
                # Look for exact basename match in already matched files
                existing_match = _find_in_matched(matched_files, basename)
                if existing_match:
                    logger.debug(f"Found {basename} in matched, falling back.")
                    recovered.append((file, existing_match[1]))
                    continue
                
                # Try removing counter like (1), (2) and search again
                if basename.endswith(')') and '(' in basename:
                    basename_no_counter = re.sub(r'\(\d+\)$', '', basename)
                    existing_match = _find_in_matched(matched_files, basename_no_counter)
                    if existing_match:
                        logger.debug(f"Found {basename} in matched, falling back.")
                        recovered.append((file, existing_match[1]))
                        continue

        # move found files into matched_files
        logger.info(f"Recovered {len(recovered)} missing metadata files.")
        matched_files += recovered
        for f, _ in recovered:
            missing_files.remove(f)
        
        recovered = []

    # stage 3: examine all the ambiguous files. this happens a lot with live photos
    if len(ambiguous_files) > 0:
        logger.info(f"Attempting to fix {len(ambiguous_files)} ambiguous metadata files...")
        with logging_redirect_tqdm():
            for file, prospects in tqdm(ambiguous_files, desc="fixing ambiguous files", leave=LEAVE_TQDM, dynamic_ncols=True):
                basename = os.path.splitext(file)[0]
                media_extension = os.path.splitext(file)[1]
                if media_extension.lower() == LIVE_PHOTO_EXTENSION: # if live photo
                    # just pick the first one because it doesn't matter, they'll be the same...? should verify this claim though
                    recovered.append((file, prospects[0]))

        # print
        logger.info(f"Recovered {len(recovered)} ambiguous metadata files.")
        matched_files += recovered

        # remove from list
        if len(recovered) > 0:
            recovered_fs, _ = zip(*recovered)
            for i, (f, _) in enumerate(ambiguous_files):
                if f in recovered_fs:
                    ambiguous_files[i] = None
            
            ambiguous_files = [x for x in ambiguous_files if x is not None]
    
    # sort by name
    matched_files.sort(key=lambda x: x[0])
    ambiguous_files.sort(key=lambda x: x[0])
    missing_files.sort()

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

def turn_tuple_list_into_dict(tuple_list:List[Tuple[str, str]]) -> Dict[str, str]:
    # assert no duplicates
    assert len(tuple_list) == len(set(tuple_list)), "Duplicate files in tuple list"
    return {file: json_file for file, json_file in tuple_list}

def find_sidecar_files(directory:str, test_case_dir:str = None):
    files_in_directory = _list_files(directory)
    
    matched_files, missing_files, ambiguous_files = match_files_from_file_list(files_in_directory)
    with logging_redirect_tqdm():
        for media_file, json_file in tqdm(matched_files, desc="validating", leave=LEAVE_TQDM, dynamic_ncols=True):
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