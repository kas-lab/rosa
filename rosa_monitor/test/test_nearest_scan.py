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
import logging
import math

from builtin_interfaces.msg import Time
from geometry_msgs.msg import TransformStamped
import pytest
from rosa_monitor.laser_scan_functions import get_nearest_scan_distance_in_base
from sensor_msgs.msg import LaserScan


# --------------------------
# Minimal Node + Fake TF
# --------------------------


class DummyNode:
    """
    Bare-minimum stand-in for rclpy.node.Node.

    Tests will inject `_nearestscan_tf_buffer` on instances of this.
    """

    def get_logger(self):
        return logging.getLogger()


class DummyTFBuffer:
    """
    Minimal stand-in for tf2_ros.Buffer that returns a fixed transform.

    Configure translation and yaw (about Z). Set fail=True to simulate
    lookup failure.
    """

    def __init__(self, tx=0.0, ty=0.0, tz=0.0, yaw_rad=0.0, fail=False):
        self.tx = tx
        self.ty = ty
        self.tz = tz
        self.yaw = yaw_rad
        self.fail = fail

    def lookup_transform(self, target, source, stamp, timeout):
        if self.fail:
            raise RuntimeError('TF lookup failed (simulated)')

        t = TransformStamped()
        t.header.stamp = stamp
        t.header.frame_id = target
        t.child_frame_id = source

        t.transform.translation.x = self.tx
        t.transform.translation.y = self.ty
        t.transform.translation.z = self.tz

        # yaw rotation about Z
        half = 0.5 * self.yaw
        t.transform.rotation.x = 0.0
        t.transform.rotation.y = 0.0
        t.transform.rotation.z = math.sin(half)
        t.transform.rotation.w = math.cos(half)

        return t


# --------------------------
# Helpers
# --------------------------

def make_scan(ranges,
              angle_min=-math.pi / 4,
              angle_inc=math.pi / 4,
              frame_id='laser',
              rmin=0.0,
              rmax=100.0,
              stamp_sec=0):
    scan = LaserScan()
    scan.header.frame_id = frame_id
    scan.header.stamp = Time(sec=stamp_sec)
    scan.angle_min = angle_min
    scan.angle_increment = angle_inc
    scan.range_min = rmin
    scan.range_max = rmax
    scan.ranges = list(ranges)
    return scan


# ------------
# Test cases
# ------------

def test_identity_transform_planar_min_is_min_range():
    # Angles: -45°, 0°, +45°. Ranges: 3, 1, 2 -> min 1.0 at 0°
    node = DummyNode()
    node._nearestscan_tf_buffer = DummyTFBuffer()  # identity
    scan = make_scan([3.0, 1.0, 2.0])

    d = get_nearest_scan_distance_in_base(
        node, scan, 'base_link', '0.1', 'True')
    assert pytest.approx(d, 1.0)


def test_translation_x_only_planar():
    # Middle beam 1.0 m at 0°; translate +1.0 in x -> (2,0,0) => distance 2.0
    node = DummyNode()
    node._nearestscan_tf_buffer = DummyTFBuffer(tx=1.0)
    scan = make_scan([10.0, 1.0, 10.0])

    d = get_nearest_scan_distance_in_base(
        node, scan, 'base_link', '0.1', 'True')
    assert pytest.approx(d, 2.0)


def test_rotation_90deg_about_z_planar():
    # All beams 1.0, yaw +90°: laser +X maps to base +Y; nearest stays 1.0
    node = DummyNode()
    node._nearestscan_tf_buffer = DummyTFBuffer(yaw_rad=math.pi / 2)
    scan = make_scan([1.0, 1.0, 1.0])

    d = get_nearest_scan_distance_in_base(
        node, scan, 'base_link', '0.1', 'True')
    assert pytest.approx(d, 1.0)


def test_invalid_values_are_filtered():
    # Only 2.5 is valid (others are inf/nan/out of range)
    node = DummyNode()
    node._nearestscan_tf_buffer = DummyTFBuffer()
    scan = make_scan(
        ranges=[math.inf, math.nan, 0.05, 2.5, 200.0],
        rmin=0.1,   # 0.05 invalid
        rmax=50.0   # 200 invalid
    )

    d = get_nearest_scan_distance_in_base(
        node, scan, 'base_link', '0.2', 'True')
    assert pytest.approx(d, 2.5)


def test_no_valid_readings_returns_inf():
    node = DummyNode()
    node._nearestscan_tf_buffer = DummyTFBuffer()
    scan = make_scan(ranges=[math.inf, math.nan, 0.05], rmin=0.1, rmax=0.09)

    d = get_nearest_scan_distance_in_base(
        node, scan, 'base_link', '0.1', 'True')
    assert math.isinf(d)


def test_tf_lookup_failure_returns_inf():
    node = DummyNode()
    node._nearestscan_tf_buffer = DummyTFBuffer(fail=True)
    scan = make_scan([1.0, 2.0, 3.0])

    d = get_nearest_scan_distance_in_base(
        node, scan, 'base_link', '0.1', 'True')
    assert math.isinf(d)


def test_full_3d_distance_changes_with_height():
    # Laser 0.5 m above base_link (tz=+0.5), middle beam 1.0 @ 0°
    node = DummyNode()
    node._nearestscan_tf_buffer = DummyTFBuffer(tz=0.5)
    scan = make_scan([10.0, 1.0, 10.0])

    d3 = get_nearest_scan_distance_in_base(
        node, scan, 'base_link', '0.1', 'False')
    assert pytest.approx(d3, math.sqrt(1.0**2 + 0.5**2))

    dp = get_nearest_scan_distance_in_base(
        node, scan, 'base_link', '0.1', 'True')
    assert pytest.approx(dp, 1.0)


def test_string_parsing_variants_for_planar_true():
    node = DummyNode()
    node._nearestscan_tf_buffer = DummyTFBuffer()
    scan = make_scan([2.0, 1.0, 3.0])

    for val in ['true', 'TRUE', '1', 'Yes', 'on', 'TrUe']:
        d = get_nearest_scan_distance_in_base(
            node, scan, 'base_link', '0.05', val)
        assert pytest.approx(d, 1.0)
