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
import pytest
from rosa_kb.typedb_model_interface import ModelInterface
from rosa_kb.typedb_model_interface \
    import convert_component_parameter_value_to_py_type
from datetime import datetime


@pytest.fixture
def kb_interface():
    kb_interface = ModelInterface(
        "localhost:1729",
        "test_model_interface",
        ["config/schema.tql", "config/ros_schema.tql"],
        ["test/test_data/test_data.tql", "test/test_data/ros_test_data.tql"],
        force_database=True,
        force_data=True,
        infer=True
    )
    return kb_interface


def test_request_action(kb_interface):
    kb_interface.request_action('action1', 'ea1')
    is_required = kb_interface.is_action_required('action1')
    query = """
        match
        $action isa Action, has action-name "action1";
        (action: $action, preference: $att) isa required-action;
        $att has name $name;
        fetch $name;
    """
    result = kb_interface.fetch_database(query)
    assert is_required is True and result[0].get('name').get('value') == 'ea1'


def test_cancel_action(kb_interface):
    kb_interface.request_action('action1')
    kb_interface.cancel_action('action1')
    is_required = kb_interface.is_action_required('action1')
    assert is_required is False


@pytest.mark.parametrize("action_name, expected_result", [
    ('action_required', True),
    # ('action_required_activated', True),
    ('action_not_required', False),
    ('action_required_empty', False),
])
def test_is_action_required(kb_interface, action_name, expected_result):
    assert kb_interface.is_action_required(action_name) is expected_result


@pytest.mark.parametrize("action_name, expected_result", [
    ('action_required', False),
    ('action_feasible', True),
    ('action_unfeasible', False),
])
def test_is_action_feasible(kb_interface, action_name, expected_result):
    assert kb_interface.is_action_feasible(action_name) is expected_result


@pytest.mark.parametrize("action_name, expected_result", [
    ('action_required', True),
    ('action_feasible', True),
    ('action_unfeasible', False),
])
def test_is_action_selectable(kb_interface, action_name, expected_result):
    assert kb_interface.is_action_selectable(action_name) is expected_result


def test_get_selectable_actions(kb_interface):
    result = kb_interface.get_selectable_actions()
    expected_result = [
        'action_feasible', 'action_required_solved']
    assert ('action_unfeasible' not in result) \
           and all(r in result for r in expected_result)


def test_get_unsolved_functions(kb_interface):
    kb_interface.request_action('action1')
    unsolved_functions = kb_interface.get_unsolved_functions()
    from collections import Counter
    print('unsolved: ', unsolved_functions)
    assert Counter(['function1', 'function2', 'f_reconfigure_f_config']) \
        == Counter(unsolved_functions)


def test_get_unsolved_components(kb_interface):
    unsolved_components = kb_interface.get_unsolved_components()
    assert 'c_required' in unsolved_components


def test_get_latest_measurement(kb_interface):
    value = 1.0
    measured_value = kb_interface.get_latest_measurement(
        'ea_measurement')
    assert value == measured_value


def test_get_measurement(kb_interface):
    value = 1.8
    measured_value = kb_interface.get_measurement(
        'ea_measurement', datetime.fromisoformat('2023-01-08T06:12:11.111'))
    assert value == measured_value


def test_add_measurement(kb_interface):
    value = 1.32
    kb_interface.add_measurement('ea_measurement', 1.32)
    measured_value = kb_interface.get_latest_measurement('ea_measurement')
    assert value == measured_value

@pytest.mark.parametrize(
    "raw, expected",
    [
        (1.32, 1.32),
        ("1.78", 1.78),
        ("  1.19  ", 1.19),
        (42, 42.0),
        ("44", 44.0),
        ("-0.5", -0.5),
        (-1.22323, -1.22323),
        (0.0, 0.0),
    ],
)
def test_add_measurement_accepts_and_stores_valid_numbers(kb_interface, raw, expected):
    kb_interface.add_measurement("ea_measurement", raw)
    measured_value = kb_interface.get_latest_measurement("ea_measurement")
    assert measured_value == pytest.approx(expected)

