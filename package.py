name = "bd.storage"

version = "0.2.10"

build_command = "python -m rezutil build {root} --ignore .env"
private_build_requires = ["rezutil"]


requires = ["bd.hooks", "PyYAML-5.4.1+", "schema-0.7.1+", "six"]


variants = [["python-3"], ["python-2", "futures"]]

hashed_variants = True


def commands():
    env.PYTHONPATH.append("{root}/python")
