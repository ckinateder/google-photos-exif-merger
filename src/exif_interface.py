import subprocess
import os
import json
from __init__ import MEDIA_EXTENSIONS
from datetime import datetime, timezone
import dateutil
import pdb
import logging
logger = logging.getLogger(__name__)


def run_command(command:str):
    result = subprocess.run(command, capture_output=True, text=True, shell=True)
    return result.stdout, result.stderr, result.returncode

def read_exif_data_on_files(file_or_directory:str) -> dict:
    """Use EXIFTOOL to load all files in a directory and then return the ones matching media extensions

    Args:
        file_or_directory (str): _description_

    Returns:
        dict: {
            "file_path>": {
                "ExifIFD": {
                    "DateTimeOriginal": "2022:05:13 11:24:07",
                    "CreateDate": "2022:05:13 11:24:07",
                }
                ...
            }
            ...
        }
    """
    command = f"exiftool -a -u -g1 -j {repr(file_or_directory)}"
    out, err, rc = run_command(command)
    if rc==0:
        parsed = json.loads(out)
        # now remove anything not in media_extensions
        to_return = {}
        for file_data in parsed:
            filename = file_data['System']['FileName']
            if os.path.splitext(filename)[-1].lower() in MEDIA_EXTENSIONS:
                to_return[filename] = file_data
        return to_return
    
    logger.error(f"Couldn't read exif data for {file_or_directory}: {err}")
    return {}

def merge_exif_data(original_metadata:dict, supplemental:dict) -> dict:
    """Merge the data read from the file and overwrite the date fields. Also confirm that geodata matchees

    Args:
        original_metadata (dict): BIG file from exiftool
        supplemental (dict): contains title, creationTime, photoTakenTime, geoData

    Returns:
        dict: updated data
    """
    # sanity checks
    if {"title", "photoTakenTime", "creationTime", "geoData"} > supplemental.keys():
        logger.warning(f"Missing metadata fields")
        print(supplemental)
        return {}
    
    if not supplemental["title"] == original_metadata["System"]["FileName"]:
        logger.warning(f"Filename does not match ({supplemental['title']}!={original_metadata['System']['FileName']})")
        return {}
    
    # load creationTime and photoTakenTime
    creationTime = datetime.fromtimestamp(int(supplemental["creationTime"]["timestamp"])).replace(tzinfo=timezone.utc)
    dateTimeOriginal = datetime.fromtimestamp(int(supplemental["photoTakenTime"]["timestamp"])).replace(tzinfo=timezone.utc)
    
    # exifIdStuff
    times_to_update = {
            "DateTimeOriginal": dateTimeOriginal.strftime("%Y:%m:%d %H:%M:%S"),
            "CreateDate": creationTime.strftime("%Y:%m:%d %H:%M:%S"),
            "OffsetTime": "+00:00", # switch to UTC
            "OffsetTimeOriginal": "+00:00", # switch to UTC
            "OffsetTimeDigitized": "+00:00", # switch to UTC
    }

    # update
    merged_metadata = original_metadata.copy()
    merged_metadata["ExifIFD"].update(times_to_update)
    return merged_metadata

def write_exif_data_to_file(file_path:str, exif_data:dict):
    """Write exif data to a file

    Args:
        file_path (str): path to the file
        exif_data (dict): exif data to write
    """
    command = f"exiftool -overwrite_original -P -g1 -j {repr(file_path)}"
    run_command(command)