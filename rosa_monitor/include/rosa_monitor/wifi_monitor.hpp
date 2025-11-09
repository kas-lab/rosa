// Copyright 2025 Gustavo Rezende Silva
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//     http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

#include <rclcpp/rclcpp.hpp>
#include <diagnostic_msgs/msg/diagnostic_array.hpp>
#include <fstream>
#include <string>
#include <chrono>
#include <cmath>
#include <cstdio>

using namespace std::chrono_literals;

namespace rosa_monitor {

uint64_t read_uint64(const std::string &path) {
    std::ifstream f(path);
    uint64_t v = 0;
    if (f) f >> v;
    return v;
}

class WifiMonitor : public rclcpp::Node {
public:
 	WifiMonitor();

private:
	inline std::string sys_path(const std::string &name) const {
		return "/sys/class/net/" + iface_ + "/statistics/" + name;
	}

  	// Returns true on success; fills sig_dbm and link (driver-dependent scale, often 0..70)
	std::optional<std::pair<double, double>> read_wireless();

	// One EMA step with lazy initialization
	double ema_step(const double &sample, const double &alpha, std::optional<double> &state);

	void tick();

	// Members
	rclcpp::Publisher<diagnostic_msgs::msg::DiagnosticArray>::SharedPtr wifi_diagnostics_pub_;
	rclcpp::TimerBase::SharedPtr wifi_diagnostics_timer_;
	std::string wifi_diagnostics_topic_{"diagnostics"};

	std::string iface_;
	int period_ms_;
	rclcpp::Time last_t_;
	uint64_t prev_rx_{0}, prev_tx_{0};

	double ema_alpha_;
	std::optional<double> ema_rx_bps_;
	std::optional<double> ema_tx_bps_;
};

}  // namespace rosa_monitor