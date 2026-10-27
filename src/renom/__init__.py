#!/usr/bin/env python3
r"""
Batch rename files and directories with pattern-based transformations.

Synopsis:
  renom [OPTIONS] INPUTS... arg1 arg2

Description:
  Rename multiple files/directories matching INPUTS patterns by applying
  transformations based on arg1 and arg2. Supports glob patterns including
  recursive '**/' matching.

Modes of operation (determined by arg1 and arg2):
  1. Replace: Both arg1 and arg2 non-empty
     Replace all occurrences of arg1 with arg2 in each name
     Example: renom * 'old' 'new'  # file_old.txt -> file_new.txt

  2. Suffix: arg1 is empty string ''
     Append arg2 to the end of each name
     Example: renom *.txt '' '.exclude'  # file.txt -> file.txt.exclude

  3. Prefix: arg2 is empty string '', arg1 NOT found in name
     Prepend arg1 to the beginning of each name
     Example: renom * 'sub-' ''  # 260129A -> sub-260129A
     
  4. Delete: arg2 is empty string '', arg1 found in name
     Remove all occurrences of arg1 from each name
     Example: renom *Sim-Cre '_Sim-Cre' ''  # sub-260129A_Sim_Cre -> sub-260129A

  5. Number increment: arg1 in name, arg2 starts with '+N' (N is integer, or '+-N')
     Find numbers following arg1 and add N to them
     Example: renom *_T*.tif '_T' '+5'  # file_T1.tif -> file_T6.tif

  6. Full replace: arg1 is '*'
     Replace the entire name with arg2 (arg1 acts as a wildcard meaning "any name")
     Example: renom */*/ses-pre_* '*' 'ses-pre'  # ses-pre_LSD-0.4 -> ses-pre

  7. Regex-matching: arg1 is regex
     Replace the part of name that matches the regex pattern specified by arg1 with arg2
     Example: renom * '\d{4}-\d{2}-\d{2}_' '' # exp-2024-04-29_Saline -> exp-Saline
     Note: escape \ and {} when wrapped inside a datalad runcmd -> '\\d{{4}}-\\d{{2}}-\\d{{2}}_'

  8. Path mode: arg1 contains '/'
     Transform the whole path instead of just the basename, so files can be
     moved across directories (missing destination directories are created).
     Combines with the replace/delete/regex modes above. A '/' in arg1 is the
     trigger, since it can never occur within a single basename.
     Example: renom 02_roi2cell/sub-A/exp-X/plane0/cells/snr.npy '02_roi2cell/(.*)/cells/snr.npy' '01_suite2p/\1/snr.npy'
              # -> 01_suite2p/sub-A/exp-X/plane0/snr.npy

  INPUTS   One or more file/directory paths or glob patterns
  arg1     Pattern/string to match (see modes above)
  arg2     Replacement/transformation (see modes above)
"""

EPILOG = """
Notes: 
  • Use * and **/ for (recursive) pattern matching.
  • Patterns are expanded by your shell, not Python, so don't use '' or "".
  • Never overwrites existing files.
  • Handles name collisions automatically (renames in optimal order)
"""
import os
import argparse
import re
import sys

def is_regex_pattern(pattern):
    """Check if a string contains regex special characters"""
    regex_special = set('.^$*+?{}[]\\|()')
    return any(char in regex_special for char in pattern)

def rename(input, arg1, arg2):
    # Path mode: a '/' in arg1 can never match within a basename (filenames
    # contain no '/'), so it signals that the transformation should apply to
    # the whole path. This enables moving files across directories — e.g.
    # '02_roi2cell/(.*)/cells/snr.npy' -> '01_suite2p/\1/snr.npy'.
    if '/' in arg1:
        parent_path, old_item = '', input
    else:
        parent_path, old_item = os.path.split(input)
    if arg1 == '*':
        # 6. Full replace: substitute the entire name with arg2
        new_item = arg2
    elif is_regex_pattern(arg1):
        # 7. Regex pattern matching - replace using regex
        try:
            new_item = re.sub(arg1, arg2, old_item)
        except re.error:
            sys.exit(f"Invalid regex pattern: {arg1}")
    elif arg1 == '':
        # 1. Add arg2 to the back
        new_item = old_item + arg2
    elif arg2 == '':
        if  arg1 not in old_item:
            # 2. Append arg1 to the front
            new_item = arg1 + old_item
        else:
            # 3. Delete arg1
            new_item = old_item.replace(arg1, arg2)
    elif (arg1 in old_item) and (arg2[0] == '+'):
        try:
            N = int(arg2[1:])
            # 5. add an integer number to the number led by arg1
            # Build regex: pattern followed by an optional minus sign and digits
            # (negative numbers can occur after a previous offsetting operation)
            regex = f'{re.escape(arg1)}(-?\\d+)'  # '_T1' or '_T_-1'

            def add_number_to_match(match):
                num = int(match.group(1))  # '1' -> 1
                return f'{arg1}{num + N}'  # '_T38'

            # Replace pattern/regex by the output of the function add_number_to_match in old_name
            new_item = re.sub(regex, add_number_to_match, old_item)
        except ValueError:
            sys.exit('Invalid number for the add-number mode.')
    else:
        # 4. replace it with arg2
        new_item = old_item.replace(arg1, arg2)

    if old_item != new_item:
        old_path = os.path.join(parent_path, old_item)
        new_path = os.path.join(parent_path, new_item)
        # do not overwrite existing file with the same name
        if os.path.exists(new_path):
            print(f"SKIP: '{new_item}' already exists. Will try to rename '{old_item}' in the next iteration.")
            return input
        # in path mode the destination may live in a directory that does not
        # exist yet (cross-tree move); create it before renaming
        dest_dir = os.path.dirname(new_path)
        if dest_dir:
            os.makedirs(dest_dir, exist_ok=True)
        os.rename(old_path, new_path)
        print(f"Rename {old_item} -> {new_item}")
    return


def main():
    parser = argparse.ArgumentParser(
        description=__doc__,
        epilog=EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument('inputs', nargs='+', help='One or more file/directory paths or glob patterns')
    parser.add_argument('arg1', help='Pattern/string to match (see modes of operation)')
    parser.add_argument('arg2', help='Replacement/transformation (see modes of operation)')
    args = parser.parse_args()

    # use sets to handle overlapping old and new names such as T1 -> T38, T38 -> T75
    # strategy: skip T38 and rename in the next iteration after T38 -> T75 has happened
    # if T38 never gets renamed into something else, avoid the infinite loop
    current_set = set(args.inputs)
    while (next_set := {rename(i, args.arg1, args.arg2) for i in current_set if i}) != current_set:
        current_set = next_set

if __name__ == "__main__":
    main()