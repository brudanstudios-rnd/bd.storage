import os
import logging
import shutil
import fnmatch
import hashlib
import marshal

LOGGER = logging.getLogger("bd.utils")


def minify(input_file):

    from pyminifier import minification

    with open(input_file, "r") as in_file:
        source = in_file.read()

    with open(input_file, "w") as out_file:
        output = minification.remove_comments_and_docstrings(source)
        output = minification.dedent(output)
        output = minification.remove_blank_lines(output)
        output = minification.reduce_operators(output)
        out_file.write(output)


def get_directory_md5(directory):

    md5_hash = hashlib.md5()

    if not directory.is_dir():
        LOGGER.error("Directory '{}' doesn't"
                     " exist".format(directory))
        return

    for path in sorted(directory.rglob("*"), key=lambda w: w.as_posix().replace("_", "}")):

        if path.name == ".md5":
            continue

        if path.is_dir():
            continue

        try:
            f = path.open("rb", buffering=4096)
        except:
            LOGGER.error("Unable to open the file:"
                         " '{}'".format(path))
            f.close()
            return

        while 1:

            buf = f.read()
            if not buf:
                break

            md5_hash.update(hashlib.md5(buf).hexdigest())

        f.close()

    return md5_hash.hexdigest()


def get_toolset_metadata(root_dir):

    import yaml

    # find .toolset configuration file with all
    # toolset's parameters
    toolset_cfg_path = root_dir / "config.yml"
    if not toolset_cfg_path.is_file():
        return

    return yaml.load(toolset_cfg_path.open())


def execute_file(filename, globals=None, locals=None):

    if filename.suffix == ".pyc":
        with open(str(filename), "rb") as f:
            f.seek(8)
            code = marshal.load(f)
            exec (code, globals, locals)
    elif filename.suffix == ".py":
        execfile(str(filename), globals, locals)


def cleanup(directory, name_patterns=None):
    """Remove all files and folders which names match
    any of the provided patterns. If there is no 'name_patterns'
    provided, remove the whole directory and all the files inside.

    Args:
        directory(pathlib2.Path): directory to cleanup.

    Kwargs:
        name_patterns(list-of-str): any directory or the file with the name
            matching one of these patterns will be removed.

    """

    directory = str(directory.resolve())

    def onerror(func, path, exc_info):
        """
        Error handler for ``shutil.rmtree``.

        If the error is due to an access error (read only file)
        it attempts to add write permission and then retries.

        If the error is for another reason it re-raises the error.

        Usage : ``shutil.rmtree(path, onerror=onerror)``
        """
        import stat
        if not os.access(path, os.W_OK):
            # Is the error an access error ?
            os.chmod(path, stat.S_IWUSR | stat.S_IREAD)
            func(path)
        else:
            raise Exception()

    if not name_patterns:
        try:
            shutil.rmtree(directory, onerror=onerror)
        except Exception, e:
            LOGGER.error("Unable to remove: {}\n{}".format(directory, str(e)))
            return False

        return True

    for root, dirnames, filenames in os.walk(directory):

        # ignore .git directory CONTENTS
        if os.path.basename(root) == ".git":
            del dirnames[:]
            continue

        # check whether any directory or filename
        # matches any name pattern
        for name in name_patterns:

            for dirname in fnmatch.filter(dirnames, name):
                path = os.path.join(root, dirname)
                try:
                    shutil.rmtree(path, onerror=onerror)
                except Exception, e:
                    LOGGER.error("Unable to remove '{}'\n{}".format(path, str(e)))
                    return False

                del dirnames[dirnames.index(dirname)]

            for filename in fnmatch.filter(filenames, name):
                path = os.path.join(root, filename)
                try:
                    os.remove(path)
                except Exception, e:
                    LOGGER.error("Unable to remove '{}'\n{}".format(path, e))
                    return False

    return True