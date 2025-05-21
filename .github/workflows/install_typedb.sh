#!/usr/bin/env bash

sudo apt install software-properties-common apt-transport-https gpg
gpg --keyserver hkp://keyserver.ubuntu.com:80 --recv-key 17507562824cfdcc
gpg --export 17507562824cfdcc | sudo tee /etc/apt/trusted.gpg.d/vaticle.gpg > /dev/null
echo "deb https://repo.typedb.com/public/public-release/deb/ubuntu trusty main" | sudo tee /etc/apt/sources.list.d/vaticle.list > /dev/null

sudo apt update
sudo apt install -y openjdk-11-jre
sudo apt install -y typedb=2.27.0
pip3 install typedb-driver==2.27.0
