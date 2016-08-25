import pdb

class MessageQueue():
    """ Message queue class """

    def __init__(self):
        """
        constructor
        """
        # Message queue is an array of tuples
        # In the format of (routing_key, [dict])
        # routing_key is the playbook to run
        # [dict] is a pyton dict to pass to the playbook
        self.message_queue = []
        self.item_zero_locked = False

    def add_message(self, message, weight = 50):
        """
        Adds a message to the queue. Suports weighting a message so it has
        higher priority and will run earlier.

        The method takes 2 arguments:
            message (REQUIRED) - The message to add to the queue in the format
                                 of (routing_key, [data])
            weight (OPTIONAL) - The weight of the message, scale of 0 to 100
                                50 is the default value.
        """
        queuedmessage = {
            "weight": weight,
            "message": message
        }

        """
        Simple algrothim to sort message_queue on insert by weight
        Not the most accurate but should be enough for our taste as we
        care about speed more
        """
        point_to_check = len(self.message_queue)
        insert_point = (weight * point_to_check) / 100
        while True:
            insert_point = (weight * point_to_check) / 100

            if insert_point == 0 or len(self.message_queue) == 0:
                break
            if self.message_queue[insert_point] and self.message_queue[insert_point]["weight"] <= weight:
                break
            point_to_check = insert_point

            if insert_point == 0 and self.item_zero_locked:
                insert_point = 1

            point_to_check = insert_point

        self.message_queue.insert(insert_point, queuedmessage)


    def get_message(self):
        """
        Returns message from item 0 in message_queue
        and removes item 0 from message_queue

        If message_queue is empty it simply returns none instead
        """
        if len(self.message_queue) == 0:
            return None

        self.item_zero_locked = True
        return_message = self.message_queue[0]["message"]
        del self.message_queue[0]
        self.item_zero_locked = False

        return return_message

# vim: set expandtab sw=4 sts=4 ts=4
