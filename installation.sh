#!/bin/bash

#For this orchestrator
sudo apt install -y python3-flask python3-pip

#For cybermapper
sudo apt install -y make build-essential curl python-dev python3-dev python-virtualenv python3-venv libfontconfig1 libfreetype6 expect sshpass npm

pip3 install apscheduler
pip3 install grequests
pip3 install flask

sudo apt install libssl-dev

pip3 install paramiko

