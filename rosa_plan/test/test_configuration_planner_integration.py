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
from lifecycle_msgs.srv import GetState
from rclpy.node import Node
from ros_typedb_msgs.srv import Query
from std_msgs.msg import String


test_node = 'test_configuration_planner_integration'
rosa_kb_name = 'rosa_kb_integration'
configuration_planner_name = 'configuration_planner_integration'


@launch_pytest.fixture
def generate_test_description():
    path_to_test = Path(__file__).parents[1]

    configuration_planner_node = launch_ros.actions.Node(
        executable=sys.executable,
        arguments=[
            str(path_to_test / 'rosa_plan' /
                'configuration_planner_node.py')],
        additional_env={'PYTHONUNBUFFERED': '1'},
        name=configuration_planner_name,
        output='screen',
    )
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
        configuration_planner_node,
        rosa_kb_node,
    ])


@pytest.mark.launch(fixture=generate_test_description)
def test_lc_states():
    rclpy.init()
    try:
        node = MakeTestNode(test_node)
        node.start_node()

        configure_res = node.change_lc_node_state(
            configuration_planner_name, 1)
        get_inactive_state_res = node.get_lc_node_state(
            configuration_planner_name)

        activate_res = node.change_lc_node_state(configuration_planner_name, 3)
        get_active_state_res = node.get_lc_node_state(
            configuration_planner_name)

        assert configure_res.success is True and \
            get_inactive_state_res.current_state.id == 2 and \
            activate_res.success is True and \
            get_active_state_res.current_state.id == 3
    finally:
        rclpy.shutdown()


@pytest.mark.skip(
    reason='Bugs with publisher')
@pytest.mark.launch(fixture=generate_test_description)
def test_event_cb():
    rclpy.init()
    try:
        node = MakeTestNode(test_node)
        node.start_node()
        node.activate_lc_node(configuration_planner_name)
        node.activate_lc_node(rosa_kb_name)

        event_pub = node.create_publisher(
            String, '/rosa_kb/events', 10)

        event_msg = String()
        event_msg.data = 'insert'
        event_pub.publish(event_msg)

        node.query_srv = node.create_client(
            Query, rosa_kb_name + '/query')

        query_req = Query.Request()
        query_req.query_type = Query.Request.GET
        query_req.query = '''
            match $rp isa reconfiguration-plan, has start-time $time;
            get $time;
            '''
        result = node.call_service(node.query_srv, query_req)
        assert len(result.results) > 0
    finally:
        rclpy.shutdown()


class MakeTestNode(Node):

    def __init__(self, name='test_node'):
        super().__init__(name)

    def start_node(self):
        self.ros_spin_thread = Thread(
            target=lambda node: rclpy.spin(node),
            args=(self,))
        self.ros_spin_thread.start()

    def change_lc_node_state(self, node_name, transition_id):
        srv = self.create_client(
            ChangeState, node_name + '/change_state')
        change_state_req = ChangeState.Request()
        change_state_req.transition.id = transition_id
        return self.call_service(srv, change_state_req)

    def get_lc_node_state(self, node_name):
        get_state_srv = self.create_client(
            GetState, node_name + '/get_state')
        get_state_req = GetState.Request()
        return self.call_service(get_state_srv, get_state_req)

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
        self.change_lc_node_state(node_name, 1)
        self.change_lc_node_state(node_name, 3)
