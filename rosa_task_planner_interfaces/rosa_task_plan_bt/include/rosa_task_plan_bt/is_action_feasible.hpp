// Copyright 2023 Gustavo Rezende Silva
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

#ifndef ROSA_TASK_PLAN_BT__IS_ACTION_FEASIBLE_HPP_
#define ROSA_TASK_PLAN_BT__IS_ACTION_FEASIBLE_HPP_

#include <chrono>
#include <string>

#include "behaviortree_cpp/behavior_tree.h"
#include "behaviortree_cpp/bt_factory.h"

#include "rclcpp/rclcpp.hpp"
#include "rosa_msgs/srv/action_query_array.hpp"

namespace rosa_task_plan_bt
{

template<class T>
class IsActionFeasible : public BT::ConditionNode
{
public:
  explicit IsActionFeasible(
    const std::string & xml_tag_name,
    const BT::NodeConfig & conf)
  : BT::ConditionNode(xml_tag_name, conf), cache_valid_(false)
  {
    node_ = config().blackboard->get<T>("node");

    selectable_actions_client_ =
      this->node_->template create_client<rosa_msgs::srv::ActionQueryArray>("/rosa_kb/action/selectable");
  };

  BT::NodeStatus tick() override
  {
    std::string action_name;
    getInput("action_name", action_name);

    double cache_ttl_s = 0.5;
    getInput("cache_ttl_s", cache_ttl_s);
    if (cache_valid_ && action_name == cached_action_name_) {
      const auto cache_age_s = std::chrono::duration<double>(
        std::chrono::steady_clock::now() - cached_at_).count();
      if (cache_age_s <= cache_ttl_s) {
        return cached_status_;
      }
    }

    double service_timeout_s = 6.0;
    getInput("service_timeout_s", service_timeout_s);

    if (!selectable_actions_client_->service_is_ready()) {
      RCLCPP_INFO(
        this->node_->template get_logger(),
        "/rosa_kb/action/selectable service not available");
      return update_cache(action_name, BT::NodeStatus::FAILURE);
    }

    auto request = std::make_shared<rosa_msgs::srv::ActionQueryArray::Request>();
    auto response = selectable_actions_client_->async_send_request(request);
    const auto timeout = std::chrono::duration_cast<std::chrono::nanoseconds>(
      std::chrono::duration<double>(service_timeout_s));

    if (response.wait_for(timeout) != std::future_status::ready) {
      RCLCPP_ERROR(
        this->node_->template get_logger(),
        "Timed out calling service actions selectable after %.3f seconds",
        service_timeout_s);
      return update_cache(action_name, BT::NodeStatus::FAILURE);
    }

    const auto selectable_actions = response.get()->actions;
    for (const auto & action: selectable_actions) {
      if (action.name == action_name) {
        return update_cache(action_name, BT::NodeStatus::SUCCESS);
      }
    }
    return update_cache(action_name, BT::NodeStatus::FAILURE);
  };

  static BT::PortsList providedPorts()
  {
    return BT::PortsList(
      {
        BT::InputPort<std::string>("action_name"),
        BT::InputPort<double>("service_timeout_s"),
        BT::InputPort<double>("cache_ttl_s"),
      });
  }

private:
  BT::NodeStatus update_cache(
    const std::string & action_name,
    BT::NodeStatus status)
  {
    cached_action_name_ = action_name;
    cached_status_ = status;
    cached_at_ = std::chrono::steady_clock::now();
    cache_valid_ = true;
    return status;
  }

  T node_;
  rclcpp::Client<rosa_msgs::srv::ActionQueryArray>::SharedPtr selectable_actions_client_;
  std::string cached_action_name_;
  BT::NodeStatus cached_status_;
  std::chrono::steady_clock::time_point cached_at_;
  bool cache_valid_;
};

} //namespace rosa_task_plan_bt

#endif  // ROSA_TASK_PLAN_BT__IS_ACTION_FEASIBLE_HPP_
