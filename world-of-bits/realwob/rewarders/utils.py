import random

def choose_one(items):
    index = random.randint(0, len(items) - 1)
    return items[index]

