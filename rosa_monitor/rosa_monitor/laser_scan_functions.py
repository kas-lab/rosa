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
import math
import numpy as np
from rclpy.duration import Duration
from sensor_msgs.msg import LaserScan
import tf_transformations  # provides quaternion_matrix()
from rosa_monitor.utils import _get_tf_buffer_for_node
from rosa_monitor.utils import _parse_bool
from rosa_monitor.utils import _parse_float

def get_nearest_laser_scan_distance(_, msg):
    return min(
        (r for r in msg.ranges if not math.isinf(r) and not math.isnan(r)),
        default=float('inf')
    )

def get_nearest_scan_distance_in_base(
    node,
    scan: LaserScan,
    target_frame: str = "base_link",
    timeout_sec: str = "0.1",
    planar: str = "True",
) -> float:
    """
    Compute the nearest valid LaserScan hit distance measured in `target_frame`,
    given only string parameters (for model-transformation constraints).

    Args:
        node: rclpy Node that owns the TF buffer.
        scan: LaserScan message.
        target_frame: target frame name (e.g., 'base_link').
        timeout_sec: TF lookup timeout, as string (e.g., '0.1').
        planar: 'True'/'False' as string. If True -> sqrt(x^2+y^2); else 3D distance.

    Returns:
        Nearest distance in meters (float('inf') if no valid reading or TF unavailable).
    """
    # Parse string args
    timeout_f = _parse_float(timeout_sec)
    planar_b = _parse_bool(planar)

    tf_buffer = _get_tf_buffer_for_node(node)

    # Lookup transform at the scan time
    try:
        tf_msg = tf_buffer.lookup_transform(
            target_frame,
            scan.header.frame_id,
            scan.header.stamp,
            Duration(seconds=timeout_f),
        ).transform
    except Exception as ex:
        # Optional: node.get_logger().warn(f"TF lookup failed: {ex}")
        return float("inf")

    # Build homogeneous transform T from quaternion + translation
    quat = [tf_msg.rotation.x, tf_msg.rotation.y, tf_msg.rotation.z, tf_msg.rotation.w]
    trans = [tf_msg.translation.x, tf_msg.translation.y, tf_msg.translation.z]

    T = tf_transformations.quaternion_matrix(quat)  # 4x4; upper-left is R
    T[0:3, 3] = trans                                # inject translation

    # Iterate rays once; keep min distance
    angle = scan.angle_min
    inc = scan.angle_increment
    rmin, rmax = scan.range_min, scan.range_max

    best = float("inf")

    for r in scan.ranges:
        # Filter invalid readings early
        if math.isnan(r) or math.isinf(r) or r < rmin or r > rmax:
            angle += inc
            continue

        # Endpoint in laser frame (planar scan => z=0)
        lx = r * math.cos(angle)
        ly = r * math.sin(angle)

        # Homogeneous point in laser frame
        vec = np.array([lx, ly, 0.0, 1.0], dtype=float)

        # Transform to target frame
        bx, by, bz, _ = T @ vec

        # Planar or full 3D distance in target frame
        d = math.hypot(bx, by) if planar_b else math.sqrt(bx*bx + by*by + bz*bz)

        if d < best:
            best = d

        angle += inc

    return best