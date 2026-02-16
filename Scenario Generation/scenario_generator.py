"""Generates OpenMATBC scenarios with variable difficulties and durations."""

# Core python imports.
import argparse
from typing import Any, List, Tuple, Set
import random
import string
import re
import math

# External library imports.
import toml
import numpy as np

# Local imports.


# Constants.
SYSMON_ITEMS = ["lights-1-failure", "lights-2-failure",
                "scales-1-failure", "scales-2-failure",
                "scales-3-failure", "scales-4-failure"]
"""The system monitoring task lights and scales."""
SYSMON_FAILURE_COMMANDS = [["true"], ["true"], ["up", "down"],
                           ["up", "down"], ["up", "down"],
                           ["up", "down"]]
"""The kinds of failure each of the system monitoring task items can have."""
SYSMON_MAX_FAILURE_TIMEOUT = 10
"""The maximum time after which the system monitoring task records a failure and
    resets the task item (i.e. at difficulty 0)."""
SYSMON_MIN_FAILURE_TIMEOUT = 2
"""The minimum time after which the system monitoring task records a failure and
    resets the task item (i.e. at difficulty 1)."""
COMMS_CALLSIGN = "CRL001"
"""Callsign to use for the participant in the comms task."""
COMMS_RADIOS = ["COM_1", "COM_2", "NAV_1", "NAV_2"]
"""The radios for the communications task."""
COMMS_FREQUENCIES = [str(float(frequency)/10) for frequency in
                     range(1181, 1370)]
"""The frequency settings allowed for the communications task."""
COMMS_MIN_EVENT_GAP = 20
"""The minimum time between communications task events in seconds."""
COMMS_MIN_EVENT_END_GAP = 30
"""The minimum time between communications task events and the end of the
    segment in seconds."""
RESMAN_TANK_MAXES = [4000, 4000, 2000, 2000]
"""Maximum levels for the resman tanks."""
RESMAN_TARGET_RANGE = [2000, 3000]
"""Range of target levels for the resman tanks."""
RESMAN_UPDATE_INTERVAL = 2
"""Interval between resman tank updates in seconds."""
RESMAN_TANK_STARTING_LEVELS = [2500, 2500, 1000, 1000, 3000, 3000]
"""Starting levels for the resman tanks."""
ZERO_DURATION_BASE_PRIORITY = 100000
"""Base priority for zero duration instructions."""
ZERO_DURATION_PRIORITY_DECREMENT = 10000
"""Priority decrement for zero duration instructions."""
FLAG_PRIORITY = 1000
"""Priority for flag instructions."""
END_FLAG_PRIORITY = 1000000
"""Priority for the end flag instruction."""
MIN_INSTRUCTION_PRIORITY = 200
"""Minimum priority for instructions."""
MIN_SCALES_PRIORITY = 100
"""Minimum priority for scales."""
COLLABORATIVE_MATCHING_IMAGES = ["737_silhouette.png",
    "bicyclist_silhouette.png", "bus_silhouette.png", "car_silhouette.png",
    "church_silhouette.png", "container_ship_silhouette.png",
    "cruise_ship_silhouette.png", "factory_silhouette.png",
    "forklift_silhouette.png", "helicopter_silhouette.png",
    "house_silhouette.png", "lighthouse_silhouette.png", "man_silhouette.png",
    "military_boat_silhouette.png", "motorcycle_silhouette.png",
    "sail_boat_silhouette.png", "scooter_silhouette.png",
    "small_plane_silhouette.png", "tractor_silhouette", "tree_silhouette.png",
    "wind_farm_silhouette.png"]
"""Images to use for collaborative matching tasks."""
COLLABORATIVE_MATCHING_IMAGE_SIZES = [(100, 100), (100, 100), (100, 100),
    (100, 100), (100, 100), (100, 100), (100, 100), (100, 100), (100, 100),
    (100, 100), (100, 100), (100, 100), (100, 100), (100, 100), (100, 100),
    (100, 100), (100, 100), (100, 100), (100, 100), (100, 100), (100, 100)]
COLLABORATIVE_MATCHING_DURATION = 59
"""Duration of collaborative matching subtasks in seconds."""
COLLABORATIVE_MATCHING_GAP_DURATION = 1
"""Duration of gaps between collaborative matching subtasks in seconds."""
COLLABORATIVE_MATCHING_SCENE_MIN_WIDTH = 1100
"""Minimum width of a collaborative matching scene."""
COLLABORATIVE_MATCHING_SCENE_MAX_WIDTH = 2500
"""Maximum width of a collaborative matching scene."""
COLLABORATIVE_MATCHING_SCENE_MIN_HEIGHT = 1100
"""Minimum height of a collaborative matching scene."""
COLLABORATIVE_MATCHING_SCENE_MAX_HEIGHT = 2500
"""Maximum height of a collaborative matching scene."""
COLLABORATIVE_MATCHING_SETUP_PRIORITY = 500
"""Priority of the setup instructions for collaborative matching."""
COLLABORATIVE_MATCHING_MAX_TARGETS = 5
"""Maximum number of target objects in a collaborative matching scene (i.e. at 
    difficulty 0)."""
COLLABORATIVE_MATCHING_MIN_TARGETS = 2
"""Maximum number of target objects in a collaborative matching scene (i.e. at 
    difficulty 0)."""
COLLABORATIVE_MATCHING_MIN_DISTRACTORS = 20
"""Minimum number of distractor objects in a collaborative matching scene (i.e.
    at difficulty 0)."""
COLLABORATIVE_MATCHING_MAX_DISTRACTORS = 80
"""Maximum number of distractor objects in a collaborative matching scene (i.e.
    at difficulty 1)."""


def replace_in_dict(dictionary: dict, key: str, value: Any):
    """Replaces all instances of key in dictionary with value.

    Args:
        dictionary (dict): Dictionary to search.
        key (str): Key to search for.
        value (str): Value to replace key with.
    """

    for k, v in dictionary.items():
        if isinstance(v, dict):
            replace_in_dict(v, key, value)
        elif isinstance(v, list):
            for item_id, item in enumerate(v):
                if isinstance(item, dict):
                    replace_in_dict(item, key, value)
                elif isinstance(item, str):
                    if item == key:
                        v[item_id] = value
        elif isinstance(v, str) and v == key:
            dictionary[k] = value


def find_regex_in_dict(dictionary: dict, regex: str) -> List[Tuple[str, Any]]:
    """Finds all instances of regex in dictionary.

    Args:
        dictionary (dict): Dictionary to search.
        regex (str): Regex to search for.

    Returns:
        list: List of tuples containing the path to the key and the value.
    """

    # Initialise the list of results.
    results = []

    # Search the dictionary.
    for k, v in dictionary.items():
        if isinstance(v, dict):
            results += find_regex_in_dict(v, regex)
        elif isinstance(v, list):
            for item_id, item in enumerate(v):
                if isinstance(item, dict):
                    results += find_regex_in_dict(item, regex)
                elif isinstance(item, str):
                    if re.search(regex, item):
                        results.append((k, v))
        elif isinstance(v, str):
            if re.search(regex, v):
                results.append((k, v))

    return results


