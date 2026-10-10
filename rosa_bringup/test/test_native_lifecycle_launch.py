# Copyright 2026 KAS-lab
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
"""Focused tests for ROSA native lifecycle launch wiring."""

import importlib.util
from pathlib import Path

from launch.actions import IncludeLaunchDescription
from launch.actions import RegisterEventHandler

from launch_ros.actions import LifecycleTransition


def _load_launch_module(path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_rosa_bringup_uses_native_lifecycle_transitions(monkeypatch):
    """ROSA bringup should use launch_ros LifecycleTransition."""
    package_root = Path(__file__).resolve().parents[1]
    rosa_root = package_root.parents[1]

    def fake_share_directory(package_name):
        return str(rosa_root / package_name)

    launch_file = package_root / 'launch' / 'rosa_bringup.launch.py'
    module = _load_launch_module(launch_file)
    monkeypatch.setattr(
        module, 'get_package_share_directory', fake_share_directory)

    description = module.generate_launch_description()
    entities = list(description.entities)

    assert sum(
        isinstance(entity, IncludeLaunchDescription)
        for entity in entities) == 3
    assert any(isinstance(entity, LifecycleTransition) for entity in entities)
    assert any(isinstance(entity, RegisterEventHandler) for entity in entities)
    assert all(
        getattr(entity, 'node_name', None) != 'rosa_lc_manager'
        for entity in entities)
