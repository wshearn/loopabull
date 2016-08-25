#
# Loopabull fedmsg plugin
#   http://www.fedmsg.com/en/latest/
#

from loopabull.plugin import Plugin

import time
import redis
import yaml

class RedisLooper(Plugin):
    """
    Loopabull plugin to implement looper for redis event loop
    """
    def __init__(self, queue, config):
        """
        stub init
        """
        self.key = "RedisLooper"

        self.setup_config(config)

        self.queue = queue

        super(RedisLooper, self).__init__(self)

    def setup_config(self, config):
        """
        Goes through and verifies the config settings and fall back to sane defaults
        """

        if config is None:
            config = dict()
        if config["host"]:
            self.host = config["host"]
        else:
            self.host = "127.0.0.1"

        if config["port"]:
            self.port = config["port"]
        else:
            self.port = 6379

        if config["db"]:
            self.db = config["db"]
        else:
            self.db = 0

    def looper(self):
        """
        Implementation of the generator to feed the event loop
        """
        self.redis_connection = redis.StrictRedis(host=self.host, port=self.port, db=self.db)
        pubsub = self.redis_connection.pubsub()
        pubsub.psubscribe('*')

        for message in pubsub.listen():
            try:
                payload = yaml.load(message["data"])
                yield(message["channel"], payload)
            except Exception as e:
                pass

# vim: set expandtab sw=4 sts=4 ts=4
