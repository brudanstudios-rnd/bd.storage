name = "bd.storage"

version = "0.2.11"

build_command = "python -m rezutil build {root} --ignore .env"
private_build_requires = ["rezutil"]


requires = ["bd.hooks", "PyYAML-5.4.1+", "schema-0.7.1+", "six"]


def commands():
    env.PYTHONPATH.append("{root}/python")
