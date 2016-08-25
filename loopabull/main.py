#!/usr/bin/env python
#
# Loopabull - an event loop driven ansible execution engine
#

import os
import sys
import imp
import pdb
import yaml
import time
import tempfile
import subprocess
import concurrent.futures
from loopabull.messagequeue import MessageQueue

class Loopabull(object):
    """
    Main Loopabull object

    This is where ansible will be executed
    """

    def __init__(self, config_path):
        """
        Loopable __init__
        """

        # set variable from conf file
        self.load_config(config_path)

        self.message_queue = MessageQueue()

        # load plugin
        self.load_plugin()

        # put together the
        self.compose_ansible_playbook_command()

    def load_config(self, config_path):
        """
        Load the various values from the config
        """

        with open(config_path, 'r') as conf_yaml:
            config = yaml.safe_load(conf_yaml)

        self.plugins_metadata = dict()

        # Load user plugins
        for plugin, plugin_config in config["plugins"].items():
            self.compose_plugin_dict(plugin_config, plugin.lower())
        # Fall back to defaults
        if "looper" not in self.plugins_metadata:
            self.compose_plugin_dict({"name": "fedmsg"}, "looper")
        if "translator" not in self.plugins_metadata:
            self.compose_plugin_dict({"name": "rkname"}, "translator")

        try:
            self.routing_keys = config["routing_keys"]
        except IndexError as e:
            print(
                "Invalid config, missing routing_keys section - {}".format(e)
            )
            sys.exit(1)

        try:
            self.workers = config["workers"]
            if not type(self.workers) == int:
                raise ValueError
        except Exception as e:
            print(
                "Invalid config, workers. Defaulting to 5"
            )
            self.workers = 5

        try:
            self.ansible = config["ansible"]
            if 'inventory_path' not in self.ansible:
                raise IndexError
            if 'playbooks_dir' not in self.ansible:
                raise IndexError
        except IndexError as e:
            print(
                "Invalid config, missing valid ansible section - {}".format(e)
            )
            sys.exit(1)

    def compose_plugin_dict(self, plugin_config, plugin_type):
        """
        A generic composer for setting up a plugins metadata for loading later on
        """
        name = plugin_config["name"].lower()
        plugin_type = plugin_type.lower()

        plugin_data = dict()
        plugin_data["name"] = name
        plugin_data["plugin_type"] = plugin_type
        plugin_data["internal_name"] = name + plugin_type
        plugin_data["module_name"] = name.capitalize() + plugin_type.capitalize()
        plugin_data["config"] = plugin_config

        self.plugins_metadata[plugin_type] = plugin_data

    def compose_ansible_playbook_command(self):
        """
        Put together ansible-playbook command with different options based on
        configuration settings
        """

        ansible_cmd = "ansible-playbook -i {}".format(
            self.ansible["inventory_path"]
        )

        if 'modules_dir' in self.ansible:
            ansible_cmd += " -M {}".format(self.ansible["modules_dir"])

        self.ansible_cmd = ansible_cmd

    def load_plugin(self):
        """
        load plugin
        """
        self.plugins = dict()
        self.plugins["loopers"] = []

        for plugin_type in self.plugins_metadata:
            plugin_meta = self.plugins_metadata[plugin_type]
            try:
                plugin_path = os.path.join(
                    os.path.dirname(__file__),
                    'plugins',
                    "{}{}".format(
                        plugin_meta["internal_name"],
                        ".py"
                    ),
                )
                plugin_module = imp.load_source(
                    plugin_meta["internal_name"],
                    plugin_path
                )
                if plugin_meta["plugin_type"] == "looper":
                    self.plugins["loopers"].append(getattr(
                        plugin_module,
                        plugin_meta["module_name"]
                    )(self.message_queue, plugin_meta["config"]))
                else:
                    self.plugins[ plugin_meta["plugin_type"] ] = getattr(
                        plugin_module,
                        plugin_meta["module_name"]
                    )(plugin_meta["config"])
            except (IOError, OSError, ImportError, SyntaxError, KeyError) as e:
                print(
                    "Failure to load module: {} : {} - {}".format(
                        plugin_meta["name"],
                        plugin_path,
                        e
                    )
                )
                sys.exit(2)

    def run(self):
        """
        Run the playbooks
        """
        """
        Threads of each looper here
        """
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.workers) as executor:
            executor.submit(self.message_queue_loop, self.message_queue)
            time.sleep(2)
            for looper in self.plugins["loopers"]:
                executor.submit(self.looper_loop, looper, self.message_queue)

    def looper_loop(self, looper, queue):
        for plugin_rk, plugin_dict in looper.looper():
            weight = 50
            try:
                if plugin_dict["weight"]:
                    weight = plugin_dict["weight"]
            except KeyError as e:
                weight = 50

            queue.add_message((plugin_rk, plugin_dict), weight)

    def message_queue_loop(self, queue):
        sleep_time = 0
        while True:
            #TODO: Add get message count and don't sleep if it is >0 otherwise sleep for upto 5 sec
            msg = queue.get_message()
            if msg is None:
                sleep_time += 1
                if sleep_time > 5:
                    sleep_time = 5
            else:
                sleep_time = 0
                try:
                    plugin_rk = msg[0]
                    plugin_dict = msg[1]
                    if plugin_rk in self.routing_keys or self.routing_keys[0] == "all":
                        tmp_varfile = tempfile.mkstemp()
                        with open(tmp_varfile[-1], 'w') as yaml_file:
                            yaml.safe_dump(plugin_dict, yaml_file, allow_unicode=False)
                            ansible_sp = subprocess.Popen(
                                "{} -e @{} {}.yml".format(
                                    self.ansible_cmd,
                                    tmp_varfile[-1],
                                    os.path.join(
                                        self.ansible["playbooks_dir"],
                                        self.plugins["translator"].translate_path(plugin_rk)
                                ),
                            ).split(),
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE
                        )
                        ansible_out, ansible_err = ansible_sp.communicate()
                        print ansible_out
                        print ansible_err

                except Exception as e:
                    print e
            time.sleep(sleep_time)


# vim: set expandtab sw=4 sts=4 ts=4
