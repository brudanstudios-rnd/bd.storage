name = 'bd.storage'

version = '0.1.8'

build_command = 'python -m rezutil build {root} --ignore .env'
private_build_requires = ['rezutil']


@late()
def requires():

    if not in_context():
        return []

    requirements = [
        'bd.api',
        'bd.hooks',
        'pyyaml-5.4.1+',
        'schema-0.7.1',
        'six'
    ]

    if 'python' not in request or request.python.startswith('python-2'):
        requirements.append('futures')

    return requirements


def commands():
    env.PYTHONPATH.append("{root}/python")
