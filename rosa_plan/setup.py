import os
from glob import glob
from setuptools import find_packages, setup

package_name = 'rosa_plan'


def package_files(pattern):
    return [path for path in glob(pattern) if os.path.isfile(path)]


setup(
    name=package_name,
    version='0.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        (os.path.join('share', package_name, 'launch'),
            package_files('launch/*'))
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='gus',
    maintainer_email='g.rezendesilva@tudelft.nl',
    description='ROSA configuration planner',
    license='Apache-2.0',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'configuration_planner_node = rosa_plan.configuration_planner_node:main'
        ],
    },
)
