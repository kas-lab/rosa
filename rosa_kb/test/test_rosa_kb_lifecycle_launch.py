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
"""Focused tests for ROSA KB launch lifecycle wiring."""

import importlib.util
from pathlib import Path

from launch_ros.actions import LifecycleNode


def _load_launch_module(path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_rosa_kb_launch_uses_lifecycle_node(monkeypatch):
    """ROSA KB should be launch-managed as a lifecycle node."""
    package_root = Path(__file__).resolve().parents[1]

    launch_file = package_root / 'launch' / 'rosa_kb.launch.py'
    module = _load_launch_module(launch_file)
    monkeypatch.setattr(
        module,
        'get_package_share_directory',
        lambda package_name: str(package_root),
    )

    description = module.generate_launch_description()
    lifecycle_nodes = [
        entity for entity in description.entities
        if isinstance(entity, LifecycleNode)
    ]

    assert len(lifecycle_nodes) == 1
