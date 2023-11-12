# Copyright 2023 Gustavo Rezende Silva
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import launch
import launch_pytest
import launch_ros

from pathlib import Path

import pytest

import sys

from ros_pytest.fixture import tester_node
from metacontrol_execute.executor import Executor

test_node = 'test_executor'
metacontrol_kb_name = 'metacontrol_kb_executor'
tested_node = 'executor'


@launch_pytest.fixture
def generate_test_description():
    path_kb = Path(__file__).parents[2] / 'metacontrol_kb'
    path_config = path_kb / 'config'
    path_test_data = path_kb / 'test' / 'test_data'

    metacontrol_kb_node = launch_ros.actions.Node(
        executable=sys.executable,
        arguments=[
            str(path_kb / 'metacontrol_kb' / 'metacontrol_kb_node.py')],
        additional_env={'PYTHONUNBUFFERED': '1'},
        name=metacontrol_kb_name,
        output='screen',
        parameters=[{
            'schema_path': str(path_config / 'schema.tql'),
            'data_path': str(path_test_data / 'test_data.tql'),
            'database_name': 'test_' + tested_node
        }]
    )
    return launch.LaunchDescription([
        metacontrol_kb_node,
    ])


@pytest.fixture()
@pytest.mark.usefixtures(fixture=tester_node)
def executor_node(tester_node):
    node = Executor(tested_node)
    tester_node.start_node(node)
    tester_node.lc_configure_activate(tested_node)
    tester_node.lc_configure_activate(metacontrol_kb_name)
    yield node


@pytest.mark.launch(fixture=generate_test_description)
def test_start_ros_node(executor_node):
    assert True
