import time
import random

def human_delay(min_s=1, max_s=2):
    time.sleep(random.uniform(min_s, max_s))

def batch_pause(min_s=20, max_s=40):
    time.sleep(random.uniform(min_s, max_s))
