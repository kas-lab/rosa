import os
from glob import glob
from setuptools import setup

package_name = 'rosa_kb'


def package_files(pattern):
    return [path for path in glob(pattern) if os.path.isfile(path)]


setup(
    name=package_name,
    version='0.0.0',
    packages=[package_name],
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        (os.path.join('share', package_name, 'config'),
            package_files('config/*')),
        (os.path.join('share', package_name, 'launch'),
            package_files('launch/*'))
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='Gustavo Rezende',
    maintainer_email='g.rezendesilva@tudelft.nl',
    description='ROSA Knowledge Base',
    license='Apache-2.0',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'rosa_kb = rosa_kb.rosa_kb_node:main'
        ],
    },
)