class SegmentConfig:
    """Defines a scenario segment.

    Attributes:
        name (str): Name of the segment.
        duration (float): Duration of the segment in seconds.
        seed_offset (int): If none, does nothing. Otherwise, the segment's
            random seed is reset to the base seed plus this offset.
        sysmon_enabled (bool): Whether the system monitoring task is enabled.
        tracking_enabled (bool): Whether the tracking task is enabled.
        comms_enabled (bool): Whether the communications task is enabled.
        resman_enabled (bool): Whether the resource management task is enabled.
        collabmatch_enabled (bool): Whether the collaborative matching task is
            enabled.
        instructions_enabled (bool): Whether the instructions task is enabled.
        scales_enabled (bool): Whether the scales task is enabled.
        sysmon_difficulty (float): Difficulty of the system monitoring task.
        tracking_difficulty (float): Difficulty of the tracking task.
        collabmatch_difficulty (float): Difficulty of the collaborative
            matching task.
        comms_difficulty (float): Difficulty of the communications task.
        resman_difficulty (float): Difficulty of the resource management task.
        sysmon_network (str): Network setup to use for the system monitoring
            task.
        tracking_network (str): Network setup to use for the tracking task.
        collabmatch_network (str): Network setup to use for the collaborative
            matching task.
        comms_network (str): Network setup to use for the communications task.
        resman_network (str): Network setup to use for the resource management
            task.
        instructions_details (list): List of dictionaries containing details of
            each of this segment's instructions tasks.
        scales_details (list): List of dictionaries containing details of each
            of this segment's scales tasks.
        collabmatch_difficulty_matching (float): Difficulty of the matching
            component of the collaborative matching task. Overrides the
            collabmatch_difficulty for generating matching tasks.
        collabmatch_difficulty_post (float): Difficulty of the post success
            component of the collaborative matching task. Overrides the
            collabmatch_difficulty for generating post success tasks.
    """

    def __init__(self, config: dict):
        """Initializes a segment config.

        Args:
            config (dict): Dictionary containing the segment configuration.
        """

        # Store the name and duration.
        self.name = config["name"]
        self.duration = int(config["duration"])

        # Initialise the seed offset.
        self.seed_offset = None
        if "seed_offset" in config:
            self.seed_offset = config["seed_offset"]

        # Initialise the possible tasks.
        self.sysmon_enabled = False
        self.tracking_enabled = False
        self.comms_enabled = False
        self.resman_enabled = False
        self.collabmatch_enabled = False
        self.instructions_enabled = False
        self.scales_enabled = False
        self.scoreboard_enabled = False
        self.sysmon_difficulty = 0.0
        self.tracking_difficulty = 0.0
        self.collabmatch_difficulty = 0.0
        self.comms_difficulty = 0.0
        self.resman_difficulty = 0.0
        self.sysmon_network = "as_host"
        self.tracking_network = "as_host"
        self.collabmatch_network = "as_host"
        self.comms_network = "as_host"
        self.resman_network = "as_host"
        self.instructions_details = []
        self.scales_details = []
        self.resman_reset_blocks = 0
        self.collabmatch_difficulty_matching = 0.0
        self.collabmatch_difficulty_post = 0.0

        # Set up all the specified tasks.
        for task in config["tasks"]:
            if task["name"] == "sysmon":
                self.sysmon_enabled = True
                self.sysmon_difficulty = task["difficulty"]
                if "network" in task:
                    self.sysmon_network = task["network"]
            elif task["name"] == "tracking":
                self.tracking_enabled = True
                self.tracking_difficulty = task["difficulty"]
                if "network" in task:
                    self.tracking_network = task["network"]
            elif task["name"] == "comms":
                self.comms_enabled = True
                self.comms_difficulty = task["difficulty"]
                if "network" in task:
                    self.comms_network = task["network"]
            elif task["name"] == "resman":
                self.resman_enabled = True
                self.resman_difficulty = task["difficulty"]
                if "network" in task:
                    self.resman_network = task["network"]
                if "reset_blocks" in task:
                    self.resman_reset_blocks = task["reset_blocks"]
            elif task["name"] == "collabmatch":
                self.collabmatch_enabled = True
                self.collabmatch_difficulty = task["difficulty"]
                if "difficulty_matching" in task:
                    self.collabmatch_difficulty_matching = \
                        task["difficulty_matching"]
                else:
                    self.collabmatch_difficulty_matching = task["difficulty"]
                if "difficulty_post" in task:
                    self.collabmatch_difficulty_post = \
                        task["difficulty_post"]
                else:
                    self.collabmatch_difficulty_post = task["difficulty"]
                if "network" in task:
                    self.collabmatch_network = task["network"]
            elif task["name"] == "instructions":
                self.instructions_enabled = True
            elif task["name"] == "scales":
                self.scales_enabled = True
            elif task["name"] == "scoreboard":
                self.scoreboard_enabled = True
            else:
                raise ValueError("Unknown task: " + task["name"])

        # Read the details of instructions tasks.
        if self.instructions_enabled:
            for task in config["tasks"]:
                if task["name"] == "instructions":
                    self.instructions_details.append({
                        "file": task["file"]
                    })
                    if "min_duration" in task:
                        self.instructions_details[-1]["min_duration"] = \
                            task["min_duration"]
                    if "image" in task:
                        self.instructions_details[-1]["image"] = task["image"]

        # Read the details of scales tasks.
        if self.scales_enabled:
            for task in config["tasks"]:
                if task["name"] == "scales":
                    self.scales_details.append({
                        "file": task["file"]
                    })

class ScenarioConfig:
    """Defines how a scenario is to be generated.

    Attributes:
        scenario_file (str): Path to the scenario config file this structure was
            created from.
        scenario_variables (dict): Dictionary of variables that were replaced
            during creation of this structure.
        segments (list): List of the segments that make up the scenario.
    """

    def __init__(self, config_file: str, replacement_vars: dict):
        """Loads a scenario specification from a TOML config file.

        Args:
            config_file (str): Path to the TOML config file.
            replacement_vars (dict): Dictionary of variables that replace values
                in the config file.
        """

        # Load config file.
        config = toml.load(config_file)

        # Replace variables.
        for var_name, var_value in replacement_vars.items():
            replace_in_dict(config, var_name, var_value)

        # Check for any remaining variables.
        results = find_regex_in_dict(config, r"^&")
        if len(results) > 0:
            raise ValueError("No value given for scenario variables: " +
                             str(set(results)))

        # Record the scenario generation settings.
        self.scenario_file = config_file
        self.scenario_variables = replacement_vars.copy()

        # Create the segments.
        self.segments = []
        for segment in config["segments"]:
            self.segments.append(SegmentConfig(segment))


