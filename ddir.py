"""
Compares two directories for files that are missing on either side and runs
a diff command on each file that differs. Prints statistics.
Written by Kevin P. Inscoe - https://github.com/KevinPInscoe/ddir
"""

import filecmp
import subprocess
import sys
import os
from pathlib import Path

def check_path_for_dots(file, pathsep):
    # If one of the directories in this path or the file itself have a
    # leading dot in it's name we want to ignore it (like .git or .terraform)
    paths = str(file).split(pathsep)
    for path in paths:
        if len(path) > 0:
            if path[0] == '.':
                return False

    return True

def compare(filea, fileb, diffcmd):
    if not filecmp.cmp(filea, fileb, shallow=False):
        print("** %s and %s differ:\n" % (filea, fileb))
        subprocess.run(diffcmd + [filea, fileb])
        return True

    return False

def files(dirpath, pathsep):
    file_list = []
    for file in Path(dirpath).rglob('*'):
        if file.is_file():
            if not file.name.startswith('.'):
                if check_path_for_dots(file, pathsep):
                    file_list.append(str(file.resolve()))

    return file_list

def get_file_suffix(file, directory):
    return os.sep + str(Path(file).relative_to(Path(directory).resolve()))

def compare_tree(dirpath, tree, comparisondir, bothfilesexisttable):
    # Find files that exists in tree but are missing from the same
    # relative path in comparisondir.
    # Files that exist in both paths get appended to bothfilesexisttable.
    missing = []
    for file in tree:
        filepathsuffix = get_file_suffix(file, dirpath)
        comparefile = comparisondir + filepathsuffix
        if not os.path.exists(comparefile):
            missing.append(file)
            print("-- Missing %s" % (comparefile))
        else:
            if filepathsuffix not in bothfilesexisttable:
                bothfilesexisttable.append(filepathsuffix)

    return bothfilesexisttable, missing

def compare_directories(dirafiles, dirbfiles, dira, dirb):
    bothfilesexisttable = []
    missinga = []
    missingb = []

    # Find missing files from dira to dirb
    bothfilesexisttable, missinga = compare_tree(dira, dirafiles, dirb, bothfilesexisttable)

    # Find missing files from dirb to dira
    bothfilesexisttable, missingb = compare_tree(dirb, dirbfiles, dira, bothfilesexisttable)

    return bothfilesexisttable, missinga, missingb

def main():
    if len(sys.argv) < 3:
        print(
            "ddir - Compare two directories recursively.\n"
            "\n"
            "Reports files missing from either side and runs a side-by-side diff\n"
            "on any files that exist in both directories but differ in content.\n"
            "Hidden files and directories (names starting with '.') are skipped.\n"
            "\n"
            "Usage: ddir <dir-a> <dir-b>\n"
            "\n"
            "Arguments:\n"
            "  dir-a   First directory to compare\n"
            "  dir-b   Second directory to compare\n"
            "\n"
            "Output:\n"
            "  -- Missing <path>   File exists in one directory but not the other\n"
            "  ** <a> and <b> differ   Side-by-side diff of files with differing content\n"
            "  Summary statistics at the end (file counts, missing, differing)\n"
        )
        sys.exit(1)

    a = sys.argv[1]
    b = sys.argv[2]

    dira = a.strip()
    dirb = b.strip()

    if not os.path.exists(dira):
        print("Directory a %s does not exist" % (dira))
        sys.exit(1)
    if not os.path.exists(dirb):
        print("Directory b %s does not exist" % (dirb))
        sys.exit(1)

    if os.name == 'nt':
        pathsep = "\\"
        # Assumes cygwin
        diffcmd = [r"C:\cygwin64\bin\diff", "--side-by-side", "--width=120", "--color=always"]
    else:
        # Assumes unix
        pathsep = "/"
        diffcmd = ["diff", "--side-by-side", "--width=120", "--color=always"]

    # Get list of dira files
    dirafiles = files(dira, pathsep)
    # Get list of dirb files
    dirbfiles = files(dirb, pathsep)
    # Build a table of files that are missing
    bothfilesexisttable, missinga, missingb = compare_directories(dirafiles, dirbfiles, dira, dirb)

    # Run diff against those files that are different
    diffcount = 0
    if len(bothfilesexisttable) > 0:
        for file in bothfilesexisttable:
            afile = dira + file
            bfile = dirb + file
            if compare(afile, bfile, diffcmd):
                diffcount += 1

    # Print statistics
    print("\n%s files in %s" % (len(dirafiles), dira))
    print("%s files in %s" % (len(dirbfiles), dirb))
    print("%s files missing from %s" % (len(missinga), dirb))
    print("%s files missing from %s" % (len(missingb), dira))
    print("%s files were different" % (diffcount))

if __name__ == '__main__':
    main()
