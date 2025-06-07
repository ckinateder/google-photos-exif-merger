import subprocess
import os
import json
from __init__ import MEDIA_EXTENSIONS
from datetime import datetime, timezone, timedelta
from util import run_command
import dateutil
import pdb
import logging
logger = logging.getLogger(__name__)


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

def parse_exif_data_from_sidecar(supplemental:dict) -> dict:
    """Parse the sidecar file and return the exif data

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
    
    # load creationTime and photoTakenTime
    creationTime = datetime.fromtimestamp(int(supplemental["creationTime"]["timestamp"])).replace(tzinfo=timezone.utc)
    dateTimeOriginal = datetime.fromtimestamp(int(supplemental["photoTakenTime"]["timestamp"])).replace(tzinfo=timezone.utc)
    
    # change times to EST
    #dateTimeOriginal = dateTimeOriginal.astimezone(timezone(timedelta(hours=-4)))
    # creationTime = creationTime.astimezone(timezone(timedelta(hours=-4)))
    offset = "+00:00"

    # exifIdStuff
    times_to_update = {
            "DateTimeOriginal": dateTimeOriginal.strftime("%Y:%m:%d %H:%M:%S")+offset,
            "CreateDate": creationTime.strftime("%Y:%m:%d %H:%M:%S")+offset,
            "FileCreateDate": creationTime.strftime("%Y:%m:%d %H:%M:%S")+offset,
            "FileModifyDate": creationTime.strftime("%Y:%m:%d %H:%M:%S")+offset,
            "OffsetTime": offset,
            "OffsetTimeOriginal": offset,
            "OffsetTimeDigitized": offset, 
    }

    return times_to_update

def write_exif_data_to_file(file_path:str, exif_data:dict):
    """Write exif data to a file

    Args:
        file_path (str): path to the file
        exif_data (dict): exif data to write (from parse_exif_data_from_sidecar)
    """
    # sanity checks
    if {"DateTimeOriginal", "CreateDate", "OffsetTime", "OffsetTimeOriginal", "OffsetTimeDigitized"} > exif_data.keys():
        logger.warning(f"Missing exif data fields")
        return False
    
    modstring = ""
    for key, value in exif_data.items():
        modstring += f"-{key}=\"{value}\" "
    
    command = f"exiftool -overwrite_original {modstring} {repr(file_path)}"
    
    _, err, rc = run_command(command)
    if rc != 0:
        logger.error(f"Error writing exif data to {file_path}: {err}")
        return err
    
    return True