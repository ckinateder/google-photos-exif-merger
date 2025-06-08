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

def read_exif_data_on_file(file_path:str) -> dict:
    """Use EXIFTOOL to load a file and return the exif data

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
    command = f"exiftool -a -u -g1 -j {repr(file_path)}"
    out, err, rc = run_command(command)
    if rc==0:
        parsed = json.loads(out)
        return parsed[0]
    
    logger.error(f"Couldn't read exif data for {file_path}: {err}")
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

def _validate_exif_fields(exif_data: dict) -> None:
    """Validate that required EXIF fields are present in the data.
    
    Args:
        exif_data: Dictionary containing EXIF data to validate
        
    Raises:
        ValueError: If required fields are missing
    """
    required_fields = {"DateTimeOriginal", "CreateDate", "OffsetTime", "OffsetTimeOriginal", "OffsetTimeDigitized"}
    if required_fields > exif_data.keys():
        raise ValueError(f"Missing required EXIF fields: {required_fields - exif_data.keys()}")

def _build_exiftool_command(exif_data: dict, file_path: str) -> str:
    """Build the exiftool command string from EXIF data.
    
    Args:
        exif_data: Dictionary containing EXIF data
        file_path: Path to the target file
        
    Returns:
        str: Complete exiftool command
    """
    modstring = " ".join(f"-{key}=\"{value}\"" for key, value in exif_data.items())
    return f"exiftool -overwrite_original {modstring} {repr(file_path)}"

def _handle_extension_mismatch(file_path: str, exif_data: dict, verbose: bool) -> str:
    """Handle case where file extension doesn't match EXIF data.
    
    Args:
        file_path: Current path of the file
        exif_data: EXIF data to write
        verbose: Whether to enable verbose logging
        
    Returns:
        str: New file path if extension was changed, original path otherwise
        
    Raises:
        RuntimeError: If EXIF data cannot be read or extension cannot be changed
    """
    exif_data_from_file = read_exif_data_on_file(file_path)
    if not exif_data_from_file:
        raise RuntimeError(f"Couldn't read EXIF data for {file_path} to change extension")
        
    extension = os.path.splitext(file_path)[1].lower()
    should_be_extension = exif_data_from_file["System"]["FileTypeExtension"].lower()
    
    if extension != should_be_extension:
        new_file_path = file_path.replace(extension, should_be_extension)
        os.rename(file_path, new_file_path)
        return new_file_path
    return file_path

def write_exif_data_to_file(file_path: str, exif_data: dict, verbose: bool = False) -> None:
    """Write EXIF data to a file.
    
    Args:
        file_path: Path to the target file
        exif_data: Dictionary containing EXIF data to write
        verbose: Whether to enable verbose logging
        
    Raises:
        ValueError: If required EXIF fields are missing
        RuntimeError: If EXIF data cannot be written or file extension cannot be changed
    """
    _validate_exif_fields(exif_data)
    
    command = _build_exiftool_command(exif_data, file_path)
    _, err, rc = run_command(command, verbose=verbose)
    
    if rc != 0:
        if verbose:
            logger.error(f"Error writing EXIF data to {file_path}: {err.strip()}")
            
        try:
            new_file_path = _handle_extension_mismatch(file_path, exif_data, verbose)
            if new_file_path != file_path:
                command = _build_exiftool_command(exif_data, new_file_path)
                _, err, rc = run_command(command, verbose=verbose)
                if rc != 0:
                    raise RuntimeError(f"Failed to write EXIF data after extension change: {err.strip()}")
                logger.info(f"Automatically changed extension from {file_path} to {new_file_path} due to mismatch")
        except Exception as e:
            raise RuntimeError(f"Failed to handle EXIF data writing: {str(e)}")