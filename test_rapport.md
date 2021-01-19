# Test rapport for Crownstone Home Assistant integration

| Home Assistant version | Integration version | Tests          | Crownstone types used for testing         | Tested by                    |
| ---------------------- | ------------------- | -------------- | ----------------------------------------- | ---------------------------- |
| 0.118.0                | 1.5.0               | 1 - 3, 6 - 29  | Crownstone Built-in One, Crownstone Plug  | Ricardo Steijn (@RicArch97)  |
| 0.118.2                | 1.5.1               | 4, 5           | Crownstone Built-in One, Crownstone Plug  | Ricardo Steijn (@RicArch97)  |
| 2021.1.4               | 1.6.0               | 30 - 33        | Crownstone Plug                           | Ricardo Steijn (@RicArch97)  |

The goal of this rapport is to get a good view of which parts of the Home Assistant integration have been tested.

## Test process

The tests will consist of actions that would happen with regular use of the integration.

| Number | Test | Actions taken | Result | Error messages (if any) | Issue (if any) |
| ------ | -----| ------------- | ------ | ----------------------- | -------------- |
| 1 | Logging in with username & password | Added integration from configuration & typed in correct email & password | Moved to the next step in configuration |
| 2 | Trying to log in with wrong username & password | Added integration from configuration & typed in wrong email & password | Error message saying "wrong email or password" and the option to try again | 
| 3 | Try to add the integration with multiple spheres configured in the app | Added integration from configuration & typed in correct email & password | New window with a drop down menu to select a sphere | 
| 4 | Add the integration a second time after it has already been set up | Added integration from configuration -> integrations | Message showing: "Configuration aborted, there can be only 1 Sphere in a house" |
| 5 | Check unique ID creation in initial setup | Added integration from configuration -> integrations, typed correct login credentials & start debugging + monitoring unique ids | All entity unique ID's are different and "unique" |  
| 6 | Switching a Crownstone without USB dongle | Pressed the switch button in Home Assistant | Crownstone switched, the state in Home Assistant is updated |
| 7 | Switching a Crownstone from the app without USB dongle | Pressed the switch button in the Crownstone app | Crownstone's state in Home Assistant instantly updated |
| 8 | Switching a Crownstone with USB dongle | Pressed the switch button in Home Assistant | Crownstone switched, the state in Home Assistant is updated |
| 9 | Switching a Crownstone from the app with USB dongle | Pressed the switch button in the Crownstone app | Crownstone's state in Home Assistant instantly updated |
| 10 | Switching a Crownstone using Switchcraft ability without USB dongle | Pressed the switch button of the ceiling light | Crownstone switches on, state in Home Assistant is not updated | | When using Switchscraft, the state is only updated when using the Crownstone USB dongle |
| 11 | Switching a Crownstone using Switchcraft ability with USB dongle | Pressed the switch button of the ceiling light | Crownstone switches on, state in Home Assistant is instantly updated |
| 12 | Dimming a Crownstone with and without USB Dongle | Adjusted the dimming slider for a dimmable Crownstone in Home Assistant | Crownstone was dimmed to the correct value, and Home Assistant state updated |
| 13 | Dimming a Crownstone from the Crownstone app with and without USB dongle | Adjusted the dimming slider for a dimmable Crownstone in the Crownstone app | State in Home Assistant is instantly updated to the correct dim value |
| 14 | Check power usage entities without USB dongle | Go to configuration -> devices -> selected a Crownstone | Entity for power usage shows "unavailable" |
| 15 | Check power usage entities with USB dongle | Go to configuration -> devices -> selected a Crownstone | Entity for power usage shows the current power usage in Watt for the Crownstone, and is updated every 1 - 2 minutes |
| 16 | Changing the name of a Crownstone in the Crownstone app | For a Crownstone in the app, pressed edit and changed the name | Crownstone's entity name instantly updated in Home Assistant, device name updated |
| 17 | Removing a Crownstone from the sphere | In the Crownstone app, for a Crownstone pressed edit and "Remove from Sphere" | Crownstone device & entities are instantly removed from Home Assistant |
| 18 | Adding a Crownstone to the sphere | In the Crownstone app, clicked the "+" -> Crownstone -> Built-in One -> selected Crownstone -> entered name & room | Crownstone is immediately added to Home Assistant | | The Crownstone switch entity ID will be called something like "light.crownstone_built-in-one" for a newly added Crownstone. That is because the Crownstone is added in 2 steps and the name is not known yet when the entity is initialized. You can manually change the entity-id if you like though it is generally not recommended |
| 19 | Turning the dimming ability on/off for a Crownstone | In the Crownstone app for a Crownstone, pressed abilities and changed the state of "Dimming" | Config entry is reloaded | | Config entry has to be reloaded (unloaded & recreated) because of the change in supported features for entities, which cannot be changed dynamically. After the reload some states may be different and power usage may be set back to 0
| 20 | Turning Switchcraft or Tap-To-Toggle on/off for a Crownstone | In the Crownstone app for a Crownstone, pressed abilities and changed the state of either "Switchcraft" or "Tap-To-Toggle" | The state attributes for the Crownstone's switch entity are updated |
| 21 | Adding a new Location to the Sphere | In the Crownstone app, clicked the "+" -> Room -> entered room name | Location is immediately added to Home Assistant |
| 22 | Removing a Location from the sphere | In the Crownstone app, for a Location (room), pressed edit and "Remove Room" | Location presence is removed from Home Assistant |
| 23 | Adding / inviting a new user to the sphere | In the Crownstone app, clicked the "+" -> Person -> entered person's email & chose access level member | User now shows up in the user list when creating an automation for a presence device |
| 24 | Removing a user from the sphere | In the Crownstone app, pressed edit -> User -> selected user -> remove from sphere | User did not show up anymore in the user list when creating an automation for a presence device |
| 25 | Location presence updates | Walked from a room into an other room | Username was removed from the previous room and added to the new room |
| 26 | Sphere presence updates | Had someone walk away with my phone from the house | Username was removed from the sphere (house) and from all other rooms |
| 27 | Presence device automation single user | Created an automation for a presence device with trigger: "A user entered the room" and action turning on a light | Upon entering the room, the light turned on |
| 28 | Presence device automation multiple users | Created an automation for a presence device with trigger: "Multiple users entered the room", and selected 2 users from the list. Action is turning on a light | When 1 user entered the room, nothing happened. Only when the second user also entered, the light turned on |
| 29 | Crownstone device automation power usage | Create an automation for a Crownstone device with trigger "above 100" and "below 0" and action turning off the device. A mobile airco was connected to the Crownstone | After switching on the airco, it took a minute for the power usage to go above 100W, to about 300W, on which the Crownstone switched off again |
| 30 | Energy usage starts at 0 after updating/reinstalling | Removed the integration, and re-added it in Home Assistant | Values started at 0 |
| 31 | Energy usage values restored after rebooting Home Assistant | Restart Home Assistant | Values restored to the state before rebooting Home Assistant |
| 32 | Energy usage values correctly updated | Checked the power usage in the Crownstone app, and set a timer for a 60 seconds, then calculated value in Wh by power (W) / 60 | Correct value added to previous energy usage value |
| 33 | Energy usage set back to 0 after a month or year has past | Created a unittest with fake values, to pretend that a month had past | In de test, de value was set back to 0 and start counting correctly after that |
