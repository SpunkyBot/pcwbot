pcwbot
======

[![Build Status](https://travis-ci.org/SpunkyBot/pcwbot.svg?branch=main)](https://travis-ci.org/SpunkyBot/pcwbot)
[![Release](https://img.shields.io/github/v/release/SpunkyBot/pcwbot.svg)](https://github.com/SpunkyBot/pcwbot/releases)
[![License](https://img.shields.io/github/license/SpunkyBot/pcwbot)](https://github.com/SpunkyBot/pcwbot/blob/main/LICENSE)

Scaled down version of Spunky Bot, optimized for PCW server and private Clan server.

Following Admin commands are supported:

* `!cyclemap` - start next map in rotation
* `!exec <filename>` - execute config file
* `!force <name> <blue/red/spec>` - force a player to the given team
* `!kick <name>` - kick a player
* `!list` - list all connected players
* `!map <ut4_name>` - load given map
* `!password <passwd>` - set private server password (empty string to remove password)
* `!reload` - reload map
* `!setnextmap <ut4_name>` - set the given map as nextmap
* `!swapteams` - swap current teams
* `!veto` - stop voting process

Head Admin commands:

* `!leveltest [<name>]` - get the admin level for a given player or myself
* `!putgroup <name> <group>`  - add a client to a group (available groups: *user*, *admin*)
* `!ungroup <name>` - remove the admin level from a player
