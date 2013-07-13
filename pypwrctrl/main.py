#!/usr/bin/env python3

from pypwrctrl import PlugMaster

import sys
import os.path
import re

from optparse import OptionParser
from configparser import ConfigParser

CONFIG_FILE=os.path.expanduser("~/.pypwrctrl")

GENERAL_SECTION="GENERAL"
PLUG_PREFIX="plug_"

def print_master(master):
    device_count = len(master.devices)
    plug_count = 0

    for device in master.devices:
        print("{} ({}):".format(device.name, device.address))

        for plug in device.plugs:
            print("- {}".format(plug.name), end="")
            if plug.state >= 0:
                print(" ({})".format("on" if plug.state else "off"), end="")
            print()

        print()

        plug_count += len(device.plugs)

    return device_count, plug_count

def load_devices(master, config):
    for section in config.sections():
        if section == GENERAL_SECTION:
            continue

        if not config.has_option(section, 'name'):
            print("Device without name in configuration, skipping")
            continue

        address = section
        name = config.get(section, 'name')

        plugs = []

        for option in config.options(section):
            if not re.match(PLUG_PREFIX + '\d+', option):
                continue

            index = int(option[len(PLUG_PREFIX):])
            pname = config.get(section, option)

            plugs.append((index, pname))

        master.create_device(address, name, plugs)

def switch(master, args, state):
    if len(args) == 0:
        print("Not enough arguments. Please add at least a plug name.")
        return 1
    elif len(args) == 1:
        plugs = master.search_plug(args[0])
    elif len(args) == 2:
        plugs = set()
        devices = master.search_device(args[0])

        for device in devices:
            plugs.update(device.search_plug(args[1]))
    else:
        print("Too many arguments. Only plug name and optionally device name expected.")
        return 1

    if len(plugs) == 0:
        print("No matching plugs found, sorry")
        return 1
    elif len(plugs) > 1:
        print("Warning: Setting multiple matching plugs")

    for plug in plugs:
        plug.switch(state)

def reset(master, args):
    if len(args) == 0:
        print("Not enough arguments. Please add the device name.")
        return 1
    elif len(args) == 1:
        devices = master.search_device(args[0])
    else:
        print("Too many arguments. Only device name expected.")
        return 1

    if len(devices) == 0:
        print("No matching devices found, sorry")
        return 1
    elif len(devices) > 1:
        print("Warning: Resetting multiple matching devices")

    for device in devices:
        device.reset()

def save(master, args):
    parser = ConfigParser()

    parser.add_section(GENERAL_SECTION)
    parser.set(GENERAL_SECTION, 'user', master.user)
    parser.set(GENERAL_SECTION, 'password', master.password)
    parser.set(GENERAL_SECTION, 'pin', str(master.pin))
    parser.set(GENERAL_SECTION, 'pout', str(master.pout))

    for device in master.devices:
        parser.add_section(device.address)
        parser.set(device.address, 'name', device.name)

        for plug in device.plugs:
            key = PLUG_PREFIX + str(plug.index)
            parser.set(device.address, key, plug.name)

    with open(CONFIG_FILE, 'w') as out:
        parser.write(out)

    device_count, plug_count = print_master(master)

    if device_count:
        print("Saved config with {} device(s) and {} plugs".format(device_count, plug_count))
    else:
        print("Saved config without any devices")

def show(master, args):
    device_count, plug_count = print_master(master)

    print("There are {} device(s) and {} plug(s)".format(device_count, plug_count))

def main():
    # available commands

    commands = {
            'on': (
                lambda master, args: switch(master, args, True),
                "[device] plug",
                "switch plug on",
                ),
            'off': (
                lambda master, args: switch(master, args, False),
                "[device] plug",
                "switch plug off",
                ),
            'save': (
                save,
                "",
                "save options and discovered devices",
                ),
            'show': (
                show,
                "",
                "show all discovered or saved devices",
                ),
            'reset': (
                reset,
                "",
                "save options and discovered devices",
                ),
            }

    # load config file if it exists

    config = ConfigParser()
    config.read([CONFIG_FILE])

    # default values

    fallback_user = config.get(GENERAL_SECTION, 'user', fallback='admin')
    fallback_password = config.get(GENERAL_SECTION, 'password', fallback='anel')
    fallback_pin = config.getint(GENERAL_SECTION, 'pin', fallback=75)
    fallback_pout = config.getint(GENERAL_SECTION, 'pout', fallback=77)

    # option parsing

    usage = "usage: %prog [options] command [comand options]"

    parser = OptionParser(usage=usage)

    parser.add_option("-l", "--list",
            action="store_true", dest="list",
            help="List available commands and options")

    parser.add_option("-d", "--discover",
            action="store_true", dest="discover",
            help="Discover devices on network")

    parser.add_option("-u", "--user", dest="user", default=fallback_user,
            help="Username on device (default from config or 'admin')", metavar="USER")
    parser.add_option("-p", "--password", dest="password", default=fallback_password,
            help="Password on device (default from config or  'anel')", metavar="PASSWORD")

    parser.add_option("-i", "--in", dest="pin", default=fallback_pin, type="int",
            help="Port to use for receiving (sending from device perspective, default from config or 75)", metavar="PORT")
    parser.add_option("-o", "--out", dest="pout", default=fallback_pout, type="int",
            help="Port to use for sending (sending from device perspective, default from config or 77)", metavar="PORT")

    (options, args) = parser.parse_args()

    # print command list
    if options.list:
        print("The following commands are available:")

        for name, (fun, usage, desc) in sorted(commands.items(), key=lambda a: a[0]):
            print("- {} {} ({})".format(name, usage, desc))

        return 0

    # command given?
    if len(args) == 0:
        print("Command missing, please add one")
        return 1

    # split arguments
    command = args[0]
    rest = args[1:]

    # valid command?
    if command not in commands:
        print("Unknown command, sorry")
        return 1

    master = PlugMaster(options.pin, options.pout, options.user, options.password)

    # do we have to load the configured devices?
    if not options.discover and command != 'save':
        load_devices(master, config)

    if options.discover:
        master.discover()

    return commands[command][0](master, rest)

if __name__ == '__main__':
    sys.exit(main())
