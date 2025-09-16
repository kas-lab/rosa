#!/usr/bin/env python3

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

"""
ROS 2 Topic Auditor.

Inspect all active ROS 2 topics, list publishers/subscribers with QoS,
measure message frequency and bandwidth by sampling live traffic, and
write results to a CSV file.

Usage:
    ./ros2_topic_audit.py
    ./ros2_topic_audit.py --duration 10 --include-hidden \
        --filter '^(?:/scan|/camera/.*)' -o /tmp/audit.csv
"""

from __future__ import annotations

import argparse
import csv
import math
import re
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import rclpy
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import Executor
from rclpy.executors import SingleThreadedExecutor
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node
from rclpy.qos import (
    QoSDurabilityPolicy,
    QoSHistoryPolicy,
    QoSProfile,
    QoSReliabilityPolicy,
)
from rclpy.serialization import serialize_message
from rclpy.topic_endpoint_info import TopicEndpointInfo
from rosidl_runtime_py.utilities import get_message

DEFAULT_EXCLUDES = {'/rosout', '/parameter_events'}


def qos_to_dict(q: QoSProfile) -> Dict[str, object]:
    """
    Convert a QoSProfile into a dictionary of its fields.

    Args:
        q: The QoSProfile instance.

    Returns:
        A dictionary with human-readable QoS parameters.
    """
    return {
        'history': q.history.name if hasattr(q.history, 'name') else str(q.history),
        'depth': q.depth,
        'reliability': (
            q.reliability.name if hasattr(q.reliability, 'name') else str(q.reliability)
        ),
        'durability': (
            q.durability.name if hasattr(q.durability, 'name') else str(q.durability)
        ),
        'deadline_ns': getattr(q.deadline, 'nanoseconds', None),
        'lifespan_ns': getattr(q.lifespan, 'nanoseconds', None),
        'liveliness': (
            q.liveliness.name if hasattr(q.liveliness, 'name') else str(q.liveliness)
        ),
        'lease_duration_ns': getattr(q.liveliness_lease_duration, 'nanoseconds', None),
    }


def qos_to_short_str(q: QoSProfile) -> str:
    """
    Convert a QoSProfile into a short semicolon-separated string.

    Args:
        q: The QoSProfile instance.

    Returns:
        Short string with key QoS parameters.
    """
    bits = [
        f"hist={q.history.name if hasattr(q.history, 'name') else q.history}",
        f'depth={q.depth}',
        f"rel={q.reliability.name if hasattr(q.reliability, 'name') else q.reliability}",
        f"dur={q.durability.name if hasattr(q.durability, 'name') else q.durability}",
    ]
    return ' & '.join(bits)

def get_full_node_name(namespace: str, name: str) -> str:
        return f'{namespace}/{name}' if namespace != '/' else f'/{name}'

@dataclass
class EndpointSummary:
    """
    Summary of a publisher or subscriber endpoint.

    Attributes:
        node_name: Name of the node.
        node_ns: Namespace of the node.
        qos: Short QoS summary string.
    """

    node_name: str
    node_ns: str
    qos: str

    def get_full_node_name(self) -> str:
        return get_full_node_name(self.node_ns, self.node_name)


@dataclass
class TopicStats:
    """
    Runtime statistics for a topic, collected by sampling messages.

    Attributes:
        count: Total number of messages received.
        bytes_total: Cumulative size of all serialized messages.
        ts: List of timestamps when each message was received.
    """

    count: int = 0
    bytes_total: int = 0
    ts: List[float] = field(default_factory=list)

    def add(self, stamp: float, size: int) -> None:
        """Add a measurement sample with timestamp and message size."""
        self.count += 1
        self.bytes_total += size
        self.ts.append(stamp)

    def window_duration(self) -> float:
        """Duration between first and last arrival timestamp (s)."""
        if len(self.ts) < 2:
            return 0.0
        return self.ts[-1] - self.ts[0]

    def freq_from_samples(self) -> Optional[float]:
        """
        Frequency computed from arrivals only:
        (N-1) / (t_last - t_first). Returns None if <2 samples.
        """
        if len(self.ts) < 2:
            return None
        dur = self.window_duration()
        return (len(self.ts) - 1) / dur if dur > 0.0 else None

    def period_stats(self) -> Tuple[Optional[float], Optional[float]]:
        """
        Compute mean and standard deviation of inter-arrival times.

        Returns:
            A tuple (mean_period, std_period) in seconds, or (None, None)
            if not enough data is available.
        """
        if len(self.ts) < 2:
            return None, None
        periods = [t2 - t1 for t1, t2 in zip(self.ts[:-1], self.ts[1:])]
        mean = sum(periods) / len(periods)
        var = sum((p - mean) ** 2 for p in periods) / len(periods)
        return mean, math.sqrt(var)

    def avg_size(self) -> Optional[float]:
        """Compute average message size in bytes."""
        if self.count == 0:
            return None
        return self.bytes_total / self.count


