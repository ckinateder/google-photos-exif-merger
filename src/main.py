# will call exiftool directly
import argparse
import pdb
import sys
from match_files import find_sidecar_files, turn_tuple_list_into_dict
from exif_interface import read_exif_data_on_files, merge_exif_data
from util import _format_list
from __init__ import *
import logging
import os 
import json
import shutil

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s:%(levelname)s: %(message)s',
    datefmt='%Y-%m-%d_%H:%M:%S'
)
logger = logging.getLogger(__name__)

# main function
def merge_metadata(inputDir:str, outputDir:str) -> bool:
    # make output dir if not exists
    # will need to check if empty later
    os.makedirs(outputDir, exist_ok=True)

    # first, get sidecar files
    matched_files, missing_files, ambiguous_files = find_sidecar_files(inputDir)

    # confirm that all files have a sidecar file
    if len(missing_files) > 0:
        logger.warning(f"Missing sidecar files for {len(missing_files)} files")
    if len(ambiguous_files) > 0:
        logger.warning(f"Ambiguous sidecar files for {len(ambiguous_files)} files")

    # turn matched_files into a dict
    matched_files_dict = turn_tuple_list_into_dict(matched_files) # {file: json_file}

    # next read exif data for directory
    exif_data = read_exif_data_on_files(inputDir) # {file: exif_data}

    # confirm that all files have exif data
    # for each file in matched_files, confirm that it has exif data
    for file in matched_files_dict:
        if file not in exif_data:
            logger.warning(f"File {file} has no exif data")
    for file in exif_data:
        if file not in matched_files_dict:
            logger.warning(f"File {file} has no sidecar file")

    # merge metadata
    for file in matched_files_dict:
        json_file = matched_files_dict[file]
        with open(json_file, "r") as f:
            json_data = json.load(f)
        exif_data = exif_data[file]
        merged_metadata = merge_exif_data(exif_data, json_data)

        # write to output dir
        output_file = os.path.join(outputDir, file)
        shutil.copy(file, output_file)
        
        
        

    return True

if __name__ == "__main__":
    logger.info(f"Welcome to google-photos-exif-merger by @ckinateder!\n--")

    parser = argparse.ArgumentParser()
    parser.add_argument("--inputDir", type=str, required=True, help="Input directory to read files from")
    parser.add_argument("--outputDir", type=str, required=True, help="Output directory to COPY files into")
    parser.add_argument("--logLevel", type=str, default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"], help="Logging level")
    parser.add_argument("--testCaseDir", type=str, required=False, help="Path to save the input and output of the sidecar matching into a test case")
    parser.add_argument("--dryRun", type=bool, default=False, help="Prints what it will do but doesn't execute")
    args = parser.parse_args()

    # argument validation
    assert args.inputDir != args.outputDir, "Input directory must be different than output directory!"

    # Set log level from command line argument
    logger.setLevel(getattr(logging, args.logLevel))

    logger.info(f"Input dir:  {args.inputDir}")
    logger.info(f"Output dir: {args.outputDir}")

    if args.dryRun:
        # dry run information
        matched_files, missing_files, ambiguous_files = find_sidecar_files(args.inputDir, args.testCaseDir)
        # TODO print of form inputdir/file1 -> inputdir/file2 (metadata file)
        #logger.info(f"Matched Files:\n{_format_list(matched_files)}")
        #logger.info(f"Missing Files:\n{_format_list(missing_files)}")
        #logger.info(f"Ambiguous Files:\n{_format_list(ambiguous_files)}")
    elif args.testCaseDir:
        logger.info(f"Running sidecar matching for testcase.")
        matched_files, missing_files, ambiguous_files = find_sidecar_files(args.inputDir, args.testCaseDir)
        logger.info(f"Exiting")
    else:
        merge_metadata(args.inputDir, args.outputDir)