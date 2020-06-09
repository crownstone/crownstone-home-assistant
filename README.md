# crownstone-home-assistant

Crownstone integration for Home Assistant

# Setting up a developer environment

1. Go to the [Home Assistant repo](https://github.com/home-assistant/core) and click fork.
2. Clone the Home Assistant repo from your fork.
3. Make sure you have Python 3.7 installed on your system.
4. It is recommended to run Home Assistant in Linux. To run Home Assistant on windows you can use Windows Subsystems for Linux. Refer to [Dev docs](https://developers.home-assistant.io/docs/development_environment) for more information and requirements about running in different operating systems.

## Install dependencies:
```console
$ sudo apt-get install python3-pip python3-dev python3-venv
```
```console
$ sudo apt-get install autoconf libssl-dev libxml2-dev libxslt1-dev libjpeg-dev libffi-dev libudev-dev zlib1g-dev pkg-config
```
```console
$ sudo apt-get install -y libavformat-dev libavcodec-dev libavdevice-dev libavutil-dev libswscale-dev libavresample-dev libavfilter-dev
```

## Set up a virtual environment
Go to the core directory and run:
```console
$ python3.7 -m venv venv
```
To activate the venv type:
```console
$ source venv/bin/activate
```

## Install Home Assistant
You can install Home Assistant by activating your venv and running:
```console
$ script/setup
```
from the core folder.

## Configuration
The configuration folder is in a different location for each system.
* Linux: ~/.homeassistant
* HassOS: /config
* MacOS: ~/.homeassistant
* Docker: /config

# Installing the Crownstone integration for debug

1. First, create a folder called "custom_components" in your configuration folder. See above for the location.
2. go to custom_components and clone this repo in the folder.

# Running Home Assistant
If you did the previous steps correctly, Home Assistant should detect the custom_components folder you just added, and will add the Crownstone integration to Home Assistant.<br>

To run Home Assistant, go to the core folder, activate the venv, and run:
```console
$ hass
```

# Entering your Home Assistant installation
Wait for Home Assistant to start. It may take some time on first boot, just be patient.<br>

Look for your computer's IP address. To see this run:
```console
$ ifconfig
```
for example:
```
192.168.178.42
```
To enter your Home Assistant installation go to your prefered browser and type the following in the address bar:
```
http://192.168.178.42:8123
```
Of course, replace this ip address with your own ip address.<br>
In the Home Asssistant frontend, simply follow the steps to set it up.

# Adding the Crownstone integration
In the Home Assistant frontend, do the following:
1. On bottom left, click on "settings"
2. Click on "integrations"
3. All the way on bottom right, click the orange button with the "+" on it
4. Select Crownstone from the list
5. Follow the steps