@pytest.mark.parametrize(
    "bad",
    [
        float("nan"),
        "nan",
        float("inf"),
        "inf",
        "-inf",
    ],
)
def test_add_measurement_rejects_nan_inf(kb_interface, bad, caplog):
    before = kb_interface.get_latest_measurement("ea_measurement")
    kb_interface.add_measurement("ea_measurement", bad)

    after = kb_interface.get_latest_measurement("ea_measurement")
    assert after == before  # should not change

@pytest.mark.parametrize(
    "bad",
    [
        "abc",
        None,
        {"x": 1},
        object(),
        [],
        "",  # empty string
    ],
)
def test_add_measurement_rejects_unparseable_inputs(kb_interface, bad, caplog):
    before = kb_interface.get_latest_measurement("ea_measurement")
    kb_interface.add_measurement("ea_measurement", bad)

    after = kb_interface.get_latest_measurement("ea_measurement")
    assert after == before


def test_select_function_design(kb_interface):
    kb_interface.select_function_design('function2', 'f2_fd1_c2_c3')
    fd1_selected = kb_interface.fetch_attribute_from_thing(
        'function-design',
        [('function-design-name', 'f2_fd1_c2_c3')],
        'is-selected')
    kb_interface.select_function_design('function2', 'f2_fd2_c4_c5')
    fd1_not_selected = kb_interface.fetch_attribute_from_thing(
        'function-design',
        [('function-design-name', 'f2_fd1_c2_c3')],
        'is-selected')
    fd2_selected = kb_interface.fetch_attribute_from_thing(
        'function-design',
        [('function-design-name', 'f2_fd2_c4_c5')],
        'is-selected')

    assert fd1_selected[0] is True and fd1_not_selected[0] is False \
           and fd2_selected[0] is True


def test_select_component_configuration(kb_interface):
    kb_interface.select_component_configuration('component1', 'high param')
    high_selected = kb_interface.fetch_attribute_from_thing(
        'component-configuration',
        [('component-configuration-name', 'high param')],
        'is-selected')
    kb_interface.select_component_configuration('component1', 'low param')
    high_not_selected = kb_interface.fetch_attribute_from_thing(
        'component-configuration',
        [('component-configuration-name', 'high param')],
        'is-selected')
    low_selected = kb_interface.fetch_attribute_from_thing(
        'component-configuration',
        [('component-configuration-name', 'low param')],
        'is-selected')
    assert high_selected[0] is True and high_not_selected[0] is False and \
           low_selected[0] is True


@pytest.mark.parametrize("c_activate, c_deactivate, c_config", [
   (['component2', 'component3'], ['component4', 'component5'], ['low param']),
   ([], ['component4', 'component5'], ['low param']),
   (['component2', 'component3'], [], ['low param']),
   (['component2', 'component3'], ['component4', 'component5'], []),
   ([], [], ['low param']),
   ([], [], []),
])
def test_create_reconfiguration_plan(
   kb_interface, c_activate, c_deactivate, c_config):
    start_time = kb_interface.create_reconfiguration_plan(
        c_activate, c_deactivate, c_config)
    query = "match ("
    end_query = ""
    if len(c_activate) == 0 and len(c_deactivate) == 0 and len(c_config) == 0:
        assert start_time is None
    else:
        if len(c_activate) > 0:
            query += "structural-adaptation:$ca"
            _match_query, _prefix_list = kb_interface.create_match_query(
                [('Component', 'component-name', c) for c in c_activate],
                'ca_')
            end_query += kb_interface.create_relationship_query(
                'component-activation',
                {'component': _prefix_list},
                prefix='ca'
            )
            end_query += _match_query

        if len(c_deactivate) > 0:
            if query != "match (":
                query += ','
            query += "structural-adaptation:$cd"
            _match_query, _prefix_list = kb_interface.create_match_query(
                [('Component', 'component-name', c) for c in c_deactivate],
                'cd_')
            end_query += kb_interface.create_relationship_query(
                'component-deactivation',
                {'component': _prefix_list},
                prefix='cd'
            )
            end_query += _match_query

        if len(c_config) > 0:
            if query != "match (":
                query += ','
            query += "parameter-adaptation:$pa"
            _match_query, _prefix_list = kb_interface.create_match_query(
                [('component-configuration', 'component-configuration-name', c)
                 for c in c_config], 'cc_')
            end_query += kb_interface.create_relationship_query(
                'parameter-adaptation',
                {'component-configuration': _prefix_list},
                prefix='cc'
            )
            end_query += _match_query

        query += f"""
            ) isa reconfiguration-plan,
                has start-time {start_time.isoformat(timespec='milliseconds')};
        """
        query += end_query
        query_result = kb_interface.get_aggregate_database(query + "get; count;")
        assert query_result > 0


