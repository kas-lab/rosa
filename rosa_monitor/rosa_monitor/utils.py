# Copyright 2025 Gustavo Rezende Silva
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
import tf2_ros


def _parse_bool(s: str) -> bool:
    return str(s).strip().lower() in {'1', 'true', 'yes', 'y', 'on'}


def _parse_float(s: str) -> float:
    return float(s)


def _parse_int(s: str) -> int:
    return int(s)


def _get_tf_buffer_for_node(node) -> tf2_ros.Buffer:
    """
    Lazily attach a tf Buffer/Listener to the node, cached on the node instance.

    Avoids creating a new listener per call.
    """
    # attribute names chosen to be unlikely to clash
    if not hasattr(node, '_nearestscan_tf_buffer'):
        node._nearestscan_tf_buffer = tf2_ros.Buffer()
        node._nearestscan_tf_listener = tf2_ros.TransformListener(
            node._nearestscan_tf_buffer, node, spin_thread=True)
    return node._nearestscan_tf_buffer