# class TopicAuditNode(Node):
#     """
#     ROS 2 node for auditing topics and endpoints.

#     Methods:
#         endpoints(topic): Return publishers and subscribers for a topic.
#     """

#     def __init__(self, name: str = 'topic_audit') -> None:
#         """Initialize the audit node."""
#         super().__init__(name)
#         # self.sub_cb_group = MutuallyExclusiveCallbackGroup()
#         # self.sub_cb_group = ReentrantCallbackGroup()

#     def endpoints(
#         self, topic: str
#     ) -> Tuple[List[TopicEndpointInfo], List[TopicEndpointInfo]]:
#         """Return publisher and subscriber endpoint info for a topic."""
#         pubs = self.get_publishers_info_by_topic(topic)
#         self.get_logger().info(f'[{topic}] has pubs [{[get_full_node_name(p.node_namespace, p.node_name) for p in pubs]}]')
#         subs = self.get_subscriptions_info_by_topic(topic)
#         return pubs, subs


def choose_subscription_qos(
    pub_infos: List[TopicEndpointInfo],
) -> QoSProfile:
    """
    Choose a QoSProfile for measuring a topic based on its publishers.

    Strategy:
        * If any publisher is RELIABLE, subscribe RELIABLE.
        * Otherwise, subscribe BEST_EFFORT.
        * Always use VOLATILE durability and keep last 10 samples.

    Args:
        pub_infos: List of publisher endpoint infos.

    Returns:
        QoSProfile suitable for receiving messages from the publishers.
    """
    any_reliable = any(
        info.qos_profile.reliability == QoSReliabilityPolicy.RELIABLE
        for info in pub_infos
    )
    reliability = (
        QoSReliabilityPolicy.RELIABLE
        if any_reliable
        else QoSReliabilityPolicy.BEST_EFFORT
    )
    return QoSProfile(
        history=QoSHistoryPolicy.KEEP_LAST,
        depth=50,
        reliability=reliability,
        durability=QoSDurabilityPolicy.VOLATILE,
    )

def get_endpoints(
        node, topic: str
    ) -> Tuple[List[TopicEndpointInfo], List[TopicEndpointInfo]]:
        """Return publisher and subscriber endpoint info for a topic."""
        pubs = node.get_publishers_info_by_topic(topic)
        node.get_logger().info(f'[{topic}] has pubs [{[get_full_node_name(p.node_namespace, p.node_name) for p in pubs]}]')
        subs = node.get_subscriptions_info_by_topic(topic)
        return pubs, subs

def endpoint_summaries(
    infos: List[TopicEndpointInfo],
) -> List[EndpointSummary]:
    """
    Convert endpoint infos into compact summaries.

    Args:
        infos: List of TopicEndpointInfo.

    Returns:
        List of EndpointSummary objects.
    """
    out: List[EndpointSummary] = []
    for info in infos:
        out.append(
            EndpointSummary(
                node_name=info.node_name,
                node_ns=info.node_namespace,
                qos=qos_to_short_str(info.qos_profile),
            )
        )
    return out


