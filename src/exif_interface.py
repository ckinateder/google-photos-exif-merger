import subprocess
import os
import json
from __init__ import MEDIA_EXTENSIONS
from datetime import datetime, timezone, timedelta
from util import run_command, is_dst
import dateutil
import pdb
import logging
logger = logging.getLogger(__name__)

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
    
    # Set offset
    offset_hours = 0
    if is_dst(dateTimeOriginal) and offset_hours != 0:
        offset_hours -= 1
    timezone_offset = timezone(timedelta(hours=offset_hours))
    dateTimeOriginal = dateTimeOriginal.astimezone(timezone_offset)
    creationTime = creationTime.astimezone(timezone_offset)
    offset = f"{offset_hours:+03d}:00" # +03d is to ensure 3 digits including sign

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

def write_exif_data_to_file(file_path:str, exif_data:dict, verbose:bool=False):
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
    
    _, err, rc = run_command(command, verbose=verbose)
    if rc != 0:
        logger.error(f"Error writing exif data to {file_path}: {err}")
        return err
    
    return True