from typing import Union, List, Tuple
import logging, os, json, pickle
from datetime import timedelta, datetime, timezone
import subprocess
logger = logging.getLogger(__name__)

def run_command(command:str, verbose:bool=False):
    if verbose:
        logger.info(f"Running command: {command}")
    result = subprocess.run(command, capture_output=True, text=True, shell=True)
    return result.stdout, result.stderr, result.returncode

# Check if date is in DST range (second Sunday in March to first Sunday in November)
def is_dst(date) -> bool:
    # Get the year
    year = date.year
    # Second Sunday in March
    dst_start = datetime(year, 3, 8, 2, 0, 0, tzinfo=timezone.utc)
    while dst_start.weekday() != 6:  # 6 is Sunday
        dst_start = dst_start + timedelta(days=1)
    # First Sunday in November
    dst_end = datetime(year, 11, 1, 2, 0, 0, tzinfo=timezone.utc)
    while dst_end.weekday() != 6:  # 6 is Sunday
        dst_end = dst_end + timedelta(days=1)
    return dst_start <= date <= dst_end
def _format_list(li) -> str:
    out = ""
    max_digits = len(str(len(li) - 1))
    for i, l in enumerate(li):
        out += f"{i:0{max_digits}d}: {l}\n"
    return out[:-2]

def _find_in_matched(l: List[Tuple[str]], item:str, key=True) -> Tuple[str]:
    """
    Search through a list of (media_file, json_file) tuples to find a match containing the given item.

    Args:
        l (List[Tuple[str]]): List of (media_file, json_file) tuples to search through
        item (str): String to search for in either the media file or json file name
        key (bool, optional): If True, search in media file names. If False, search in json file names. Defaults to True.

    Returns:
        Tuple[str]: The matching (media_file, json_file) tuple if found, False otherwise
    """
    for mediaf, jsonf in l:
        if key:
            if item in mediaf:
                return (mediaf, jsonf)
        else:
            if item in jsonf:
                return (mediaf, jsonf)
    return False

def _remove_from_list(l: List[Tuple[str, Tuple[str]]], item:str) -> bool:
    i = None
    for index, (f, _) in enumerate(l):
        if f == item:
            i = index

    if i:
        l.remove(l[i])
        return True
    return False
    
def _list_files(directory:str)->List[str]:
    if os.path.exists(directory):
        return os.listdir(directory)
    logger.warning(f"Directory '{directory}' not found!")
    return []

def _save_list(l:list, fpath:str):
    with open(fpath, 'w+') as file:
        data_to_write = json.dumps(l)
        file.write(data_to_write)

def _load_list(fpath:str):
    with open(fpath, 'r') as file:
        return json.load(file)
    