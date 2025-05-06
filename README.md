[![documentation](https://github.com/kas-lab/rosa/actions/workflows/doc.yml/badge.svg)](https://github.com/kas-lab/rosa/actions/workflows/doc.yml) [![test](https://github.com/kas-lab/rosa/actions/workflows/test.yml/badge.svg)](https://github.com/kas-lab/rosa/actions/workflows/test.yml)

# ROSA

This repository contains ROSA, a knowledge-based framework for robotics self-adaptation.
ROSA is implemented as a ROS 2-based system, with its knowledge base implemented with TypeDB.

This is still a work in progress, therefore the repository is unstable.

This package was tested with ROS 2 Humble and TypeDB 2.27.0

## Installing

[Install ROS 2 Humble](https://docs.ros.org/en/humble/Installation.html)

Install TypeDB:

```Bash
sudo apt install software-properties-common apt-transport-https gpg
gpg --keyserver hkp://keyserver.ubuntu.com:80 --recv-key 8F3DA4B5E9AEF44C
gpg --export 8F3DA4B5E9AEF44C | sudo tee /etc/apt/trusted.gpg.d/vaticle.gpg > /dev/null
echo "deb https://repo.vaticle.com/repository/apt/ trusty main" | sudo tee /etc/apt/sources.list.d/vaticle.list > /dev/null

sudo apt update
sudo apt install openjdk-11-jre
sudo apt install typedb-server=2.24.17 typedb-console=2.24.15 typedb-bin=2.24.16
pip3 install typedb-driver==2.24.15
```

Download ROSA:
```Bash
mkdir -p ~/rosa_ws/src
cd ~/rosa_ws/src
git clone git@github.com:kas-lab/rosa.git
vcs import . < rosa/rosa.rosinstall
```

Install dependencies:
```Bash
cd ~/rosa_ws/
source /opt/ros/humble/setup.bash
rosdep install --from-paths src --ignore-src -r -y
```

Build ROSA:
```Bash
cd ~/rosa_ws/
source /opt/ros/humble/setup.bash
colcon build --symlink-install
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

### TypeDB 3.0 with docker

[Typedb 3.0](https://typedb.com/docs/manual/install/CE)

```Bash
docker pull typedb/typedb:latest
```

```Bash
docker volume create typedb-data
docker create --name typedb -v typedb-data:/opt/typedb-all-linux-x86_64/server/data -p 1729:1729 --platform linux/amd64 typedb/typedb:latest
```

```Bash
docker start typedb
```

```Bash
docker stop typedb
```

```Bash
sudo typedb console --address typedb-core://localhost:1729 --username admin --tls-disabled
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
