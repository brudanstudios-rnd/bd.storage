import os
import marshal
import cPickle
from distutils.version import LooseVersion

from .logger import get_logger

LOGGER = get_logger(__name__)


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


def resolve(path):
    if not path:
        return path

    return path.replace('\\', '/').replace('/', os.path.sep)


def get_context():
    """Get the latest context data from the environment.

    Returns:
        Context dictionary.

    """

    base64_config = os.getenv("BD_CONTEXT")

    # if this script is run from the desktop toolkit,
    # the core configuration is already up to date and
    # serialized into BD_CORE_CONFIG_DATA environment
    # variable
    #
    if base64_config:
        try:
            return cPickle.loads(base64_config.decode("base64", "strict"))
        except Exception:
            raise Exception("Unable to load context "
                            "data stored in 'BD_CONTEXT' variable")


def get_available_preset_infos():
    preset_root_dir = os.environ["BD_PRESETS_DIR"]

    preset_infos = []

    active_preset_info = get_active_preset_info()

    if active_preset_info:

        preset_infos.append(active_preset_info)

    else:
        for preset_name in os.listdir(preset_root_dir):

            preset_version = None
            preset_dir = os.path.join(preset_root_dir, preset_name)

            if not os.path.exists(os.path.join(preset_dir, ".git")):

                preset_versions = [version for version in os.listdir(preset_dir)]
                if not preset_versions:
                    continue

                preset_versions.sort(key=lambda x: LooseVersion(x.lstrip("v")))

                preset_version = preset_versions[-1]
                preset_dir = os.path.join(preset_dir, preset_version)

            preset_infos.append({
                "name": preset_name,
                "version": preset_version,
                "dirname": preset_dir
            })

    return preset_infos


def get_active_preset_info():

    context = get_context()
    if not context:
        return

    active_preset_ctx = context.get("active_preset")

    preset_name = active_preset_ctx["name"]
    preset_version = active_preset_ctx.get("version")
    preset_dir = os.path.join(os.environ["BD_PRESETS_DIR"], preset_name)

    if not os.path.exists(os.path.join(preset_dir, ".git")):

        preset_version = active_preset_ctx.get("version")
        if not preset_version:
            raise Exception("Active preset version is not defined in the context.")

        preset_dir = os.path.join(preset_dir, preset_version)
        if not os.path.exists(preset_dir):
            raise Exception("Active preset directory doesn't exist: {}".format(preset_dir))

    return {
        "name": preset_name,
        "version": preset_version,
        "dirname": preset_dir
    }