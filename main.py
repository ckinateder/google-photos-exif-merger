# will call exiftool directly
import argparse
import os
import pathlib
import json
import re
import pdb

MEDIA_EXTENSIONS = [".jpg", ".jpeg", ".png", ".heic", ".heif", ".mp4", ".mov", ".avi", ".mkv", ".wmv", ".flv", ".f4v", ".f4p", ".f4a", ".f4b"]
JSON_EXTENSION = ".json"
JSON_SUFFIX = ["supple", "supplemen", "supplemental-metadata", "s"]

def _search_in_matches(matches: list[tuple[str,str]]) -> bool:
    for f, j in matches:
        pass

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
    missing_files = []
    ambiguous_files = []

    # stage 1: match the json files with the media files
    all_json_files = [f for f in os.listdir(directory) if os.path.splitext(f)[1].lower() == JSON_EXTENSION]
    all_media_files = [f for f in os.listdir(directory) if os.path.splitext(f)[1].lower() in MEDIA_EXTENSIONS]
    total_media_files = len(all_media_files)
    total_json_files = len(all_json_files)
    print(f"Found {total_media_files} media files and {total_json_files} json files")

    for file in all_media_files:
        fullpath = os.path.join(directory, file)
        basename = os.path.splitext(file)[0]
        media_extension = os.path.splitext(file)[1].lower()
        print(f"Checking '{file}'...", end=' ')
        if os.path.isfile(fullpath) and media_extension in MEDIA_EXTENSIONS:
            # get basename
            # remove -edited suffix if there
            basename = re.sub(r'-edited$', '', basename, flags=re.IGNORECASE)

            # BASIC: use regex to check if there exists a file with the same base name, anything, then .json
            pattern = re.compile(rf'^{re.escape(basename)}.*\{JSON_EXTENSION}$')
            potential_jsons = [f for f in all_json_files if pattern.match(f)]

            # Handle edge case like 'foo(1).jpg' => 'foo.jpg(1).json'
            pattern = re.compile(r"(?P<name>.*)(?P<counter>\(\d+\))$")
            match = pattern.match(basename)
            if match:
                name = match.group("name")
                counter = match.group("counter")
                potential_jsons.append(f"{name}{media_extension}{counter}.json")
            
            # Handle trailing characters: _, _n, _n-
            if basename.endswith(('_n-', '_n', '_')):
                potential_jsons.append(f"{basename[:-1]}.json")

            # get rid of duplicates
            potential_jsons = list(set(potential_jsons))

            #if basename == "IMG_0361":
            #    pdb.set_trace()

            # if less than 1 potential matches, there is a problem. move on
            if len(potential_jsons) < 1:
                missing_files.append(file)
                print(f"no match found.")
                continue
            elif len(potential_jsons) > 1: # we have too many
                # get the media extension and match it that way
                # REMEMBER this could be MP4 too and there may not be a json for it. in that case idk
                ambiguous_files.append((file, potential_jsons))
                print(f"{len(potential_jsons)} potential matches found.")
                continue

            # if we are this far, then it matched successfully for this instance
            json_file = potential_jsons[0]
            matched_files.append((file, json_file))
            print(f"match found at '{json_file}'!")

    # stage 2: search deeeper for missing files
    print(f"Attempting to fix {len(missing_files)} missing metadata files...")
    recovered = []
    for file in missing_files:
        # just try a bunch of random things
        potential_jsons = []
        basename = os.path.splitext(file)[0]
        if len(basename) >= 47: # i don't know why this cutoff is at 46
            # just check to see if the cutoff exists.
            cutoff_file = basename[:46] + JSON_EXTENSION 
            if os.path.exists(os.path.join(directory, cutoff_file)):
                recovered.append((file, cutoff_file))
            
    # move found files into matched_files
    print(f"Recovered {len(recovered)} missing metadata files.")
    matched_files += recovered
    for f, _ in recovered:
        missing_files.remove(f)
    

    # stage 3: examine all the duplicates
    for file, prospects in ambiguous_files:
        pass
        
    print("Matched:")
    [print(f"- {p}") for p in matched_files]
    print("Missing:")
    [print(f"- {p}") for p in missing_files]
    print("Ambiguous:")
    [print(f"- {p}") for p in ambiguous_files]
    print(f"Matched    {len(matched_files)} files")
    print(f"Missing    {len(missing_files)} files")
    print(f"Ambiguous  {len(ambiguous_files)} files")

    # conservation of mass
    accounted_for_media_files = len(matched_files) + len(missing_files) + len(ambiguous_files)
    assert accounted_for_media_files == total_media_files, f"accounted_for_media_files != total_media_files ({accounted_for_media_files} != {total_media_files})"
    return matched_files, missing_files, ambiguous_files


def match_files_from_json(directory) -> list[tuple[str, str]]:
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
    missing_files = []

    # stage 1: match the json files with the media files
    all_json_files = [f for f in os.listdir(directory) if os.path.splitext(f)[1].lower() == JSON_EXTENSION]
    all_media_files = [f for f in os.listdir(directory) if os.path.splitext(f)[1].lower() in MEDIA_EXTENSIONS]

    for json_filename in all_json_files:
        json_fullpath = os.path.join(directory, json_filename)
        basename = os.path.splitext(json_filename)[0]
        
        # load json
        with open(json_fullpath, 'r') as f:
            metadata = json.load(f)

        # load media path
        media_filename = metadata["title"]
        media_fullpath = os.path.join(directory, media_filename)
        if not os.path.exists(media_fullpath):
            print(f"Warning: no file found for {media_filename}")
            missing_files.append(json_filename)
            continue

        # if we made it this far, then the file exists
        matched_files.append((media_filename, json_filename))


    return matched_files, missing_files, []


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--inputDir", type=str, required=True, help="Input directory")
    parser.add_argument("--outputDir", type=str, required=True, help="Output directory")
    args = parser.parse_args()

    print(args.inputDir)
    print(args.outputDir)

    matched_files, missing_files, ambiguous_files = match_files(args.inputDir)