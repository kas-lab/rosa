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


@pytest.fixture
def kb_interface():
    kb_interface = ModelInterface(
        "localhost:1729",
        "pytest_database",
        "config/schema.tql",
        "test/test_data/test_data.tql",  # TODO:better way to handle empty data
        force_database=True,
        force_data=True,
        infer=True
    )
    return kb_interface


@pytest.mark.parametrize("att_name, att_value, config_name, constraint_status", [
    ('ea1', 2.5, 'high param', 'violated'),
    ('ea1', 2.5, 'high param >=', 'violated'),
    ('ea1', 3.25, 'high param >=', 'satisfied'),
    ('ea1', 3.25, 'high param >', 'violated'),
    ('ea1', 3.5, 'high param >', 'satisfied'),
    ('ea1', 3.5, 'high param <=', 'violated'),
    ('ea1', 3.25, 'high param <=', 'satisfied'),
    ('ea1', 3.25, 'high param <', 'violated'),
    ('ea1', 2.5, 'high param <', 'satisfied'),
    ('ea1', 2.5, 'low param', 'satisfied'),
    ('ea1', '', 'low param', 'not evaluated'),
])
def test_constraint_status_inference(
        kb_interface, att_name, att_value, config_name, constraint_status):

    if att_value != '':
        kb_interface.add_measurement(att_name, att_value)
    query = f'''
        match
            $ea isa EnvironmentalAttribute, has measure-name "{att_name}";
            $config isa component-configuration,
                has component-configuration-name "{config_name}";
            (constraint: $ea, constrained: $config) isa constraint,
                has constraint-status $status;
            fetch $status;
    '''
    query_result = kb_interface.fetch_database(query)
    inferred_status = [
        status.get("status").get('value') for status in query_result]
    assert inferred_status[0] == constraint_status


@pytest.mark.parametrize("type, name", [
    ('Action', 'action_constrained'),
    ('function-design', 'fd_constrained'),
    ('Component', 'c_constrained'),
    ('component-configuration', 'cc_constrained'),
])
def test_constraint_status_propagation(kb_interface, type, name):
    status_inferred = kb_interface.fetch_attribute_from_thing(
        type,
        [(type.lower()+'-name', name)],
        type.lower()+'-status')
    assert 'unfeasible' == status_inferred[0]


@pytest.mark.parametrize("att_name, att_value, config_name, config_status", [
    ('ea1', 2.5, 'high param', 'unfeasible'),
    ('ea1', 2.5, 'low param', 'feasible'),
    ('ea1', '', 'low param', 'feasible'),
])
def test_component_configuration_status_inference(
        kb_interface, att_name, att_value, config_name, config_status):
    if att_value != '':
        kb_interface.add_measurement(att_name, att_value)
    query = f'''
        match
            $config isa component-configuration,
                has component-configuration-name "{config_name}",
                has component-configuration-status $status;
            fetch $status;
    '''
    query_result = kb_interface.fetch_database(query)
    inferred_status = [
        status.get("status").get('value') for status in query_result]
    assert inferred_status[0] == config_status


@pytest.mark.parametrize("configurations, c_name, c_required, c_active, c_status", [
    ([('low param', 'unfeasible', True), ('high param', 'unfeasible', False)], 'component1', False, False, 'unfeasible'),
    ([('low param', 'unfeasible', True), ('high param', 'feasible', False)], 'component1', True, False, 'configuration error'),
    ([('low param', 'feasible', False), ('high param', 'feasible', False)], 'component1', True, False, 'unsolved'),
    ([('low param', 'feasible', True), ('high param', 'feasible', False)], 'component1', True, False, 'unsolved'),
    ([('low param', 'feasible', True), ('high param', 'unfeasible', False)], 'component1', True, False, 'unsolved'),
    ([], 'component1', True, False, 'unsolved'),
    ([('low param', 'feasible', True), ('high param', 'feasible', False)], 'component1', False, False, 'feasible'),
    ([('low param', 'feasible', False), ('high param', 'unfeasible', False)], 'component1', False, False, 'feasible'),
    ([], 'component1', False, False, 'feasible'),
    ([('low param', 'feasible', True), ('high param', 'feasible', False)], 'component1', True, True, 'solved'),
    ([('low param', 'feasible', True), ('high param', 'unfeasible', False)], 'component1', True, True, 'solved'),
])
def test_component_status_inference(
        kb_interface, configurations, c_name, c_required, c_active, c_status):
    for config in configurations:
        kb_interface.update_attribute_in_thing(
            'component-configuration',
            'component-configuration-name',
            config[0],
            'component-configuration-status',
            config[1]
        )
        # if config[2] == True:
        kb_interface.update_attribute_in_thing(
            'component-configuration',
            'component-configuration-name',
            config[0],
            'is-selected',
            config[2])
    kb_interface.update_attribute_in_thing(
        'Component',
        'component-name',
        c_name,
        'is-required',
        c_required)
    kb_interface.update_attribute_in_thing(
        'Component',
        'component-name',
        c_name,
        'is-active',
        c_active)
    c_status_inferred = kb_interface.fetch_attribute_from_thing(
        'Component',
        [('component-name', c_name)],
        'component-status')
    print(c_status_inferred)
    assert all(x in c_status_inferred for x in [c_status]) is True


