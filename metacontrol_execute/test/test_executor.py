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
import rclpy
import os
import signal

from metacontrol_execute.executor import Executor

tested_node = 'executor_tested'


def test_start_ros_node():
    rclpy.init()
    try:
        node_name = 'executor_mock'
        node_dict = {
            'package': 'metacontrol_execute',
            'executable': 'executor',
            'name': node_name,
            'parameters': [{'test': 'test'}],
        }
        executor_node = Executor(tested_node)
        process = executor_node.start_ros_node(node_dict)
        assert process is not False and process.poll() is None and \
            node_name in executor_node.get_node_names()
    finally:
        os.killpg(os.getpgid(process.pid), signal.SIGTERM)
        process.kill()
        process.wait()
        rclpy.shutdown()


def test_start_ros_launchfile():
    rclpy.init()
    try:
        node_dict = {
            'package': 'metacontrol_execute',
            'launch_file': 'executor.launch.py',
            'parameters': [{'test': 'test'}],
        }
        executor_node = Executor(tested_node)
        process = executor_node.start_ros_launchfile(node_dict)
        assert process is not False and process.poll() is None and \
            'executor' in executor_node.get_node_names()
    finally:
        os.killpg(os.getpgid(process.pid), signal.SIGTERM)
        process.kill()
        process.wait()
        rclpy.shutdown()
