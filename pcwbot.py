#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
pcwbot - An automated game server bot
http://www.spunkybot.de/pcwbot
Author: Alexander Kress

This program is released under the MIT License. See LICENSE for more details.

## About ##
pcwbot is a scaled down version of Spunky Bot, the lightweight game server
administration bot and RCON tool, which is optimized for private war server.

## Configuration ##
Modify the UrT server config as follows:
 * seta g_logsync "1"
Modify the configuration file 'settings.conf'
Run the bot: python pcwbot.py
"""

__version__ = '0.9.10'


### IMPORTS
import re
import time
import sqlite3
import textwrap
import ConfigParser
import socket

from Queue import Queue
from threading import Thread
from threading import RLock


class Q3Player(object):
    """
    Q3Player class
    """
    def __init__(self, num, name, frags, ping, address=None, bot=-1):
        """
        create a new instance of Q3Player
        """
        self.num = num
        self.name = name
        self.frags = frags
        self.ping = ping
        self.address = address
        self.bot = bot


class PyQuake3(object):
    """
    PyQuake3 class - Python Quake 3 Library
    http://misc.slowchop.com/misc/wiki/pyquake3
    Copyright (C) 2006-2007 Gerald Kaszuba
    """
    packet_prefix = '\xff' * 4
    player_reo = re.compile(r'^(\d+) (\d+) "(.*)"')

    rcon_password = None
    port = None
    address = None
    players = None
    values = None

    def __init__(self, server, rcon_password=''):
        """
        create a new instance of PyQuake3
        """
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.set_server(server)
        self.set_rcon_password(rcon_password)

    def set_server(self, server):
        """
        set IP address and port and connect to socket
        """
        try:
            self.address, self.port = server.split(':')
        except:
            raise ValueError('Server address format must be: "address:port"')
        self.port = int(self.port)
        self.sock.connect((self.address, self.port))

    def get_address(self):
        """
        get IP address and port
        """
        return '%s:%s' % (self.address, self.port)

    def set_rcon_password(self, rcon_password):
        """
        set RCON password
        """
        self.rcon_password = rcon_password

    def send_packet(self, data):
        """
        send packet
        """
        self.sock.send('%s%s\n' % (self.packet_prefix, data))

    def recv(self, timeout=1):
        """
        receive packets
        """
        self.sock.settimeout(timeout)
        try:
            return self.sock.recv(8192)
        except socket.error, err:
            raise Exception('Error receiving the packet: %s' % err[1])

    def command(self, cmd, timeout=1, retries=5):
        """
        send command and receive response
        """
        while retries:
            self.send_packet(cmd)
            try:
                data = self.recv(timeout)
            except Exception:
                data = None
            if data:
                return self.parse_packet(data)
            retries -= 1
        raise Exception('Server response timed out')

    def rcon(self, cmd):
        """
        send RCON command
        """
        r_cmd = self.command('rcon "%s" %s' % (self.rcon_password, cmd))
        if r_cmd[1] == 'No rconpassword set on the server.\n' or r_cmd[1] == 'Bad rconpassword.\n':
            raise Exception(r_cmd[1][:-1])
        return r_cmd

    def parse_packet(self, data):
        """
        parse the received packet
        """
        if data.find(self.packet_prefix) != 0:
            raise Exception('Malformed packet')

        first_line_length = data.find('\n')
        if first_line_length == -1:
            raise Exception('Malformed packet')

        response_type = data[len(self.packet_prefix):first_line_length]
        response_data = data[first_line_length + 1:]
        return response_type, response_data

    def parse_status(self, data):
        """
        parse the response message and return a list
        """
        split = data[1:].split('\\')
        values = dict(zip(split[::2], split[1::2]))
        # if there are \n's in one of the values, it's the list of players
        for var, val in values.items():
            pos = val.find('\n')
            if pos == -1:
                continue
            split = val.split('\n', 1)
            values[var] = split[0]
            self.parse_players(split[1])
        return values

    def parse_players(self, data):
        """
        parse player information - name, frags and ping
        """
        self.players = []
        for player in data.split('\n'):
            if not player:
                continue
            match = self.player_reo.match(player)
            if not match:
                print 'couldnt match', player
                continue
            frags, ping, name = match.groups()
            self.players.append(Q3Player(1, name, frags, ping))

    def update(self):
        """
        get status
        """
        data = self.command('getstatus')[1]
        self.values = self.parse_status(data)

    def rcon_update(self):
        """
        perform RCON status update
        """
        data = self.rcon('status')[1]
        lines = data.split('\n')

        players = lines[3:]
        self.players = []
        for ply in players:
            while ply.find('  ') != -1:
                ply = ply.replace('  ', ' ')
            while ply.find(' ') == 0:
                ply = ply[1:]
            if ply == '':
                continue
            ply = ply.split(' ')
            try:
                self.players.append(Q3Player(int(ply[0]), ply[3], int(ply[1]), int(ply[2]), ply[5]))
            except (IndexError, ValueError):
                continue


### CLASS Rcon ###
class Rcon(object):
    """
    RCON class, version 1.0.7
    """

    def __init__(self, host, port, passwd):
        """
        create a new instance of Rcon

        @param host: The server IP address
        @type  host: String
        @param port: The server port
        @type  port: String
        @param passwd: The RCON password
        @type  passwd: String
        """
        self.live = False
        self.quake = PyQuake3("%s:%s" % (host, port), passwd)
        self.queue = Queue()
        self.rcon_lock = RLock()
        # start Thread
        self.processor = Thread(target=self.process)
        self.processor.setDaemon(True)
        self.processor.start()

    def push(self, msg):
        """
        execute RCON command

        @param msg: The RCON command
        @type  msg: String
        """
        if self.live:
            with self.rcon_lock:
                self.queue.put(msg)

    def go_live(self):
        """
        go live
        """
        self.live = True

    def get_rcon_output(self, value):
        """
        get RCON output for value
        """
        if self.live:
            with self.rcon_lock:
                return self.quake.rcon(value)

    def process(self):
        """
        Thread process
        """
        while 1:
            if not self.queue.empty():
                if self.live:
                    with self.rcon_lock:
                        try:
                            command = self.queue.get()
                            if command != 'status':
                                self.quake.rcon(command)
                            else:
                                self.quake.rcon_update()
                        except Exception:
                            pass
            time.sleep(.33)


### CLASS Log Parser ###
class LogParser(object):
    """
    log file parser
    """
    def __init__(self, config_file):
        """
        create a new instance of LogParser

        @param config_file: The full path of the bot configuration file
        @type  config_file: String
        """
        # RCON commands for the different admin roles
        self.admin_cmds = ['cyclemap', 'exec', 'force', 'kick', 'list', 'map', 'password', 'reload', 'setnextmap', 'swapteams', 'veto']
        self.headadmin_cmds = self.admin_cmds + ['leveltest', 'putgroup', 'ungroup']
        # alphabetic sort of the commands
        self.admin_cmds.sort()
        self.headadmin_cmds.sort()

        self.config_file = config_file
        config = ConfigParser.ConfigParser()
        config.read(config_file)
        print "- Imported config file '%s' successful." % config_file

        games_log = config.get('server', 'log_file')
        # open game log file
        self.log_file = open(games_log, 'r')
        # go to the end of the file
        self.log_file.seek(0, 2)
        print "- Parsing games log file '%s' successful." % games_log

        self.game = None
        self.players_lock = RLock()

        # enable/disable option to get Head Admin by checking existence of head admin in database
        curs.execute("SELECT COUNT(*) FROM `admins` WHERE `admin_role` = 100")
        self.iamgod = True if curs.fetchone()[0] < 1 else False

        # start parsing the games logfile
        self.read_log()

    def read_log(self):
        """
        read the logfile
        """
        # create instance of Game
        self.game = Game(self.config_file)

        while self.log_file:
            line = self.log_file.readline()
            if line:
                self.parse_line(line)
            else:
                if not self.game.live:
                    self.game.go_live()
                time.sleep(.125)

    def parse_line(self, string):
        """
        parse the logfile and search for specific action
        """
        line = string[7:]
        tmp = line.split(":", 1)
        line = tmp[1].strip() if len(tmp) > 1 else tmp[0].strip()
        try:
            action = tmp[0].strip()
            if action == 'ClientUserinfo':
                self.handle_userinfo(line)
            elif action == 'ClientDisconnect':
                self.handle_disconnect(line)
            elif action == 'say':
                self.handle_say(line)
        except (IndexError, KeyError):
            pass
        except Exception, err:
            print "%s: %s" % (err.__class__.__name__, err)

    def explode_line(self, line):
        """
        explode line
        """
        arr = line.lstrip().lstrip('\\').split('\\')
        key = True
        key_val = None
        values = {}
        for item in arr:
            if key:
                key_val = item
                key = False
            else:
                values[key_val.rstrip()] = item.rstrip()
                key_val = None
                key = True
        return values

    def handle_userinfo(self, line):
        """
        handle player user information, auto-kick known cheater ports or guids
        """
        with self.players_lock:
            player_num = int(line[:2].strip())
            line = line[2:].lstrip("\\").lstrip()
            values = self.explode_line(line)
            name = re.sub(r"\s+", "", values['name']) if 'name' in values else "UnnamedPlayer"
            ip_port = values['ip'] if 'ip' in values else "0.0.0.0:0"
            guid = values['cl_guid'] if 'cl_guid' in values else "None"
            ip_address = ip_port.split(":")[0].strip()

            if player_num not in self.game.players:
                player = Player(player_num, ip_address, guid, name)
                self.game.add_player(player)

            if self.game.players[player_num].get_guid() != guid:
                self.game.players[player_num].set_guid(guid)
            if self.game.players[player_num].get_name() != name:
                self.game.players[player_num].set_name(name)

    def handle_disconnect(self, line):
        """
        handle player disconnect
        """
        with self.players_lock:
            player_num = int(line)
            del self.game.players[player_num]

    def player_found(self, user):
        """
        return True and instance of player or False and message text
        """
        victim = None
        name_list = []
        append = name_list.append
        for player in self.game.players.itervalues():
            player_name = player.get_name()
            player_num = player.get_player_num()
            if (user.upper() == player_name.upper() or user == str(player_num)) and player_num != 1022:
                victim = player
                name_list = ["^3%s [^2%d^3]" % (player_name, player_num)]
                break
            elif user.upper() in player_name.upper() and player_num != 1022:
                victim = player
                append("^3%s [^2%d^3]" % (player_name, player_num))
        if len(name_list) == 0:
            return False, None, "^3No Player found"
        elif len(name_list) > 1:
            return False, None, "^7Players matching %s: ^3%s" % (user, ', '.join(name_list))
        else:
            return True, victim, None

    def map_found(self, map_name):
        """
        return True and map name or False and message text
        """
        map_list = []
        append = map_list.append
        for maps in self.game.get_all_maps():
            if map_name.lower() == maps or ('ut4_%s' % map_name.lower()) == maps:
                append(maps)
                break
            elif map_name.lower() in maps:
                append(maps)
        if not map_list:
            return False, None, "^3Map not found"
        elif len(map_list) > 1:
            return False, None, "^7Maps matching %s: ^3%s" % (map_name, ', '.join(map_list))
        else:
            return True, map_list[0], None

    def handle_say(self, line):
        """
        handle say commands
        """
        with self.players_lock:
            line = line.strip()
            try:
                divider = line.split(": ", 1)
                number = divider[0].split(" ", 1)[0]
                cmd = divider[1].split()[0]

                sar = {'player_num': int(number), 'command': cmd}
            except IndexError:
                sar = {'player_num': 1022, 'command': ''}

            if sar['command'] == '!help' or sar['command'] == '!h':
                if self.game.players[sar['player_num']].get_admin_role() == 40:
                    self.game.rcon_tell(sar['player_num'], "^7Admin commands: ^3%s" % ", ".join(self.admin_cmds))
                elif self.game.players[sar['player_num']].get_admin_role() > 80:
                    self.game.rcon_tell(sar['player_num'], "^7Head Admin commands: ^3%s" % ", ".join(self.headadmin_cmds))

## admin level 40
            # force - force a player to the given team
            elif sar['command'] == '!force' and self.game.players[sar['player_num']].get_admin_role() >= 40:
                if line.split(sar['command'])[1]:
                    arg = line.split(sar['command'])[1].split()
                    if len(arg) > 1:
                        user = arg[0]
                        team = arg[1]
                        team_dict = {'red': 'red', 'r': 'red', 're': 'red',
                                     'blue': 'blue', 'b': 'blue', 'bl': 'blue', 'blu': 'blue',
                                     'spec': 'spectator', 'spectator': 'spectator', 's': 'spectator', 'sp': 'spectator', 'spe': 'spectator',
                                     'green': 'green'}
                        found, victim, msg = self.player_found(user)
                        if not found:
                            self.game.rcon_tell(sar['player_num'], msg)
                        else:
                            if team in team_dict:
                                victim_player_num = victim.get_player_num()
                                self.game.rcon_forceteam(victim_player_num, team_dict[team])
                            else:
                                self.game.rcon_tell(sar['player_num'], "^7Usage: !force <name> <blue/red/spec>")
                    else:
                        self.game.rcon_tell(sar['player_num'], "^7Usage: !force <name> <blue/red/spec>")
                else:
                    self.game.rcon_tell(sar['player_num'], "^7Usage: !force <name> <blue/red/spec>")

            # kick - kick a player
            elif (sar['command'] == '!kick' or sar['command'] == '!k') and self.game.players[sar['player_num']].get_admin_role() >= 40:
                if line.split(sar['command'])[1]:
                    user = line.split(sar['command'])[1].strip()
                    found, victim, msg = self.player_found(user)
                    if not found:
                        self.game.rcon_tell(sar['player_num'], msg)
                    else:
                        if sar['player_num'] != victim.get_player_num():
                            self.game.kick_player(victim.get_player_num())
                        else:
                            self.game.rcon_tell(sar['player_num'], "^7You cannot kick yourself")
                else:
                    self.game.rcon_tell(sar['player_num'], "^7Usage: !kick <name>")

            # list - list all connected players
            elif sar['command'] == '!list' and self.game.players[sar['player_num']].get_admin_role() >= 40:
                msg = "^7Current players: %s" % ", ".join(["^3%s [^2%d^3]" % (player.get_name(), player.get_player_num()) for player in self.game.players.itervalues() if player.get_player_num() != 1022])
                self.game.rcon_tell(sar['player_num'], msg)

            # veto - stop voting process
            elif sar['command'] == '!veto' and self.game.players[sar['player_num']].get_admin_role() >= 40:
                self.game.send_rcon('veto')

            # reload
            elif sar['command'] == '!reload' and self.game.players[sar['player_num']].get_admin_role() >= 40:
                self.game.send_rcon('reload')

            # password - set private server password
            elif sar['command'] == '!password' and self.game.players[sar['player_num']].get_admin_role() >= 40:
                if line.split(sar['command'])[1]:
                    arg = line.split(sar['command'])[1].strip()
                    self.game.send_rcon('g_password %s' % arg)
                    self.game.rcon_tell(sar['player_num'], "^7Password set to '%s' - Server is private" % arg)
                else:
                    self.game.send_rcon('g_password ""')
                    self.game.rcon_tell(sar['player_num'], "^7Password removed - Server is public")

            # exec - execute config file
            elif sar['command'] == '!exec' and self.game.players[sar['player_num']].get_admin_role() >= 40:
                if line.split(sar['command'])[1]:
                    arg = line.split(sar['command'])[1].strip()
                    self.game.send_rcon('exec %s' % arg)
                else:
                    self.game.rcon_tell(sar['player_num'], "^7Usage: !exec <filename>")

            # map - load given map
            elif sar['command'] == '!map' and self.game.players[sar['player_num']].get_admin_role() >= 40:
                if line.split(sar['command'])[1]:
                    arg = line.split(sar['command'])[1].strip()
                    found, newmap, msg = self.map_found(arg)
                    if not found:
                        self.game.rcon_tell(sar['player_num'], msg)
                    else:
                        self.game.send_rcon('map %s' % newmap)
                else:
                    self.game.rcon_tell(sar['player_num'], "^7Usage: !map <ut4_name>")

            # setnextmap - set the given map as nextmap
            elif sar['command'] == '!setnextmap' and self.game.players[sar['player_num']].get_admin_role() >= 40:
                if line.split(sar['command'])[1]:
                    arg = line.split(sar['command'])[1].strip()
                    found, nextmap, msg = self.map_found(arg)
                    if not found:
                        self.game.rcon_tell(sar['player_num'], msg)
                    else:
                        self.game.send_rcon('g_nextmap %s' % nextmap)
                else:
                    self.game.rcon_tell(sar['player_num'], "^7Usage: !setnextmap <ut4_name>")

            # cyclemap - start next map in rotation
            elif sar['command'] == '!cyclemap' and self.game.players[sar['player_num']].get_admin_role() >= 40:
                self.game.send_rcon('cyclemap')

            # swapteams - swap current teams
            elif sar['command'] == '!swapteams' and self.game.players[sar['player_num']].get_admin_role() >= 80:
                self.game.send_rcon('swapteams')

## head admin level 100
            # leveltest
            elif (sar['command'] == '!leveltest' or sar['command'] == '!lt') and self.game.players[sar['player_num']].get_admin_role() == 100:
                if line.split(sar['command'])[1]:
                    user = line.split(sar['command'])[1].strip()
                    found, victim, msg = self.player_found(user)
                    if not found:
                        self.game.rcon_tell(sar['player_num'], msg)
                    else:
                        self.game.rcon_tell(sar['player_num'], "^3Level %s [^2%d^3]: ^7%s" % (victim.get_name(), victim.get_admin_role(), victim.roles[victim.get_admin_role()]))
                else:
                    self.game.rcon_tell(sar['player_num'], "^3Level %s [^2%d^3]: ^7%s" % (self.game.players[sar['player_num']].get_name(), self.game.players[sar['player_num']].get_admin_role(), self.game.players[sar['player_num']].roles[self.game.players[sar['player_num']].get_admin_role()]))

            # putgroup - add a client to a group
            elif sar['command'] == '!putgroup' and self.game.players[sar['player_num']].get_admin_role() == 100:
                if line.split(sar['command'])[1]:
                    arg = line.split(sar['command'])[1].split()
                    if len(arg) > 1:
                        user = arg[0]
                        right = arg[1]
                        found, victim, msg = self.player_found(user)
                        if not found:
                            self.game.rcon_tell(sar['player_num'], msg)
                        else:
                            if victim.get_registered_user():
                                new_role = victim.get_admin_role()
                            else:
                                # register new user in DB and set role to 1
                                victim.register_user_db(role=1)
                                new_role = 1

                            if right == "user":
                                self.game.rcon_tell(sar['player_num'], "^3%s put in group User" % victim.get_name())
                                new_role = 1
                            elif right == "admin":
                                self.game.rcon_tell(sar['player_num'], "^3%s added as ^7Admin" % victim.get_name())
                                new_role = 40
                            else:
                                self.game.rcon_tell(sar['player_num'], "^3Sorry, you cannot put %s in group <%s>" % (victim.get_name(), right))
                            victim.update_db_admin_role(role=new_role)
                    else:
                        self.game.rcon_tell(sar['player_num'], "^7Usage: !putgroup <name> <group>")
                else:
                    self.game.rcon_tell(sar['player_num'], "^7Usage: !putgroup <name> <group>")

            # ungroup - remove the admin level from a player
            elif sar['command'] == '!ungroup' and self.game.players[sar['player_num']].get_admin_role() == 100:
                if line.split(sar['command'])[1]:
                    user = line.split(sar['command'])[1].strip()
                    found, victim, msg = self.player_found(user)
                    if not found:
                        self.game.rcon_tell(sar['player_num'], msg)
                    else:
                        if 1 < victim.get_admin_role() < 100:
                            self.game.rcon_tell(sar['player_num'], "^3%s put in group User" % victim.get_name())
                            victim.update_db_admin_role(role=1)
                        else:
                            self.game.rcon_tell(sar['player_num'], "^3Sorry, you cannot put %s in group User" % victim.get_name())
                else:
                    self.game.rcon_tell(sar['player_num'], "^7Usage: !ungroup <name>")

## iamgod
            # iamgod - register user as Head Admin
            elif sar['command'] == '!iamgod':
                if self.iamgod:
                    if not self.game.players[sar['player_num']].get_registered_user():
                        # register new user in DB and set admin role to 100
                        self.game.players[sar['player_num']].register_user_db(role=100)
                    else:
                        self.game.players[sar['player_num']].update_db_admin_role(role=100)
                    self.iamgod = False
                    self.game.rcon_tell(sar['player_num'], "^7You are registered as ^6Head Admin")

## unknown command
            elif sar['command'].startswith('!') and len(sar['command']) > 1 and self.game.players[sar['player_num']].get_admin_role() >= 40:
                if sar['command'].lstrip('!') in self.headadmin_cmds:
                    self.game.rcon_tell(sar['player_num'], "^7Insufficient privileges to use command ^3%s" % sar['command'])


### CLASS Player ###
class Player(object):
    """
    Player class
    """
    teams = {0: "green", 1: "red", 2: "blue", 3: "spectator"}
    roles = {0: "Guest", 1: "User", 40: "Admin", 100: "Head Admin"}

    def __init__(self, player_num, ip_address, guid, name):
        """
        create a new instance of Player
        """
        self.player_num = player_num
        self.guid = guid
        self.name = name.replace(' ', '')
        self.registered_user = False
        self.admin_role = 0
        self.address = ip_address
        self.team = 3

        self.prettyname = self.name
        # remove color characters from name
        for item in xrange(10):
            self.prettyname = self.prettyname.replace('^%d' % item, '')

    def check_database(self):
        # check admins table
        values = (self.guid,)
        curs.execute("SELECT `admin_role` FROM `admins` WHERE `guid` = ?", values)
        result = curs.fetchone()
        if result:
            self.admin_role = result[0]
            self.registered_user = True
        else:
            self.registered_user = False

    def register_user_db(self, role=1):
        if not self.registered_user:
            values = (self.guid, self.prettyname, self.address, role)
            curs.execute("INSERT INTO `admins` (`guid`,`name`,`ip_address`,`admin_role`) VALUES (?,?,?,?)", values)
            conn.commit()
            self.admin_role = role

    def update_db_admin_role(self, role):
        values = (role, self.guid)
        curs.execute("UPDATE `admins` SET `admin_role` = ? WHERE `guid` = ?", values)
        conn.commit()
        # overwrite admin role in game, no reconnect of player required
        self.set_admin_role(role)

    def set_name(self, name):
        self.name = name.replace(' ', '')

    def get_name(self):
        return self.name

    def set_guid(self, guid):
        self.guid = guid

    def get_guid(self):
        return self.guid

    def get_player_num(self):
        return self.player_num

    def get_registered_user(self):
        return self.registered_user

    def set_admin_role(self, role):
        self.admin_role = role

    def get_admin_role(self):
        return self.admin_role


### CLASS Game ###
class Game(object):
    """
    Game class
    """
    def __init__(self, config_file):
        """
        create a new instance of Game

        @param config_file: The full path of the bot configuration file
        @type  config_file: String
        """
        self.all_maps_list = []
        self.players = {}
        self.live = False
        game_cfg = ConfigParser.ConfigParser()
        game_cfg.read(config_file)
        self.rcon_handle = Rcon(game_cfg.get('server', 'server_ip'), game_cfg.get('server', 'server_port'), game_cfg.get('server', 'rcon_password'))

        # add pcwbot as player 'World' to the game
        world = Player(1022, '127.0.0.1', 'NONE', 'World')
        self.add_player(world)
        print "- Added pcwbot successful to the game.\n"
        print "pcwbot is running until you are closing this session or pressing CTRL + C to abort this process."
        print "*** Note: Use the provided initscript to run pcwbot as daemon ***\n"

    def send_rcon(self, command):
        """
        send RCON command

        @param command: The RCON command
        @type  command: String
        """
        if self.live:
            self.rcon_handle.push(command)

    def rcon_tell(self, player_num, msg):
        """
        tell message to a specific player

        @param player_num: The player number
        @type  player_num: Integer
        @param msg: The message to display in private chat
        @type  msg: String
        """
        lines = textwrap.wrap(msg, 128)
        for line in lines:
            self.send_rcon('tell %d %s' % (player_num, line))

    def rcon_forceteam(self, player_num, team):
        """
        force player to given team

        @param player_num: The player number
        @type  player_num: Integer
        @param team: The team (red, blue, spectator)
        @type  team: String
        """
        self.send_rcon('forceteam %d %s' % (player_num, team))

    def kick_player(self, player_num):
        """
        kick player

        @param player_num: The player number
        @type  player_num: Integer
        """
        self.send_rcon('kick %d' % player_num)

    def go_live(self):
        """
        go live
        """
        self.live = True
        self.rcon_handle.go_live()
        self.set_all_maps()

    def set_all_maps(self):
        """
        set a list of all available maps
        """
        all_maps = self.rcon_handle.get_rcon_output("dir map bsp")[1].split()
        all_maps_list = [maps.replace("/", "").replace(".bsp", "") for maps in all_maps if maps.startswith("/")]
        pk3_list = self.rcon_handle.get_rcon_output("fdir *.pk3")[1].split()
        all_pk3_list = [maps.replace("/", "").replace(".pk3", "").replace(".bsp", "") for maps in pk3_list if maps.startswith("/ut4_")]

        all_together = list(set(all_maps_list + all_pk3_list))
        all_together.sort()
        if all_together:
            self.all_maps_list = all_together

    def get_all_maps(self):
        """
        get a list of all available maps
        """
        return self.all_maps_list

    def add_player(self, player):
        """
        add a player to the game

        @param player: The instance of the player
        @type  player: Instance
        """
        self.players[player.get_player_num()] = player
        player.check_database()


### Main ###
print "\n\nStarting pcwbot %s:" % __version__

# connect to database
conn = sqlite3.connect('./data.sqlite')
curs = conn.cursor()

# create tables if not exists
curs.execute('CREATE TABLE IF NOT EXISTS admins (id INTEGER PRIMARY KEY NOT NULL, guid TEXT NOT NULL, name TEXT NOT NULL, ip_address TEXT NOT NULL, admin_role INTEGER DEFAULT 1)')

print "- Connected to database 'data.sqlite' successful."

# create instance of LogParser
LogParser('./settings.conf')

# close database connection
conn.close()
