# will call exiftool directly
import argparse
import os
import pathlib
import json
import re

MEDIA_EXTENSIONS = [".jpg", ".jpeg", ".png", ".heic", ".heif", ".mp4", ".mov", ".avi", ".mkv", ".wmv", ".flv", ".f4v", ".f4p", ".f4a", ".f4b"]
JSON_EXTENSION = ".json"
JSON_SUFFIX = ["supple", "supplemen", "supplemental-metadata", "s"]

def match_files(directory) -> list[tuple[str, str]]:
    """
    This function will match the json metadata files with the images in the same directory. There will be a default matching scheme, but there will be cases for other matching schemes.

    Args:
        directory (str): The directory to match the files in.

    Returns:
        list[tuple[str, str]]: A list of tuples, where the first element is the path to the media file and the second element is the path to corresponding the metadata file.
    """
    # start with getting a list of all the files in the directory that are media files. then check if there is a json file with the same base name
    # if there is a json file with the same base name, then add the tuple to the matched list, if not, add it to the unmatched list
    matched_files = []
    unmatched_files = []

    # stage 1: match the json files with the media files
    all_json_files = [f for f in os.listdir(directory) if os.path.splitext(f)[1].lower() == JSON_EXTENSION]
    all_media_files = [f for f in os.listdir(directory) if os.path.splitext(f)[1].lower() in MEDIA_EXTENSIONS]

    for file in all_media_files:
        fullpath = os.path.join(directory, file)
        basename = os.path.splitext(file)[0]
        media_extension = os.path.splitext(file)[1].lower()
        print(f"Checking {fullpath}")
        if os.path.isfile(fullpath) and media_extension in MEDIA_EXTENSIONS:
            # get basename
            # remove -edited suffix if there
            basename = re.sub(r'-edited$', '', basename, flags=re.IGNORECASE)

            # use regex to check if there exists a file with the same base name, anything, then .json
            pattern = re.compile(rf'^{re.escape(basename)}.*\{JSON_EXTENSION}$')
            potential_jsons = [f for f in all_json_files if pattern.match(f)]

            # Handle edge case like 'foo(1).jpg' => 'foo.jpg(1).json'
            match = re.match(r"(?P<name>.*)(?P<counter>\(\d+\))$", basename)
            if match:
                name = match.group("name")
                counter = match.group("counter")
                potential_jsons.append(f"{name}{media_extension}{counter}.json")
            
            # Handle trailing characters: _, _n, _n-
            if basename.endswith(('_n-', '_n', '_')):
                potential_jsons.append(f"{basename[:-1]}.json")

            # get rid of duplicates
            potential_jsons = list(set(potential_jsons))

            # if more than 1 or less than 1 potential matches, there is a problem. move on
            if len(potential_jsons) != 1:
                unmatched_files += [file]
                continue

            # if we are this far, then it matched successfully for this instance
            json_file = potential_jsons[0]
            matched_files.append((file, json_file))

    return matched_files, unmatched_files


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--inputDir", type=str, required=True, help="Input directory")
    parser.add_argument("--outputDir", type=str, required=True, help="Output directory")
    args = parser.parse_args()

    print(args.inputDir)
    print(args.outputDir)

    matched_files, unmatched_files = match_files(args.inputDir)
    print("Matched:")
    [print(f"- {p}") for p in matched_files]

    print("Unatched:")
    [print(f"- {p}") for p in unmatched_files]
    print(f"Matched {len(matched_files)} files")
    print(f"Unmatched {len(unmatched_files)} files")