# def discover_topics(node, executor, stable_threshold: int = 3, timeout_s: float = 2.0) -> List[Tuple[str, List[str]]]:
def discover_topics(stable_threshold: int = 3, timeout_s: float = 2.0) -> List[Tuple[str, List[str]]]:
    """Spin briefly so ROS graph discovery converges, then return topics."""
    node = Node('discover_topics_node')
    executor = SingleThreadedExecutor()
    executor.add_node(node)

    end = time.monotonic() + timeout_s
    last_len = -1
    stable = 0
    topics = []
    while time.monotonic() < end:
        executor.spin_once(timeout_sec=0.1)
        now = node.get_topic_names_and_types(no_demangle=False)
        if len(now) == last_len:
            stable += 1
            if stable >= stable_threshold:  # a few consecutive stable reads
                topics = now
                break
        else:
            stable = 0
            last_len = len(now)
    if not topics:  # fallback if we left by timeout
        topics = node.get_topic_names_and_types(no_demangle=False)

    # Teardown: remove node from executor BEFORE destroying entities.
    executor.spin_once(timeout_sec=0.0)
    executor.remove_node(node)

    time.sleep(0.5)

    node.destroy_node()

    return topics

def measure_topic(
    # node: TopicAuditNode,
    # executor: Executor,
    topic: str,
    type_str: str,
    duration_s: float,
    pub_infos: List[TopicEndpointInfo],
    executor_spin_time_out: float = 0.001
) -> TopicStats:
    """
    Subscribe to a topic temporarily and measure statistics.

    Args:
        topic: Topic name.
        type_str: ROS 2 message type as string.
        duration_s: Sampling duration in seconds.
        pub_infos: Publisher endpoint infos for choosing QoS.

    Returns:
        TopicStats with frequency, bandwidth, and timing statistics.
    """
    stats = TopicStats()

    node = Node('topic_measurement_node')
    try:
        msg_cls = get_message(type_str)
    except Exception as exc:
        node.get_logger().warn(
            f'Cannot resolve type for {topic} ({type_str}): {exc}'
        )
        return stats

    qos = choose_subscription_qos(pub_infos)

    def cb(msg) -> None:
        t = time.perf_counter()
        try:
            payload = serialize_message(msg)
            stats.add(t, len(payload))
        except Exception:
            stats.add(t, 0)

    # Should we use a MutuallyExclusiveCallbackGroup ?
    meas_group = ReentrantCallbackGroup()
    sub = node.create_subscription(
        msg_cls, topic, cb, qos, callback_group=meas_group
    )

    # Private executor so nothing else can touch this wait-set.
    # Should we use a MultiThreadedExecutor ?
    mexec = SingleThreadedExecutor()
    mexec.add_node(node)

    try:
        t_first: Optional[float] = None
        end_time: Optional[float] = None
        safety_deadline = time.perf_counter() + max(2.0, duration_s * 2.0)

        while True:
            mexec.spin_once(timeout_sec=executor_spin_time_out)

            if stats.count > 0 and t_first is None:
                t_first = stats.ts[0]
                end_time = t_first + duration_s

            now = time.perf_counter()
            if (end_time is not None and now >= end_time) or now >= safety_deadline:
                break
    finally:
        # Teardown: remove node from executor BEFORE destroying entities.
        mexec.spin_once(timeout_sec=0.0)
        mexec.remove_node(node)

        # Tiny guard to ensure any in-flight callback returns to idle.
        # (SingleThreadedExecutor makes this essentially a no-op.)
        time.sleep(max(0.5 * executor_spin_time_out, 0.001))

        try:
            node.destroy_subscription(sub)
        finally:
            node.destroy_node()

    return stats


