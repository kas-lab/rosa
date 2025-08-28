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

def get_data_field(msg, field):
	return getattr(msg, field)

def get_nearest_laser_scan_distance(msg, *args):
    return min(
        (r for r in msg.ranges if not math.isinf(r) and not math.isnan(r)),
        default=float('inf')
    )