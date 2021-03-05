name = 'bd.storage'

version = '0.1.5'

build_command = 'python -m rezutil build {root}'
private_build_requires = ['rezutil']


@late()
def requires():
    return ['python', '~bd.api', 'bd.hooks']


def commands():
    env.PYTHONPATH.append("{root}/lib")
