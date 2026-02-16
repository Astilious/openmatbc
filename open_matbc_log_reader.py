"""This module contains a class for reading and analysing OpenMATBC logs.

This module contains a class for reading and analysing an OpenMATBC log,
OpenMATBCLogManager.
"""

# Python imports.
import os
from datetime import datetime
from datetime import timedelta
import json
import pickle
import argparse
import csv

# External imports.
import numpy as np

# Local imports.
import analysis_support

OPEN_MATB_LOG_DATETIME_FORMAT = "%Y%m%d%H:%M:%S.%f"
"""The datetime formate used by OpenMATBCLogReader.

The datetime format that results from concatenating the date from the file name 
with a timestamp.
"""

NASA_TLX_QUESTIONS = ["Mental demand", "Physical demand", "Time pressure",
                                         "Performance", "Effort", "Frustration"]
"""The questions asked for the NASA TLX.
"""

ESC_KEYCODE = 16777216
"""OpenMATBC logs ESC as text rather than keycode (unlike all the other keys). 
This allows translation back to the real value.
"""

COMMS_TIME_FOR_FAILURE = analysis_support.ONE_MIN_NS
"""The maximum response time before a comms task response is considered a 
failure.
"""


class OpenMATBCLogReader:
    """Reads and analyses an OpenMATBC log.

    Reads and analyses an OpenMATBC log. Log can be in a single file or split
    over multiple files.

    Attributes:
        file_paths (list): Paths to the log files.
        log_names (list): List of strings, each of which is the name of one of
        the logs (with the date time portion stripped off).
        log_dates (list): List of strings containing the date at which each log
        starts.
        log_data (dict): Dictionary containing all data from the logs.
    """

    def __init__(self, log_paths : list, load_path : str = None) -> None:
        """Create a new OpenMATBCLogReader to read and analyse the given files.

        Args:
            log_paths (list): List of strings indicating the locations of the
                OpenMATBC log files from which the data this instance manages is
                drawn.
            load_path (str): Path to an existing file which was saved by a
                OpenMATBCLogReader that had already read the files in
                "log_paths". It is assumed the file holds the correct data with
                no checks, so use cautiously. If a path is provided but there is
                no file, a new file is saved there once a standard load is
                complete. If "None" no saving or loading is performed.
        """

        # If there is a file to load, load it instead of doing a normal load.
        if load_path is not None and os.path.exists(load_path):
            self.load_fast_reload_data(load_path)
            return

        # Record the file paths.
        self.file_paths = log_paths.copy()

        # Extract file names and dates.
        self.log_names = []
        self.log_dates = []
        log_times = []
        for path in log_paths:

            # Extract the full file name from the path.
            _, filename = os.path.split(path)

            # Date and time are at the end of the filename, separated from the
            # rest with "_". Extract the date and time.
            filename_components = filename.split("_")
            self.log_dates.append(filename_components[-2])
            log_times.append(filename_components[-1].split(".")[0])

            # Extract the name of the file alone.
            self.log_names.append('_'.join(filename_components[:-2]))

        # Sort the logs by date and time from earliest to latest.
        self.log_dates, log_times, self.file_paths, self.log_names = \
            (list(t) for t in zip(*sorted(zip(self.log_dates, log_times,
                                             self.file_paths, self.log_names))))

        # Load the log data into the data dictionary.
        self.log_data = {}
        for log_path, date in zip(self.file_paths, self.log_dates):
            OpenMATBCLogReader._read_log(log_path, self.log_data, date)

        # Preprocess the data in preparation for analysis.
        self._preprocess_data()

        # Save a copy of the data to speed up future loads.
        if load_path is not None:
            self.save_data_for_fast_reload(load_path)


    @staticmethod
    def _read_log(log_path, log_dictionary, date) -> None:
        """Adds the log at the given location to the given dictionary.

        Reads the log at "log_path" into the dictionary "log_dictionary".
        Entries are timestamped using the time from the log and the date given
        by "date".

        Args:
            log_path (str): The path to a log file.
            log_dictionary (dict): Dictionary of log file data to which this
            data is to be added.
            date (str): The date associated with the log file.
        """

        # Go through the file line by line.
        with open(log_path, 'r') as file:

            # Run through the full file.
            line = file.readline()
            while len(line) != 0:

                # Ignore lines that are empty or comment lines.
                line = line.strip()
                cur_dict = log_dictionary
                if len(line) != 0 and line[0] != "#":

                    # Split every message line into the tab seperated
                    # components.
                    line_components = line.split("\t")
                    line_components = [component for component in
                                             line_components if component != ""]

                    # First component is the timestamp.

                    # Convert to ns since epoch timestamp.
                    timestamp = int((datetime.strptime(date +
                        line_components[0], OPEN_MATB_LOG_DATETIME_FORMAT) -
                        datetime(1970, 1, 1)) / timedelta(seconds=1) *
                                                   analysis_support.ONE_BILLION)

                    # Build any needed parts of the dictionary that don't exist
                    # yet.
                    for component in line_components[1:-1]:
                        if component[0] != "{" and component not in cur_dict:
                            cur_dict[component] = {}

                        # Comms logs some of its data as a string describing a
                        # dictionary. This needs special decoding.
                        elif component[0] == "{":

                            # Read the dictionary.
                            json_style_dict = component.replace("'", "\"")
                            json_style_dict = json_style_dict.replace("<", "\"")
                            json_style_dict = json_style_dict.replace(">", "\"")
                            json_style_dict = \
                                           json_style_dict.replace("None", "-1")
                            component_dict = json.loads(json_style_dict)

                            # This dictionary section can go in the component
                            # corresponding to the radio name.
                            alt_key = component_dict["name"]
                            if alt_key not in cur_dict:
                                cur_dict[alt_key] = {}
                            component = alt_key

                            # Record the state data dictionary in this
                            # component.
                            if "state_dicts" in cur_dict[component]:
                                cur_dict[component]["state_dicts"]["data"][
                                                 "timestamps"].append(timestamp)
                                cur_dict[component]["state_dicts"]["data"][
                                                "values"].append(component_dict)
                            else:
                                cur_dict[component]["state_dicts"] = {}
                                cur_dict[component]["state_dicts"]["data"] = {}
                                cur_dict[component]["state_dicts"]["data"][
                                                   "timestamps"] = [timestamp, ]
                                cur_dict[component]["state_dicts"]["data"][
                                                  "values"] = [component_dict, ]

                        # Dive deeper.
                        cur_dict = cur_dict[component]

                    # Add the bottom level key value pair.
                    if "data" in cur_dict:
                        cur_dict["data"]["timestamps"].append(timestamp)
                        cur_dict["data"]["values"].append(line_components[-1])
                    else:
                        cur_dict["data"] = {}
                        cur_dict["data"]["timestamps"] = [timestamp,]
                        cur_dict["data"]["values"] = [line_components[-1],]

                # Grab the next line to process.
                line = file.readline()


    def _preprocess_data(self) -> None:
        """Prepares the data read into the dictionary for use.

        Preprocess data read into the dictionary into appropriate types to make
        it easier and more efficient to use. This means converting strings to
        ints and floats, lists to numpy arrays, etc.
        """

        # Convert all timestamp lists to numpy arrays.
        def convert_timestamp_lists(dictionary, key_list, value):
            if key_list[-1] == "timestamps":
                dictionary["timestamps"] = np.array(value, dtype=np.int64)
        analysis_support.traverse_dict(self.log_data, convert_timestamp_lists)

        # Convenience function for conversions.
        convert_to_floats = lambda l: np.array([float(x) for x in l],
                                                               dtype=np.float32)
        convert_to_ints = lambda l: np.array([int(x) for x in l],
                                                                 dtype=np.int32)
        strip_point_convert_to_ints = lambda l: \
                  np.array([int(x.replace(".", "")) for x in l], dtype=np.int32)

        # Convert the X and Y tracking values to floats.
        try:
            self.log_data["TRACK"]["STATE"]["CURSOR"]["X"]["data"]["values"] = \
                convert_to_floats(self.log_data["TRACK"]["STATE"]["CURSOR"]["X"
                                                            ]["data"]["values"])
            self.log_data["TRACK"]["STATE"]["CURSOR"]["Y"]["data"]["values"] = \
                convert_to_floats(self.log_data["TRACK"]["STATE"]["CURSOR"]["Y"
                                                            ]["data"]["values"])
        except KeyError:
            pass

        # Convert the collaborative matching time limits to ints.
        try:
            self.log_data["COLLABMATCH"]["TASK"]["TIMELIMIT"]["data"]["values"
                ] = convert_to_ints(self.log_data["COLLABMATCH"]["TASK"][
                                                 "TIMELIMIT"]["data"]["values"])
        except KeyError:
            pass

        # Convert collaborative matchint time on target to ints.
        try:
            self.log_data["COLLABMATCH"]["TRACKING"]["ONTARGETMS"]["data"][
                "values"] = convert_to_ints(self.log_data["COLLABMATCH"][
                                    "TRACKING"]["ONTARGETMS"]["data"]["values"])
        except KeyError:
            pass

        # Convert the tank level values to ints.
        try:
            self.log_data["RESMAN"]["STATE"]["TANKA"]["LEVEL"]["data"]["values"
                ] = convert_to_ints(self.log_data["RESMAN"]["STATE"]["TANKA"
                                                   ]["LEVEL"]["data"]["values"])
            self.log_data["RESMAN"]["STATE"]["TANKB"]["LEVEL"]["data"]["values"
                ] = convert_to_ints(self.log_data["RESMAN"]["STATE"]["TANKB"][
                                                     "LEVEL"]["data"]["values"])
        except KeyError:
            pass

        # Convert comms values.

        # Own comms.
        try:
            comms_own_dict = self.log_data["COMMUN"]["STATE"]["OWN"]
            for channel_name, values in comms_own_dict.items():

                # Convert target frequencies to ints.
                if "TARGET" in values:
                    values["TARGET"]["data"]["values"] = \
                        strip_point_convert_to_ints(
                                             values["TARGET"]["data"]["values"])

                # Extract prompts and convert frequencies.
                if "data" in values:

                    # Extract selected, start and end prompts.
                    start_prompt_bool = [x == "START_PROMPT" for x in
                                                       values["data"]["values"]]
                    start_prompts = np.argwhere(start_prompt_bool)[:,0]
                    values["START_PROMPTS"] = {}
                    values["START_PROMPTS"]["data"] = {}
                    values["START_PROMPTS"]["data"]["timestamps"] = \
                                     values["data"]["timestamps"][start_prompts]
                    values["START_PROMPTS"]["data"]["values"] = \
                            [values["data"]["values"][i] for i in start_prompts]
                    end_prompt_bool = [x == "END_PROMPT" for x in
                                                       values["data"]["values"]]
                    end_prompts = np.argwhere(end_prompt_bool)[:, 0]
                    values["END_PROMPTS"] = {}
                    values["END_PROMPTS"]["data"] = {}
                    values["END_PROMPTS"]["data"]["timestamps"] = \
                                       values["data"]["timestamps"][end_prompts]
                    values["END_PROMPTS"]["data"]["values"] = \
                              [values["data"]["values"][i] for i in end_prompts]
                    selected_bool = [x == "SELECTED" for x in
                                                       values["data"]["values"]]
                    selecteds = np.argwhere(selected_bool)[:, 0]
                    values["SELECTED"] = {}
                    values["SELECTED"]["data"] = {}
                    values["SELECTED"]["data"]["timestamps"] = \
                                         values["data"]["timestamps"][selecteds]
                    values["SELECTED"]["data"]["values"] = \
                                [values["data"]["values"][i] for i in selecteds]

                    # Convert the frequencies.
                    frequency_values = np.argwhere(np.logical_and(
                        np.logical_and(np.logical_not(start_prompt_bool),
                        np.logical_not(end_prompt_bool)),
                                            np.logical_not(selected_bool)))[:,0]
                    values["data"]["timestamps"] = \
                                  values["data"]["timestamps"][frequency_values]
                    values["data"]["values"] = strip_point_convert_to_ints(
                        [values["data"]["values"][i] for i in frequency_values])
        except KeyError:
            pass

        # Other comms.
        try:
            comms_other_dict = self.log_data["COMMUN"]["STATE"]["OTHER"]
            for channel_name, values in comms_other_dict.items():

                # Convert target frequencies to ints.
                if "TARGET" in values:
                    values["TARGET"]["data"]["values"] = \
                        strip_point_convert_to_ints(
                                             values["TARGET"]["data"]["values"])

                # Extract prompts.
                if "data" in values:

                    # Extract start and end prompts.
                    start_prompt_bool = [x == "START_PROMPT" for x in
                                                       values["data"]["values"]]
                    start_prompts = np.argwhere(start_prompt_bool)[:, 0]
                    values["START_PROMPTS"] = {}
                    values["START_PROMPTS"]["data"] = {}
                    values["START_PROMPTS"]["data"]["timestamps"] = \
                        values["data"]["timestamps"][start_prompts]
                    values["START_PROMPTS"]["data"]["values"] = \
                            [values["data"]["values"][i] for i in start_prompts]
                    end_prompt_bool = [x == "END_PROMPT" for x in
                                                       values["data"]["values"]]
                    end_prompts = np.argwhere(end_prompt_bool)[:, 0]
                    values["END_PROMPTS"] = {}
                    values["END_PROMPTS"]["data"] = {}
                    values["END_PROMPTS"]["data"]["timestamps"] = \
                                       values["data"]["timestamps"][end_prompts]
                    values["END_PROMPTS"]["data"]["values"] = \
                              [values["data"]["values"][i] for i in end_prompts]
        except KeyError:
            pass

        # Convert key values.
        # NOTE: KEY_PRESS was added by me, and isn't used at all by default.
        # All events are triggered by key releases (which also seem to fire if a
        # key is held for an extended period).
        try:
            self.log_data["MAIN"]["INPUT"]["KEY_PRESS"]["data"]["values"] = \
                convert_to_ints([ESC_KEYCODE if keycode == "ESC" else keycode
                for keycode in self.log_data["MAIN"]["INPUT"]["KEY_PRESS"][
                                                             "data"]["values"]])
        except KeyError:
            pass
        try:
            self.log_data["MAIN"]["INPUT"]["KEY_RELEASE"]["data"]["values"] = \
                convert_to_ints([ESC_KEYCODE if keycode == "ESC" else keycode
                for keycode in self.log_data["MAIN"]["INPUT"]["KEY_RELEASE"][
                                                             "data"]["values"]])
        except KeyError:
            pass


    def calculate_tracking_error(self, time_period : tuple) -> float:
        """Calculates tracking error over the given time period.

        Calculates the average deviation from the centre of the cursor over the
        givent time period.

        Args:
            time_period (tuple): The time period to consider, with the form
            (start, end). Times should be given as UTC nanoseconds since epoch
            timestamps.

        Return:
            float: The average offset from the centre over the given time
            period.
        """

        # Check there is tracking data for the given period.
        try:
            # Get the cursor position data.
            tracking_x_vals = self.log_data["TRACK"]["STATE"]["CURSOR"]["X"][
                                                               "data"]["values"]
            tracking_y_vals = self.log_data["TRACK"]["STATE"]["CURSOR"]["Y"][
                                                               "data"]["values"]
        except KeyError:
            # No tracking data, so return None.
            return None

        # Determine the IDs corresponding to the time range for the cursor
        # position data.
        tracking_x_id_range = analysis_support.get_ids_for_time_range(
            self.log_data["TRACK"]["STATE"]["CURSOR"]["X"]["data"]["timestamps"
                                                                 ], time_period)
        tracking_y_id_range = analysis_support.get_ids_for_time_range(
            self.log_data["TRACK"]["STATE"]["CURSOR"]["Y"]["data"]["timestamps"
                                                                 ], time_period)

        # Calculate the average offset from the centre (which is at 0,0).
        average_offset = np.linalg.norm(np.array((
            tracking_x_vals[tracking_x_id_range[0]:tracking_x_id_range[1]],
            tracking_y_vals[tracking_y_id_range[0]:tracking_y_id_range[1]])),
                                                                  axis=1).mean()

        # Return the average tracking offset.
        return average_offset


    def calculate_tracking_times_out_of_bounds(self, time_period : tuple) -> \
                                                                     np.ndarray:
        """Calculates the times the cursor was out of bounds in "time_period".

        Calculates the periods within the given time period that the cursor was
        out of bounds, where bounds is the "TARGETRADIUS" used by OpenMATBC.

        Args:
            time_period (tuple): The time period to consider, with the form
            (start, end). Times should be given as UTC nanoseconds since epoch
            timestamps.

        Return:
            ndarray: The periods in which the cursor was out of bounds, with the
            form (start/end, timestamps). None if there are no tracking events
            in the given time period.
        """

        # Check there is tracking data for the given period.
        try:
            # Get the size of the target area.
            target_size = float(self.log_data["TRACK"]["STATE"]["TARGET"][
                                                 "RADIUS"]["data"]["values"][0])
        except KeyError:
            # No tracking data, so return None.
            return None

        # Get the cursor position data.
        tracking_x_timestamps = self.log_data["TRACK"]["STATE"]["CURSOR"]["X"][
                                                           "data"]["timestamps"]
        tracking_x_vals = self.log_data["TRACK"]["STATE"]["CURSOR"]["X"]["data"
                                                                     ]["values"]
        tracking_y_vals = self.log_data["TRACK"]["STATE"]["CURSOR"]["Y"]["data"
                                                                     ]["values"]

        # Determine the IDs corresponding to the time range for the cursor
        # position data.
        tracking_x_id_range = analysis_support.get_ids_for_time_range(
            self.log_data["TRACK"]["STATE"]["CURSOR"]["X"]["data"]["timestamps"
                                                                 ], time_period)
        tracking_y_id_range = analysis_support.get_ids_for_time_range(
            self.log_data["TRACK"]["STATE"]["CURSOR"]["Y"]["data"]["timestamps"
                                                                 ], time_period)

        # Check that there are tracking events within the time range.
        if tracking_x_id_range[0] == tracking_x_id_range[1]:
            return None

        # This only works if the x and y entries are paired.
        assert(tracking_x_id_range[0] == tracking_y_id_range[0] and
                               tracking_x_id_range[1] == tracking_y_id_range[1])

        # Determine the IDs at which the cursor is out of bounds.
        out_of_bounds_times = [i for i in range(tracking_x_id_range[0],
            tracking_x_id_range[1]) if tracking_x_vals[i] > target_size or
                                               tracking_y_vals[i] > target_size]

        # Calculate timestamps for the out of bounds periods.
        start_out_of_bounds = [tracking_x_timestamps[max(id-1,
            tracking_x_id_range[0])] for local_id, id in
            enumerate(out_of_bounds_times) if local_id == 0 or
                                        out_of_bounds_times[local_id-1] != id-1]
        end_out_of_bounds = [tracking_x_timestamps[
            min(id+1, tracking_x_id_range[1]-1)] for local_id, id in
            enumerate(out_of_bounds_times) if local_id ==
            len(out_of_bounds_times)-1 or
                                        out_of_bounds_times[local_id+1] != id+1]

        # Check start and end counts match.
        assert(len(start_out_of_bounds) == len(end_out_of_bounds))

        # Return the out of bounds periods.
        return np.array((start_out_of_bounds, end_out_of_bounds),
                                                                dtype=np.uint64)


    def calculate_total_tracking_time_out_of_bounds(self, time_period : tuple) \
                                                                         -> int:
        """Calculates the time the cursor was out of bounds in "time_period".

        Calculates the total time within the given time period that the cursor
        was out of bounds, where bounds is the "TARGETRADIUS" used by OpenMATBC.

        Args:
            time_period (tuple): The time period to consider, with the form
            (start, end). Times should be given as UTC nanoseconds since epoch
            timestamps.

        Return:
            int: The total amount of time the cursor was out of bounds during
            the given time period in nanoseconds. None if there are no tracking
            events in the given time period.
        """

        # Get the out of bounds periods over time_period.
        times_out_of_bounds = \
                        self.calculate_tracking_times_out_of_bounds(time_period)

        # Return the total time out of bounds.
        if times_out_of_bounds is None:
            return None
        else:
            return np.sum(times_out_of_bounds[1,:] - times_out_of_bounds[0,:])


    def count_sysmon_performance(self, time_period : tuple) -> tuple:
        """Calculates statistics on the system monitor task in "time_period".

        Calculates some basic statistics on performance over the given time
        period. Events, hits, misses and failures are counted (see returns for
        descriptions of each).

        Args:
            time_period (tuple): The time period to consider, with the form
            (start, end). Times should be given as UTC nanoseconds since epoch
            timestamps.

        Return:
            events (int): The total number of system monitor events during the
            period. An event is when a guage goes out of range or a light goes
            to the wrong state, requiring participant response.
            hits (int): The total number of times the participant hit a system
            monitor key and successfully resolved an event.
            misses (int): The total number of times the participant hit a system
            monitor key when there was no event associated with that key.
            failures (int): The total number of times a system monitor event
            occurred and the participant did not respond correctly within the
            time out period.
        """

        # Count the number of events.
        total_events = 0
        sysmon_event_dict = self.log_data["MAIN"]["SCENARIO"]["SYSMON"]
        for entity_with_event, entity_event_dict in sysmon_event_dict.items():
            if entity_with_event != "SCALESTYLE":
                id_range = analysis_support.get_ids_for_time_range(
                           entity_event_dict["data"]["timestamps"], time_period)
                total_events += id_range[1] - id_range[0]

        # Count the number of hits, misses and failures.
        total_hits = 0
        total_misses = 0
        total_failures = 0
        if "CLIENT" in self.log_data["SYSMON"]["ACTION"] or "SERVER" in \
                                              self.log_data["SYSMON"]["ACTION"]:
            sysmon_action_dict = self.log_data["SYSMON"]["ACTION"]["CLIENT"] \
                if "CLIENT" in self.log_data["SYSMON"]["ACTION"] else \
                self.log_data["SYSMON"]["ACTION"]["SERVER"]
            if "CLIENT" in self.log_data["SYSMON"]["ACTION"] and "SERVER" in \
                                              self.log_data["SYSMON"]["ACTION"]:
                sysmon_action_dict = {**sysmon_action_dict,
                    **self.log_data["SYSMON"]["ACTION"]["SERVER"]}
        else:
            sysmon_action_dict = self.log_data["SYSMON"]["ACTION"]
        for key_pressed, key_dict in sysmon_action_dict.items():

            # Get the IDs in the time range.
            id_range = analysis_support.get_ids_for_time_range(
                                key_dict["data"]["timestamps"], time_period)

            # Add the hits.
            hit_ids = np.argwhere([key_dict["data"]["values"][id] == "HIT" for
                     id in range(id_range[0], id_range[1])])[:, 0] + id_range[0]
            total_hits += len(hit_ids)

            # Add the misses (which OpenMATBC's log calls "FA").
            miss_ids = np.argwhere([key_dict["data"]["values"][id] == "FA"
                 for id in range(id_range[0], id_range[1])])[:, 0] + id_range[0]
            total_misses += len(miss_ids)

            # Add the failures (which OpenMATBC's log calls a "MISS").
            failure_ids = np.argwhere([key_dict["data"]["values"][id] == "MISS"
                 for id in range(id_range[0], id_range[1])])[:, 0] + id_range[0]
            total_failures += len(failure_ids)

        return total_events, total_hits, total_misses, total_failures


    def calculate_sysmon_response_time(self, time_period : tuple) -> int:
        """Calculates average response time for the system monitoring task.

        Calculates response time for the system monitoring task. Failures, where
        an event accured and the participant did not respond before the time
        out, are included as taking just the full time out period.

        Args:
            time_period (tuple): The time period to consider, with the form
            (start, end). Times should be given as UTC nanoseconds since epoch
            timestamps.

        Return:
            int: Average response time. Time is given in nanoseconds.
        """

        # Mapping between event names and key responses.
        event_key_map = {"SCALES-1-FAILURE": "F1", "SCALES-2-FAILURE": "F2",
            "SCALES-3-FAILURE": "F3", "SCALES-4-FAILURE": "F4",
                             "LIGHTS-1-FAILURE": "F5", "LIGHTS-2-FAILURE": "F6"}

        # Initialise event start and end dictionary.
        events = {}
        for _, value in event_key_map.items():
            events[value + "_starts"] = []
            events[value + "_stops"] = []

        # Get all the event starts.
        sysmon_event_dict = self.log_data["MAIN"]["SCENARIO"]["SYSMON"]
        for entity_with_event, entity_event_dict in sysmon_event_dict.items():
            if entity_with_event not in ["SCALESTYLE", "ALERTTIMEOUT",
                                                                     "NETWORK"]:
                id_range = analysis_support.get_ids_for_time_range(
                           entity_event_dict["data"]["timestamps"], time_period)
                events[event_key_map[entity_with_event] + "_starts"] += \
                    list(entity_event_dict["data"]["timestamps"][
                                                       id_range[0]:id_range[1]])

        # Get all the event stops.
        sysmon_state_dict = self.log_data["SYSMON"]["STATE"]
        for key_with_event, key_dict in sysmon_state_dict.items():
            id_range = analysis_support.get_ids_for_time_range(
                                    key_dict["data"]["timestamps"], time_period)
            safe_ids = np.argwhere([key_dict["data"]["values"][id] == "SAFE" for
                     id in range(id_range[0], id_range[1])])[:, 0] + id_range[0]
            events[key_with_event + "_stops"] += \
                                  list(key_dict["data"]["timestamps"][safe_ids])

        # Get the total response time.
        total_response_time = 0
        total_responses = 0
        for _, key_name in event_key_map.items():
            total_responses += len(events[key_name + "_starts"])
            total_response_time += np.sum( np.array(events[key_name + "_stops"],
                dtype=np.uint64) - np.array(events[key_name + "_starts"
                         ][:len(events[key_name + "_stops"])], dtype=np.uint64))

        # Return the average response time.
        average_response_time = 0 if total_responses == 0 else \
                                      int(total_response_time / total_responses)
        return average_response_time


    def calculate_resman_times_out_of_range(self, time_period : tuple) -> tuple:
        """Calculates total time outside the target range for the resman task.

        Calculates the total time outside the target range for the resource
        management task within the specified time period.

        Args:
            time_period (tuple): The time period to consider, with the form
            (start, end). Times should be given as UTC nanoseconds since epoch
            timestamps.

        Return:
            tank_a_out_of_range_times (ndarray): The periods in which the
            resource levels of tank a were out of range, with the form
            (start/end, timestamps).
            tank_b_out_of_range_times (ndarray): The periods in which the
            resource levels of tank b were out of range, with the form
            (start/end, timestamps).
        """

        # Determine the allowable range for each tank.
        tolerance = int(self.log_data["RESMAN"]["STATE"]["TANK"]["TOLERANCE"][
                                                           "data"]["values"][0])
        tank_a_target = int(self.log_data["RESMAN"]["STATE"]["TANKA"]["TARGET"][
                                                           "data"]["values"][0])
        tank_b_target = int(self.log_data["RESMAN"]["STATE"]["TANKB"]["TARGET"][
                                                           "data"]["values"][0])
        tank_a_low = tank_a_target - tolerance
        tank_a_high = tank_a_target + tolerance
        tank_b_low = tank_b_target - tolerance
        tank_b_high = tank_b_target + tolerance

        # Get the levels of each tank over the time period.
        tank_a_timestamps = self.log_data["RESMAN"]["STATE"]["TANKA"]["LEVEL"][
                                                           "data"]["timestamps"]
        tank_b_timestamps = self.log_data["RESMAN"]["STATE"]["TANKB"]["LEVEL"][
                                                           "data"]["timestamps"]
        tank_a_id_range = analysis_support.get_ids_for_time_range(
                                                 tank_a_timestamps, time_period)
        tank_b_id_range = analysis_support.get_ids_for_time_range(
                                                 tank_b_timestamps, time_period)
        tank_a_levels = self.log_data["RESMAN"]["STATE"]["TANKA"]["LEVEL"][
                                                               "data"]["values"]
        tank_b_levels = self.log_data["RESMAN"]["STATE"]["TANKB"]["LEVEL"][
                                                               "data"]["values"]

        # Check there are tank level events within the time range.
        if tank_a_id_range[0] == tank_a_id_range[1]:
            return None

        # Get the IDs of the times at which the tanks are out of range.
        tank_a_out_of_range_time_ids = [i for i in range(tank_a_id_range[0],
            tank_a_id_range[1]) if tank_a_levels[i] > tank_a_high or
                                                  tank_a_levels[i] < tank_a_low]
        tank_b_out_of_range_time_ids = [i for i in range(tank_b_id_range[0],
            tank_b_id_range[1]) if tank_b_levels[i] > tank_b_high or
                                                  tank_b_levels[i] < tank_b_low]

        # Get the times at which an out of range period starts for each tank.
        tank_a_out_of_range_starts = [tank_a_timestamps[max(id-1,
            tank_a_id_range[0])] for local_id, id in
            enumerate(tank_a_out_of_range_time_ids) if local_id == 0 or
                               tank_a_out_of_range_time_ids[local_id-1] != id-1]
        tank_b_out_of_range_starts = [tank_b_timestamps[max(id-1,
            tank_b_id_range[0])] for local_id, id in
            enumerate(tank_b_out_of_range_time_ids) if local_id == 0 or
                               tank_b_out_of_range_time_ids[local_id-1] != id-1]

        # Get the times at which an out of range period ends for each tank.
        tank_a_out_of_range_stops = [tank_a_timestamps[
            min(id+1, tank_a_id_range[1]-1)] for local_id, id in
            enumerate(tank_a_out_of_range_time_ids) if local_id ==
            len(tank_a_out_of_range_time_ids)-1 or
                               tank_a_out_of_range_time_ids[local_id+1] != id+1]
        tank_b_out_of_range_stops = [tank_b_timestamps[
            min(id+1, tank_b_id_range[1]-1)] for local_id, id in
            enumerate(tank_b_out_of_range_time_ids) if local_id ==
            len(tank_b_out_of_range_time_ids)-1 or
                               tank_b_out_of_range_time_ids[local_id+1] != id+1]

        # Combine start and stop arrays.
        tank_a_out_of_range_times = np.array((tank_a_out_of_range_starts,
                                    tank_a_out_of_range_stops), dtype=np.uint64)
        tank_b_out_of_range_times = np.array((tank_b_out_of_range_starts,
                                    tank_b_out_of_range_stops), dtype=np.uint64)

        # Return the periods in which resource levels were out of range.
        return tank_a_out_of_range_times, tank_b_out_of_range_times


    def calculate_resman_total_time_out_of_range(self, time_period : tuple) -> \
                                                                            int:
        """Calculates total time outside the target range for the resman task.

        Calculates the total time outside the target range for the resource
        management task within the specified time period.

        Args:
            time_period (tuple): The time period to consider, with the form
            (start, end). Times should be given as UTC nanoseconds since epoch
            timestamps.

        Return:
            int: Total time outside the target range. Time is given in
            nanoseconds.
        """

        # Get the out of range periods over time_period.
        times_out_of_range = \
                           self.calculate_resman_times_out_of_range(time_period)

        # Return the total time out of bounds.
        if times_out_of_range is None:
            return None
        else:
            return np.sum(times_out_of_range[0][1,:] -
                times_out_of_range[0][0,:]) + np.sum(times_out_of_range[1][1,:]
                                                   - times_out_of_range[1][0,:])


    def calculate_comms_response_times(self, time_period : tuple) -> dict:
        """Calculate response time for each comms event in "time_period".

        Calculates the time taken for the participant to respond appropriately
        to each comms event in the given time period. Includes both events
        targeting participant's comms and distractor events. So both how quickly
        the participant responded to events relating to their own command and
        whether they responded to any distractor events can be easily extracted.
        Time taken is based on when the participant changes the correct channel
        to the correct frequency and does not change it again until at least one
        minute after the event began. If the participant does not change to the
        correct frequency at all or does not change to the correct frequency for
        a full minute after the comms event the time taken is recorded as one
        minute.

        Args:
            time_period (tuple): The time period to consider, with the form
            (start, end). Times should be given as UTC nanoseconds since epoch
            timestamps.

        Return:
            dict: Dictionary with the form {"timestamps": timestamps (ndarray),
            "audio_dones" (ndarray): audio prompt playback finish timestamp,
            "owns": own comms (ndarray), "channels": channels (list), "targets":
            target frequencies (ndarray), "times_taken": time taken (ndarray)}.
            "timestamps" contains a list of UTC nanoseconds since epoch
            timestamps for when each comms event started. "audio_dones" contains
            a list of UTC nanoseconds since epoch timestamps for when the audio
            prompt for each comms event finished playback. "owns" contains
            whether each comms event targeted the participant or was a
            distraction event. "channels" contains the channel for each comms
            event. "targets" contains the target frequency for each comms event.
            "times_taken" contains the time taken for the participant to adjust
            comms to the target frequency. "count" is the total number of comms
            callouts. "own_count" is the total number of comms callouts that
            should have been responded to. "failures" is the total number of
            comms callouts that were not responded to correctly. Note that this
            return is NOT sorted.
        """

        # Initialise the comms event dictionary.
        comms_events = {"timestamps": [], "audio_dones": [], "owns": [],
                               "channels": [], "targets": [], "times_taken": []}

        # Extract all comms events in the time period.

        # Run through both own and other events.
        for event_type in ["OWN", "OTHER"]:

            # Check there are events of this type.
            if event_type not in self.log_data["COMMUN"]["STATE"]:
                continue

            # Run through events for each channel.
            comms_state_data = self.log_data["COMMUN"]["STATE"][event_type]
            for channel_name in comms_state_data.keys():

                # Check there are events for this channel.
                if "START_PROMPTS" not in comms_state_data[channel_name] or \
                        "END_PROMPTS" not in comms_state_data[channel_name] or \
                        "TARGET" not in comms_state_data[channel_name]:
                    continue

                # Get the events in this time range.
                event_timestamps = comms_state_data[channel_name][
                                          "START_PROMPTS"]["data"]["timestamps"]
                prompt_ids = analysis_support.get_ids_for_time_range(
                                                  event_timestamps, time_period)

                # Record each event in the time range in the appropriate format.
                prompt_ends = comms_state_data[channel_name]["END_PROMPTS"][
                                                           "data"]["timestamps"]
                event_targets = comms_state_data[channel_name]["TARGET"]["data"
                                                                     ]["values"]
                own = event_type == "OWN"
                for id in range(prompt_ids[0], prompt_ids[1]):
                    comms_events["timestamps"].append(event_timestamps[id])
                    comms_events["audio_dones"].append(prompt_ends[id])
                    comms_events["owns"].append(own)
                    comms_events["channels"].append(channel_name)
                    comms_events["targets"].append(event_targets[id])
                    comms_events["times_taken"].append(0)

        # Now that arrays have reached full size convert to numpy arrays where
        # appropriate.
        comms_events["timestamps"] = np.array(comms_events["timestamps"],
                                                                dtype=np.uint64)
        comms_events["audio_dones"] = np.array(comms_events["audio_dones"],
                                                                dtype=np.uint64)
        comms_events["owns"] = np.array(comms_events["owns"], dtype=bool)
        comms_events["targets"] = np.array(comms_events["targets"],
                                                                 dtype=np.int32)
        comms_events["times_taken"] = np.array(comms_events["times_taken"],
                                                                dtype=np.uint64)

        # Determine response time for each comms event.
        comms_changes = self.log_data["COMMUN"]["STATE"]["OWN"]
        for id in range(np.shape(comms_events["timestamps"])[0]):

            # Grab frequency changes for the associated channel over one minute
            # after the event.
            channel_name = comms_events["channels"][id]
            event_time = comms_events["timestamps"][id]
            target_frequency = comms_events["targets"][id]
            if channel_name in comms_changes.keys():

                # Get changes that occur within a minute of the event.
                change_id_range = analysis_support.get_ids_for_time_range(
                    comms_changes[channel_name]["data"]["timestamps"],
                           (event_time, event_time+analysis_support.ONE_MIN_NS))

                # If the last frequency set for the channel within a minute of
                # the event is the target frequency, record the time taken to
                # settle on it.
                if change_id_range[0] != change_id_range[1] and comms_changes[
                        channel_name]["data"]["values"][change_id_range[1]-1] \
                                                            == target_frequency:
                    comms_events["times_taken"][id] = comms_changes[channel_name
                        ]["data"]["timestamps"][change_id_range[1]-1] - \
                                                                      event_time

                # If the final setting in the time period is incorrect or the
                # channel was not changed during the time period, record maximum
                # time taken.
                else:
                    comms_events["times_taken"][id] = \
                                                     analysis_support.ONE_MIN_NS

            # If the relevant channel was not changed during the entire
            # experiment record maximum time taken.
            else:
                comms_events["times_taken"][id] = analysis_support.ONE_MIN_NS

        # Determine the comms task count and failures.
        comms_events["count"] = comms_events["timestamps"].shape[0]
        comms_events["own_count"] = np.count_nonzero(comms_events["owns"])
        comms_events["failures"] = np.count_nonzero(np.logical_and(
            comms_events["times_taken"] >= COMMS_TIME_FOR_FAILURE,
                                                          comms_events["owns"]))

        # Return the comms task response data calculated.
        return comms_events


    def calculate_average_comms_response_time(self, time_period : tuple) -> int:
        """Calculates the average response time for the communications task.

        Calculates the average response time for the communications task in the
        given time period. If the participant does not change to the correct
        frequency at all or does not change to the correct frequency for a full
        minute after the comms event the time taken is treated as one minute.

        Args:
            time_period (tuple): The time period to consider, with the form
            (start, end). Times should be given as UTC nanoseconds since epoch
            timestamps.

        Return:
            int: The average time taken to respond to the comms task in
            nanoseconds.
        """

        # Get the participant's performance on the comms task in the time
        # period.
        comms_dict = self.calculate_comms_response_times(time_period)

        # Calculate average response time for the comms task.
        total_response_time = 0
        num_responses = 0
        for event_id, response_time in enumerate(comms_dict["times_taken"]):
            if comms_dict["owns"][event_id]:
                total_response_time += response_time
                num_responses += 1

        # Return the average response time.
        average_response_time = 0 if num_responses == 0 else \
                                        int(total_response_time / num_responses)
        return average_response_time


    def calculate_collabmatch_stats(self, time_period : tuple) -> dict:
        """Calculates statistics for the collaborative matching task.

        Calculates statistics for the collaborative matching task in the given
        time period. The statistics calculated are returned in a dictionary and
        are as follows:
        - "count": The number of collaborative matching tasks runs.
        - "successes": The number of collaborative matching task successes.
        - "failures": The number of collaborative matching task failures.
        - "average_time": The average time taken to complete a collaborative
        matching task in nanoseconds.
        - "on_target_time": The total time spent over the target object after
        completing a collaborative matching task in nanoseconds.
        - "off_target_time": The total time not over the target object after
        completing a collaborative matching task in nanoseconds.
        - "total_post_success_time": The total time spent in the post success
        state reached after completing a collaborative matching task in
        nanoseconds.
        - "total_time": The total time spent on the collaborative matching task.
        - "matching_score": The inverse of the portion of time spent in the
        matching state relative to total time (i.e. so that a higher score
        indicates better performance).
        - "post_success_score": The portion of the time in the post success
        state in which the cursor was over the target object.
        - "score": The score achieved in the collaborative matching task,
        calculated as the on_target_time divided by the total_time.

        Args:
            time_period (tuple): The time period to consider, with the form
            (start, end). Times should be given as UTC nanoseconds since epoch
            timestamps.

        Return:
            dict: Dictionary containing the statistics calculated (see
            description body for details).
        """

        # The return dictionary.
        collabmatch_stats = {}

        # Get the collaborative matching successes and failures.
        collabmatch_counts = self.calculate_collabmatch_successes(time_period)
        for key, value in collabmatch_counts.items():
            collabmatch_stats[key] = value

        # Get the collaborative matching times.
        collabmatch_times = self.calculate_collabmatch_times(time_period)
        for key, value in collabmatch_times.items():
            collabmatch_stats[key] = value

        # Calculate the scores.
        collabmatch_stats["matching_score"] = 0 if collabmatch_stats[
            "count"] == 0 else 0.5 * ((1 - collabmatch_stats["total_match_time"]
            / collabmatch_stats["total_time"]) +
                (collabmatch_counts["successes"] / collabmatch_counts["count"]))
        collabmatch_stats["post_success_score"] = 0 if collabmatch_stats[
            "total_post_success_time"] == 0 else (
            collabmatch_stats["on_target_time"] /
                                   collabmatch_stats["total_post_success_time"])
        collabmatch_stats["score"] = 0 if collabmatch_stats["count"] == 0 \
            else collabmatch_stats["on_target_time"] / \
                                                 collabmatch_stats["total_time"]

        # Return the collaborative matching statistics.
        return collabmatch_stats


    def calculate_collabmatch_times(self, time_period : tuple) -> dict:
        """Calculates the collaborative matching times.

        Calculates the collaborative matching times for the given time period.
        The times are returned in a dictionary and are as follows:
        - "total_match_time": The total time spent in the matching portion of
        the collaborative matching task in nanoseconds.
        - "average_time": The average time taken to complete a collaborative
        matching task in nanoseconds.
        - "on_target_time": The total time spent over the target object after
        completing a collaborative matching task in nanoseconds.
        - "off_target_time": The total time not over the target object after
        completing a collaborative matching task in nanoseconds.
        - "total_post_success_time": The total time spent in the post success
        state reached after completing a collaborative matching task in
        nanoseconds.
        - "total_time": The total time spent on the collaborative matching task.

        Args:
            time_period (tuple): The time period to consider, with the form
            (start, end). Times should be given as UTC nanoseconds since epoch
            timestamps.

        Returns:
            dict: Dictionary containing the collaborative matching times (see
            description body for details).
        """

        # The return dictionary.
        collabmatch_times = {}

        # Get the collaborative matching task state periods.
        collabmatch_periods = self.determine_collabmatch_periods(time_period)

        # Get the post success state statistics.
        target_stats = self.calculate_collabmatch_target_stats(time_period,
                                       collabmatch_periods["post_success_task"])

        # Calculate the total and average completion time.
        collabmatch_times["total_match_time"] = 0
        for period in collabmatch_periods["primary_task"]:
            collabmatch_times["total_match_time"] += period[1] - period[0]
        collabmatch_times["average_time"] = 0 if \
            len(collabmatch_periods["primary_task"]) == 0 else \
            int(collabmatch_times["total_match_time"] //
                                       len(collabmatch_periods["primary_task"]))

        # Add the target statistics.
        collabmatch_times["on_target_time"] = target_stats["on_target_time"]
        collabmatch_times["off_target_time"] = target_stats["off_target_time"]

        # Calculate the total time spent in the post success stage.
        collabmatch_times["total_post_success_time"] = 0
        for period in collabmatch_periods["post_success_task"]:
            collabmatch_times["total_post_success_time"] += period[1] - \
                                                                       period[0]

        # Calculate the total time spent on the collaborative matching task.
        collabmatch_times["total_time"] = 0
        for period in collabmatch_periods["active"]:
            collabmatch_times["total_time"] += period[1] - period[0]

        # Return the collaborative matching times.
        return collabmatch_times


    def calculate_collabmatch_target_stats(self, time_period : tuple,
                                   post_success_periods : tuple = None) -> dict:
        """Calculates statistics for collaborative matching post success stage.

        Calculates statistics for the collaborative matching post success stage
        in the given time period. This primarily means the total amount of time
        spent over the target object and the total amount of time spent not over
        the target object while the post success stage was active. The
        statistics are returned in a dictionary and are as follows:
        - "on_target_time": The total time spent over the target object after
        completing a collaborative matching task in nanoseconds.
        - "off_target_time": The total time not over the target object after
        completing a collaborative matching task in nanoseconds.

        Args:
            time_period (tuple): The time period to consider, with the form
            (start, end). Times should be given as UTC nanoseconds since epoch
            timestamps.
            post_success_periods (tuple): The periods spent in the post success
            stage as a list of tuples of start and end times given as UTC
            nanoseconds since epoch. If None, the periods will be determined
            automatically.

        Returns:
            dict: Dictionary containing the collaborative matching post success
            stage statistics (see description body for details).
        """

        # The return dictionary.
        target_stats = {}

        # Get the post success periods if necessary.
        if post_success_periods is None:
            collabmatch_periods = self.determine_collabmatch_periods(
                                                                    time_period)
            post_success_periods = collabmatch_periods["post_success_task"]

        # Calculate the total time spent over the target object.
        try:
            target_time_timestamps = self.log_data["COLLABMATCH"]["TRACKING"][
                                             "ONTARGETMS"]["data"]["timestamps"]
            target_times = self.log_data["COLLABMATCH"]["TRACKING"]["ONTARGETMS"
                                                             ]["data"]["values"]
            target_time_ids = analysis_support.get_ids_for_time_range(
                                            target_time_timestamps, time_period)
            target_times = target_times[target_time_ids[0]:target_time_ids[1]]

        except KeyError:
            target_times = [0]
        target_stats["on_target_time"] = int(np.sum(target_times)) * 1000000

        # Small errors in the sum could result in an on target time greater
        # than the total time spent in the post success stage. In this case,
        # cap the on target time at the total time spent in the post success
        # stage.
        target_stats["on_target_time"] = min(target_stats["on_target_time"],
            int(np.sum([period[1] - period[0] for period in
                        post_success_periods])))

        # Calculate the total time spent not over the target object.
        target_stats["off_target_time"] = int(np.sum([period[1] - period[0] for
              period in post_success_periods])) - target_stats["on_target_time"]

        # Return the collaborative matching post success stage statistics.
        return target_stats


    def determine_collabmatch_periods(self, time_period : tuple) -> dict:
        """Determines the state of the collaborative matching task.

        Determines the state of the collaborative matching task in the given
        time period. The state is returned in a dictionary and is as follows:
        - "active": The periods in which the collaborative matching task is
        active as a list of tuples of start and end times given as UTC
        nanoseconds since epoch.
        - "not_active": The periods spent without the collaborative matching
        task active as a list of tuples of start and end times given as UTC
        nanoseconds since epoch.
        - "primary_task": The periods spent in the primary task state as a list
        of tuples of start and end times given as UTC nanoseconds since epoch.
        - "post_success_task": The periods spent in the post success task state
        as a list of tuples of start and end times given as UTC nanoseconds
        since epoch.

        Args:
            time_period (tuple): The time period to consider, with the form
            (start, end). Times should be given as UTC nanoseconds since epoch
            timestamps.

        Returns:
            dict: Dictionary containing the collaborative matching task state
            (see description body for details).
        """

        # Early exit if there is no collaborative matching data.
        if "COLLABMATCH" not in self.log_data:
            return {"active": [], "not_active": [], "primary_task": [],
                    "post_success_task": []}

        # Get the collaborative matching time limits for the period.
        time_limits = self.log_data["COLLABMATCH"]["TASK"]["TIMELIMIT"]["data"][
                                                                       "values"]
        time_limit_timestamps = self.log_data["COLLABMATCH"]["TASK"]["TIMELIMIT"
                                                         ]["data"]["timestamps"]
        time_limit_ids = analysis_support.get_ids_for_time_range(
                                             time_limit_timestamps, time_period)
        time_limits = time_limits[time_limit_ids[0]:time_limit_ids[1]]
        time_limit_timestamps = time_limit_timestamps[time_limit_ids[0]:
                                                              time_limit_ids[1]]

        # Get the collaborative matching signals for the period.
        collabmatch_signals = self.log_data["COLLABMATCH"]["TASK"]["data"
                                                                     ]["values"]
        collabmatch_signal_timestamps = self.log_data["COLLABMATCH"][
                                                   "TASK"]["data"]["timestamps"]
        signal_ids = analysis_support.get_ids_for_time_range(
                                     collabmatch_signal_timestamps, time_period)
        collabmatch_signals = collabmatch_signals[signal_ids[0]:signal_ids[1]]
        collabmatch_signal_timestamps = collabmatch_signal_timestamps[
                                                    signal_ids[0]:signal_ids[1]]

        # Collect the RESET events, each of which indicates the start of a
        # collaborative matching task.
        reset_events = [timestamp for signal, timestamp in zip(
            collabmatch_signals, collabmatch_signal_timestamps) if signal ==
                                                                        "RESET"]

        # Determine the periods in which the collaborative matching task is
        # active.
        active_periods = []
        for reset_event_id, reset_event in enumerate(reset_events):

            # Get the time limit at the time of this reset event.
            cur_time_limit = None
            for time_limit, time_limit_timestamp in zip(time_limits,
                                                         time_limit_timestamps):
                if time_limit_timestamp > reset_event:
                    break
                else:
                    # int() prevents it from being a 32-bit integer, which will
                    # overflow.
                    cur_time_limit = int(time_limit)

            # Time limit is expressed in milliseconds, so convert to
            # nanoseconds.
            cur_time_limit *= 1000000

            # Check this reset event against the next reset event, if there is
            # one. If their time difference is less than the time limit, then
            # this reset is discarded.
            if reset_event_id < len(reset_events) - 1:
                if reset_events[reset_event_id + 1] - reset_event < \
                                                                cur_time_limit:
                    continue

            # This active period runs from the reset to the reset plus the time
            # limit.
            active_periods.append((reset_event, reset_event + cur_time_limit))

        # Determine the periods spent without the collaborative matching task
        # active. Periods less than 100 milliseconds are ignored.
        not_active_periods = []
        if len(active_periods) > 0:
            if active_periods[0][0] - time_period[0] > 100000000:
                not_active_periods.append((time_period[0],
                                                          active_periods[0][0]))
            for i in range(len(active_periods) - 1):
                if active_periods[i + 1][0] - active_periods[i][1] > 100000000:
                    not_active_periods.append((active_periods[i][1],
                                                      active_periods[i + 1][0]))
            if time_period[1] - active_periods[-1][1] > 100000000:
                not_active_periods.append((active_periods[-1][1],
                                                                time_period[1]))

        # Determine the periods spent in the primary task state, which is the
        # period between a reset and the following SUCCESS or TIMEOUT signal,
        # and the post success state, which is the period between a SUCCESS
        # signal and the end of the task period.
        primary_task_periods = []
        post_success_task_periods = []
        for task_period in active_periods:

            # Get the index of the reset event.
            reset_index = collabmatch_signal_timestamps.tolist().index(
                                                                 task_period[0])

            # Get the index of the next SUCCESS or TIMEOUT signal.
            try:
                success_index = collabmatch_signals.index("SUCCESS",
                                                                    reset_index)
            except ValueError:
                success_index = len(collabmatch_signals)
            try:
                timeout_index = collabmatch_signals.index("TIMEOUT",
                                                                    reset_index)
            except ValueError:
                timeout_index = len(collabmatch_signals)
            if success_index < timeout_index:
                primary_task_periods.append((task_period[0],
                                  collabmatch_signal_timestamps[success_index]))
                post_success_task_periods.append((collabmatch_signal_timestamps[
                                                success_index], task_period[1]))
            else:
                primary_task_periods.append((task_period[0], task_period[1]))

        # Return the collaborative matching task state.
        return {
            "active": active_periods,
            "not_active": not_active_periods,
            "primary_task": primary_task_periods,
            "post_success_task": post_success_task_periods
        }


    def calculate_collabmatch_successes(self, time_period : tuple) -> dict:
        """Calculates the collaborative matching successes and failure counts.

        Args:
            time_period (tuple): The time period to consider, with the form
            (start, end). Times should be given as UTC nanoseconds since epoch
            timestamps.

        Returns:
            dict: Dictionary containing the collaborative matching successes and
            failure counts. The dictionary has the following form:
            {
                "count": The number of collaborative matching tasks runs.
                "successes": The number of collaborative matching task
                successes.
                "failures": The number of collaborative matching task failures.
            }
        """

        # The return dictionary.
        collabmatch_counts = {
            "count": 0,
            "successes": 0,
            "failures": 0
        }

        # Early return if there is no collaborative matching data.
        if "COLLABMATCH" not in self.log_data:
            return collabmatch_counts

        # Get the success and failure signal list.
        collabmatch_signals = self.log_data["COLLABMATCH"]["TASK"]["data"
                                                                     ]["values"]
        collabmatch_signal_timestamps = self.log_data["COLLABMATCH"][
                                                   "TASK"]["data"]["timestamps"]

        # Determine the ID range for the time period.
        signal_ids = analysis_support.get_ids_for_time_range(
                                     collabmatch_signal_timestamps, time_period)

        # Determine the number of successes and failures.
        for signal_id in range(signal_ids[0], signal_ids[1]):
            if collabmatch_signals[signal_id] == "SUCCESS":
                collabmatch_counts["successes"] += 1
            elif collabmatch_signals[signal_id] == "TIMEOUT":
                collabmatch_counts["failures"] += 1
        collabmatch_counts["count"] += collabmatch_counts["successes"] + \
                                                  collabmatch_counts["failures"]

        # Return the collaborative matching counts.
        return collabmatch_counts


    def determine_subtask_periods(self):
        """Determines the time range associated with each subtask.

        Determines the time range associated with each subtask. A subtask is
        defined by the period between two FLAG events.

        Return:
            list: List of tuples with the form (period name, start timestamp,
            end timestamp), where the timestamps are given in UTC nanoseconds
            since epoch.
        """

        # Get the list of flag events.
        flag_events = self.log_data["MAIN"]["SCENARIO"]["FLAG"]["FLAG"]
        subtask_periods = []
        for timestamp, value in zip(flag_events["data"]["timestamps"],
                                    flag_events["data"]["values"]):

            # Get the name of the subtask.
            new_subtask_list = value.split("_")
            new_subtask_name = '_'.join(new_subtask_list[:-1])

            # If the subtask is a start event, add a new entry.
            if new_subtask_list[-1] == "begin":
                subtask_periods.append((new_subtask_name, timestamp, None))

            # If the subtask is an end event, update the end time of the
            # corresponding start event.
            elif new_subtask_list[-1] == "end":
                for subtask_id, subtask in enumerate(subtask_periods):
                    if subtask[0] == new_subtask_name:
                        subtask_periods[subtask_id] = (subtask[0], subtask[1],
                                                                      timestamp)
                        break

            # Could make use of other flag types here.
            else:
                pass

        # Return the subtask periods generated.
        return subtask_periods


    def get_survey_results(self, time_period : tuple) -> list:
        """Returns survey results received during the time period given.

        Args:
            time_period (tuple): The time period to consider, with the form
            (start, end). Times should be given as UTC nanoseconds since epoch
            timestamps.

        Return:
            list: List of tuples with the form (timestamp, question label,
            participant response).
        """

        # Initialise the survey results list.
        survey_results = []

        # Run through all survey question labels.
        survey_data = self.log_data["SCALES"]["INPUT"]
        for label, label_data in survey_data.items():

            # Get the responses under this label for the time period.
            range_ids = analysis_support.get_ids_for_time_range(
                                  label_data["data"]["timestamps"], time_period)

            # Add a list entry for each response.
            for id in range(range_ids[0], range_ids[1]):
                survey_results.append((label_data["data"]["timestamps"][id],
                                  label, int(label_data["data"]["values"][id])))

        # Return the collected survey response data.
        return survey_results


    def get_tlx_responses(self, time_period) -> dict:
        """Returns responses to individual NASA TLX questions.

        Returns responses all NASA TLX questions over the given time period.

        Args:
            time_period (tuple): The time period to consider, with the form
                (start, end). Times should be given as UTC nanoseconds since
                epoch timestamps.

        Return:
            list: List of lists with the form [timestamp, {question:
                response}].
        """

        # Get the survey results for the time period.
        survey_results = self.get_survey_results(time_period)

        # Get the total for each set of TLX results.
        results = []
        for timestamp, question, response in survey_results:

            # Check if this is a NASA TLX question.
            if question in NASA_TLX_QUESTIONS:

                # If this is a NASA TLX question, check if there is an entry
                # for the set of questions asked at this time yet.
                target_id = len(results)
                for i in range(len(results)):
                    if np.abs(timestamp - results[i][0]) < \
                                                   analysis_support.ONE_BILLION:
                        target_id = i

                # If no existing entry was found create a new  entry.
                if target_id == len(results):
                    responses = {question: response}
                    results.append([timestamp, responses])

                # If there is an existing entry, add the new result to it.
                else:
                    results[target_id][1][question] = response

        # Return the NASA TLX results found.
        return results


    def get_tlx_score(self, time_period : tuple) -> dict:
        """Returns all NASA TLX results over the given time period.

        Returns all NASA TLX results over the given time period. Results here
        refers to the overall load figure attained by summing the load factors.

        Args:
            time_period (tuple): The time period to consider, with the form
            (start, end). Times should be given as UTC nanoseconds since epoch
            timestamps.

        Return:
            list: List of tuples with the form (timestamp, tlx result)
        """

        # Get the survey results for the time period.
        survey_results = self.get_survey_results(time_period)

        # Get the total for each set of TLX results.
        results = []
        for timestamp, question, response in survey_results:

            # Check if this is a NASA TLX question.
            if question in NASA_TLX_QUESTIONS:

                # If this is a NASA TLX question, check if there is an entry
                # for the set of questions asked at this time yet.
                target_id = len(results)
                for i in range(len(results)):
                    if np.abs(timestamp - results[i][0]) < \
                                                   analysis_support.ONE_BILLION:
                        target_id = i

                # If no existing entry was found create a new  entry.
                if target_id == len(results):
                    results.append([timestamp, response])

                # If there is an existing entry, add the new result to it.
                else:
                    results[target_id][1] += response

        # Return the NASA TLX results found.
        return results


    def calculate_success_portion(self, time_period: tuple,
            sysmon_events: list = None,
            tracking_total_time_out_of_bounds: float = None,
            collabmatch_score: float = None,
            collabmatch_matching_score: float = None,
            collabmatch_post_success_score: float = None,
            comms_responses: dict = None,
            resman_total_time_out_of_range: float = None) -> dict:
        """Calculate the portion of maximum score achieved.

        Calculate the portion of maximum score achieved within the given time
        period.

        Args:
            time_period (tuple): The time period on which performance data is
            to be calculated, with the form (start, end). Times should be given
            as UTC nanoseconds since epoch timestamps.
            sysmon_events: Can be provided to save computation time. Calculated
            automatically if not provided.
            tracking_total_time_out_of_bounds: Can be provided to save
            computation time. Calculated automatically if not provided.
            collabmatch_score: Can be provided to save computation time.
            Calculated automatically if not provided.
            collabmatch_matching_score: Can be provided to save computation
            time. Calculated automatically if not provided.
            collabmatch_post_success_score: Can be provided to save computation
            time. Calculated automatically if not provided.
            comms_responses: Can be provided to save computation time.
            Calculated automatically if not provided.
            resman_total_time_out_of_range: Can be provided to save computation
            time. Calculated automatically if not provided.

        Returns:
            Dictionary. Each item is the name of a task (i.e. "sysmon",
            "tracking", "collabmatch", "resman", "comms") and the portion of
            maximum score for that task, as a float between 0 and 1. In
            addition, "average" and "product" are provided, which give overall
            score calculated by averaging or multiplying (respectively) all task
            scores.
        """

        # Gather up the per task data to be used for this assessment.
        if sysmon_events is None and "SYSMON" in self.log_data:
            sysmon_events = self.count_sysmon_performance(time_period)
        if tracking_total_time_out_of_bounds is None and "TRACK" in \
                                                                  self.log_data:
            tracking_total_time_out_of_bounds = \
                   self.calculate_total_tracking_time_out_of_bounds(time_period)
        if (collabmatch_score is None or collabmatch_matching_score is None
                or collabmatch_post_success_score is None) and "COLLABMATCH" \
                                                               in self.log_data:
            collabmatch_stats = self.calculate_collabmatch_stats(time_period)
            collabmatch_matching_score = collabmatch_stats["matching_score"]
            collabmatch_post_success_score = \
                                         collabmatch_stats["post_success_score"]
            collabmatch_score = collabmatch_stats["score"]
        if comms_responses is None and "COMMUN" in self.log_data:
            comms_responses = self.calculate_comms_response_times(time_period)
        if resman_total_time_out_of_range is None and "RESMAN" in self.log_data:
            resman_total_time_out_of_range = \
                      self.calculate_resman_total_time_out_of_range(time_period)

        # Calculate per task percent success.
        time_in_time_period = float(time_period[1] - time_period[0])
        if sysmon_events is not None and sysmon_events[0] > 0:
            sysmon_score = 1.0 - min((sysmon_events[2] + sysmon_events[3])
                                                 / float(sysmon_events[0]), 1.0)
        else:
            sysmon_score = None
        if tracking_total_time_out_of_bounds is not None:
            tracking_score = 1.0 - (tracking_total_time_out_of_bounds /
                                                            time_in_time_period)
        else:
            tracking_score = None
        if comms_responses is not None and comms_responses["own_count"] > 0:
            comms_score = 1.0 - min(comms_responses["failures"] /
                                       float(comms_responses["own_count"]), 1.0)
        elif comms_responses is not None and comms_responses["count"] > 0:
            comms_score = 1.0
        else:
            comms_score = None
        if resman_total_time_out_of_range is not None:
            resman_score = 1.0 - ((resman_total_time_out_of_range/2) /
                                                            time_in_time_period)
        else:
            resman_score = None

        # Calculate the composite scores.
        average_score = 0.0
        product_score = 1.0
        average_score_no_collab = 0.0
        num_scores = 0.0
        if sysmon_score is not None:
            average_score += sysmon_score
            product_score *= sysmon_score
            num_scores += 1.0
        if tracking_score is not None:
            average_score += tracking_score
            product_score *= tracking_score
            num_scores += 1.0
        if collabmatch_score is not None:
            average_score += collabmatch_score
            product_score *= collabmatch_score
            num_scores += 1.0
        if comms_score is not None:
            average_score += comms_score
            product_score *= comms_score
            num_scores += 1.0
        if resman_score is not None:
            average_score += resman_score
            product_score *= resman_score
            num_scores += 1.0
        if num_scores > 0:
            average_score /= num_scores
        else:
            average_score = None

        # Package everything into a dictionary.
        scores = {
            "sysmon": sysmon_score,
            "tracking": tracking_score,
            "collabmatch": collabmatch_score,
            "collabmatch_matching": collabmatch_matching_score,
            "collabmatch_post_success": collabmatch_post_success_score,
            "comms": comms_score,
            "resman": resman_score,
            "average": average_score,
            "product": product_score,
        }

        # Return the calculated scores.
        return scores


    def performance_evaluation(self, time_period):
        """Calculate performance statistics for the given period.

        Calculates performance statistics for all OpenMATBC tasks over the given
        period.

        Args:
            time_period (tuple): The time period on which performance data is
            to be calculated, with the form (start, end). Times should be given
            as UTC nanoseconds since epoch timestamps.

        Returns:
            dict: Performance statistics over the given period. Each result
            corresponds to one of this class's functions. See each function's
            docstrings for details on what each statistic means.
            "average_tracking_error": calculate_tracking_error
            "tracking_times_out_of_bounds":
                                          calculate_tracking_times_out_of_bounds
            "tracking_total_time_out_of_bounds":
                                     calculate_total_tracking_time_out_of_bounds
            "sysmon_events", "sysmon_hits", "sysmon_misses", "sysmon_failures":
                                                        count_sysmon_performance
            "sysmon_average_response_time": calculate_sysmon_response_time
            "resman_times_out_of_range": calculate_resman_times_out_of_range
            "resman_total_time_out_of_range":
                                        calculate_resman_total_time_out_of_range
            "comms_responses": calculate_comms_response_times
            "comms_average_response_time": calculate_average_comms_response_time
            "survey_results": get_survey_results
            "scores": calculate_success_portion
        """

        # Initialise the performance statistics dictionary.
        performance_statistics = {}

        # System monitoring statistics.
        if "SYSMON" in self.log_data:
            sysmon_stats = self.count_sysmon_performance(time_period)
            performance_statistics["sysmon_events"] = sysmon_stats[0]
            performance_statistics["sysmon_hits"] = sysmon_stats[1]
            performance_statistics["sysmon_misses"] = sysmon_stats[2]
            performance_statistics["sysmon_failures"] = sysmon_stats[3]
            performance_statistics["sysmon_average_response_time"] = \
                                self.calculate_sysmon_response_time(time_period)
        else:
            sysmon_stats = None
            performance_statistics["sysmon_events"] = None
            performance_statistics["sysmon_hits"] = None
            performance_statistics["sysmon_misses"] = None
            performance_statistics["sysmon_failures"] = None
            performance_statistics["sysmon_average_response_time"] = None

        # Tracking task statistics.
        if "TRACK" in self.log_data:
            performance_statistics["average_tracking_error"] = \
                                      self.calculate_tracking_error(time_period)
            performance_statistics["tracking_times_out_of_bounds"] = \
                        self.calculate_tracking_times_out_of_bounds(time_period)
            performance_statistics["tracking_total_time_out_of_bounds"] = \
                   self.calculate_total_tracking_time_out_of_bounds(time_period)
        else:
            performance_statistics["average_tracking_error"] = None
            performance_statistics["tracking_times_out_of_bounds"] = None
            performance_statistics["tracking_total_time_out_of_bounds"] = None

        # Collaborative matching statistics.
        if "COLLABMATCH" in self.log_data:
            collabmatch_stats = self.calculate_collabmatch_stats(time_period)
            performance_statistics["collabmatch_count"] = \
                                                      collabmatch_stats["count"]
            performance_statistics["collabmatch_successes"] = \
                                                  collabmatch_stats["successes"]
            performance_statistics["collabmatch_failures"] = \
                                                   collabmatch_stats["failures"]
            performance_statistics["collabmatch_average_time"] = \
                                               collabmatch_stats["average_time"]
            performance_statistics["collabmatch_on_target_time"] = \
                                             collabmatch_stats["on_target_time"]
            performance_statistics["collabmatch_off_target_time"] = \
                                            collabmatch_stats["off_target_time"]
            performance_statistics["collabmatch_total_post_success_time"] = \
                                    collabmatch_stats["total_post_success_time"]
            performance_statistics["collabmatch_total_time"] = \
                                                 collabmatch_stats["total_time"]
        else:
            collabmatch_stats = {"score": None, "matching_score": None,
                                 "post_success_score": None}
            performance_statistics["collabmatch_count"] = None
            performance_statistics["collabmatch_successes"] = None
            performance_statistics["collabmatch_failures"] = None
            performance_statistics["collabmatch_average_time"] = None
            performance_statistics["collabmatch_on_target_time"] = None
            performance_statistics["collabmatch_off_target_time"] = None
            performance_statistics["collabmatch_total_post_success_time"] = None
            performance_statistics["collabmatch_total_time"] = None

        # Communications statistics.
        if "COMMUN" in self.log_data:
            performance_statistics["comms_responses"] = \
                                self.calculate_comms_response_times(time_period)
            performance_statistics["comms_average_response_time"] = \
                         self.calculate_average_comms_response_time(time_period)
        else:
            performance_statistics["comms_responses"] = None
            performance_statistics["comms_average_response_time"] = None

        # Resource manager statistics.
        if "RESMAN" in self.log_data:
            performance_statistics["resman_times_out_of_range"] = \
                           self.calculate_resman_times_out_of_range(time_period)
            performance_statistics["resman_total_time_out_of_range"] = \
                      self.calculate_resman_total_time_out_of_range(time_period)
        else:
            performance_statistics["resman_times_out_of_range"] = None
            performance_statistics["resman_total_time_out_of_range"] = None

        # Survey results.
        if "SCALES" in self.log_data:
            performance_statistics["survey_results"] = \
                                            self.get_survey_results(time_period)
        else:
            performance_statistics["survey_results"] = None

        # Scores.
        performance_statistics["scores"] = \
            self.calculate_success_portion(time_period,
            sysmon_events = sysmon_stats,
            tracking_total_time_out_of_bounds =
            performance_statistics["tracking_total_time_out_of_bounds"],
            collabmatch_score = collabmatch_stats["score"],
            collabmatch_matching_score = collabmatch_stats["matching_score"],
            collabmatch_post_success_score =
                                        collabmatch_stats["post_success_score"],
            comms_responses = performance_statistics["comms_responses"],
            resman_total_time_out_of_range =
                       performance_statistics["resman_total_time_out_of_range"])

        # Return the performance statistics calculated.
        return performance_statistics


    def save_data_for_fast_reload(self, path : str) -> None:
        """Saves the reader's data to "path" in a quick to load format.

        Args:
            path: Path at which the file in which data is to be saved should be
                created.
        """

        # The nested dictionaries used by OpenMATBCLogReader aren't convenient
        # to put in a h5 and json files aren't super fast to load. This is also
        # just for buffering and not for data storage. Altogether this means a
        # simple use of pickle is justifiable.
        with open(path, 'wb') as file:
            pickle.dump([self.file_paths, self.log_names, self.log_dates,
                                                           self.log_data], file)


    def load_fast_reload_data(self, path : str) -> None:
        """Loads data from a file saved with "save_data_for_fast_reload".

        Args:
            path: Path to the file from which data is to be loaded.
        """

        # Load the pickle file into the instance variables.
        with open(path, 'rb') as file:
            data = pickle.load(file)
            self.file_paths = data[0]
            self.log_names = data[1]
            self.log_dates = data[2]
            self.log_data = data[3]


    def get_scenario_name(self) -> list:
        """Returns the name of the scenario(s) used in the log.

        Returns:
            list: The name of the scenario(s) used in the log.
        """

        # Get the scenario name(s) from the log data.
        scenario_names = self.log_data["MAIN"]["INFO"]["SCENARIO"]["FILENAME"][
                                                               "data"]["values"]

        # Return the scenario name(s).
        return scenario_names


    def get_scenario_generation_info(self):
        """Gets information on how the scenario(s) were generated.

        Returns:
            dict: Information on how the scenario(s) were generated.
        """

        # Get the flag events from the log data.
        flag_events = self.log_data["MAIN"]["SCENARIO"]["FLAG"]["FLAG"]

        # Get the scenario generation information from the log data.
        scenario_generation_info = {}
        for value in flag_events["data"]["values"]:

            # Check if this is a scenario generation event.
            split_values = value.split(":")
            if len(split_values) > 1:

                # The file from which the scenario was generated.
                if split_values[0] == "scenario_file":
                    if "scenario_file" in scenario_generation_info:
                        raise ValueError("Multiple scenario files found.")
                    scenario_generation_info["scenario_file"] = split_values[1]

                # Scenario generation variable values.
                elif split_values[0][0] == "&":
                    if split_values[0] in scenario_generation_info:
                        raise ValueError("Multiple " + split_values[0] +
                                         " values found.")
                    scenario_generation_info[split_values[0]] = split_values[1]

        # Return the collected scenario generation information.
        return scenario_generation_info


    def save_csv(self, file_path : str, subtasks : bool = False) -> None:
        """Saves a log data summary to a csv file.

        Saves a summary of the log data to a csv file. The summary includes
        information on the scenario(s) used, the scenario generation, and
        performance statistics.

        Args:
            file_path (str): The path to the file to which the summary is to be
                saved.
            subtasks (bool): Whether to look for subtasks in the log (any period
                separated by two FLAG events is considered a subtask). Note that
                the scenario generator includes these by default.
        """

        # Get the scenario name(s) from the log data.
        scenario_names = self.get_scenario_name()

        # Get the scenario generation information from the log data.
        scenario_generation_info = self.get_scenario_generation_info()

        # Get the subtask periods.
        if subtasks:
            subtask_periods = self.determine_subtask_periods()
        else:
            subtask_periods = [("Full_Period",
                self.log_data["MAIN"]["INFO"]["START"]["data"]["timestamps"][0],
                self.log_data["MAIN"]["INFO"]["END"]["data"]["timestamps"][0]),]

        # Get the performance statistics for the log data.
        performance_statistics = [(name, self.performance_evaluation((start,
                                 end))) for name, start, end in subtask_periods]

        # Create the csv file.
        with open(file_path, 'w') as file:
            writer = csv.writer(file)

            # Write the scenario name(s) to the csv file.
            writer.writerow(["Scenario Name"])
            for scenario_name in scenario_names:
                writer.writerow([scenario_name])
            writer.writerow([])

            # Write the scenario generation information to the csv file.
            writer.writerow(["Scenario Generation Information"])
            for key, value in scenario_generation_info.items():
                writer.writerow([key, value])
            writer.writerow([])

            # Write the subtask and their start and end times to the csv file.
            writer.writerow(["Subtask Periods"])
            writer.writerow(["Subtask", "Start", "End"])
            for subtask, start, end in subtask_periods:
                writer.writerow([subtask, start, end])

            # Write the performance statistics to the csv file.
            writer.writerow(["Performance Statistics"])
            writer.writerow([])
            for name, performance in performance_statistics:
                writer.writerow([name])
                for key, value in performance.items():
                    if key == "scores":
                        for subkey, subvalue in value.items():
                            writer.writerow([subkey + "_score", subvalue])
                    else:
                        writer.writerow([key, value])
                writer.writerow([])


if __name__ == "__main__":

    # Read in the command line arguments.
    parser = argparse.ArgumentParser(prog = "open_matbc_log_reader",
        description = "Reads an OpenMATBC log and saves summary statistics to"
                      "a csv file.")
    parser.add_argument("-f", "--file",
                        help="The path to the log file to read.")
    parser.add_argument("-o", "--output", default="./log_summary.csv",
                        help="The path to the file to which the log summary is "
                             "to be saved.")
    parser.add_argument("-s", "--subtasks", default="False",
                        action="store_true",
                        help="Whether to look for subtasks in the log (any "
                             "period separated by two FLAG events is "
                             "considered a subtask). Note that the scenario "
                             "generator includes these by default.")
    args = parser.parse_args()

    # Read the log.
    reader = OpenMATBCLogReader([args.file,])

    # Create the output csv file.
    reader.save_csv(args.output, args.subtasks)