@pytest.mark.parametrize("components, fd_name, fd_selected, fd_status", [
    ([('component2', 'failure')], 'f2_fd1_c2_c3', False, 'unfeasible'),
    ([('component2', 'failure'), ('component3', 'feasible')], 'f2_fd1_c2_c3', False, 'unfeasible'),
    ([('component2', 'failure'), ('component3', 'solved')], 'f2_fd1_c2_c3', True, 'unfeasible'),
    ([('component2', 'failure'), ('component3', 'configuration error')], 'f2_fd1_c2_c3', True, 'unfeasible'),
    ([('component2', 'unfeasible')], 'f2_fd1_c2_c3', False, 'unfeasible'),
    ([('component2', 'unfeasible')], 'f2_fd1_c2_c3', True, 'unfeasible'),
    ([('component2', 'solved'), ('component3', 'configuration error')], 'f2_fd1_c2_c3', True, 'implicit configuration error'),
    ([('component2', 'configuration error'), ('component3', 'feasible')], 'f2_fd1_c2_c3', True, 'implicit configuration error'),
    ([('component2', 'unsolved'), ('component3', 'unsolved')], 'f2_fd1_c2_c3', True, 'unsolved'),
    ([('component2', 'feasible'), ('component3', 'feasible')], 'f2_fd1_c2_c3', True, 'unsolved'),
    ([('component2', 'solved'), ('component3', 'unsolved')], 'f2_fd1_c2_c3', True, 'unsolved'),
    ([('component2', 'solved'), ('component3', 'feasible')], 'f2_fd1_c2_c3', True, 'unsolved'),
    ([], 'f2_fd1_c2_c3', True, 'unsolved'),
    ([('component2', 'feasible'), ('component3', 'configuration error')], 'f2_fd1_c2_c3', False, 'feasible'),
    ([('component2', 'feasible'), ('component3', 'feasible')], 'f2_fd1_c2_c3', False, 'feasible'),
    ([], 'f2_fd1_c2_c3', False, 'feasible'),
    ([('component2', 'solved'), ('component3', 'solved')], 'f2_fd1_c2_c3', True, 'solved'),
])
def test_function_design_status_inference(
     kb_interface, components, fd_name, fd_selected, fd_status):

    for component in components:
        kb_interface.update_attribute_in_thing(
            'Component',
            'component-name',
            component[0],
            'component-status',
            component[1]
        )
        if component[1] == 'solved':
            kb_interface.update_attribute_in_thing(
                'Component',
                'component-name',
                component[0],
                'is-active',
                True)
    kb_interface.update_attribute_in_thing(
        'function-design',
        'function-design-name',
        fd_name,
        'is-selected',
        fd_selected)
    fd_status_inferred = kb_interface.fetch_attribute_from_thing(
        'function-design',
        [('function-design-name', fd_name)],
        'function-design-status')
    assert all(x in fd_status_inferred for x in [fd_status]) is True