@pytest.mark.parametrize("selected_fd, selected_config, exp_c_activate, exp_c_deactivate, exp_c_config ", [
    ([('f_reconfigure_fd', 'fd_reconfig_1')], [('component_reconfig_3', 'cp_reconfig_1')], [], ['c_not_required'], []),
    ([('f_reconfigure_fd', 'fd_reconfig_2')], [('component_reconfig_3', 'cp_reconfig_1')], ['component_reconfig_2'], ['component_reconfig_1', 'c_not_required'], []),
    ([('f_reconfigure_fd', 'fd_reconfig_1')], [('component_reconfig_3', 'cp_reconfig_2')], [], ['c_not_required'], ['cp_reconfig_2']),
    ([('f_reconfigure_fd', 'fd_reconfig_2')], [('component_reconfig_3', 'cp_reconfig_2')], ['component_reconfig_2'], ['component_reconfig_1', 'c_not_required'], ['cp_reconfig_2']),
])
def test_select_configuration(
        kb_interface,
        selected_fd,
        selected_config,
        exp_c_activate,
        exp_c_deactivate,
        exp_c_config
     ):
    start_time = kb_interface.select_configuration(
        selected_fd, selected_config)
    if exp_c_activate == [] and exp_c_deactivate == [] and exp_c_config == []:
        assert start_time is None
    else:
        query = "match $rp "
        end_query = ""
        if len(exp_c_activate) > 0:
            if query == "match $rp ":
                query += '('
            query += "structural-adaptation:$ca"
            _match_query, _prefix_list = kb_interface.create_match_query(
                [('Component', 'component-name', c) for c in exp_c_activate],
                'ca')
            end_query += kb_interface.create_relationship_query(
                'component-activation',
                {'component': _prefix_list},
                prefix='ca'
            )
            end_query += _match_query
        if len(exp_c_deactivate) > 0:
            if query == "match $rp ":
                query += '('
            elif len(query) > len("match $rp ("):
                query += ','
            query += "structural-adaptation:$cd"
            _match_query, _prefix_list = kb_interface.create_match_query(
                [('Component', 'component-name', c) for c in exp_c_deactivate],
                'cd')
            end_query += kb_interface.create_relationship_query(
                'component-deactivation',
                {'component': _prefix_list},
                prefix='cd'
            )
            end_query += _match_query
        if len(exp_c_config) > 0:
            if query == "match $rp ":
                query += '('
            elif len(query) > len("match $rp ("):
                query += ','
            query += "parameter-adaptation:$pa"
            _match_query, _prefix_list = kb_interface.create_match_query(
                [('component-configuration', 'component-configuration-name', c)
                 for c in exp_c_config], 'cc_')
            end_query += kb_interface.create_relationship_query(
                'parameter-adaptation',
                {'component-configuration': _prefix_list},
                prefix='cc'
            )
            end_query += _match_query

        if query != "match $rp ":
            query += ')'

        query += " isa reconfiguration-plan, has start-time {};".format(
            start_time.isoformat(timespec='milliseconds'))
        query += end_query
        query_result = kb_interface.get_aggregate_database(
            query + "get; count;")

        right_fd_selected = True
        for fd in selected_fd:
            _fd = kb_interface.get_relationship_with_attribute(
                'Function',
                fd[0],
                'function-design',
                'is-selected',
                True
            )
            right_fd_selected = (fd[1] == _fd[0])
        right_conf_selected = True
        for config in selected_config:
            _config = kb_interface.get_relationship_with_attribute(
                'Component',
                config[0],
                'component-configuration',
                'is-selected',
                True
            )
            right_conf_selected = (config[1] == _config[0])
        assert query_result > 0 and right_fd_selected \
            and right_conf_selected


