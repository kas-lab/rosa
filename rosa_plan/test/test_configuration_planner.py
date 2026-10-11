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
import rclpy

from threading import Thread

import sys

from lifecycle_msgs.srv import ChangeState
from rclpy.node import Node

from std_msgs.msg import String
from rosa_plan.configuration_planner import ConfigurationPlanner
from ros_typedb_msgs.srv import Query

from rosa_msgs.msg import ComponentConfiguration
from rosa_msgs.msg import FunctionDesign

test_node = 'test_configuration_planner'
rosa_kb_name = 'rosa_kb'
configuration_planner_name = 'configuration_planner'


@launch_pytest.fixture
def generate_test_description():
    path_kb = Path(__file__).parents[2] / 'rosa_kb'
    path_config = path_kb / 'config'
    path_test_data = path_kb / 'test' / 'test_data'

    rosa_kb_node = launch_ros.actions.Node(
        executable=sys.executable,
        arguments=[
            str(path_kb / 'rosa_kb' / 'rosa_kb_node.py')],
        additional_env={'PYTHONUNBUFFERED': '1'},
        name=rosa_kb_name,
        output='screen',
        parameters=[{
            'schema_path': [str(path_config / 'schema.tql')],
            'data_path': [str(path_test_data / 'test_data.tql')],
            'database_name': 'test_' + configuration_planner_name
        }]
    )
    return launch.LaunchDescription([
        rosa_kb_node,
    ])


def create_configuration_planner():
    configuration_planner = ConfigurationPlanner(configuration_planner_name)
    executor = rclpy.executors.MultiThreadedExecutor()
    executor.add_node(configuration_planner)
    Thread(target=executor.spin).start()
    return configuration_planner


@pytest.mark.launch(fixture=generate_test_description)
def test_plan_function_adaptation():
    rclpy.init()
    try:
        configuration_planner = create_configuration_planner()

        node = MakeTestNode(test_node)
        node.start_node()

        node.activate_lc_node(configuration_planner_name)
        node.activate_lc_node(rosa_kb_name)

        result = configuration_planner.plan_function_adaptation()
        selected_fd = FunctionDesign()
        selected_fd.function.name = 'f_always_improve'
        selected_fd.name = 'f_improve_fd1'
        assert selected_fd in result
    finally:
        configuration_planner.destroy_node()
        rclpy.shutdown()


@pytest.mark.launch(fixture=generate_test_description)
def test_plan_component_adaptation():
    rclpy.init()
    try:
        configuration_planner = create_configuration_planner()

        node = MakeTestNode(test_node)
        node.start_node()

        node.activate_lc_node(configuration_planner_name)
        node.activate_lc_node(rosa_kb_name)

        result = configuration_planner.plan_component_adaptation()
        selected_cc = ComponentConfiguration()
        selected_cc.component.name = 'c_always_improve'
        selected_cc.name = 'c_improve_fd1'
        assert selected_cc in result
    finally:
        configuration_planner.destroy_node()
        rclpy.shutdown()


@pytest.mark.launch(fixture=generate_test_description)
def test_plan_adaptation():
    rclpy.init()
    try:
        configuration_planner = create_configuration_planner()

        node = MakeTestNode(test_node)
        node.start_node()

        node.activate_lc_node(configuration_planner_name)
        node.activate_lc_node(rosa_kb_name)

        result = configuration_planner.plan_adaptation()

        selected_fd = FunctionDesign()
        selected_fd.function.name = 'f_always_improve'
        selected_fd.name = 'f_improve_fd1'

        selected_cc = ComponentConfiguration()
        selected_cc.component.name = 'c_always_improve'
        selected_cc.name = 'c_improve_fd1'

        assert selected_fd in result.selected_fds and \
            selected_cc in result.selected_component_configs
    finally:
        configuration_planner.destroy_node()
        rclpy.shutdown()


@pytest.mark.launch(fixture=generate_test_description)
def test_manual_event_cb():
    rclpy.init()
    try:
        configuration_planner = create_configuration_planner()

        node = MakeTestNode(test_node)
        node.start_node()

        node.activate_lc_node(configuration_planner_name)
        node.activate_lc_node(rosa_kb_name)

        event = String()
        event.data = 'insert_monitoring_data'
        result = configuration_planner.event_cb(event)

        node.query_srv = node.create_client(
            Query, rosa_kb_name + '/query')

        query_req = Query.Request()
        query_req.query_type = Query.Request.FETCH
        query_req.query = '''
            match $rp isa reconfiguration-plan, has start-time $time;
            fetch $time;
            '''
        result = node.call_service(node.query_srv, query_req)
        assert len(result.results) > 0
    finally:
        configuration_planner.destroy_node()
        rclpy.shutdown()


class MakeTestNode(Node):

    def __init__(self, name='test_node'):
        super().__init__(name)

    def start_node(self):
        self.ros_spin_thread = Thread(
            target=lambda node: rclpy.spin(node),
            args=(self,))
        self.ros_spin_thread.start()

    def change_lc_node_state(self, srv, transition_id):
        change_state_req = ChangeState.Request()
        change_state_req.transition.id = transition_id
        return self.call_service(srv, change_state_req)

    def call_service(self, cli, request):
        if cli.wait_for_service(timeout_sec=5.0) is False:
            self.get_logger().error(
                'service not available {}'.format(cli.srv_name))
            return None
        future = cli.call_async(request)
        if self.executor.spin_until_future_complete(
                future, timeout_sec=5.0) is False:
            self.get_logger().error(
                'Future not completed {}'.format(cli.srv_name))
            return None

        return future.result()

    def activate_lc_node(self, node_name):
        srv = self.create_client(
            ChangeState, node_name + '/change_state')
        self.change_lc_node_state(srv, 1)
        self.change_lc_node_state(srv, 3)
