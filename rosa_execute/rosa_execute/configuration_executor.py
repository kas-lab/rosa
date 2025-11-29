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
import subprocess
import shlex

from rclpy.callback_groups import MutuallyExclusiveCallbackGroup
from rclpy.callback_groups import ReentrantCallbackGroup

from rclpy.lifecycle import Node
from rclpy.lifecycle import State
from rclpy.lifecycle import TransitionCallbackReturn

from lifecycle_msgs.srv import ChangeState
from lifecycle_msgs.srv import GetState

from std_msgs.msg import String
from rosa_msgs.srv import ComponentQuery
from rosa_msgs.srv import ComponentProcessQuery
from rosa_msgs.srv import ComponentProcessQueryArray
from rosa_msgs.srv import GetComponentParameters
from rosa_msgs.srv import ReconfigurationPlanQuery

from rcl_interfaces.srv import SetParametersAtomically


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
    if param_value.type in _param_type:
        value = getattr(param_value, _param_type[param_value.type])
    return value


def check_lc_active(func):
    def inner(*args, **kwargs):
        if args[0].active is True:
            return func(*args, **kwargs)
    return inner


class ConfigurationExecutor(Node):
    """ConfigurationExecutor."""

    def __init__(self, node_name, **kwargs):
        super().__init__(node_name, **kwargs)
        self.active = False
        self.cb_group = MutuallyExclusiveCallbackGroup()

        self.declare_parameter('fake_execution', False)

    def on_configure(self, state: State) -> TransitionCallbackReturn:
        self.get_logger().info(self.get_name() + ': on_configure() is called.')

        self.event_sub = self.create_subscription(
            String,
            '/rosa_kb/events',
            self.event_cb,
            10,
            callback_group=MutuallyExclusiveCallbackGroup())

        self.get_reconfig_plan_srv = self.create_client(
            ReconfigurationPlanQuery,
            '/rosa_kb/reconfiguration_plan/get_latest',
            callback_group=self.cb_group
        )

        self.set_reconfig_plan_result_srv = self.create_client(
            ReconfigurationPlanQuery,
            '/rosa_kb/reconfiguration_plan/result/set',
            callback_group=self.cb_group
        )

        self.set_component_active_srv = self.create_client(
            ComponentQuery,
            '/rosa_kb/component/active/set',
            callback_group=self.cb_group,
        )

        self.get_component_parameters_srv = self.create_client(
            GetComponentParameters,
            '/rosa_kb/component_parameters/get',
            callback_group=self.cb_group,
        )

        self.component_process_insert_srv = self.create_client(
            ComponentProcessQuery,
            '/rosa_kb/component_process/insert',
            callback_group=self.cb_group
        )

        self.component_process_get_active_srv = self.create_client(
            ComponentProcessQueryArray,
            '/rosa_kb/component_process/get_active',
            callback_group=self.cb_group
        )
        self.component_process_set_end_srv = self.create_client(
            ComponentProcessQuery,
            '/rosa_kb/component_process/end/set',
            callback_group=self.cb_group
        )

        self.get_logger().info(self.get_name() + ': on_configure() completed.')
        return TransitionCallbackReturn.SUCCESS

    def on_activate(self, state: State) -> TransitionCallbackReturn:
        self.get_logger().info(self.get_name() + ': on_activate() is called.')
        self.active = True
        self.get_logger().info(
            self.get_name() + ': on_activate() is completed.')
        return super().on_activate(state)

    def on_deactivate(self, state: State) -> TransitionCallbackReturn:
        self.get_logger().info("on_deactivate() is called.")
        self.active = False
        return super().on_deactivate(state)

    def on_cleanup(self, state: State) -> TransitionCallbackReturn:
        self.destroy_subscription(self.event_sub)
        self.active = False
        self.get_logger().info('on_cleanup() is called.')
        return TransitionCallbackReturn.SUCCESS

    def on_shutdown(self, state: State) -> TransitionCallbackReturn:
        self.get_logger().info('on_shutdown() is called.')
        self.active = False
        self.kill_all_components()
        return super().on_shutdown(state)

    @check_lc_active
    def change_lc_node_state(self, node_name, transition_id):
        srv = self.create_client(
            ChangeState,
            node_name + '/change_state',
            callback_group=self.cb_group)
        change_state_req = ChangeState.Request()
        change_state_req.transition.id = transition_id
        return self.call_service(srv, change_state_req)

    @check_lc_active
    def get_lc_node_state(self, node_name):
        get_state_srv = self.create_client(
            GetState,
            node_name + '/get_state',
            callback_group=self.cb_group)
        get_state_req = GetState.Request()
        return self.call_service(get_state_srv, get_state_req)

    @check_lc_active
    def call_service(self, cli, request):
        if cli.wait_for_service(timeout_sec=5.0) is False:
            self.get_logger().error(
                'service not available {}'.format(cli.srv_name))
            return None
        future = cli.call_async(request)
        self.executor.spin_until_future_complete(future, timeout_sec=5.0)
        if future.done() is False:
            self.get_logger().error(
                'Future not completed {}'.format(cli.srv_name))
            return None
        return future.result()

    @check_lc_active
    def event_cb(self, msg):
        if msg.data == 'insert_reconfiguration_plan':
            self.execute()

    @check_lc_active
    def execute(self):
        reconfig_plan = self.call_service(
            self.get_reconfig_plan_srv, ReconfigurationPlanQuery.Request())
        if reconfig_plan is not None and reconfig_plan.success is True:
            reconfig_result = self.perform_reconfiguration_plan(
                reconfig_plan.reconfig_plan)
            rp_query = ReconfigurationPlanQuery.Request()
            rp_query.reconfig_plan.start_time = \
                reconfig_plan.reconfig_plan.start_time
            if reconfig_result is True:
                rp_query.reconfig_plan.result = 'completed'
            else:
                rp_query.reconfig_plan.result = 'failed'
            self.call_service(self.set_reconfig_plan_result_srv, rp_query)

    @check_lc_active
    def perform_reconfiguration_plan(self, reconfig_plan):
        if self.get_parameter('fake_execution').value is True:
            self.get_logger().info('Fake execution enabled, skipping reconfiguration.')
            return True

        result_deactivation = self.deactivate_components(
            reconfig_plan.components_deactivate)
        result_activation = self.activate_components(
            reconfig_plan.components_activate)
        result_update = self.perform_parameter_adaptation(
            reconfig_plan.component_configurations)
        return result_deactivation and result_activation and result_update

    def kill_component_component_process(self, component_process):
        pid = component_process.pid
        c = component_process.component.name
        try:
            pgid = os.getpgid(pid)
            os.killpg(pgid, signal.SIGTERM)
            os.waitid(os.P_PGID, pgid, os.WEXITED)
            self.call_service(
                self.component_process_set_end_srv,
                ComponentProcessQuery.Request(
                    component_process=component_process)
            )
        except ProcessLookupError:
            self.get_logger().warning(f'''
                Component {c} process with pid {pid} not found''')
        except Exception as e:
            self.get_logger().error(f'''
                Exception when killing component {c} with pid {pid}:
                {e}''')

    def kill_all_components(self):
        active_components = self.call_service(
            self.component_process_get_active_srv,
            ComponentProcessQueryArray.Request())

        for component_process in active_components.component_process:
            self.kill_component_component_process(component_process)
        return True

    def kill_component(self, component):
        active_components = self.call_service(
            self.component_process_get_active_srv,
            ComponentProcessQueryArray.Request())
        for component_process in active_components.component_process:
            if component.name == component_process.component.name:
                self.kill_component_component_process(component_process)
        return True

    def deactivate_lc_component(self, component):
        if component.node_type == 'LifeCycleNode' and \
           component.name in self.get_node_names():
            _state = self.get_lc_node_state(component.name)
            if _state.current_state.id == 3:
                self.change_lc_node_state(component.name, 4)
            _state = self.get_lc_node_state(component.name)
            if _state.current_state.id != 2:
                return False
        return True

    @check_lc_active
    def deactivate_components(self, components):
        return_value = True
        for component in components:
            _return_value = True
            if component.node_type == 'LifeCycleNode':
                _return_value = self.deactivate_lc_component(component)

            if component.node_type == 'ROSNode':
                _return_value = self.kill_component(component)

            if _return_value is True:
                result_deactivate = self.set_component_active(component, False)
                if result_deactivate.success is not True:
                    _return_value = False
            return_value = _return_value
        return return_value

    def start_component(self, component):
        c_types = ['ROSNode', 'LifeCycleNode']
        if component.node_type in c_types and \
           component.name not in self.get_node_names():
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
                return False

            component_process = ComponentProcessQuery.Request()
            component_process.component_process.component.name = component.name
            component_process.component_process.pid = result_start.pid
            self.call_service(
                self.component_process_insert_srv, component_process)
        return True

    def activate_lc_component(self, component):
        if component.node_type == 'LifeCycleNode' and \
           component.name in self.get_node_names():
            _state = self.get_lc_node_state(component.name)
            if _state.current_state.id == 0:
                _state = self.get_lc_node_state(component.name)
            if _state.current_state.id == 1:
                self.change_lc_node_state(component.name, 1)
            _state = self.get_lc_node_state(component.name)
            if _state.current_state.id == 2:
                self.change_lc_node_state(component.name, 3)
            _state = self.get_lc_node_state(component.name)
            if _state.current_state.id != 3:
                return False
        return True

    def update_component_activation_attribute(self, component):
        if component.name != '':
            result_activate = self.set_component_active(component, True)
            if result_activate.success is not True:
                return False
        return True

    @check_lc_active
    def activate_components(self, components):
        return_value = True
        for component in components:
            start_component = self.start_component(component)
            if start_component is False:
                continue
            activate_lc_component = self.activate_lc_component(component)
            if activate_lc_component is False:
                continue
            if start_component is True and activate_lc_component is True:
                return_value = return_value and \
                    self.update_component_activation_attribute(component)
        # TODO: set attribute in the component to indicate which state it is
        # in case of LC nodes
        return return_value

    @check_lc_active
    def set_component_active(self, component, is_active):
        _ca = ComponentQuery.Request()
        _ca.component = component
        _ca.component.is_active = is_active
        result = self.call_service(self.set_component_active_srv, _ca)
        if result.success is not True:
            self.get_logger().error(
                'error setting component {0} to active {1} in the KB'.format(
                    component.name, is_active))
        return result

    @check_lc_active
    def perform_parameter_adaptation(self, configurations):
        return_value = True
        for config in configurations:
            request = GetComponentParameters.Request()
            request.c_config = config
            res_get_param = self.call_service(
                self.get_component_parameters_srv, request)

            if res_get_param == GetComponentParameters.Response():
                continue

            set_parameters_atomically_srv = self.create_client(
                SetParametersAtomically,
                res_get_param.component.name + '/set_parameters_atomically',
                callback_group=ReentrantCallbackGroup(),
            )

            req_set_param = SetParametersAtomically.Request(
                parameters=res_get_param.parameters)
            res_set_param = self.call_service(
                set_parameters_atomically_srv, req_set_param)
            if res_set_param is None or res_set_param.result.successful is False:
                return_value = False
                self.get_logger().error(
                    f'''Error in parameter adaptation with:
                    component: {res_get_param.component.name}
                    component config: {config}
                    parameters: {res_get_param.parameters}
                    reason: {res_set_param.result.reason}
                    '''
                )
        return return_value

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
                start_new_session=True
            )
            try:
                outs, errs = process.communicate(timeout=1)
                self.get_logger().error(f'''
                    {_func} failed!
                    input _dict: {_dict}
                    resulting errors: {errs}''')
                return False
            except subprocess.TimeoutExpired:
                return process
        except Exception as e:
            self.get_logger().error(f'''
                {_func} failed!
                input _dict: {_dict}
                raised exception: {e}''')
            return False