@pytest.mark.parametrize("fds, f_name, f_required, f_status", [
    ([], 'function_no_fd', False, 'unfeasible'),
    ([('f1_fd1', 'unfeasible', False)], 'function1', False, 'unfeasible'),
    ([('f1_fd1', 'unfeasible', False)], 'function1', True, 'unfeasible'),
    ([('f2_fd1_c2_c3', 'unfeasible', True), ('f2_fd2_c4_c5', 'unfeasible', False)], 'function2', True, 'unfeasible'),
    ([('f2_fd1_c2_c3', 'unfeasible', True)], 'function2', True, 'configuration error'),
    ([('f2_fd1_c2_c3', 'unfeasible', True), ('f2_fd2_c4_c5', 'feasible', False)], 'function2', True, 'configuration error'),
    ([('f2_fd1_c2_c3', 'implicit configuration error', True)], 'function2', True, 'implicit configuration error'),
    ([('f2_fd1_c2_c3', 'implicit configuration error', True), ('f2_fd2_c4_c5', 'feasible', False)], 'function2', True, 'implicit configuration error'),
    ([], 'function1', True, 'unsolved'),
    ([('f2_fd1_c2_c3', 'feasible', False), ('f2_fd2_c4_c5', 'feasible', False)], 'function2', True, 'unsolved'),
    ([('f2_fd1_c2_c3', 'feasible', False), ('f2_fd2_c4_c5', 'unfeasible', False)], 'function2', True, 'unsolved'),
    ([('f2_fd1_c2_c3', 'unsolved', True), ('f2_fd2_c4_c5', 'feasible', False)], 'function2', True, 'unsolved'),
    ([('f2_fd1_c2_c3', 'solved', True), ('f2_fd2_c4_c5', 'feasible', False)], 'function2', True, 'solved'),
    ([('f2_fd1_c2_c3', 'solved', True), ('f2_fd2_c4_c5', 'unfeasible', False)], 'function2', True, 'solved'),
    ([], 'function1', False, 'feasible'),
    ([('f2_fd1_c2_c3', 'implicit configuration error', False)], 'function2', False, 'feasible'),
    ([('f2_fd1_c2_c3', 'implicit configuration error', False), ('f2_fd2_c4_c5', 'unfeasible', False)], 'function2', False, 'feasible'),
    ([('f2_fd1_c2_c3', 'feasible', False), ('f2_fd2_c4_c5', 'unfeasible', False)], 'function2', False, 'feasible'),
    ([('f2_fd1_c2_c3', 'feasible', False), ('f2_fd2_c4_c5', 'feasible', False)], 'function2', False, 'feasible'),
])
def test_function_status_inference(
     kb_interface, fds, f_name, f_required, f_status):
    for fd in fds:
        kb_interface.update_attribute_in_thing(
            'function-design',
            'function-design-name',
            fd[0],
            'function-design-status',
            fd[1]
        )
        # if fd[2] == True:
        kb_interface.update_attribute_in_thing(
            'function-design',
            'function-design-name',
            fd[0],
            'is-selected',
            fd[2])
    kb_interface.update_attribute_in_thing(
        'Function',
        'function-name',
        f_name,
        'is-required',
        f_required)
    f_status_inferred = kb_interface.fetch_attribute_from_thing(
        'Function',
        [('function-name', f_name)],
        'function-status')
    assert all(x in f_status_inferred for x in [f_status]) is True


@pytest.mark.parametrize("functions, t_name, t_required, t_status", [
    ([('function1', 'unfeasible')], 'action1', False, 'unfeasible'),
    ([('function1', 'unsolved'), ('function2', 'unfeasible')], 'action1', True, 'unfeasible'),
    ([('function1', 'configuration error'), ('function2', 'unfeasible')], 'action1', True, 'unfeasible'),
    ([('function1', 'configuration error')], 'action1', True, 'implicit configuration error'),
    ([('function1', 'configuration error'), ('function2', 'feasible')], 'action1', True, 'implicit configuration error'),
    ([('function1', 'configuration error'), ('function2', 'implicit configuration error')], 'action1', True, 'implicit configuration error'),
    ([('function1', 'implicit configuration error')], 'action1', True, 'implicit configuration error'),
    ([('function1', 'configuration error'), ('function2', 'solved')], 'action1', True, 'implicit configuration error'),
    ([('function1', 'configuration error'), ('function2', 'unsolved')], 'action1', True, 'implicit configuration error'),
    ([('function1', 'unsolved')], 'action1', True, 'unsolved'),
    ([('function1', 'unsolved'), ('function2', 'solved')], 'action1', True, 'unsolved'),
    ([('function1', 'unsolved'), ('function2', 'unsolved')], 'action1', True, 'unsolved'),
    ([('function1', 'feasible')], 'action1', False, 'feasible'),
    ([('function1', 'unsolved')], 'action1', False, 'feasible'),
    ([('function1', 'configuration error'), ('function2', 'unsolved')], 'action1', False, 'feasible'),
    ([('function1', 'configuration error'), ('function2', 'implicit configuration error')], 'action1', False, 'feasible'),
    ([('function1', 'feasible'), ('function2', 'feasible')], 'action1', False, 'feasible'),
    ([('function1', 'solved'), ('function2', 'solved')], 'action1', True, 'solved'),
])
def test_action_status_inference(
     kb_interface, functions, t_name, t_required, t_status):
    for f in functions:
        kb_interface.update_attribute_in_thing(
            'Function',
            'function-name',
            f[0],
            'function-status',
            f[1]
        )
    kb_interface.update_attribute_in_thing(
        'Action',
        'action-name',
        t_name,
        'is-required',
        t_required)
    t_status_inferred = kb_interface.fetch_attribute_from_thing(
        'Action',
        [('action-name', t_name)],
        'action-status')
    assert all(x in t_status_inferred for x in [t_status]) is True
