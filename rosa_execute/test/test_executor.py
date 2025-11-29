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
import os
import signal
import sys
import rclpy
import subprocess
from threading import Thread
from pathlib import Path

import launch
import launch_pytest
import launch_ros

import pytest
from ros_pytest.fixture import tester_node

from rosa_execute.configuration_executor import ConfigurationExecutor

from rosa_msgs.msg import Component
from rosa_msgs.msg import ComponentConfiguration
from rosa_msgs.msg import ReconfigurationPlan
from rosa_msgs.srv import ComponentQuery
from rcl_interfaces.msg import Parameter
from rcl_interfaces.msg import ParameterValue
from rcl_interfaces.srv import GetParameters

configuration_executor_node_name = 'executor_tested'
rosa_kb_name = 'rosa_kb'


@launch_pytest.fixture
def generate_test_description():
    path_execute_test_data = Path(__file__).parents[0] / 'test_data'
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
            'schema_path': [
                str(path_config / 'schema.tql'),
                str(path_config / 'ros_schema.tql')
            ],
            'data_path': [
                str(path_test_data / 'test_data.tql'),
                str(path_test_data / 'ros_test_data.tql'),
                str(path_execute_test_data / 'test_data.tql')
            ],
            'database_name': 'test_' + configuration_executor_node_name,
            'force_database': True,
            'force_data': True,
        }]
    )
    return launch.LaunchDescription([
        rosa_kb_node,
    ])


def spin_srv(executor):
    try:
        executor.spin()
    except rclpy.executors.ExternalShutdownException:
        pass


@pytest.mark.usefixtures(fixture=tester_node)
@pytest.fixture(scope='module')
def configuration_executor_node(tester_node):
    configuration_executor_node = ConfigurationExecutor(
        configuration_executor_node_name)

    executor = rclpy.executors.MultiThreadedExecutor()
    executor.add_node(configuration_executor_node)
    new_thread = Thread(target=spin_srv, args=(executor, ), daemon=True)
    new_thread.start()

    tester_node.activate_lc_node(configuration_executor_node_name)
    yield configuration_executor_node
    configuration_executor_node.destroy_node()
    executor.shutdown()
    new_thread.join()


def test_start_ros_node(configuration_executor_node):
    try:
        node_name = 'executor_mock_start_ros_node'
        node_dict = {
            'package': 'rosa_execute',
            'executable': 'configuration_executor',
            'name': node_name,
            'parameters': [{'test': 'test'}],
        }
        process = configuration_executor_node.start_ros_node(node_dict)
        assert process is not False and process.poll() is None and \
            node_name in configuration_executor_node.get_node_names()
    finally:
        if type(process) is subprocess.Popen:
            pgid = os.getpgid(process.pid)
            os.killpg(pgid, signal.SIGTERM)
            os.waitid(os.P_PGID, pgid, os.WEXITED)


def test_start_ros_launchfile(configuration_executor_node):
    try:
        node_dict = {
            'package': 'rosa_execute',
            'launch_file': 'rosa_execute.launch.py',
            'parameters': [{'test': 'test'}],
        }
        process = configuration_executor_node.start_ros_launchfile(node_dict)
        assert process is not False and process.poll() is None and \
            'configuration_executor' in \
            configuration_executor_node.get_node_names()
    finally:
        if type(process) is subprocess.Popen:
            pgid = os.getpgid(process.pid)
            os.killpg(pgid, signal.SIGTERM)
            os.waitid(os.P_PGID, pgid, os.WEXITED)


@pytest.mark.launch(fixture=generate_test_description)
@pytest.mark.usefixtures(fixture=tester_node)
def test_activate_components(configuration_executor_node, tester_node):
    try:
        tester_node.activate_lc_node(rosa_kb_name)

        component = Component()
        component.name = 'executor_mock'
        component.package = 'rosa_execute'
        component.executable = 'configuration_executor'
        component.node_type = 'ROSNode'

        param = Parameter()
        param.name = 'teste'
        param.value.type = 4
        param.value.string_value = 'teste'

        component.parameters.append(param)

        component2 = Component()
        component2.name = 'executor_mock_2'
        component2.package = 'rosa_execute'
        component2.executable = 'configuration_executor'
        component2.node_type = 'LifeCycleNode'

        param2 = Parameter()
        param2.name = 'teste'
        param2.value.type = 4
        param2.value.string_value = 'teste'

        component2.parameters.append(param2)

        result = configuration_executor_node.activate_components(
            [component, component2])
        component2_state = configuration_executor_node.get_lc_node_state(
            component2.name)

        srv_get = configuration_executor_node.create_client(
            ComponentQuery, '/rosa_kb/component/active/get')
        component_query = ComponentQuery.Request()
        component_query.component = component
        result_get = configuration_executor_node.call_service(
            srv_get, component_query)

        component_query_2 = ComponentQuery.Request()
        component_query_2.component = component2
        result_get_2 = configuration_executor_node.call_service(
            srv_get, component_query_2)

        assert result is True \
            and component2_state.current_state.id == 3 \
            and result_get.component.is_active is True \
            and result_get_2.component.is_active is True
    finally:
        configuration_executor_node.kill_all_components()


