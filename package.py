name = 'bd.storage'

version = '0.1.5'

build_command = 'python -m rezutil build {root} --ignore .env'
private_build_requires = ['rezutil']


@late()
def requires():
    return [
        'python',
        '~bd.api',
        'bd.hooks',
        'boto3-1.17.20+',
        'parse-1.19.0+',
        'PyYAML-5.4.1+',
        'schema',
        'six',
        'contextlib2'
    ]


def commands():
    env.PYTHONPATH.append("{root}/python")