@pytest.mark.parametrize("thing, status, exp", [
    ('Action', 'feasible', 'action_feasible'),
    ('Action', 'unfeasible', 'action_unfeasible'),
    ('Function', 'unsolved', 'f_unsolved'),
    ('Component', 'unsolved', 'c_unsolved'),
    ('function-design', 'unsolved', 'fd_unsolved'),
])
def test_get_instances_of_thing_with_status(kb_interface, thing, status, exp):
    result = kb_interface.get_instances_of_thing_with_status(thing, status)
    assert exp in result


@pytest.mark.parametrize("thing, exp", [
    ('Function', 'f_always_improve'),
    ('Component', 'c_always_improve'),
])
def test_get_instances_thing_always_improve(kb_interface, thing, exp):
    result = kb_interface.get_instances_thing_always_improve(thing)
    assert exp in result


def test_get_adaptable_functions(kb_interface):
    expected_result = ['f_unsolved', 'f_always_improve']
    result = kb_interface.get_adaptable_functions()
    assert all(r in result for r in expected_result)


def test_get_adaptable_component(kb_interface):
    expected_result = ['c_unsolved', 'c_always_improve']
    kb_interface.unselect_obsolete_fds_cc()
    result = kb_interface.get_adaptable_components()
    print(result)
    assert all(r in result for r in expected_result) and \
        'c_not_required' not in result


def test_get_components_in_function_design(kb_interface):
    result = kb_interface.get_components_in_function_design('f2_fd1_c2_c3')
    expected_result = ['component2', 'component3']
    assert all(r in result for r in expected_result)


def test_get_latest_reconfiguration_plan_time(kb_interface):
    c_activate = ['component2', 'component3']
    c_deactivate = ['component4', 'component5']
    c_config = ['low param']
    kb_interface.create_reconfiguration_plan(
        c_activate, c_deactivate, c_config)

    c_activate = ['component3']
    c_deactivate = ['component5']
    c_config = ['low param']
    start_time_2 = kb_interface.create_reconfiguration_plan(
        c_activate, c_deactivate, c_config)
    lastest_plan = kb_interface.get_latest_reconfiguration_plan_time()
    assert lastest_plan == start_time_2


def test_get_latest_reconfiguration_plan_time_no_rp(kb_interface):
    lastest_plan = kb_interface.get_latest_reconfiguration_plan_time()
    assert lastest_plan is None


def test_get_reconfiguration_plan(kb_interface):
    c_activate = ['component2', 'component3']
    c_deactivate = ['component4', 'component5']
    c_config = ['low param']
    start_time = kb_interface.create_reconfiguration_plan(
        c_activate, c_deactivate, c_config)

    reconfig_plan = kb_interface.get_reconfiguration_plan(start_time)
    assert sorted(c_activate) == sorted(reconfig_plan['c_activate']) and \
        sorted(c_deactivate) == sorted(reconfig_plan['c_deactivate']) and \
        sorted(c_config) == sorted(reconfig_plan['c_config'])


