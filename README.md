[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg?style=for-the-badge)](https://github.com/custom-components/hacs)
[![GitHub release (latest by date)](https://img.shields.io/github/v/release/crownstone/crownstone-home-assistant?label=Latest%20release&style=for-the-badge)](https://github.com/crownstone/crownstone-home-assistant/releases)
[![Maintained](https://img.shields.io/maintenance/yes/2021?style=for-the-badge)](https://github.com/RicArch97)

# Crownstone Home Assistant Integration Beta

![Crownstone Home Assistant banner](/images/crownstone_home_assistant.png)

# Features

Crownstone Home Assistant integration beta to test new features before they are integrated into the core version.

The Crownstone integration is available in Home Assistant core since version 2021.10.0. It is however limited in features and only supports switching and dimming Crownstones for now. With time, features will be migrated from this version to the core version.

This version supports the following extra features over the core integration:

* Instant data (names and firmware version) updates
* Dynamically adding and removing devices/entities when Crownstones or locations are added or removed in the app
* Real-time power usage measurements using the Crownstone USB
* Real-time energy usage statistics using the Crownstone USB, which can be added to the energy dashboard
* Presence devices/entities to keep track of who is in which room
* Custom presence triggers that can be used in automations to make your whole home react to presence changes
* Custom presence conditions that can be used in automations to check current presence of specific users in a room

This version builds directly on top of the core integration, so the core is stable. The extra features have been tested well, but have not been reviewed by any Home Assistant members, it is therefore possible they are not fully optimized yet or contain bugs. For the most stable experience, we recommend using the core version. If you like the extra features, you can keep using the HACS version.

![Crownstone integration dashboard example](/images/dashboard.png)

# Installation

## HACS

Visit the [HACS installation page](https://hacs.xyz/docs/installation/installation) to install HACS, and the [HACS setup page](https://hacs.xyz/docs/configuration/basic) to enabled HACS in Home Assistant.

In HACS, Click the 3 dots button in the top right corner, and click custom repositories. Select category integration, and add the link of this repository. 

After adding the repository, in the HACS store, click the "+ explore & add repositories" button in the bottom right corner, and search for Crownstone. Then just follow the installation steps. Make sure to select the newest version!

## Manually

Copy all files from custom_components/crownstone/ to custom_components/crownstone inside your HA config folder.

# Languages

This beta version of the integration currently supports English and Dutch.

# Crownstone USB dongle

To use the Crownstone USB dongle in Home Assistant, plug the dongle in a USB port of the device that runs Home Assistant. In most cases that will be a Raspberry Pi. **You must** then add the dongle to a Sphere in the Crownstone app, otherwise it will not work. It can be added like any other Crownstone. In the app, simply press the "+" button, select Crownstone, and then select Crownstone USB.

When setting up the Crownstone integration in Home Assistant, you will have to select the serial port of the Crownstone USB dongle. You can do so by selecting the correct entry from the list:

![Crownstone USB setup](/images/crownstone_usb_setup.png)

Future USB dongles will likely have the `Crownstone dongle` product string. However older dongles will show `CP2104 USB to UART Bridge Controller` for the description. If you have more dongles with VID 10C4 and PID EA60, for example, the Z-wave Zooz stick, unplug those devices and only leave the Crownstone dongle connected, and select the `Refresh list` option to scan again, to make sure you select the correct dongle.

If your USB dongle is not listed because you created your own udev rule and the system fails to detect it, you can select the `Enter manually` option, and manually enter the path. E.g. `/dev/crownstone`. If your entered port is incorrect and the integration cannot establish a connection, it will show a notification and use the cloud instead. You can always try the setup again later from the integration options.

If you don't want to set up a USB dongle, select `Don't use USB`. The Crownstone Cloud will be used to switch Crownstones, and power/energy entities will not be added.

In case you have multiple Spheres configured in the Crownstone app, you will have to select the Sphere where the USB dongle is configured, because the dongle by itself is not aware in which Sphere it is. You can check this by going into the Crownstone app. If you only have 1 Sphere, this step will be skipped.

![Crownstone USB Sphere](/images/crownstone_usb_sphere.png)

If you did not set up a USB dongle from the beginning or the setup was unsuccessful, you can start the setup again at any point from the integration options.
Go to configuration -> integrations, look for your Crownstone account and click **Configure**. 

![Crownstone options disabled](/images/crownstone_options_disabled.png)

When checking this option and clicking submit, you can instantly start configuring a Crownstone USB dongle. When a dongle was set up, this option will be checked. Unchecking this option will remove the existing USB configuration and use the Crownstone Cloud again.

You can also change the Sphere where the USB is configured on the fly. This depends on where it is configured in the Crownstone app. It is quite rare that this changes, but in case you have a mobile instance you could add the USB to an other Sphere in the Crownstone app, and change this setting.

![Crownstone options enabled](/images/crownstone_options_enabled.png)

## Comparison

The integration works with the Crownstone Cloud and the Crownstone USB dongle. The differences between the two are only relevant for the Crownstones. The integration uses the Crownstone Cloud by default, to use the Crownstone USB you'll have to purchase one from the Crownstone store.

Presence updates and data updates are always done using the Crownstone Cloud.

### Crownstone Cloud

- [x] Switching Crownstones
- [x] Dimming Crownstones
- [x] State updates in Home Assistant when switching from Crownstone app
- [x] Can switch multiple Crownstones at once
- [ ] No delay when switching Crownstones
- [ ] State updates in Home Assistant when using lightswitch with Switchcraft
- [ ] Can switch Crownstones independently (no smartphone in proximity required)
- [ ] Can use power usage & energy usage entities

### Crownstone USB Dongle

- [x] Switching Crownstones
- [x] Dimming Crownstones
- [x] State updates in Home Assistant when switching from Crownstone app
- [x] Can switch multiple Crownstones at once
- [x] No delay when switching Crownstones
- [x] State updates in Home Assistant when using lightswitch with Switchcraft
- [x] Can switch Crownstones independently (no smartphone in proximity required)
- [x] Can use power usage & energy usage entities

Get your Crownstone USB dongle [here](https://shop.crownstone.rocks/products/crownstone-usb-dongle) and enhance your Home Assistant experience!

## Remote access

In case you have multiple Spheres, only the Crownstones that are located in the same Sphere as the USB dongle can use the dongle, as it uses BLE and hooks directly into the Crownstone mesh network. The Crownstones from the other Spheres will use the Cloud. If you want to switch Crownstones in your other Spheres remotely, you will need a device at the receiving end to switch the Crownstones for you, as the Cloud only posts a command for the switch. This device is usually a smarthphone, or a Crownstone hub (gateway).

In case you want to control your Home Assistant instance remotely and switch Crownstones, make sure you are using a Crownstone USB so it can switch Crownstones even when you're not home. It is recommended to use [Home Assistant Cloud](https://www.nabucasa.com/) (Nabu Casa) to easily set up a remote connection with your Home Assistant instance.

# Crownstones

Crownstone are represented in the light platform, and can switch or dim. You can create a card in the overview and add your Crownstone entities to have a nice overview of your Crownstones! If a Crownstone supports dimming, there will be a brightness slider to dim your Crownstone.

![Crownstone entity](/images/crownstone_entity.png)

When the ability state of **dimming** is changed through the Crownstone app, your config entry will reload to process the change in supported features. 

# Presence

The unique selling point of Crownstone, the presence on room level, is also available in Home Assistant!

The state sensor is a string of the first names of the people who are in the room. It is possible for multiple people to be in the same room, the names of the users is separated by a comma.

Apart from the room presence there is also sphere presence. this shows who is currently in the sphere (house, apartment). If a user is at home (in the sphere), the user's name will be shown in sphere presence and one of the room presence entities.

The Crownstone app is leading the presence functionality, for any issues with your presence detection make sure to go to your Crownstone app and retrain your rooms. 4 Crownstones are required for the localisation on room level. If you don't have 4 Crownstones, it will only show your presence in the sphere (house).

## Presence device automation

To create automations with the Crownstone presence detection on room level, device triggers and conditions are available. You can trigger automations on presence changes for a specific user or any user, and optionally check if someone is present in a room before switching devices.

The following device triggers are available for the Crownstone presence devices:
- A user has left a room / the house
- A user has entered a room / the house
- Any user has entered a room / the house
- Any user has left a room / the house

The following device conditions are available for the Crownstone presence devices:
- Any user is present in a room / the house
- Users are present in a room / the house
- Users are not present in a room / the house

### Setting up an automation using the UI

- go to configuration -> automations -> add automation -> start with an empty automation -> select a presence device and trigger in the **trigger** section or a presence device and condition in the **condition** section.
- go to configuration -> devices -> select device -> new automation -> select a trigger or condition.

The names of the users are their **full name**, So first name + last name. You can see what name you have configured by entering the Crownstone app, and going to Settings -> My Account.

# Power usage & Energy usage

Crownstone's live power usage streaming, and energy usage summation, are is also available in Home Assistant. Because of the constant updates, this functionality is only available when using the [Crownstone USB dongle](#crownstone-usb-dongle).

The power usage and energy usage for each Crownstone update every minute, or instantly for a particular Crownstone when switching it.

## Energy usage

- Takes the total energy amount directly from the Crownstone. This can be a big value depending on when the Crownstone started counting.
- A Crownstone's energy usage total amount is reset back to 0 when the Crownstone is rebooted (power loss, reset or after a software update). This means the value of the energy sensor will also go back to 0, this does not affect the total amount saved in Home Assistant. You can view your delta's in the Home Assistant energy dashboard.

![Crownstone power usage](/images/device.png)

The connection entity depends on whether this entity is in the same Sphere as the Crownstone USB. You should have selected in which Sphere it is in the configuration. If a device is not in the same Sphere as the Crownstone USB and can therefore not be switched by it or receive energy/power updates, the connection entity will show "Cloud". 

# Roadmap

- [x] Publish initial Crownstone integration to Home Assistant Core
- [x] Optimize configuration flow for easier setup
- [x] Create device triggers for Presence devices
- [x] Add power usage entities to Crownstone devices
- [x] Fix state updates coming from the Crownstone app not being done in Home Assistant
- [x] Dynamically update data & add/remove Crownstone and Location devices without restarting or reloading
- [x] Add energy usage entities to Crownstone devices
- [x] Create device conditions for Presence devices

Any ideas for future updates? Let us [know](mailto:ask@crownstone.rocks?subject=[GitHub]%20Crownstone%20Home%20Assistant%20Integration)!

![Crownstones with HA Pi](/images/crownstone_with_pi.jpg)
