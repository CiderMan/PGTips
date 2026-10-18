from pathlib import Path, PurePath


def find_all_files(files, include=None, exclude=None):
    """
    Return a list of the files given, where each of the files may be a file or a directory to
    search (recursively). Files are filtered by extension (case-insensitively) to those in
    include, if given, and not in exclude, if given
    """
    if include is not None:
        include = [e.lower() for e in include]
    if exclude is not None:
        exclude = [e.lower() for e in exclude]

    def wanted(f):
        ext = f.suffix.lower()
        return (include is None or ext in include) and (exclude is None or ext not in exclude)

    fList = []
    if isinstance(files, (str, PurePath)):
        files = [files]

    for path in map(Path, files):
        if path.is_file():
            if wanted(path):
                fList.append(path)
        else:
            for dirpath, _dirnames, filenames in path.walk():
                fList += [dirpath / f for f in filenames if wanted(dirpath / f)]

    return fList