def main() -> None:
    """
    CLI entry point for the ROS 2 Topic Auditor script.

    Parse CLI arguments, initialize a ROS 2 node, audit all topics,
    measure traffic for active publishers, and write results to a CSV.
    """
    parser = argparse.ArgumentParser(
        description=(
            'Audit ROS 2 topics: endpoints + QoS + bandwidth + frequency -> CSV'
        )
    )
    parser.add_argument(
        '-d',
        '--duration',
        type=float,
        default=10.0,
        help='Sampling duration per topic in seconds',
    )
    parser.add_argument(
        '-o',
        '--output',
        type=str,
        default='topics_audit.csv',
        help='CSV output file',
    )
    parser.add_argument(
        '--filter',
        type=str,
        default=None,
        help='Regex to include only matching topics',
    )
    parser.add_argument(
        '--exclude',
        type=str,
        default=None,
        help='Regex to exclude matching topics',
    )
    parser.add_argument(
        '--skip-quiet',
        action='store_true',
        help='Skip topics with zero publishers',
    )
    parser.add_argument(
        '--discovery-timeout', type=float, default=2.0,
        help='Seconds to wait for graph discovery before snapshotting.',
    )
    parser.add_argument(
        '--spin-timeout', type=float, default=0.001,
        help='spin_once timeout (s) during measurement; lower = lower callback latency',
    )

    args = parser.parse_args()

    include_re = re.compile(args.filter) if args.filter else None
    exclude_re = re.compile(args.exclude) if args.exclude else None

    rclpy.init()
    try:
        start_time = time.monotonic()
        # node = TopicAuditNode()
        node = Node('topic_audit_node')
        executor = MultiThreadedExecutor()
        executor.add_node(node)

        topics = discover_topics(
            # node=node,
            # executor=executor,
            stable_threshold=3,
            timeout_s=args.discovery_timeout
        )
        node.get_logger().info(f'{len(topics)} were discovered')
        rows: List[Dict[str, object]] = []

        for topic, types in topics:
            if not types:
                continue

            type_str = types[0]

            if topic in DEFAULT_EXCLUDES:
                continue
            if include_re and not include_re.search(topic):
                continue
            if exclude_re and exclude_re.search(topic):
                continue

            # pubs, subs = node.endpoints(topic)
            pubs, subs = get_endpoints(node, topic)
            if args.skip_quiet and len(pubs) == 0:
                continue

            pub_summ = endpoint_summaries(pubs)
            sub_summ = endpoint_summaries(subs)

            hz: Optional[float] = None
            bw_bps: Optional[float] = None
            avg_sz: Optional[float] = None
            mean_period: Optional[float] = None
            std_period: Optional[float] = None

            if pubs:
                # stats = measure_topic(
                #     node, executor, topic, type_str, args.duration, pubs, args.spin_timeout
                # )
                stats = measure_topic(
                    topic, type_str, args.duration, pubs, args.spin_timeout
                )
                hz = stats.freq_from_samples()
                avg_sz = stats.avg_size()
                bw_bps = (stats.bytes_total / stats.window_duration()) if stats.window_duration() > 0 else None
                mean_period, std_period = stats.period_stats()

            rows.append(
                {
                    'topic': topic,
                    'type': type_str,
                    'num_publishers': len(pubs),
                    'num_subscribers': len(subs),
                    'active': (len(pubs) > 0 and len(subs) > 0),
                    'publishers': ' | '.join(
                        p.get_full_node_name() for p in pub_summ
                    ) or '',
                    'publishers_qos': ' | '.join(p.qos for p in pub_summ) or '-',
                    'subscribers': ' | '.join(
                        s.get_full_node_name() for s in sub_summ
                    ) or '',
                    'subscribers_qos': ' | '.join(s.qos for s in sub_summ) or '-',
                    'freq_hz': f'{hz:.3f}' if hz is not None else '-',
                    'effective_window_s': f'{stats.window_duration():.6f}' if stats.window_duration() > 0 else '-',
                    'avg_msg_bytes': f'{avg_sz:.1f}' if avg_sz is not None else '-',
                    'bandwidth_Bps': f'{bw_bps:.1f}' if bw_bps is not None else '-',
                    'mean_period_s': (
                        f'{mean_period:.6f}' if mean_period is not None else '-'
                    ),
                    'std_period_s': (
                        f'{std_period:.6f}' if std_period is not None else '-'
                    ),
                    'sample_duration_s': args.duration if pubs else 0.0,
                    'real_time_stamps': stats.ts,
                }
            )

        fieldnames = [
            'topic',
            'active',
            'num_publishers',
            'num_subscribers',
            'freq_hz',
            'effective_window_s',
            'avg_msg_bytes',
            'bandwidth_Bps',
            'mean_period_s',
            'std_period_s',
            'sample_duration_s',
            'type',
            'publishers',
            'publishers_qos',
            'subscribers',
            'subscribers_qos',
            'real_time_stamps',
        ]
        with open(args.output, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for row in rows:
                writer.writerow(row)

        node.get_logger().info(f'Wrote {len(rows)} topics to {args.output} in {time.monotonic() - start_time} seconds')
    finally:
        rclpy.shutdown()


if __name__ == '__main__':
    main()
