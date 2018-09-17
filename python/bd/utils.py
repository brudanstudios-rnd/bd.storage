import os
import shutil
import fnmatch
import hashlib
import marshal
import compileall

from .logger import get_logger

LOGGER = get_logger(__name__)


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


def compile(root_dir, cmpl_ignored=[]):

    # minify, compile and delete .py files
    for current_dir, _, filenames in os.walk(root_dir):

        for filename in filenames:

            if not filename.endswith(".py"):
                continue

            is_ignored = False
            if cmpl_ignored:
                is_ignored = any(map(lambda x: fnmatch.fnmatch(filename, x), cmpl_ignored))

            if is_ignored:
                continue

            fullname = os.path.join(current_dir, filename)

            minify(fullname)

            compileall.compile_file(fullname, force=True)
            os.remove(fullname)


def get_directory_hash(root_dir):

    sha256_hash = hashlib.sha256()

    if not os.path.isdir(root_dir):
        LOGGER.error("Directory '{}' doesn't"
                     " exist".format(root_dir))
        return

    paths = [os.path.join(dp, f) for dp, dn, fn in os.walk(root_dir) for f in fn if f != ".sha256"]

    for path in sorted(paths, key=lambda k: k.replace("_", "}")):

        try:
            f = open(path, "rb", buffering=4096)
        except:
            LOGGER.error("Unable to open the file:"
                         " '{}'".format(path))
            f.close()
            return

        while 1:

            buf = f.read()
            if not buf:
                break

            sha256_hash.update(hashlib.sha256(buf).hexdigest())

        f.close()

    return sha256_hash.hexdigest()


def get_toolset_metadata(root_dir):

    import yaml

    # find .toolset configuration file with all
    # toolset's parameters
    toolset_cfg_path = os.path.join(root_dir, "config.yml")
    if not os.path.isfile(toolset_cfg_path):
        return

    with open(toolset_cfg_path, "r") as f:
        return yaml.load(f)


def execute_file(filepath, globals=None, locals=None):
    if filepath.endswith(".pyc"):
        with open(filepath, "rb") as f:
            f.seek(8)
            code = marshal.load(f)
            exec (code, globals, locals)
    elif filepath.endswith(".py"):
        execfile(filepath, globals, locals)


def cleanup(directory, name_patterns=None):
    """Remove all files and folders which names match
    any of the provided patterns. If there is no 'name_patterns'
    provided, remove the whole directory and all the files inside.

    Args:
        directory(str): directory to cleanup.

    Kwargs:
        name_patterns(list-of-str): any directory or the file with the name
            matching one of these patterns will be removed.

    """

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


def resolve(path):
    if not path:
        return path

    return path.replace('\\', '/').replace('/', os.path.sep)