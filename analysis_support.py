"""This module contains miscelaneous support functions for analysis code

This module contains a number of constants and support functions for use by
the analysis code.
"""

# Python imports.
import typing

# External imports.
import numpy as np

# Local imports.


# Constants.

ONE_BILLION = 1000000000
"""One billion as an integer.
"""

ONE_MILLION = 1000000
"""One million as an integer.
"""

ONE_MIN_NS = 60*ONE_BILLION
"""The number of nanoseconds in a minute as an integer.
"""


def traverse_dict(dictionary : dict, action : typing.Callable,
                                                          key_list : list = []):
    """Traverses a nested dictionary, performing action.

    Traverses dictionary "dictionary". Action is called on each key
    value pair. "action" is passed both the keys to reach this point and
    the value at this point. Specifically, action should expect to be called as
    action(dictionary, key_list, value).

    Args:
        dictionary (dict): The nested dictionary to traverse.
        action (Callable): The function to be called on each key value pair in
        the nested dictionary. Should expect to be called as action(dictionary,
        key_list, value), where dictionary is the most recent dictionary.
        key_list (list): All keys used to reach this point in the dictionary, in
        the order they were used.
    """

    # Run through all the dictionary items, recurring on nested dictionaries.
    new_key_list = key_list.copy()
    new_key_list.append("")
    for key, value in dictionary.items():

        # Create a key list with the new key.
        new_key_list[-1] = key

        # Make the required call to action.
        action(dictionary, new_key_list, value)

        # If the value is itself a dictionary, recur.
        if isinstance(value, dict):
            traverse_dict(value, action, new_key_list)


def get_ids_for_time_range(timestamps : np.ndarray, time_range : tuple) -> \
                                                                          tuple:
    """Gets the IDs of the timestamps at the start and end of a time range.

    Gets the ID of the first time stamp within the time range and the ID just
    after the last time stamp within the time range.

    Args:
        timestamps (ndarray): Array of timestamps on the same timeline as
        "time_range"'s values. Assumed to be sorted in ascending order. The
        returned IDs are relative to this array.
        time_range (tuple): The earliest and latest times to include in the
        range given by the output, with the form (earliest, latest).

    Return:
        tuple: The ID of the first timestamp within the time range and the ID
        just after the last time stamp within the time range, with the form
        (first, after last).
    """

    # Get the ID of the first timestamp within the time range.
    earliest = np.searchsorted(timestamps, time_range[0])
    latest = np.searchsorted(timestamps, time_range[1])

    # Return the IDs found.
    return earliest, latest