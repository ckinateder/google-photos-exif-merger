from typing import Union, List, Tuple

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