# will call exiftool directly
import argparse
import pdb
from match_files import find_sidecar_files
from __init__ import *
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s:%(levelname)s: %(message)s',
    datefmt='%Y-%m-%d_%H:%M:%S'
)
logger = logging.getLogger(__name__)

if __name__ == "__main__":
    logger.info(f"Welcome to google-photos-exif-merger by @ckinateder!\n--")

    parser = argparse.ArgumentParser()
    parser.add_argument("--inputDir", type=str, required=True, help="Input directory to read files from")
    parser.add_argument("--outputDir", type=str, required=True, help="Output directory to COPY files into")
    parser.add_argument("--logLevel", type=str, default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"], help="Logging level")
    parser.add_argument("--testCaseDir", type=str, required=False, help="Path to save the input and output as a test case")
    args = parser.parse_args()

    # Set log level from command line argument
    logger.setLevel(getattr(logging, args.logLevel))

    logger.info(f"Input dir:  {args.inputDir}")
    logger.info(f"Output dir: {args.outputDir}")

    matched_files, missing_files, ambiguous_files = find_sidecar_files(args.inputDir, args.testCaseDir)
