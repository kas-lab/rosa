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
import subprocess
import shlex

from rclpy.lifecycle import Node
from rclpy.lifecycle import State
from rclpy.lifecycle import TransitionCallbackReturn

from lifecycle_msgs.srv import ChangeState
from lifecycle_msgs.srv import GetState

from std_msgs.msg import String
from metacontrol_kb_msgs.srv import GetReconfigurationPlan


def get_parameter_value(param_value):
    _param_type = {
        1: 'bool_value',
        2: 'integer_value',
        3: 'double_value',
        4: 'string_value',
        5: 'byte_array_value',
        6: 'bool_array_value',
        7: 'integer_array_value',
        8: 'double_array_value',
        9: 'string_array_value',
    }
    value = None
    if param_value.type != 0:
        value = getattr(param_value, _param_type[param_value.type])
    return value


class Executor(Node):
    """Executor."""

    def __init__(self, node_name, **kwargs):
        super().__init__(node_name, **kwargs)

    def on_configure(self, state: State) -> TransitionCallbackReturn:
        self.get_logger().info(self.get_name() + ': on_configure() is called.')

        self.event_sub = self.create_subscription(
            String,
            '/metacontrol_kb/events',
            self.event_cb,
            10)

        self.get_reconfig_plan_srv = self.create_client(
            GetReconfigurationPlan, '/metacontrol_kb/reconfiguration_plan/get')

        self.get_logger().info(self.get_name() + ': on_configure() completed.')
        return TransitionCallbackReturn.SUCCESS

    def on_activate(self, state: State) -> TransitionCallbackReturn:
        self.get_logger().info(self.get_name() + ': on_activate() is called.')
        return super().on_activate(state)

    def on_cleanup(self, state: State) -> TransitionCallbackReturn:
        self.destroy_subscription(self.event_sub)

        self.get_logger().info('on_cleanup() is called.')
        return TransitionCallbackReturn.SUCCESS

    def event_cb(self, msg):
        if msg.data == 'insert':
            reconfig_plan = self.call_service(
                self.get_reconfig_plan_srv, GetReconfigurationPlan.Request())
            result_deactivation = self.deactivate_components(
                reconfig_plan.components_deactivate)
            result_activation = self.activate_components(
                reconfig_plan.components_activate)
            result_update = self.update_component_params(
                reconfig_plan.component_configurations)
            result = result_deactivation and result_activation \
                and result_update
            # TODO: update reconfig plan result

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

    def deactivate_components(self, components):
        pass

    def activate_components(self, components):
        return_value = True
        for component in components:
            if component.name not in self.get_node_names():
                parameters = []
                for parameter in component.parameters:
                    _param_value = get_parameter_value(parameter.value)
                    if _param_value is not None:
                        parameters.append({parameter.name: _param_value})
                node_dict = {
                    'package': component.package,
                    'executable': component.executable,
                    'name': component.name,
                    'parameters': parameters,
                }
                result_start = self.start_ros_node(node_dict)
                if result_start is False:
                    return_value = False
            if component.node_type == 'lifecycle' and \
               component.name in self.get_node_names():
                _state = self.get_lc_node_state(component.name)
                if _state.current_state.id == 1:
                    self.change_lc_node_state(component.name, 1)
                _state = self.get_lc_node_state(component.name)
                if _state._state.current_state.id == 2:
                    self.change_lc_node_state(component.name, 3)
                _state = self.get_lc_node_state(component.name)
                if _state._state.current_state.id != 3:
                    return_value = False
        # TODO: set attribute in the component to indicate if it is running
        # and in which state it is (in case of LC nodes)
        return return_value

    def update_component_params(self, configurations):
        pass

    def start_ros_node(self, node_dict):
        cmd = 'ros2 run '
        if 'package' in node_dict and 'executable' in node_dict:
            cmd += node_dict['package'] + ' '
            cmd += node_dict['executable']
            if 'name' in node_dict or 'parameters' in node_dict:
                cmd += ' --ros-args '
                if 'name' in node_dict:
                    cmd += ' -r __node:=' + node_dict['name']
                if 'parameters' in node_dict:
                    for param in node_dict['parameters']:
                        for key, value in param.items():
                            cmd += ' -r ' + str(key) + ':=' + str(value)
            return self.run_process(cmd, 'start_ros_node', node_dict)
        else:
            return False

    def start_ros_launchfile(self, launch_dict, **kwargs):
        cmd = 'ros2 launch '
        if 'package' in launch_dict and 'launch_file' in launch_dict:
            cmd += launch_dict['package'] + ' '
            cmd += launch_dict['launch_file']
            if 'parameters' in launch_dict:
                if 'parameters' in launch_dict:
                    for param in launch_dict['parameters']:
                        for key, value in param.items():
                            cmd += ' ' + str(key) + ':=' + str(value)
            return self.run_process(cmd, 'start_ros_launchfile', launch_dict)
        else:
            return False

    def run_process(self, cmd, _func, _dict):
        try:
            process = subprocess.Popen(
                shlex.split(cmd),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                preexec_fn=os.setsid,
            )
            try:
                outs, errs = process.communicate(timeout=.5)
                self.get_logger().error(f'''
                    {_func} failed!
                    input _dict: {_dict}
                    resulting erros: {errs}''')
                return False
            except subprocess.TimeoutExpired:
                return process
        except Exception as e:
            self.get_logger().error(f'''
                {_func} failed!
                input _dict: {_dict}
                raised exception: {e}''')
            return False
