



class FixedSizeQueue:
    def __init__(self, max_size):
        self.max_size = max_size
        self.queue = []

    def enqueue(self, item):
        if len(self.queue) == self.max_size:
            self.queue.pop(0)  # Remove the oldest item
        self.queue.append(item)  # Add the new item

    def dequeue(self):
        if self.queue:
            return self.queue.pop(0)
        else:
            return None  # or raise an exception, based on your preference                                          #Example_Point

    def empty(self):
        return len(self.queue) == 0

    def __str__(self):
        return str(self.queue)





#Example usage
# queue = FixedSizeQueue(3)
# queue.enqueue(1)
# queue.enqueue(2)
# queue.enqueue(3)
# print(queue)  # Should print [1, 2, 3]

# queue.enqueue(4)
# print(queue)  # Should print [2, 3, 4] as 1 is removed

# queue.enqueue(5)
# print(queue)  # Should print [3, 4, 5] as 2 is removed
