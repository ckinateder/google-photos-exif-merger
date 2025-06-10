# will call exiftool directly
import argparse
import pdb
from match_files import find_sidecar_files, turn_tuple_list_into_dict
from exif_interface import parse_exif_data_from_sidecar, write_exif_data_to_file
from util import run_command
from __init__ import *
import logging
import os
import json
import shutil
from tqdm import tqdm
from tqdm.contrib.logging import logging_redirect_tqdm
import eventlet

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s:%(levelname)s: %(message)s',
    datefmt='%Y-%m-%d_%H:%M:%S'
)
logger = logging.getLogger(__name__)

# main function
def merge_metadata(inputDir: str, outputDir: str, dryRun: bool = False, overwrite_if_exists: bool = False, progress_callback=None) -> bool:
    try:
        # make output dir if not exists
        # will need to check if empty later
        if not dryRun:
            # delete output dir if it exists
            if os.path.exists(outputDir) and not overwrite_if_exists:
                logger.warning(f"Output directory {outputDir} already exists! Exiting.")
                return False
            elif os.path.exists(outputDir) and overwrite_if_exists:
                logger.info(f"Overwriting files in output directory {outputDir}")
            else:
                logger.info(f"Creating output directory {outputDir}")
                os.makedirs(outputDir, exist_ok=True)

        # first, get sidecar files
        matched_files, missing_files, ambiguous_files = find_sidecar_files(
            inputDir)

        # confirm that all files have a sidecar file
        if len(missing_files) > 0:
            logger.warning(f"Missing sidecar files for {len(missing_files)} files")
        if len(ambiguous_files) > 0:
            logger.warning(
                f"Ambiguous sidecar files for {len(ambiguous_files)} files")

        # turn matched_files into a dict
        matched_files_dict = turn_tuple_list_into_dict(
            matched_files)  # {file: json_file}
        failed_files = {}

        # merge metadata
        with logging_redirect_tqdm():
            total_files = len(matched_files_dict)
            for idx, file in enumerate(tqdm(matched_files_dict, desc="copying metadata", leave=LEAVE_TQDM, dynamic_ncols=True, disable=dryRun)):
                try:
                    # Check for interruption
                    eventlet.sleep(0)
                    
                    input_file = os.path.join(
                        inputDir, file)  # input file with path
                    json_file = os.path.join(
                        inputDir, matched_files_dict[file])  # json file with path
                    with open(json_file, "r") as f:
                        json_data = json.load(f)
                    exif_data_from_sidecar = parse_exif_data_from_sidecar(
                        json_data)
                    
                    # copy file to output dir
                    output_file = os.path.join(
                        outputDir, file)  # output file with path
                    if not dryRun:
                        logger.debug(f"Copying {input_file} -> {output_file}")
                        shutil.copy(input_file, output_file)  # copy file to output dir
                    else:
                        logger.info(f"Would have copied {input_file} -> {output_file}")

                    # write to output dir
                    if not dryRun:
                        write_exif_data_to_file(
                            output_file, exif_data_from_sidecar)  # update exif data
                        logger.info(f"Wrote exif data to {output_file} using {json_file}")
                    else:
                        logger.info(f"Would have written exif data using {json_file}")

                    # Send progress update through callback
                    if progress_callback:
                        current_progress = idx + 1
                        percent = int((current_progress / total_files) * 100)
                        progress_callback({
                            'current': current_progress,
                            'total': total_files,
                            'percent': percent,
                            'file': file,
                            'mute_in_log': True
                        })

                except eventlet.greenlet.GreenletExit:
                    logger.warning(f"Processing interrupted at file: {file}")
                    if not dryRun and os.path.exists(output_file):
                        try:
                            os.remove(output_file)
                            logger.info(f"Cleaned up partial file: {output_file}")
                        except Exception as e:
                            logger.error(f"Error cleaning up file {output_file}: {e}")
                    raise
                except Exception as e:
                    logger.error(f"Error merging metadata for {file}: {e}")
                    failed_files[file] = e

        if len(failed_files) > 0:
            logger.warning(
                f"Failed to merge metadata for {len(failed_files)} files")
            logger.warning(f"Failed files: {failed_files}")
            return False
        
        logger.info(
            f"Successfully merged metadata for all {len(matched_files_dict)} files. Copied from {inputDir} to {outputDir}")
        return True
    except eventlet.greenlet.GreenletExit:
        logger.warning("Processing interrupted")
        raise
    except Exception as e:
        logger.error(f"Unexpected error during processing: {e}")
        return False


if __name__ == "__main__":
    logger.info(f"Welcome to google-photos-exif-merger by @ckinateder!\n--")
    parser = argparse.ArgumentParser()
    parser.add_argument("--inputDir", type=str, required=True,
                        help="Input directory to read files from")
    parser.add_argument("--outputDir", type=str, required=True,
                        help="Output directory to COPY files into")
    parser.add_argument("--logLevel", type=str, default="INFO", choices=[
                        "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"], help="Logging level")
    parser.add_argument("--testCaseDir", type=str, required=False,
                        help="Path to save the input and output of the sidecar matching into a test case")
    parser.add_argument("--dryRun", action="store_true",
                        help="Prints what it will do but doesn't execute")
    parser.add_argument("--overwriteIfExists", action="store_true",
                        help="Overwrite the output directory if it exists")
    args = parser.parse_args()

    # argument validation
    assert args.inputDir != args.outputDir, "Input directory must be different than output directory!"

    # Set log level from command line argument
    logger.setLevel(getattr(logging, args.logLevel))

    logger.info(f"Input dir:  {args.inputDir}")
    logger.info(f"Output dir: {args.outputDir}")

    if args.testCaseDir:
        logger.info(f"Running sidecar matching for testcase.")
        matched_files, missing_files, ambiguous_files = find_sidecar_files(
            args.inputDir, args.testCaseDir)
        logger.info(f"Exiting")
    else:
        merge_metadata(args.inputDir, args.outputDir, args.dryRun, args.overwriteIfExists)