def test_get_latest_reconfiguration_plan(kb_interface):
    c_activate = ['component2', 'component3']
    c_deactivate = ['component4', 'component5']
    c_config = ['low param']
    kb_interface.create_reconfiguration_plan(
        c_activate, c_deactivate, c_config)

    c_activate = ['component3']
    c_deactivate = ['component5']
    c_config = ['low param']
    start_time_2 = kb_interface.create_reconfiguration_plan(
        c_activate, c_deactivate, c_config)
    reconfig_plan = kb_interface.get_latest_reconfiguration_plan()
    assert reconfig_plan['start_time'] == start_time_2 and \
        sorted(c_activate) == sorted(reconfig_plan['c_activate']) and \
        sorted(c_deactivate) == sorted(reconfig_plan['c_deactivate']) and \
        sorted(c_config) == sorted(reconfig_plan['c_config'])


def test_update_reconfiguration_plan_result(kb_interface):
    c_activate = ['component2', 'component3']
    c_deactivate = ['component4', 'component5']
    c_config = ['low param']
    start_time = kb_interface.create_reconfiguration_plan(
        c_activate, c_deactivate, c_config)

    kb_interface.update_reconfiguration_plan_result(start_time, 'completed')
    query = f'''
        match $rp isa reconfiguration-plan,
            has start-time {start_time.isoformat(timespec='milliseconds')},
            has end-time $end-time,
            has result $result;
            fetch $end-time; $result;
    '''
    query_result = kb_interface.fetch_database(query)
    result = [r.get('result').get('value') for r in query_result]
    assert len(result) > 0 and result[0] == 'completed'


def test_get_latest_completed_reconfiguration_plan_time(kb_interface):
    c_activate = ['component2', 'component3']
    c_deactivate = ['component4', 'component5']
    c_config = ['low param']
    start_time_1 = kb_interface.create_reconfiguration_plan(
        c_activate, c_deactivate, c_config)

    kb_interface.update_reconfiguration_plan_result(start_time_1, 'completed')

    c_activate = ['component3']
    c_deactivate = ['component5']
    c_config = ['low param']
    start_time_2 = kb_interface.create_reconfiguration_plan(
        c_activate, c_deactivate, c_config)
    kb_interface.update_reconfiguration_plan_result(start_time_2, 'completed')
    end_time = kb_interface.get_latest_completed_reconfiguration_plan_time()
    assert end_time is not None and type(end_time) is datetime


def test_get_latest_pending_reconfiguration_plan_time(kb_interface):
    c_activate = ['component2', 'component3']
    c_deactivate = ['component4', 'component5']
    c_config = ['low param']
    start_time_1 = kb_interface.create_reconfiguration_plan(
        c_activate, c_deactivate, c_config)

    c_activate = ['component3']
    c_deactivate = ['component5']
    c_config = ['low param']
    start_time_2 = kb_interface.create_reconfiguration_plan(
        c_activate, c_deactivate, c_config)
    kb_interface.update_reconfiguration_plan_result(start_time_2, 'completed')
    r_start_time = kb_interface.get_latest_pending_reconfiguration_plan_time()
    assert r_start_time is not None \
        and type(r_start_time) is datetime and r_start_time == start_time_1


def test_get_outdated_reconfiguration_plans(kb_interface):
    c_activate = ['component2', 'component3']
    c_deactivate = ['component4', 'component5']
    c_config = ['low param']
    start_time_1 = kb_interface.create_reconfiguration_plan(
        c_activate, c_deactivate, c_config)

    c_activate = ['component3']
    c_deactivate = ['component5']
    c_config = ['low param']
    start_time_2 = kb_interface.create_reconfiguration_plan(
        c_activate, c_deactivate, c_config)
    kb_interface.update_reconfiguration_plan_result(start_time_2, 'completed')

    times = kb_interface.get_outdated_reconfiguration_plans()

    assert start_time_1 in times


