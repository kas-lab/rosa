[![documentation](https://github.com/kas-lab/rosa/actions/workflows/doc.yml/badge.svg)](https://github.com/kas-lab/rosa/actions/workflows/doc.yml) [![test](https://github.com/kas-lab/rosa/actions/workflows/test.yml/badge.svg)](https://github.com/kas-lab/rosa/actions/workflows/test.yml)

# ROSA

This repository contains ROSA, a knowledge-based framework for robotics self-adaptation.
ROSA is implemented as a ROS 2-based system, with its knowledge base implemented with TypeDB.

This is still a work in progress, therefore the repository is unstable.

This package was tested with ROS 2 Humble and TypeDB 2.27.0

**Note for Ubuntu 22.04 (Jammy) users:** If you're using ROS 2 Rolling on Ubuntu 22.04, please see the special rosdep setup instructions below to resolve missing dependency definitions.

## Installing

[Install ROS 2 Humble](https://docs.ros.org/en/humble/Installation.html)

Install TypeDB:

```Bash
sudo apt install software-properties-common apt-transport-https gpg
gpg --keyserver hkp://keyserver.ubuntu.com:80 --recv-key 17507562824cfdcc
gpg --export 17507562824cfdcc | sudo tee /etc/apt/trusted.gpg.d/vaticle.gpg > /dev/null
echo "deb https://repo.typedb.com/public/public-release/deb/ubuntu trusty main" | sudo tee /etc/apt/sources.list.d/vaticle.list > /dev/null

sudo apt update
sudo apt install openjdk-11-jre
sudo apt install typedb=2.27.0
pip3 install typedb-driver==2.27.0
```

Download ROSA:
```Bash
mkdir -p ~/rosa_ws/src
cd ~/rosa_ws/src
git clone git@github.com:kas-lab/rosa.git
vcs import . < rosa/rosa.repos
```

Install dependencies:
```Bash
cd ~/rosa_ws/
source /opt/ros/humble/setup.bash

# For Ubuntu 22.04 (Jammy) with ROS 2 Rolling, setup custom rosdep dependencies first:
./src/rosa/setup_rosdep.sh

rosdep install --from-paths src --ignore-src -r -y
```

Build ROSA:
```Bash
cd ~/rosa_ws/
source /opt/ros/humble/setup.bash
colcon build --symlink-install
```

### Troubleshooting Ubuntu 22.04 (Jammy) with ROS 2 Rolling

If you encounter rosdep errors about missing definitions for packages like `behaviortree_cpp`, `popf`, `launch_pytest`, `rclcpp_cascade_lifecycle`, or `tf_transformations`, you can manually add the custom rosdep source:

```Bash
# Create rosdep sources directory
mkdir -p ~/.ros/rosdep/sources.list.d/

# Add ROSA custom rosdep definitions
echo "yaml file://$(pwd)/src/rosa/rosdep.yaml" > ~/.ros/rosdep/sources.list.d/50-rosa.list

# Update rosdep database
rosdep update

# Now retry the rosdep install
rosdep install --from-paths src --ignore-src -r -y
```

## Running

Start typedb:

```Bash
typedb server
```

Run ROSA:
```Bash
ros2 launch rosa_bringup rosa_bringup.launch.py
```

## Example

An example of how to use ROSA can be found in the [suave_rosa repo](https://github.com/kas-lab/suave_rosa), where ROSA was applied to the [SUAVE examplar](https://github.com/kas-lab/suave).

## Configure ROSA to your use case

To use ROSA to solve self-adaptation in a ROS 2-based robotic system, the following steps must be followed:

**Step 1)** Model the use case conforming to ROSA's knowledge model: Model and implement the use case with TypeDB conforming to ROSA's knowledge model, capturing the robot's architecture, possible adaptations, the reasons to perform adaptation, and how to select adaptations. Check [suave.tql](https://github.com/kas-lab/suave_rosa/blob/main/config/suave.tql) for an example.

**Step 2)** Model use case mission: Model and implement how the robot's mission is accomplished as a BT, reusing [RosaAction](https://github.com/kas-lab/rosa/blob/main/rosa_plan/include/rosa_plan/rosa_action.hpp) action node. Check [SearchPipeline](https://github.com/kas-lab/suave_rosa/blob/main/include/suave_rosa/action_search_pipeline.hpp) for an example.

**Step 3)** Implement monitor nodes: Implement the monitor nodes required for the specific application. Check [WaterVisibilityObserver](https://github.com/kas-lab/suave/blob/main/suave/suave/water_visibility_observer.py)

**Step 4)** Setup ROS launch files:
Configure ROS launch files to start ROSA with the knowledge model files (from Step 1), the BT node (from Step 2), and the monitor nodes (from Step 3). Check [suave_rosa.launch.py](https://github.com/kas-lab/suave_rosa/blob/main/launch/suave_rosa.launch.py)

## Tests

Start typedb:

```Bash
typedb server
```

```Bash
colcon test --event-handlers console_cohesion+ --packages-select rosa_kb rosa_plan rosa_execute
```

## Citation

If you find this repository useful, please consider citing the [ROSA paper](https://www.frontiersin.org/journals/robotics-and-ai/articles/10.3389/frobt.2025.1531743/full):

```
@ARTICLE{10.3389/frobt.2025.1531743,
  
AUTHOR={Rezende Silva, Gustavo  and Päßler, Juliane  and Tapia Tarifa, S. Lizeth  and Johnsen, Einar Broch  and Hernández Corbato, Carlos },
         
TITLE={ROSA: a knowledge-based solution for robot self-adaptation},
        
JOURNAL={Frontiers in Robotics and AI},
        
VOLUME={Volume 12 - 2025},

YEAR={2025},

URL={https://www.frontiersin.org/journals/robotics-and-ai/articles/10.3389/frobt.2025.1531743},

DOI={10.3389/frobt.2025.1531743},

ISSN={2296-9144},

ABSTRACT={Autonomous robots must operate in diverse environments and handle multiple tasks despite uncertainties. This creates challenges in designing software architectures and task decision-making algorithms, as different contexts may require distinct task logic and architectural configurations. To address this, robotic systems can be designed as self-adaptive systems capable of adapting their task execution and software architecture at runtime based on their context. This paper introduces ROSA, a novel knowledge-based framework for RObot Self-Adaptation, which enables task-and-architecture co-adaptation (TACA) in robotic systems. ROSA achieves this by providing a knowledge model that captures all application-specific knowledge required for adaptation and by reasoning over this knowledge at runtime to determine when and how adaptation should occur. In addition to a conceptual framework, this work provides an open-source ROS 2-based reference implementation of ROSA and evaluates its feasibility and performance in an underwater robotics application. Experimental results highlight ROSA’s advantages in reusability and development effort for designing self-adaptive robotic systems.}}
```

## Acknowledgments

<a href="https://remaro.eu/">
    <img height="60" alt="REMARO Logo" src="https://remaro.eu/wp-content/uploads/2020/09/remaro1-right-1024.png">
</a>

This work is part of the Reliable AI for Marine Robotics (REMARO) Project. For more info, please visit: <a href="https://remaro.eu/">https://remaro.eu/

<br>

<a href="https://research-and-innovation.ec.europa.eu/funding/funding-opportunities/funding-programmes-and-open-calls/horizon-2020_en">
    <img align="left" height="60" alt="EU Flag" src="https://remaro.eu/wp-content/uploads/2020/09/flag_yellow_low.jpg">
</a>

This project has received funding from the European Union's Horizon 2020 research and innovation programme under the Marie Skłodowska-Curie grant agreement No. 956200.
