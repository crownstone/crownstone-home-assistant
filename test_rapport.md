# Test rapport for Crownstone Home Assistant integration

| Home Assistant version | Integration version | Tested by                   | 
| ---------------------- | ------------------- | ---------------------------
| 0.118.0                | 1.5.0               | Ricardo Steijn (@RicArch97)

The goal of this rapport is to get a good view of which parts of the Home Assistant integration have been tested.

## Test process

The tests will consist of actions that would happen with regular use of the integration.

| Test | Actions taken | Result | Error messages (if any) | Issue (if any) |
| -----| ------------- | ------ | ----------------------- | -------------- |
| Logging in with username & password | Added integration from configuration & typed in correct email & password | Moved to the next step in configuration |
| Trying to log in with wrong username & password | Added integration from configuration & typed in wrong email & password | Error message saying "wrong email or password" and the option to try again | 
| Try to add the integration with multiple spheres configured in the app | Added integration from configuration & typed in correct email & password | New window with a drop down menu to select a sphere | 
| Add the integration a second time after it has already been set up once, and logging in with the same account & selecting the same sphere | Added the integration from configuration & typed in correct email & password, and selected an already configured sphere | Message showing "sphere already configured, aborting." |
| Add the integration a second time after it has already been set up once, and logging in with the same account & selecting a different sphere | Added the integration from configuration & typed in correct email & password, and selected a new sphere | New entry generated with new entities & devices | "Platform crownstone does not generate unique IDs. ID 3 already exists - ignoring sensor.bedroom" & "Connection to USB failed. Retrying..." | Items with the same name give problems with unique id generation, multiple entries are trying to connect to the Crownstone USB, which is not possible |
| Switching a Crownstone without USB dongle | Pressed the switch button in Home Assistant | Crownstone switched, the state in Home Assistant is updated |
| Switching a Crownstone from the app without USB dongle | Pressed the switch button in the Crownstone app | Crownstone's state in Home Assistant instantly updated |
| Switching a Crownstone with USB dongle | Pressed the switch button in Home Assistant | Crownstone switched, the state in Home Assistant is updated |
| Switching a Crownstone from the app with USB dongle | Pressed the switch button in the Crownstone app | Crownstone's state in Home Assistant instantly updated |
| Switching a Crownstone using Switchcraft ability without USB dongle | Pressed the switch button of the ceiling light | Crownstone switches on, state in Home Assistant is not updated | | When using Switchscraft, the state is only updated when using the Crownstone USB dongle |
| Switching a Crownstone using Switchcraft ability with USB dongle | Pressed the switch button of the ceiling light | Crownstone switches on, state in Home Assistant is instantly updated |
| Dimming a Crownstone with and without USB Dongle | Adjusted the dimming slider for a dimmable Crownstone in Home Assistant | Crownstone was dimmed to the correct value, and Home Assistant state updated |
| Dimming a Crownstone from the Crownstone app with and without USB dongle | Adjusted the dimming slider for a dimmable Crownstone in the Crownstone app | State in Home Assistant is instantly updated to the correct dim value |
| Check power usage entities without USB dongle | Go to configuration -> devices -> selected a Crownstone | Entity for power usage shows "unavailable" |
| Check power usage entities with USB dongle | Go to configuration -> devices -> selected a Crownstone | Entity for power usage shows the current power usage in Watt for the Crownstone, and is updated every 1 - 2 minutes |
| Changing the name of a Crownstone in the Crownstone app | For a Crownstone in the app, pressed edit and changed the name | Crownstone's entity name instantly updated in Home Assistant, device name updated |
| Removing a Crownstone from the sphere | In the Crownstone app, for a Crownstone pressed edit and "Remove from Sphere" | Crownstone device & entities are instantly removed from Home Assistant |
| Adding a Crownstone to the sphere | In the Crownstone app, clicked the "+" -> Crownstone -> Built-in One -> selected Crownstone -> entered name & room | Crownstone is immediately added to Home Assistant | | The Crownstone switch entity ID will be called something like "light.crownstone_built-in-one" for a newly added Crownstone. That is because the Crownstone is added in 2 steps and the name is not known yet when the entity is initialized. You can manually change the entity-id if you like though it is generally not recommended |
| Turning the dimming ability on/off for a Crownstone | In the Crownstone app for a Crownstone, pressed abilities and changed the state of "Dimming" | Config entry is reloaded | | Config entry has to be reloaded (unloaded & recreated) because of the change in supported features for entities, which cannot be changed dynamically. After the reload some states may be different and power usage may be set back to 0
| Turning Switchcraft or Tap-To-Toggle on/off for a Crownstone | In the Crownstone app for a Crownstone, pressed abilities and changed the state of either "Switchcraft" or "Tap-To-Toggle" | The state attributes for the Crownstone's switch entity are updated |
| Adding a new Location to the Sphere | In the Crownstone app, clicked the "+" -> Room -> entered room name | Location is immediately added to Home Assistant |
| Removing a Location from the sphere | In the Crownstone app, for a Location (room), pressed edit and "Remove Room" | Location presence is removed from Home Assistant |
| Adding / inviting a new user to the sphere | In the Crownstone app, clicked the "+" -> Person -> entered person's email & chose access level member | User now shows up in the user list when creating an automation for a presence device |
| Removing a user from the sphere | In the Crownstone app, pressed edit -> User -> selected user -> remove from sphere | User did not show up anymore in the user list when creating an automation for a presence device |
| Location presence updates | Walked from a room into an other room | Username was removed from the previous room and added to the new room |
| Sphere presence updates | Had someone walk away with my phone from the house | Username was removed from the sphere (house) and from all other rooms |
| Presence device automation single user | Created an automation for a presence device with trigger: "A user entered the room" and action turning on a light | Upon entering the room, the light turned on |
| Presence device automation multiple users | Created an automation for a presence device with trigger: "Multiple users entered the room", and selected 2 users from the list. Action is turning on a light | When 1 user entered the room, nothing happened. Only when the second user also entered, the light turned on |
| Crownstone device automation power usage | Create an automation for a Crownstone device with trigger "above 100" and "below 0" and action turning off the device. A mobile airco was connected to the Crownstone | After switching on the airco, it took a minute for the power usage to go above 100W, to about 300W, on which the Crownstone switched off again |