def test_get_reconfiguration_plan_result(kb_interface):
    c_activate = ['component2', 'component3']
    c_deactivate = ['component4', 'component5']
    c_config = ['low param']
    start_time = kb_interface.create_reconfiguration_plan(
        c_activate, c_deactivate, c_config)

    kb_interface.update_reconfiguration_plan_result(start_time, 'completed')
    result = kb_interface.get_reconfiguration_plan_result(start_time)
    assert result == 'completed'


def test_update_outdated_reconfiguration_plans_result(kb_interface):
    kb_interface.update_outdated_reconfiguration_plans_result()

    c_activate = ['component2', 'component3']
    c_deactivate = ['component4', 'component5']
    c_config = ['low param']
    start_time_1 = kb_interface.create_reconfiguration_plan(
        c_activate, c_deactivate, c_config)

    c_activate = ['component3']
    c_deactivate = ['component5']
    c_config = ['low param']
    start_time_2 = kb_interface.create_reconfiguration_plan(
        c_activate, c_deactivate, c_config)

    c_activate = ['component2']
    c_deactivate = ['component4']
    c_config = ['high param']
    start_time_3 = kb_interface.create_reconfiguration_plan(
        c_activate, c_deactivate, c_config)

    kb_interface.update_reconfiguration_plan_result(start_time_2, 'completed')
    kb_interface.update_outdated_reconfiguration_plans_result()

    result1 = kb_interface.get_reconfiguration_plan_result(start_time_1)
    result2 = kb_interface.get_reconfiguration_plan_result(start_time_2)
    result3 = kb_interface.get_reconfiguration_plan_result(start_time_3)

    assert result1 == 'abandoned' and result2 == 'completed' \
           and result3 == 'abandoned'


def test_get_selectable_fds(kb_interface):
    result = kb_interface.get_selectable_fds('f_fd_feasible_unfeasible')
    expected_result = ['f_fd_feasible']
    assert all(r in result for r in expected_result)


def test_get_selectable_c_configs(kb_interface):
    result = kb_interface.get_selectable_c_configs('c_cc_feasible_unfeasible')
    expected_result = ['c_cc_feasible']
    assert all(r in result for r in expected_result)


@pytest.mark.parametrize("type, param, expected", [
    ('boolean', 'True', True),
    ('boolean_array', '[True, False]', [True, False]),
    ('double', '3.0', 3.0),
    ('double_array', '[3.0, 4.0 , 5.0 ]', [3.0, 4.0, 5.0]),
    ('long', '10', 10),
    ('long_array', '[10, 33, 44 ]', [10, 33, 44]),
    ('string', 'teste', 'teste'),
    ('string_array', '[ teste, t2 , t3 ]', ['teste', 't2', 't3']),
])
def test_convert_component_parameter_value_to_py_type(type, param, expected):
    result = convert_component_parameter_value_to_py_type(param, type)
    assert result == expected


def test_get_component_parameters(kb_interface):
    c_config = 'get_cp_cc'
    expected = {
        'component': 'get_cp_c',
        'component_parameters': [
            {'key': 'get_cp_1', 'value': True, 'type': 'boolean'},
            {'key': 'get_cp_2',
             'value': [True, False], 'type': 'boolean_array'},
            {'key': 'get_cp_3', 'value': 3.0, 'type': 'double'},
            {'key': 'get_cp_4', 'value': [3.0, 5.0], 'type': 'double_array'},
            {'key': 'get_cp_5', 'value': 10, 'type': 'long'},
            {'key': 'get_cp_6', 'value': [10, 14], 'type': 'long_array'},
            {'key': 'get_cp_7', 'value': 'teste', 'type': 'string'},
            {'key': 'get_cp_8',
             'value': ['teste', 'teste2'], 'type': 'string_array'},
        ]
    }
    result = kb_interface.get_component_parameters(c_config)
    assert result['component'] == expected['component'] and \
        all(r in result['component_parameters'] for
            r in expected['component_parameters'])