@pytest.mark.launch(fixture=generate_test_description)
@pytest.mark.usefixtures(fixture=tester_node)
def test_set_component_active(configuration_executor_node, tester_node):
    tester_node.activate_lc_node(rosa_kb_name)

    component = Component()
    component.name = 'executor_mock'
    component.package = 'rosa_execute'
    component.executable = 'configuration_executor'
    component.node_type = 'ROSNode'

    param = Parameter()
    param.name = 'teste'
    param.value.type = 4
    param.value.string_value = 'teste'

    component.parameters.append(param)
    result = configuration_executor_node.set_component_active(component, True)

    srv_get = configuration_executor_node.create_client(
        ComponentQuery, '/rosa_kb/component/active/get')
    component_query = ComponentQuery.Request()
    component_query.component = component
    result_get = configuration_executor_node.call_service(
        srv_get, component_query)

    assert result.success is True and result_get.component.is_active is True


@pytest.mark.launch(fixture=generate_test_description)
@pytest.mark.usefixtures(fixture=tester_node)
def test_deactivate_components(configuration_executor_node, tester_node):
    try:
        tester_node.activate_lc_node(rosa_kb_name)

        component = Component()
        component.name = 'executor_mock'
        component.package = 'rosa_execute'
        component.executable = 'configuration_executor'
        component.node_type = 'ROSNode'

        param = Parameter()
        param.name = 'teste'
        param.value.type = 4
        param.value.string_value = 'teste'

        component.parameters.append(param)

        component2 = Component()
        component2.name = 'executor_mock_2'
        component2.package = 'rosa_execute'
        component2.executable = 'configuration_executor'
        component2.node_type = 'LifeCycleNode'

        param2 = Parameter()
        param2.name = 'teste'
        param2.value.type = 4
        param2.value.string_value = 'teste'

        component2.parameters.append(param2)

        result_activate = configuration_executor_node.activate_components(
            [component, component2])
        result_deactivate = configuration_executor_node.deactivate_components(
            [component, component2])

        component2_state = configuration_executor_node.get_lc_node_state(
            component2.name)

        srv_get = configuration_executor_node.create_client(
            ComponentQuery, '/rosa_kb/component/active/get')

        component_query = ComponentQuery.Request()
        component_query.component = component
        result_get = configuration_executor_node.call_service(
            srv_get, component_query)

        component_query_2 = ComponentQuery.Request()
        component_query_2.component = component2
        result_get_2 = configuration_executor_node.call_service(
            srv_get, component_query_2)

        assert result_activate is True and result_deactivate is True \
            and component2_state.current_state.id == 2 \
            and result_get.component.is_active is False \
            and result_get_2.component.is_active is False
            # and 'executor_mock' not in \
            #     configuration_executor_node.component_pids_dict
    finally:
        configuration_executor_node.kill_all_components()


@pytest.mark.launch(fixture=generate_test_description)
@pytest.mark.usefixtures(fixture=tester_node)
def test_perform_parameter_adaptation(
   configuration_executor_node, tester_node):
    try:
        tester_node.activate_lc_node(rosa_kb_name)

        component = Component()
        component.name = 'ros_typedb_test'
        component.package = 'ros_typedb'
        component.executable = 'ros_typedb'
        component.node_type = 'LifeCycleNode'

        component2 = Component()
        component2.name = 'ros_typedb_test_2'
        component2.package = 'ros_typedb'
        component2.executable = 'ros_typedb'
        component2.node_type = 'LifeCycleNode'

        result = configuration_executor_node.activate_components(
            [component, component2])

        config = ComponentConfiguration(name='ros_typedb_config')
        config_2 = ComponentConfiguration(name='ros_typedb_config_2')
        result = configuration_executor_node.perform_parameter_adaptation(
            [config, config_2])

        get_param_srv = configuration_executor_node.create_client(
            GetParameters, '/ros_typedb_test/get_parameters')
        get_param_srv_2 = configuration_executor_node.create_client(
            GetParameters, '/ros_typedb_test_2/get_parameters')

        param_req = GetParameters.Request(
            names=[
                'database_name', 'force_database', 'force_data', 'data_path'])
        params = configuration_executor_node.call_service(
            get_param_srv, param_req)
        params_2 = configuration_executor_node.call_service(
            get_param_srv_2, param_req)

        expected_params = [
            ParameterValue(type=4, string_value='ros_typedb_executor'),
            ParameterValue(type=1, bool_value=True),
            ParameterValue(type=1, bool_value=False),
            ParameterValue(
                type=9, string_array_value=["test_data/test_data.tql"]),
        ]
        expected_params_2 = [
            ParameterValue(type=4, string_value='ros_typedb_executor_2'),
            ParameterValue(type=1, bool_value=False),
            ParameterValue(type=1, bool_value=True),
            ParameterValue(
                type=9, string_array_value=["test_data/test_data.tql"]),
        ]

        assert result is True and \
            all(p in params.values for p in expected_params) and \
            all(p in params_2.values for p in expected_params_2)
    finally:
        configuration_executor_node.kill_all_components()


