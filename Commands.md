# pcwbot

## Admin Levels and Bot Commands


### Admins [40]

- **cyclemap** - start next map in rotation
	- Usage: `!cyclemap`
- **exec** - execute config file
	- Usage: `!exec <filename>`
- **force** - force a player to the given team
	- Usage: `!force <name> <blue/red/spec> [<lock>]`
- **kick** - kick a player
	- Usage: `!kick <name> <reason>`
	- Short: `!k <name> <reason>`
- **list** - list all connected players
	- Usage: `!list`
- **map** - load given map
	- Usage: `!map <ut4_name>`
- **password** - set private server password (empty string to remove password)
	- Usage: `!password <passwd>`
- **reload** - reload map
	- Usage: `!reload`
- **setnextmap** - set the given map as nextmap
	- Usage: `!setnextmap <ut4_name>`
- **swapteams** - swap the current teams
	- Usage: `!swapteams`
- **veto** - stop voting process
	- Usage: `!veto`


### Head Admin [100]

- **leveltest** - get the admin level for a given player or myself
	- Usage: `!leveltest [<name>]`
	- Short: `!lt [<name>]`
- **putgroup** - add a client to a group
	- Usage: `!putgroup <name> <group>`
	- Available Groups: _user_, _admin_
- **ungroup** - remove admin level from a player
	- Usage: `!ungroup <name>`
