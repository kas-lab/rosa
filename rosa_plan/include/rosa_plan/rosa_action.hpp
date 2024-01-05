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

#ifndef ROSA_PLAN__ROSA_ACTION_HPP_
#define ROSA_PLAN__ROSA_ACTION_HPP_

#include "behaviortree_cpp/behavior_tree.h"
#include "behaviortree_cpp/bt_factory.h"

#include "rclcpp/rclcpp.hpp"
#include "rosa_msgs/srv/action_query.hpp"

namespace rosa_plan
{

class RosaAction : public BT::StatefulActionNode{

public:
  RosaAction(
      const std::string& name,
      const BT::NodeConfig & conf
  );

  BT::NodeStatus onStart() override;

  void onHalted() override;

  static BT::PortsList providedPorts()
  {
    return BT::PortsList(
      {
      });
  }

protected:
  rclcpp::Node::SharedPtr node_;
  rclcpp::Client<rosa_msgs::srv::ActionQuery>::SharedPtr action_req_client;
  void cancel_action();
};

}  // namespace rosa_plan

#endif  // ROSA_PLAN__ROSA_ACTION_HPP_