@pytest.mark.launch(fixture=generate_test_description)
@pytest.mark.usefixtures(fixture=tester_node)
def test_perform_reconfiguration_plan(
   configuration_executor_node, tester_node):
    try:
        tester_node.activate_lc_node(rosa_kb_name)

        component = Component()
        component.name = 'executor_mock'
        component.package = 'rosa_execute'
        component.executable = 'configuration_executor'
        component.node_type = 'LifeCycleNode'

        component2 = Component()
        component2.name = 'executor_mock_2'
        component2.package = 'rosa_execute'
        component2.executable = 'configuration_executor'
        component2.node_type = 'LifeCycleNode'

        configuration_executor_node.activate_components(
            [component, component2])

        component3 = Component()
        component3.name = 'ros_typedb_test'
        component3.package = 'ros_typedb'
        component3.executable = 'ros_typedb'
        component3.node_type = 'LifeCycleNode'

        component4 = Component()
        component4.name = 'ros_typedb_test_2'
        component4.package = 'ros_typedb'
        component4.executable = 'ros_typedb'
        component4.node_type = 'LifeCycleNode'

        config = ComponentConfiguration(name='ros_typedb_config')
        config_2 = ComponentConfiguration(name='ros_typedb_config_2')

        reconfig_plan = ReconfigurationPlan()
        reconfig_plan.components_deactivate = [component, component2]
        reconfig_plan.components_activate = [component3, component4]
        reconfig_plan.component_configurations = [config, config_2]

        result = configuration_executor_node.perform_reconfiguration_plan(
            reconfig_plan)

        assert result is True
    finally:
        configuration_executor_node.kill_all_components()


@pytest.mark.launch(fixture=generate_test_description)
@pytest.mark.usefixtures(fixture=tester_node)
def test_fake_perform_reconfiguration_plan(
   configuration_executor_node, tester_node):
    try:
        tester_node.activate_lc_node(rosa_kb_name)

        component = Component()
        component.name = 'fake'
        component.package = 'rosa_execute'
        component.executable = 'configuration_executor'
        component.node_type = 'LifeCycleNode'

        config = ComponentConfiguration(name='fake_config')

        reconfig_plan = ReconfigurationPlan()
        reconfig_plan.components_deactivate = [component]
        reconfig_plan.components_activate = [component]
        reconfig_plan.component_configurations = [config]

        configuration_executor_node.set_parameters([rclpy.parameter.Parameter(
            'fake_execution', rclpy.Parameter.Type.BOOL, True)])
        result = configuration_executor_node.perform_reconfiguration_plan(
            reconfig_plan)

        assert result is True

    finally:
        configuration_executor_node.kill_all_components()

@pytest.mark.launch(fixture=generate_test_description)
@pytest.mark.usefixtures(fixture=tester_node)
def test_execute(configuration_executor_node, tester_node):
    try:
        tester_node.activate_lc_node(rosa_kb_name)

        component = Component()
        component.name = 'executor_mock_2'
        component.package = 'rosa_execute'
        component.executable = 'configuration_executor'
        component.node_type = 'LifeCycleNode'

        configuration_executor_node.activate_components([component])

        configuration_executor_node.execute()

        component_state = configuration_executor_node.get_lc_node_state(
            component.name)
        active_nodes = configuration_executor_node.get_node_names()

        get_param_srv = configuration_executor_node.create_client(
            GetParameters, '/ros_typedb_test_execute/get_parameters')
        param_req = GetParameters.Request(
            names=[
                'database_name', 'force_database', 'force_data', 'data_path'])
        params = configuration_executor_node.call_service(
            get_param_srv, param_req)
        expected_params = [
            ParameterValue(type=4, string_value='ros_typedb_executor'),
            ParameterValue(type=1, bool_value=True),
            ParameterValue(type=1, bool_value=False),
            ParameterValue(
                type=9, string_array_value=['test_data/test_data.tql']),
        ]
        assert component_state.current_state.id == 2 and \
            'executor_mock' in active_nodes and \
            'ros_typedb_test_execute' in active_nodes and \
            all(p in params.values for p in expected_params)
    finally:
        configuration_executor_node.kill_all_components()
