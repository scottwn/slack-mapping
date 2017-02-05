import json
import os

def get_dict(filename):
    if os.path.isfile(filename):
        with open(filename, 'r') as infile:
            return json.load(infile)
    return {}

# timestamp should be a Unix timestamp in milliseconds.
def track(number, timestamp, filename):
    numbers = get_dict(filename)
    numbers[number] = timestamp
    with open(filename, 'w') as outfile:
        json.dump(numbers, outfile)

def already_notified(number, filename):
    numbers = get_dict(filename)
    return number in numbers or str(number) in numbers

# current_time should be a Unix timestamp in milliseconds. max_age should also
# be in milliseconds.
def clean(current_time, max_age, filename):
    numbers = get_dict(filename)
    old_numbers = []
    for number in numbers:
        # numbers[number] refers to the timestamp of the number in the dict.
        if current_time - numbers[number] > max_age:
            old_numbers.append(number)
    for number in old_numbers:
        del numbers[number]
    with open(filename, 'w') as outfile:
        json.dump(numbers, outfile)