class ScenarioGenerator:
    """Generates OpenMATBC scenarios with variable difficulties and durations.

    Attributes:
        config (ScenarioConfig): Configuration of the scenario to generate.
    """


    def __init__(self, config: ScenarioConfig, seed: int = 42):
        """Initializes a scenario generator.

        Args:
            config (ScenarioConfig): Configuration of the scenario to generate.
            seed (int): Seed for the random number generator.
        """

        self.config = config
        self.seed = seed


    def secs_to_time(self, secs: int, priority: int = None) -> str:
        """Converts a time in seconds to a time in the format HH:MM:SS.

        Args:
            secs (int): Time in seconds.
            priority (int): Priority of the command, if any.

        Returns:
            str: Time in the format HH:MM:SS.
        """

        # Calculate the time.
        hours = secs // 3600
        mins = (secs - hours * 3600) // 60
        secs = secs - hours * 3600 - mins * 60

        # Return the time.
        if priority is None:
            return "{:01d}:{:02d}:{:02d}".format(hours, mins, secs)
        else:
            return "{:01d}:{:02d}:{:02d}-{:02d}".format(hours, mins, secs,
                                                        priority)


    def construct_command(self, time_secs: int, command_words: List[str],
                          priority: int = None) -> str:
        """Constructs a command for OpenMATBC.

        Args:
            time_secs (int): Time in seconds to execute the command.
            command_words (list): List of words in the command.
            priority (int): Priority of the command, if any.

        Returns:
            str: The command as a string.
        """

        # Construct the command.
        command = self.secs_to_time(time_secs, priority) + ";"
        for word in command_words[:-1]:
            command += word + ";"
        command += command_words[-1] + "\n"

        # Return the command.
        return command


    def determine_active_tasks(self) -> Set[str]:
        """Determines which tasks are active in the scenario.

        Returns:
            set: Set of the active tasks, given by name string.
        """

        # The active tasks.
        active_tasks: Set[str] = set([])

        # Run through each segment checking which tasks are active.
        for segment in self.config.segments:
            if segment.sysmon_enabled:
                active_tasks.add("sysmon")
            if segment.tracking_enabled:
                active_tasks.add("track")
            if segment.comms_enabled:
                active_tasks.add("communications")
            if segment.resman_enabled:
                active_tasks.add("resman")
            if segment.collabmatch_enabled:
                active_tasks.add("collaborativematching")
            if segment.scoreboard_enabled:
                active_tasks.add("scoreboard")
            active_tasks.add("flag")

        # Return the active tasks.
        return active_tasks


    def construct_start_active_tasks_commands(self, time_secs: int) -> str:
        """Constructs a command to start all active tasks.

        Args:
            time_secs (int): Time in seconds to execute the command.

        Returns:
            str: The command as a string.
        """

        # Construct the command.
        command = ""
        for task in self.determine_active_tasks():
            if task == "collaborativematching":
                command += self.construct_command(time_secs, [task, "start"],
                           COLLABORATIVE_MATCHING_SETUP_PRIORITY+1)
            else:
                command += self.construct_command(time_secs, [task, "start"])

        # Return the command.
        return command


    def construct_pause_hide_active_tasks_commands(self, time_secs: int) -> str:
        """Constructs a command to pause and hide all active tasks.

        Args:
            time_secs (int): Time in seconds to execute the command.

        Returns:
            str: The command as a string.
        """

        # Construct the command.
        command = ""
        for task in self.determine_active_tasks():
            command += self.construct_command(time_secs, [task, "pause"]) + \
                       self.construct_command(time_secs, [task, "hide"])

        # Return the command.
        return command


    def construct_stop_active_tasks_commands(self, time_secs: int) -> str:
        """Constructs a command to stop all active tasks.

        Args:
            time_secs (int): Time in seconds to execute the command.

        Returns:
            str: The command as a string.
        """

        # Construct the command.
        command = "# Stop Commands. \n"
        for task in self.determine_active_tasks():
            command += self.construct_command(time_secs, [task, "stop"])

        # Return the command.
        return command


    def generate(self) -> str:
        """Generates a scenario.

        Returns:
            str: The scenario as a string in a format readable by OpenMATBC.
        """

        # Create the preamble that sets up the tasks.

        # Initialise the timer.
        cur_time = 0

        # Introduction comment.
        scenario = "# OpenMATBC scenario file.\n" + \
            "# This file was generated by scenario_generator.py. Do not " + \
            "edit.\n\n"

        # Set up commands.
        scenario += "# Set up commands.\n"

        # Prevent escape with 'ESC' key.
        scenario += self.construct_command(cur_time, ["allowescape", "false"])

        # Set up the tasks.
        scenario += self.construct_start_active_tasks_commands(cur_time)

        # Pause and hide the tasks.
        scenario += self.construct_pause_hide_active_tasks_commands(cur_time)

        # Miscellaneous setup commands.
        if "sysmon" in self.determine_active_tasks():
            scenario += self.construct_command(cur_time,
                                               ["sysmon", "scalestyle", "2"], 1)
        if "communications" in self.determine_active_tasks():
            scenario += self.construct_command(cur_time, ["communications",
                        "othercallsignnumber", "5"], 1) + \
                self.construct_command(cur_time, ["communications",
                                       "owncallsign", COMMS_CALLSIGN], 1) + \
                self.construct_command(cur_time, ["communications",
                                                  "voicegender", "male"], 1) + \
                self.construct_command(cur_time, ["communications",
                                                  "voiceidiom", "english"], 1)
        scenario += "\n"

        # Flag scenario generation setting in the log.
        scenario += "# Scenario generation settings.\n"
        scenario += self.construct_command(cur_time, ["flag", "flag",
                                           "scenario_file:" +
                                           self.config.scenario_file])
        for var_name, var_value in self.config.scenario_variables.items():
            scenario += self.construct_command(cur_time, ["flag", "flag",
                                               var_name + ":" + str(var_value)])
        scenario += "\n"

        # Generate the scenario.
        cur_time = 0
        zero_duration_priority = ZERO_DURATION_BASE_PRIORITY
        for segment in self.config.segments:

            # Zero duration segments need to be assigned extra priority to
            # ensure they are executed before the next segment begins.
            if segment.duration == 0:
                if zero_duration_priority < ZERO_DURATION_PRIORITY_DECREMENT:
                    raise ValueError("Too many consecutive zero-duration " +
                                     "segments!")
                scenario += self.generate_segment(segment, cur_time,
                                                  zero_duration_priority)
                zero_duration_priority -= ZERO_DURATION_PRIORITY_DECREMENT

            # Standard duration segments.
            else:
                scenario += self.generate_segment(segment, cur_time)
                zero_duration_priority = ZERO_DURATION_BASE_PRIORITY

            # Add the duration of the segment just added to the current time.
            cur_time += segment.duration

        # Close the scenario.
        scenario += self.construct_stop_active_tasks_commands(cur_time) + "\n"
        cur_time += 1
        scenario += "# End of scenario.\n" + \
            self.construct_command(cur_time, ["end"])

        return scenario


    def generate_segment(self, segment: SegmentConfig, start_time: int,
                         general_priority: int = 0) -> \
            str:
        """Generates a segment for a scenario.

        Args:
            segment (SegmentConfig): Configuration of the segment to generate.
            start_time (int): The time at the start of the segment in seconds.
            general_priority (int): A priority to add to all commands in the
                segment. Currently only supports instruction, scale and flag
                commands.

        Returns:
            str: The segment as a string in a format readable by OpenMATBC.
        """

        # Mark the segment with its name.
        segment_text = "# " + segment.name + "\n"
        segment_text += self.construct_command(start_time,
                                               ["flag", "flag",
                                                segment.name + "_begin"],
                                               general_priority +
                                               FLAG_PRIORITY) + "\n"

        # Add one to non collaborative matching class seeds to ensure that the
        # client and server have different tasks.
        add_to_seed = 0
        if segment.collabmatch_network == "client":
            add_to_seed = 1

        # Generate the task commands.
        if segment.instructions_enabled:
            segment_text += self.generate_instructions(start_time, segment,
                                                       general_priority +
                                                       MIN_INSTRUCTION_PRIORITY)
        if segment.scales_enabled:
            segment_text += self.generate_scales(start_time, segment,
                                                 general_priority +
                                                 MIN_SCALES_PRIORITY)
        if segment.sysmon_enabled:
            if segment.seed_offset is not None:
                random.seed(self.seed + segment.seed_offset + add_to_seed)
            segment_text += self.generate_sysmon(start_time, segment.duration,
                                                 segment.sysmon_difficulty,
                                                 segment.sysmon_network)
        if segment.tracking_enabled:
            if segment.seed_offset is not None:
                random.seed(self.seed + segment.seed_offset + add_to_seed)
            segment_text += self.generate_tracking(start_time, segment.duration,
                                                   segment.tracking_difficulty,
                                                   segment.tracking_network)
        if segment.comms_enabled:
            if segment.seed_offset is not None:
                random.seed(self.seed + segment.seed_offset + add_to_seed)
            segment_text += self.generate_comms(start_time, segment.duration,
                                                segment.comms_difficulty,
                                                segment.comms_network)
        if segment.resman_enabled:
            if segment.seed_offset is not None:
                random.seed(self.seed + segment.seed_offset + add_to_seed)
            segment_text += self.generate_resman(start_time, segment.duration,
                                                 segment.resman_difficulty,
                                                 segment.resman_network,
                                                 segment.resman_reset_blocks)
        if segment.collabmatch_enabled:
            if segment.seed_offset is not None:
                random.seed(self.seed + segment.seed_offset)
            segment_text += self.generate_collabmatch(start_time,
                            segment.duration,
                            segment.collabmatch_difficulty_matching,
                            segment.collabmatch_difficulty_post,
                            segment.collabmatch_network)
        if segment.scoreboard_enabled:
            segment_text += self.generate_scoreboard(start_time,
                                                     segment.duration)

        # Close the segment.
        segment_text += "# End of " + segment.name + "\n"
        if segment.duration == 0:
            segment_text += self.construct_command(start_time +
                            segment.duration, ["flag", "flag",
                            segment.name + "_end"], general_priority) + "\n"
        else:
            segment_text += self.construct_command(start_time +
                            segment.duration, ["flag", "flag",
                            segment.name + "_end"],
                            general_priority + END_FLAG_PRIORITY) + "\n"

        # Return the commands that make up the segment.
        return segment_text


    def generate_instructions(self, start_time: int, segment: SegmentConfig,
                              base_priority: int) -> str:
        """Generates commands for instructions screens.

        Args:
            start_time (int): The time at the start of the segment in seconds.
            segment (SegmentConfig): Configuration of the segment to generate,
                including the instructions details.
            base_priority (int): The priority that the last instruction command
                should have, with each earlier command higher priority than the
                last by one.

        Returns:
            str: The instructions commands as a string in a format readable by
                OpenMATBC.
        """

        # The priority of the next instruction command.
        num_commands = 0
        for instruction_details in segment.instructions_details:
            num_commands += 2
            if "min_duration" in instruction_details:
                num_commands += 1
            if "image" in instruction_details:
                num_commands += 1
        priority = base_priority + num_commands - 1

        # Run through each of the instruction windows to display.
        instruction_text = "# Instructions commands.\n"
        for instruction_details in segment.instructions_details:

            # Set the file to display.
            instruction_text += self.construct_command(start_time,
                                ["instruction", "filename",
                                 instruction_details["file"]], priority)
            priority -= 1

            # If there is a minimum duration, set it.
            if "min_duration" in instruction_details:
                instruction_text += self.construct_command(start_time,
                                    ["instruction", "mindurationsec",
                                     str(instruction_details["min_duration"])],
                                    priority)
                priority -= 1

            # If there is an image to display, add the command to do so.
            if "image" in instruction_details:
                instruction_text += self.construct_command(start_time,
                                    ["instruction", "image",
                                     instruction_details["image"]], priority)
                priority -= 1

            # Add the start command to display the instruction.
            instruction_text += self.construct_command(start_time,
                                                       ["instruction", "start"],
                                                       priority)
            priority -= 1

        # Add a space.
        instruction_text += "\n"

        # Return the generated commands.
        return instruction_text


    def generate_scales(self, start_time: int, segment: SegmentConfig,
                        base_priority: int) -> str:
        """Generates commands for scales screens.

        Args:
            start_time (int): The time at the start of the segment in seconds.
            segment (SegmentConfig): Configuration of the segment to generate,
                including the scales details.
            base_priority (int): The priority that the last scales command
                should have, with each earlier command higher priority than the
                last by one.

        Returns:
            str: The scales commands as a string in a format readable by
                OpenMATBC.
        """

        # The priority of the next generic scales command.
        num_commands = len(segment.scales_details)
        priority = base_priority + num_commands - 1

        # Run through each of the scale windows to display.
        scale_text = "# Scales commands. \n"
        for scale_details in segment.scales_details:

            # Set the file to display.
            scale_text += self.construct_command(start_time, ["genericscales",
                                                 "filename",
                                                 scale_details["file"]],
                                                 priority)
            priority -= 1

            # Add the start command to display the instruction.
            scale_text += self.construct_command(start_time, ["genericscales",
                                                "start"], priority)
            priority -= 1

        # Add a space.
        scale_text += "\n"

        # Return the generated commands.
        return scale_text

    def generate_sysmon(self, start_time: int, duration: int, difficulty: int,
                        network: str) -> str:
        """Generates commands for a sysmon segment.

        Generates commands for a sysmon segment of the given duration and
        difficulty.

        Args:
            start_time (int): The time at the start of the segment in seconds.
            duration (int): The duration of the segment in seconds.
            difficulty (int): The difficulty of the segment.
            network (str): The network configuration to use for the segment.

        Returns:
            str: The sysmon commands as a string in a format readable by
                OpenMATBC.
        """

        # The inverse of the difficulty.
        inv_diff = 1.0 - difficulty

        # Calculate the failure timeout based on the difficulty.
        sysmon_failure_timeout = int(max(SYSMON_MAX_FAILURE_TIMEOUT * inv_diff,
                                         SYSMON_MIN_FAILURE_TIMEOUT))

        # The end of this segment.
        end_time = start_time + duration

        # The maximum time between commands given the difficulty.
        max_time_between_commands = sysmon_failure_timeout + (1-difficulty) * \
                                    120
        max_time_between_commands = int(max(max_time_between_commands,
                                                      sysmon_failure_timeout+2))

        # Initialise the task text.
        sysmon_text = "# Sysmon commands.\n\n"

        # Set up and start the task.
        sysmon_text += "# Set up and resume the task.\n" + \
            self.construct_command(start_time, ["sysmon", "show"]) + \
            self.construct_command(start_time, ["sysmon", "resume"]) + \
            self.construct_command(start_time, ["sysmon", "alerttimeout",
                                   str(1000*sysmon_failure_timeout)]) + \
            self.construct_command(start_time, ["sysmon", "network", network]) \
                + "\n"

        # Generate commands for each item.
        for i in range(len(SYSMON_ITEMS)):

            # Comment on what these commands are.
            sysmon_text += "# " + SYSMON_ITEMS[i] + " commands.\n"

            # Determine the time the first command for this item should occur.
            cur_time = start_time + random.randint(0, max_time_between_commands
                                                   - sysmon_failure_timeout)

            # Generate commands for this item.
            while cur_time < end_time - sysmon_failure_timeout:
                failure_command = random.choice(SYSMON_FAILURE_COMMANDS[i])
                command = self.construct_command(cur_time,
                                                 ["sysmon",
                                                  SYSMON_ITEMS[i],
                                                  failure_command])
                sysmon_text += command
                cur_time += random.randint(sysmon_failure_timeout,
                                           max_time_between_commands)

            # Add a newline.
            sysmon_text += "\n"

        # Pause and hide the task.
        sysmon_text += "# Pause and hide the task.\n" + \
            self.construct_command(end_time, ["sysmon", "pause"]) + \
            self.construct_command(end_time, ["sysmon", "hide"]) + "\n"

        # Return the commands.
        return sysmon_text


    def generate_tracking(self, start_time: int, duration: int,
                          difficulty: int, network: str) -> str:
        """Generates commands for a tracking segment.

        Generates commands for a tracking segment of the given duration and
        difficulty.

        Args:
            start_time (int): The time at the start of the segment in seconds.
            duration (int): The duration of the segment in seconds.
            difficulty (int): The difficulty of the segment.
            network (str): The network configuration to use for the segment.

        Returns:
            str: The tracking commands as a string in a format readable by
                OpenMATBC.
        """

        # The end of this segment.
        end_time = start_time + duration

        # Set up the tracking task for this segment.
        tracking_text = "# Tracking commands.\n" + \
            self.construct_command(start_time, ["track", "show"]) + \
            self.construct_command(start_time, ["track", "resume"]) + \
            self.construct_command(start_time, ["track", "network", network]) +\
            self.construct_command(start_time, ["track", "multiplier",
                                                str(1.0 + 4.0*difficulty)]) + \
            self.construct_command(start_time, ["track", "setcursorx",
                                                "0.0"]) + \
            self.construct_command(start_time, ["track", "setcursory",
                                                "0.0"]) + \
            self.construct_command(start_time, ["track", "settime",
                                                str(random.randrange(1000)*3600)
                                                ]) + \
            self.construct_command(end_time, ["track", "pause"]) + \
            self.construct_command(end_time, ["track", "hide"]) + "\n"

        # Return the commands.
        return tracking_text


    def generate_comms(self, start_time: int, duration: int,
                       difficulty: int, network: str) -> str:
        """Generates commands for a communications segment.

        Generates commands for a communications segment of the given duration
        and difficulty.

        Args:
            start_time (int): The time at the start of the segment in seconds.
            duration (int): The duration of the segment in seconds.
            difficulty (int): The difficulty of the segment.
            network (str): The network configuration to use for the segment.

        Returns:
            str: The comms commands as a string in a format readable by
                OpenMATBC.
        """

        # The end of this segment.
        end_time = start_time + duration

        # Calculate inverse difficulty.
        inv_diff = 1.0 - difficulty

        # The number of other callsigns.
        comms_num_other_callsigns = 2 + int(8*difficulty)

        # Probability each event targeting the participant's callsign.
        true_event_probability = 0.25 + 0.5*difficulty

        # Determine the maximum time between events.
        max_time_between_events = COMMS_MIN_EVENT_GAP + inv_diff * 60
        max_time_between_events = int(max(max_time_between_events,
                                          COMMS_MIN_EVENT_GAP+5))

        # Generate the other callsigns.
        other_callsigns = []
        for i in range(comms_num_other_callsigns):
            new_callsign = list(COMMS_CALLSIGN)
            while "".join(new_callsign) in (other_callsigns + [COMMS_CALLSIGN]):
                for j in range(3):
                    if random.random() < inv_diff+0.1:
                        new_callsign[j] = random.choice(string.ascii_uppercase)
                for j in range(3, 6):
                    if random.random() < inv_diff+0.1:
                        new_callsign[j] = random.choice(string.digits)
            other_callsigns.append("".join(new_callsign))

        # Initialise the task text.
        comms_text = "# Communications commands.\n\n"

        # Start the task.
        comms_text += "# Show and resume the task.\n" + \
            self.construct_command(start_time, ["communications", "show"]) + \
            self.construct_command(start_time, ["communications", "resume"]) + \
            self.construct_command(start_time, ["communications", "network",
                                                network]) + "\n"

        # Initialise comms frequencies.
        comms_text += "# Reset radio frequencies.\n"
        for radio in COMMS_RADIOS:
            comms_text += self.construct_command(start_time, ["communications",
                "updatefrequency-" + radio, random.choice(COMMS_FREQUENCIES)])

        # Add a newline.
        comms_text += "\n"

        # Generate comms task events.
        comms_text += "# Segment events.\n"
        cur_time = start_time + random.randint(0, max_time_between_events)
        while cur_time < end_time - COMMS_MIN_EVENT_END_GAP:

            # Determine the target callsign for this event.
            if random.random() < true_event_probability:
                event_callsign = COMMS_CALLSIGN
            else:
                event_callsign = random.choice(other_callsigns)

            # Determine the target radio for this event.
            event_radio = random.choice(COMMS_RADIOS)

            # Determine the target frequency for this event.
            event_frequency = random.choice(COMMS_FREQUENCIES)

            # Add the event.
            comms_text += self.construct_command(cur_time, ["communications",
                                                 "nextfrequencyoverride",
                                                 event_frequency], 1) + \
                self.construct_command(cur_time, ["communications",
                                                  "nextradiooverride",
                                                  event_radio], 1)
            if event_callsign == COMMS_CALLSIGN:
                comms_text += self.construct_command(cur_time,
                                                     ["communications",
                                                      "radioprompt", "own"])
            else:
                comms_text += self.construct_command(cur_time,
                                                     ["communications",
                                                      "nextcallsignoverride",
                                                      event_callsign], 1) + \
                              self.construct_command(cur_time,
                                                     ["communications",
                                                      "radioprompt", "other"])

            # Determine the time of the next event.
            cur_time += random.randint(COMMS_MIN_EVENT_GAP,
                                       max_time_between_events)

        # Add a newline.
        comms_text += "\n"

        # Pause and hide the task.
        comms_text += "# Pause and hide the task.\n" + \
            self.construct_command(end_time, ["communications", "pause"]) + \
            self.construct_command(end_time, ["communications", "hide"]) + "\n"

        # Return the commands.
        return comms_text


    def predict_resman_optimal(self, cur_tank_levels: List[int],
                               pump_states: List[bool], flow_rates: List[int],
                               duration: int) -> Tuple[List[int], int]:
        """Predicts the best possible tank levels for a resman segment.
        
        Predicts the best possible tank levels for a resource management segment
        where the tank levels start at the given levels and the pumps are in the
        given states. 
        
        The (assumed, not proven) optimal strategy is to keep tanks A and B as 
        close to the top of the target range as possible at all times. 
        Secondarily, keep tanks C and D as full as possible. 
        
        To do this, keep pumps 2, 4, 5 and 6 on at all times. Turn on pump 1 if
        tank A is below the maximum level. Turn on pump 2 if tank B is below the
        maximum level. Turn on pump 3 if tank C is below the maximum level. Turn
        on pump 7 if tank B is lower than tank A. Turn on pump 8 if tank A is
        lower than tank B.

        Args:
            cur_tank_levels (List[int]): The current tank levels.
            pump_states (List[bool]): The current pump states, where True is
                working and False is disabled.
            flow_rates (List[int]): The flow rates of each pump in units per
                second. In addition, an extra two elements at the end should be
                the main tank drain rates.
            duration (int): The period to forcast forward over.

        Returns:
            Tuple[List[int], int]: The predicted tank levels after the given
            duration and the amount of leeway for human error detected.
        """

        # The predicted tank levels.
        pred_tank_levels = cur_tank_levels.copy()

        # The amount of lee-way detected. Used to help measure the amount of
        # room for human error and therefore difficulty.
        lee_way = 0

        # Run through the duration in time steps equal to the resman update
        # interval.
        for i in range(duration // RESMAN_UPDATE_INTERVAL):

            # Apply the main tank drain.
            pred_tank_levels[0] -= int(flow_rates[-2] * RESMAN_UPDATE_INTERVAL)
            pred_tank_levels[1] -= int(flow_rates[-1] * RESMAN_UPDATE_INTERVAL)

            # Update tank levels based on the always on pumps.
            if pump_states[1]:
                pred_tank_levels[0] += int(flow_rates[1] *
                                           RESMAN_UPDATE_INTERVAL)
                if pred_tank_levels[0] > RESMAN_TARGET_RANGE[1]:
                    pred_tank_levels[0] -= int(flow_rates[1] *
                                               RESMAN_UPDATE_INTERVAL)
            if pump_states[3]:
                pred_tank_levels[1] += int(flow_rates[3] *
                                           RESMAN_UPDATE_INTERVAL)
                if pred_tank_levels[1] > RESMAN_TARGET_RANGE[1]:
                    pred_tank_levels[1] -= int(flow_rates[3] *
                                               RESMAN_UPDATE_INTERVAL)
            if pump_states[4]:
                pred_tank_levels[2] += int(flow_rates[4] *
                                           RESMAN_UPDATE_INTERVAL)
                if pred_tank_levels[2] > RESMAN_TANK_MAXES[2]:
                    pred_tank_levels[2] = RESMAN_TANK_MAXES[2]
            if pump_states[5]:
                pred_tank_levels[3] += int(flow_rates[5] *
                                           RESMAN_UPDATE_INTERVAL)
                if pred_tank_levels[3] > RESMAN_TANK_MAXES[3]:
                    pred_tank_levels[3] = RESMAN_TANK_MAXES[3]

            # Update tank levels based on the conditional pumps.

            # Pump 1.
            possible_flow = min(flow_rates[0] * RESMAN_UPDATE_INTERVAL,
                                pred_tank_levels[2])
            if pump_states[0] and pred_tank_levels[0] < \
                    RESMAN_TARGET_RANGE[1] - possible_flow:
                pred_tank_levels[0] += int(possible_flow)
                pred_tank_levels[2] -= int(possible_flow)
            elif pump_states[0]:
                lee_way += int(possible_flow)

            # Pump 3.
            possible_flow = min(flow_rates[2] * RESMAN_UPDATE_INTERVAL,
                                pred_tank_levels[3])
            if pump_states[2] and pred_tank_levels[1] < \
                    RESMAN_TARGET_RANGE[1] - possible_flow:
                pred_tank_levels[1] += int(possible_flow)
                pred_tank_levels[3] -= int(possible_flow)
            elif pump_states[2]:
                lee_way += int(possible_flow)

            # Pump 7.
            if pump_states[6] and pred_tank_levels[1] < pred_tank_levels[0]:
                possible_flow = flow_rates[6] * RESMAN_UPDATE_INTERVAL
                pred_tank_levels[1] += int(possible_flow)
                if pred_tank_levels[1] > RESMAN_TARGET_RANGE[1]:
                    pred_tank_levels[1] -= int(possible_flow)
                else:
                    pred_tank_levels[0] -= int(possible_flow)

            # Pump 8.
            if pump_states[7] and pred_tank_levels[0] < pred_tank_levels[1]:
                possible_flow = flow_rates[7] * RESMAN_UPDATE_INTERVAL
                pred_tank_levels[0] += int(possible_flow)
                if pred_tank_levels[0] > RESMAN_TARGET_RANGE[1]:
                    pred_tank_levels[0] -= int(possible_flow)
                else:
                    pred_tank_levels[1] -= int(possible_flow)

        # Return the predicted tank levels.
        return pred_tank_levels, lee_way
        

    def generate_resman_reset(self, reset_time, reset_timer=None) -> str:
        """Generates the set of commands to reset the resource management task.

        Args:
            reset_time (int): The time at which the reset occurs.
            reset_timer (int): The time until the next reset after this one. If
                None, no timer will be shown.

        Returns:
            str: The reset commands as a string in a format readable by
                OpenMATBC.
        """

        # Initialise the reset commands text.
        reset_commands = ""

        # Reset tank levels.
        reset_commands += "# Reset tank levels.\n" + \
            self.construct_command(reset_time, ["resman", "tank-a-level",
                                   str(RESMAN_TANK_STARTING_LEVELS[0])]) + \
            self.construct_command(reset_time, ["resman", "tank-b-level",
                                   str(RESMAN_TANK_STARTING_LEVELS[1])]) + \
            self.construct_command(reset_time, ["resman", "tank-c-level",
                                   str(RESMAN_TANK_STARTING_LEVELS[2])]) + \
            self.construct_command(reset_time, ["resman", "tank-d-level",
                                   str(RESMAN_TANK_STARTING_LEVELS[3])]) + \
            self.construct_command(reset_time, ["resman", "tank-e-level",
                                   str(RESMAN_TANK_STARTING_LEVELS[4])]) + \
            self.construct_command(reset_time, ["resman", "tank-f-level",
                                   str(RESMAN_TANK_STARTING_LEVELS[5])])

        # Reset pump states.
        reset_commands += "# Reset pump states.\n" + \
            self.construct_command(reset_time, ["resman", "pump-1-state",
                                                "0"]) + \
            self.construct_command(reset_time, ["resman", "pump-2-state",
                                                "0"]) + \
            self.construct_command(reset_time, ["resman", "pump-3-state",
                                                "0"]) + \
            self.construct_command(reset_time, ["resman", "pump-4-state",
                                                "0"]) + \
            self.construct_command(reset_time, ["resman", "pump-5-state",
                                                "0"]) + \
            self.construct_command(reset_time, ["resman", "pump-6-state",
                                                "0"]) + \
            self.construct_command(reset_time, ["resman", "pump-7-state",
                                                "0"]) + \
            self.construct_command(reset_time, ["resman", "pump-8-state",
                                                "0"])

        # Reset the timer.
        if reset_timer is not None:
            reset_commands += "# Set reset timer.\n" + \
                self.construct_command(reset_time, ["resman",
                "progresstimertime", str(reset_timer)]) + \
                self.construct_command(reset_time, ["resman",
                                                    "progresstimerstart"])

        # Return the reset commands text.
        return reset_commands


    def generate_resman(self, start_time: int, duration: int,
                        difficulty: int, network: str, reset_blocks: int) -> str:
        """Generates commands for a resource management segment.

        Generates commands for a resource management segment of the given
        duration and difficulty.

        Args:
            start_time (int): The time at the start of the segment in seconds.
            duration (int): The duration of the segment in seconds.
            difficulty (int): The difficulty of the segment.
            network (str): The network configuration to use for the segment.
            reset_blocks (int): The resource management task's tank levels are
                reset every reset_blocks resource management time blocks. Never
                reset if set to 0.

        Returns:
            str: The resman commands as a string in a format readable by
                OpenMATBC.
        """

        # The end of this segment.
        end_time = start_time + duration

        # Calculate inverse difficulty.
        inv_diff = 1 - difficulty

        # Calculate the pump flow rates.
        flow_mult = 1
        if difficulty > 0.1:
            flow_mult = int(difficulty * 8)
        pump_flow_rates = [800, 600, 800, 600, 600, 600, 400, 400, 800, 800]
        for i in range(len(pump_flow_rates)):
            pump_flow_rates[i] *= flow_mult

        # Determine the minimum acceptable tank levels.
        if difficulty < 0.5:
            min_tank_level = RESMAN_TARGET_RANGE[1] - max(pump_flow_rates[-1],
                                                          pump_flow_rates[-2])
        elif difficulty < 0.8:
            min_tank_level = (RESMAN_TARGET_RANGE[1] - RESMAN_TARGET_RANGE[0]) \
                             // 2
        else:
            min_tank_level = RESMAN_TARGET_RANGE[0]

        # Calculate the duration of resman blocks.
        resman_block_duration = (int(10 + (30*inv_diff)) //
                                RESMAN_UPDATE_INTERVAL) * RESMAN_UPDATE_INTERVAL

        # Determine the minimum acceptable lee-way at each step.
        MINIMUM_LEE_WAY_PER_SECOND_BASE_FLOW = 2000 // 60
        minimum_lee_way = int((MINIMUM_LEE_WAY_PER_SECOND_BASE_FLOW *
                              (flow_mult * resman_block_duration)) *
                              max(0.2, inv_diff))

        # Determine the reset time.
        if reset_blocks != 0:
            reset_timer = resman_block_duration * reset_blocks
        else:
            reset_timer = None

        # Create the resman setup.

        # Add a section heading
        resman_text = "# Resource management commands.\n\n"

        # Start the task.
        resman_text += "# Show and resume the task.\n" + \
                      self.construct_command(start_time, ["resman", "show"]) + \
                      self.construct_command(start_time, ["resman", "resume"]) \
                      + self.construct_command(start_time, ["resman", "network",
                                                            network]) + "\n"

        # Set flow rates.
        resman_text += "# Resman flow rates.\n" + \
            self.construct_command(start_time, ["resman",
                                                "tank-a-lossperminute",
                                                str(800 * flow_mult)]) + \
            self.construct_command(start_time, ["resman",
                                                "tank-b-lossperminute",
                                                str(800 * flow_mult)]) + \
            self.construct_command(start_time, ["resman",
                                                "pump-1-flow",
                                                str(pump_flow_rates[0])]) + \
            self.construct_command(start_time, ["resman",
                                                "pump-2-flow",
                                                str(pump_flow_rates[1])]) + \
            self.construct_command(start_time, ["resman",
                                                "pump-3-flow",
                                                str(pump_flow_rates[2])]) + \
            self.construct_command(start_time, ["resman",
                                                "pump-4-flow",
                                                str(pump_flow_rates[3])]) + \
            self.construct_command(start_time, ["resman",
                                                "pump-5-flow",
                                                str(pump_flow_rates[4])]) + \
            self.construct_command(start_time, ["resman",
                                                "pump-6-flow",
                                                str(pump_flow_rates[5])]) + \
            self.construct_command(start_time, ["resman",
                                                "pump-7-flow",
                                                str(pump_flow_rates[6])]) + \
            self.construct_command(start_time, ["resman",
                                                "pump-8-flow",
                                                str(pump_flow_rates[7])]) + "\n"



        # Reset the tank levels.
        resman_text += self.generate_resman_reset(start_time, reset_timer) + \
                       "\n"

        # Create the resman events.
        cur_tank_levels = RESMAN_TANK_STARTING_LEVELS.copy()
        resman_text += "# Resman events.\n"
        for block_id, cur_time in enumerate(range(start_time, end_time,
                                                  resman_block_duration)):

            # Attempt to create a set of pump disablings that is sufficiently
            # difficult but not impossible.
            pump_states = [True, True, True, True, True, True, True, True]
            while True:

                # Choose a pump disabling setup.
                for pump in range(len(pump_states)):
                    pump_states[pump] = random.random() > (difficulty*0.75)

                # Simulate the pump disabling setup.
                next_tank_levels, lee_way = self.predict_resman_optimal(
                    cur_tank_levels, pump_states,
                    np.array(pump_flow_rates) / 60, resman_block_duration)

                # Add lee-way from tanks being above minimum level.
                lee_way += (next_tank_levels[0] - min_tank_level) + \
                           (next_tank_levels[1] - min_tank_level)

                # If the tank levels are above the minimum, accept the setup.
                if next_tank_levels[0] > min_tank_level and \
                        next_tank_levels[1] > min_tank_level and \
                        lee_way > minimum_lee_way:
                    break

            # Update the current tank levels.
            cur_tank_levels = next_tank_levels.copy()

            # Create the resman commands.
            for pump in range(len(pump_states)):
                if not pump_states[pump]:
                    resman_text += \
                        self.construct_command(cur_time, ["resman",
                                               "pump-{}-state".format(pump+1),
                                               "-1"]) + \
                        self.construct_command(min(cur_time +
                                                   resman_block_duration,
                                                   end_time),
                                               ["resman",
                                               "pump-{}-state".format(pump+1),
                                               "0"])

            # Reset if necessary.
            if reset_blocks != 0 and block_id % reset_blocks == reset_blocks-1:
                resman_text += "# Within segment reset.\n" + \
                               self.generate_resman_reset(
                               min(cur_time + resman_block_duration, end_time)
                               , reset_timer) + "# End within segment reset.\n"
                cur_tank_levels = RESMAN_TANK_STARTING_LEVELS.copy()

        # Add a newline.
        resman_text += "\n"

        # Pause and hide the task.
        resman_text += "# Pause and hide the task.\n" + \
                       self.construct_command(end_time, ["resman", "pause"]) + \
                       self.construct_command(end_time, ["resman", "hide"]) + \
                       "\n"

        # Return the commands.
        return resman_text


    def check_object_intersection(self, object1: tuple, object2: tuple) -> bool:
        """Checks if two axis aligned rectangles intersect.

        Args:
            object1 (tuple): The bounds of the first object, in the format
                (left, top, right, bottom).
            object2 (tuple): The bounds of the second object, in the format
                (left, top, right, bottom).

        Returns:
            bool: True if the objects intersect, False otherwise.
        """

        # Check if the objects intersect.
        if object1[0] > object2[2] or object1[2] < object2[0] or \
                object1[1] > object2[3] or object1[3] < object2[1]:
            return False
        else:
            return True


    def generate_add_object_commands(self, scene_width: int, scene_height: int,
            object_id: int, cur_time: int, existing_objects: list,
            next_priority: int) -> str:
        """Generates commands for adding an object to the scene.

        Generates commands for adding an object to a collaborative matching
        subtask.

        Args:
            scene_width (int): The width of the scene.
            scene_height (int): The height of the scene.
            object_id (int): The ID of the object to add.
            cur_time (int): The current time.
            existing_objects (list): The bounds of the objects already in the
                scene, in the format (left, top, right, bottom).
            next_priority (int): The priority of the next command.

        Returns:
            str: The commands to add an object to a collaborative matching task
                as a string in a format readable by OpenMATBC.
        """

        # The width and height of this object.
        width = COLLABORATIVE_MATCHING_IMAGE_SIZES[object_id][0]
        height = COLLABORATIVE_MATCHING_IMAGE_SIZES[object_id][1]

        # Find a location for the object that doesn't intersect with an existing
        # object.
        while True:
            x = random.randint(-scene_width // 2, scene_width // 2 - width)
            y = random.randint(-scene_height // 2, scene_height // 2 - height)
            if not np.any([self.check_object_intersection((x, y, x+width,
                                                           y+height),
                    existing_object) for existing_object in existing_objects]):
                break

        # The commands to add the object.
        add_object_commands = \
            self.construct_command(cur_time, ["collaborativematching",
                "nextobjectimage",
                COLLABORATIVE_MATCHING_IMAGES[object_id]],
                next_priority) + \
            self.construct_command(cur_time, ["collaborativematching",
                "nextobjectposx", str(x)], next_priority) + \
            self.construct_command(cur_time, ["collaborativematching",
                "nextobjectposy", str(y)], next_priority) + \
            self.construct_command(cur_time, ["collaborativematching",
                "nextobjectsizex", str(width)], next_priority) + \
            self.construct_command(cur_time, ["collaborativematching",
                "nextobjectsizey", str(height)], next_priority) + \
            self.construct_command(cur_time, ["collaborativematching",
                "nextobjecttypeid", str(object_id)], next_priority) + \
            self.construct_command(cur_time, ["collaborativematching",
                                   "addobject"], next_priority - 1)

        # Add the object to the list of existing objects.
        existing_objects.append((x, y, x+width, y+height))

        # Return the commands.
        return add_object_commands


    def generate_collabmatch(self, start_time: int, duration: int,
                             difficulty_matching: float, difficulty_post: float,
                             network: str) -> str:
        """Generates commands for a collaborative matching segment.

        Generates commands for a collaborative matching segment of the given
        duration.

        Args:
            start_time (int): The time at the start of the segment in seconds.
            duration (int): The duration of the segment in seconds.
            difficulty_matching (float): The difficulty of the matching task
                component for this segment.
            difficulty_post (float): The difficulty of the post success
                component for this segment.
            network (str): The network configuration to use for the segment.

        Returns:
            str: The collaborative matching commands as a string in a format
                readable by OpenMATBC.
        """

        # The end of this segment.
        end_time = start_time + duration

        # The inverse of the difficulty.
        inv_diff_match = 1.0 - difficulty_matching

        # The object ID list.
        all_object_ids = list(range(len(COLLABORATIVE_MATCHING_IMAGES)))

        # The number of target and distractor objects in each subtask.
        num_target_objects = max(COLLABORATIVE_MATCHING_MIN_TARGETS,
                                 int(inv_diff_match *
                                 (COLLABORATIVE_MATCHING_MAX_TARGETS -
                                  COLLABORATIVE_MATCHING_MIN_TARGETS)))
        num_distractor_objects = max(COLLABORATIVE_MATCHING_MIN_DISTRACTORS,
                                     int(difficulty_matching *
                                     (COLLABORATIVE_MATCHING_MAX_DISTRACTORS -
                                      COLLABORATIVE_MATCHING_MIN_DISTRACTORS)))

        # Determine the size of the collaborative matching scene.
        min_area = COLLABORATIVE_MATCHING_SCENE_MIN_WIDTH * \
            COLLABORATIVE_MATCHING_SCENE_MIN_HEIGHT
        max_area = COLLABORATIVE_MATCHING_SCENE_MAX_WIDTH * \
            COLLABORATIVE_MATCHING_SCENE_MAX_HEIGHT
        target_area = min_area + \
                      int(difficulty_matching * (max_area - min_area))
        ratio = (COLLABORATIVE_MATCHING_SCENE_MIN_HEIGHT + difficulty_matching *
                 (COLLABORATIVE_MATCHING_SCENE_MAX_HEIGHT -
                  COLLABORATIVE_MATCHING_SCENE_MIN_HEIGHT)) / \
                (COLLABORATIVE_MATCHING_SCENE_MIN_WIDTH + difficulty_matching *
                 (COLLABORATIVE_MATCHING_SCENE_MAX_WIDTH -
                  COLLABORATIVE_MATCHING_SCENE_MIN_WIDTH))
        """
        Calculate the width and height of the scene given the target area and 
        the aspect ratio.
        wh = a
        h/w = r
        h = rw
        rw^2 = a
        w^2 = a/r
        w = sqrt(a/r)
        """
        scene_width = int(math.sqrt(target_area / ratio))
        scene_height = int(target_area / scene_width)

        # Set up the collaborative matching task for this segment.
        collabmatch_text = "# Collaborative matching commands.\n" + \
            self.construct_command(start_time, ["collaborativematching",
                                                "show"]) + \
            self.construct_command(start_time, ["collaborativematching",
                                                "resume"]) + \
            self.construct_command(start_time, ["collaborativematching",
                                                "network", network]) + \
            self.construct_command(start_time, ["collaborativematching",
                                                "driftmultiplier",
                                                str(0.2 + 2.0*difficulty_post)])

        # Create the collaborative matching subtasks.
        cur_time = start_time
        client_commands = "# Task commands.\n"
        server_commands = "# Task commands.\n"
        while cur_time + COLLABORATIVE_MATCHING_DURATION + \
                COLLABORATIVE_MATCHING_GAP_DURATION <= end_time:

            # The objects already in the scene.
            existing_objects = []

            # Choose the target object.
            target_id = random.choice(all_object_ids)

            # Get the remaining object IDs.
            remaining_ids = all_object_ids.copy()
            remaining_ids.remove(target_id)

            # Get the set of objects for the server and their IDs.
            object_ids = random.sample(remaining_ids, max(2,
                         int(difficulty_matching *
                         ((len(COLLABORATIVE_MATCHING_IMAGES)-1) // 2))))

            # Get the set of objects for the client and their IDs.
            remaining_ids = [x for x in remaining_ids if x not in object_ids]
            client_object_ids = random.sample(remaining_ids, max(2,
                int(difficulty_matching *
                ((len(COLLABORATIVE_MATCHING_IMAGES)-1) // 2))))

            # Set up the subtask.
            next_priority = COLLABORATIVE_MATCHING_SETUP_PRIORITY
            setup_commands = \
                self.construct_command(cur_time, ["collaborativematching",
                    "scenemaxx", str(scene_width // 2)], next_priority) + \
                self.construct_command(cur_time, ["collaborativematching",
                    "scenemaxy", str(scene_height // 2)], next_priority) + \
                self.construct_command(cur_time, ["collaborativematching",
                    "sceneminx", str(-scene_width // 2)], next_priority) + \
                self.construct_command(cur_time, ["collaborativematching",
                    "sceneminy", str(-scene_height // 2)], next_priority) + \
                self.construct_command(cur_time, ["collaborativematching",
                    "timelimit", str(COLLABORATIVE_MATCHING_DURATION*1000)],
                    next_priority) + \
                self.construct_command(cur_time, ["collaborativematching",
                                                  "refresh"], next_priority-1)
            client_commands += setup_commands
            server_commands += setup_commands
            next_priority -= 2

            # Add the target objects.
            for i in range(num_target_objects):
                server_commands += self.generate_add_object_commands(
                    scene_width, scene_height, target_id, cur_time,
                    existing_objects, next_priority)
                client_commands += self.generate_add_object_commands(
                    scene_width, scene_height, target_id, cur_time,
                    existing_objects, next_priority)
                next_priority -= 2

            # Add the distractor objects.
            for i in range(num_distractor_objects):
                server_commands += self.generate_add_object_commands(
                    scene_width, scene_height, random.choice(object_ids),
                    cur_time, existing_objects, next_priority)
                client_commands += self.generate_add_object_commands(
                    scene_width, scene_height, random.choice(client_object_ids),
                    cur_time, existing_objects, next_priority)
                next_priority -= 2

            # Update the time.
            cur_time += COLLABORATIVE_MATCHING_DURATION + \
                COLLABORATIVE_MATCHING_GAP_DURATION

        # Add the appropriate commands to the text.
        if network == "client":
            collabmatch_text += client_commands
        elif network == "server":
            collabmatch_text += server_commands
        else:
            raise ValueError("Network type '" + network + "' is not valid for" +
                             " the collaborative matching task.")

        # Pause and hide the task.
        collabmatch_text += "# Pause and hide the task.\n" + \
            self.construct_command(end_time, ["collaborativematching",
                                              "pause"]) + \
            self.construct_command(end_time, ["collaborativematching",
                                              "hide"]) + "\n"

        # Return the commands.
        return collabmatch_text


    def generate_scoreboard(self, start_time: int, duration: int) -> str:
        """Generates commands for a scoreboard segment.

        Generates commands for a scoreboard segment of the given duration.

        Args:
            start_time (int): The time at the start of the segment in seconds.
            duration (int): The duration of the segment in seconds.

        Returns:
            str: The scoreboard commands as a string in a format readable by
                OpenMATBC.
        """

        # The end of this segment.
        end_time = start_time + duration

        # Set up the tracking task for this segment.
        scoreboard_text = "# Scoreboard commands.\n" + \
            self.construct_command(start_time, ["scoreboard", "show"]) + \
            self.construct_command(start_time, ["scoreboard", "resume"]) + \
            self.construct_command(end_time, ["scoreboard", "pause"]) + \
            self.construct_command(end_time, ["scoreboard", "hide"]) + "\n"

        # Return the commands.
        return scoreboard_text


def generate_matb_scenario(arg_config: str, arg_var: List[str], arg_seed: int,
                           arg_output: str):
    """Generates OpenMATBC scenarios with variable difficulties and durations.

    Generates OpenMATBC scenarios with variable difficulties and durations. Note
    that if all the parameters are None, then the function will attempt to read
    them from the command line.

    Args:
        arg_config: Path to config file.
        arg_var: Should be of the form 'name=value'. Strings in the config file
            of the form &name will be replaced with the raw string if it is not
            numeric, int(value) if it is an integer or float(value) if it is a
            decimal.
        arg_seed: Seed for randomisation of scenario generation.
        arg_output: Path to output file.
    """

    # Parse command line arguments if this not been run with parameters.
    if arg_config is None and arg_var is None and arg_seed is None and \
            arg_output is None:

        # Parse the command line arguments.
        parser = argparse.ArgumentParser()
        parser.add_argument(
            "--config", "-c", type=str, default="config.toml", required=True,
            help="Path to config file.")
        parser.add_argument(
            "--var", "-v", type=str, action="append", default=[],
            help="Should be of the form 'name=value'. Strings in the config " +
                 "file of the form &name will be replaced with float(value).")
        parser.add_argument(
            "--seed", "-s", type=int, default=42,
            help="Seed for randomisation of scenario generation.")
        parser.add_argument(
            "--output", "-o", type=str, required=True,
            help="Path to output file.")
        args = parser.parse_args()

        # Read the arguments into the standard parameter names.
        arg_config = args.config
        arg_var = args.var
        arg_seed = args.seed
        arg_output = args.output

    # Parse replacement variables.
    replacement_vars = {}
    for var in arg_var:
        var_name, var_value = var.split("=")

        # Replace the variable with the appropriate type.
        try:
            replacement_vars["&" + var_name] = int(var_value)
        except ValueError:
            try:
                replacement_vars["&" + var_name] = float(var_value)
            except ValueError:
                replacement_vars["&" + var_name] = var_value

    # Load config file.
    config = ScenarioConfig(arg_config, replacement_vars)

    # Generate scenario.
    generator = ScenarioGenerator(config, arg_seed)
    scenario_text = generator.generate()

    # Write the scenario to a file.
    with open(arg_output, "w") as f:
        f.write(scenario_text)


if __name__ == "__main__":
    generate_matb_scenario(None, None, None, None)