def test_get_component_all_attributes(kb_interface):
    result = kb_interface.get_component_all_attributes('c_attributes')
    result2 = kb_interface.get_component_all_attributes('ros_typedb_test')

    expected_result = {
        'type': 'Component',
        'component_name': 'c_attributes',
        'is_active': True,
        'is_required': True,
        'component_status': 'solved',
    }

    expected_result2 = {
        'type': 'LifeCycleNode',
        'component_name': 'ros_typedb_test',
        'package': 'ros_typedb',
        'executable': 'ros_typedb',
        'component_status': 'feasible',
    }

    assert result == expected_result and result2 == expected_result2


def test_get_obsolete_components(kb_interface):
    query_result = kb_interface.get_obsolete_components()
    expected_result = ['c_not_required', 'c_active', 'c_attributes']
    assert all(r in query_result for r in expected_result)


def test_get_obsolete_fds(kb_interface):
    query_result = kb_interface.get_obsolete_fds()
    expected_result = ['fd_selected_not_required']
    assert all(r in query_result for r in expected_result)


def test_get_obsolete_component_configurations(kb_interface):
    query_result = kb_interface.get_obsolete_component_configurations()
    expected_result = ['cc_not_required']
    assert all(r in query_result for r in expected_result)


def test_get_active_component_process(kb_interface):
    kb_interface.insert_component('c_test_component_process')
    kb_interface.insert_component('c_test_component_process2')
    kb_interface.insert_component_process('c_test_component_process', 2333)
    kb_interface.insert_component_process('c_test_component_process2', 22222)
    expected_result = [
        {'pid': 2333, 'component': 'c_test_component_process'},
        {'pid': 22222, 'component': 'c_test_component_process2'}
    ]
    query_result = kb_interface.get_active_component_process()
    for r in query_result:
        del r['start_time']
    assert all(r in query_result for r in expected_result)


@pytest.mark.parametrize("action_name, result", [
    ('action1', True),
    ('action_not_in_model', False),
])
def test_has_action(kb_interface, action_name, result):
    assert kb_interface.has_action(action_name) == result

def test_get_measures_inferfaces(kb_interface):
    interfaces = kb_interface.get_measures_inferfaces()
    qa_test_topic_dict = {
        'type': 'topic-interface',
        'measure-name': 'qa_test_topic',
        'measurement-interface-name': '/subscription',
        'measurement-interface-type': 'std_msgs/msg/Float64',
        'measurement-function-name': 'get_data_field',
        'measurement-function-lib': 'rosa_monitor.monitor_functions',
        'measurement-function-args': 'data',
    }
    qa_test_topic_dict_2 = {
        'type': 'topic-interface',
        'measure-name': 'qa_test_topic_2',
        'measurement-interface-name': '/subscription2',
        'measurement-interface-type': 'std_msgs/msg/Float64',
        'qos': {
            'reliability' : 'RELIABLE',
            'history': 'KEEP_LAST',
            'depth': 10,
            'durability': 'TRANSIENT_LOCAL',
            'lifespan': 2.0,
            'deadline': 2.0,
            'liveliness': 'MANUAL_BY_TOPIC',
            'lease-duration': 2.0,
        }
    }

    laser_scan_dict = {
        'type': 'topic-interface',
        'measure-name': 'laser_nearest_object',
        'measurement-interface-name': '/scan',
        'measurement-interface-type': 'sensor_msgs/msg/LaserScan',
        'measurement-function-name': 'get_nearest_scan_distance_in_base',
        'measurement-function-lib': 'rosa_monitor.laser_scan_functions',
        'qos': {
            'reliability' : 'BEST_EFFORT',
            'history': 'KEEP_LAST',
            'depth': 5,
            'durability': 'VOLATILE',
            'lifespan': 0.0,
            'deadline': 0.0,
            'liveliness': 'SYSTEM_DEFAULT',
            'lease-duration': 0.0,
        }
    }

    assert len(interfaces) == 3
    assert qa_test_topic_dict in interfaces
    assert qa_test_topic_dict_2 in interfaces
    assert laser_scan_dict in interfaces