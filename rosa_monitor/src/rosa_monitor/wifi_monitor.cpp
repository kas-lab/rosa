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

#include "rosa_monitor/wifi_monitor.hpp"

namespace rosa_monitor {

	WifiMonitor::WifiMonitor() : rclcpp::Node("wifi_mon")
	{
		iface_     = declare_parameter<std::string>("iface", "wlan0");
		period_ms_ = declare_parameter<int>("period_ms", 1000);
		ema_alpha_     = declare_parameter<double>("ema_alpha", 0.2);   // 0..1

		pub_ = create_publisher<diagnostic_msgs::msg::DiagnosticArray>("wifi/status", rclcpp::QoS(1).best_effort());

		prev_rx_ = read_uint64(sys_path("rx_bytes"));
		prev_tx_ = read_uint64(sys_path("tx_bytes"));
		last_t_  = this->get_clock()->now();

		ema_rx_bps_.reset();
		ema_tx_bps_.reset();

		timer_ = create_wall_timer(std::chrono::milliseconds(period_ms_), [this]{ tick(); });
	}

	std::optional<std::pair<double, double>> WifiMonitor::read_wireless() {
		std::ifstream f("/proc/net/wireless");
		if (!f) return std::nullopt;

		std::string line;
		std::getline(f, line); // header 1
		std::getline(f, line); // header 2
		while (std::getline(f, line)) {
			auto pos = line.find(iface_ + ":");
			if (pos == std::string::npos) continue;
			// Format (example):
			// "  wlan0: 0000   54.  -46.  -256        0      0      0      0      0        0"
			double status=0.0, linkv=0.0, level=0.0, noise=0.0;
			if (std::sscanf(line.c_str() + pos, "%*[^:]: %lf %lf %lf %lf", &status, &linkv, &level, &noise) >= 3) {
				return std::make_pair(level, linkv);
			}
    	}
    	return std::nullopt;
  	}

	// One EMA step with lazy initialization
	double WifiMonitor::ema_step(const double &sample, const double &alpha, std::optional<double> &state) {
		if (!state.has_value()) {
			state = sample;          // initialize from first sample
		} else {
			state = alpha * sample + (1.0 - alpha) * state.value();
		}
		return state.value();
	}

	void WifiMonitor::tick() {
		// elapsed time
		auto t = this->get_clock()->now();
		const double dt = (t - last_t_).seconds();
		if (dt <= 0.0) return;
		last_t_ = t;

		// counters -> raw throughput
		const uint64_t rx = read_uint64(sys_path("rx_bytes"));
		const uint64_t tx = read_uint64(sys_path("tx_bytes"));
		const double rx_bps = (rx >= prev_rx_) ? (rx - prev_rx_) * 8.0 / dt : 0.0;
		const double tx_bps = (tx >= prev_tx_) ? (tx - prev_tx_) * 8.0 / dt : 0.0;
		prev_rx_ = rx; prev_tx_ = tx;

		// EMA smoothing
		const double rx_bps_ema = ema_step(rx_bps, std::clamp(ema_alpha_, 0.0, 1.0), ema_rx_bps_);
		const double tx_bps_ema = ema_step(tx_bps, std::clamp(ema_alpha_, 0.0, 1.0), ema_tx_bps_);

		// signal/quality (best-effort)
		auto wireless_data = read_wireless();
		double sig_dbm = NAN, link = NAN;
		if (wireless_data.has_value()) {
			sig_dbm = wireless_data->first;
			link = wireless_data->second;
		}

		diagnostic_msgs::msg::DiagnosticStatus st;
		st.name = "wifi/" + iface_;
		st.level = diagnostic_msgs::msg::DiagnosticStatus::OK;
		st.message = "OK";
		st.values.reserve(6);

		diagnostic_msgs::msg::KeyValue kv;
		kv.key = "signal_dbm"; kv.value = std::to_string(sig_dbm);
		st.values.push_back(kv);

		diagnostic_msgs::msg::KeyValue kv2;
		kv2.key = "link_quality_raw"; kv2.value = std::to_string(link);
		st.values.push_back(kv2);

		diagnostic_msgs::msg::KeyValue kv3;
		kv3.key = "rx_bps_raw"; kv3.value = std::to_string((long long)rx_bps);
		st.values.push_back(kv3);

		diagnostic_msgs::msg::KeyValue kv4;
		kv4.key = "tx_bps_raw"; kv4.value = std::to_string((long long)tx_bps);
		st.values.push_back(kv4);

		diagnostic_msgs::msg::KeyValue kv5;
		kv5.key = "rx_bps_ema"; kv5.value = std::to_string((long long)rx_bps_ema);
		st.values.push_back(kv5);

		diagnostic_msgs::msg::KeyValue kv6;
		kv6.key = "tx_bps_ema"; kv6.value = std::to_string((long long)tx_bps_ema);
		st.values.push_back(kv6);

		diagnostic_msgs::msg::DiagnosticArray arr;
		arr.header.stamp = t;
		arr.status.push_back(std::move(st));
		pub_->publish(std::move(arr));
  	}

}  // namespace rosa_monitor

