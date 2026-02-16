"""The message types used in multiplayer OpenMATBC.
"""

REQUEST_SCENARIO_PATH = 0
PROVIDE_SCENARIO_PATH = 1
REQUEST_TIME = 2
PROVIDE_TIME = 3

SERVER_GET_TIME = "get_time"
"""Function to get the current time from the server."""
SERVER_CONFIRM_CONNECTED = "confirm_connected"
"""Tells the server the client has successfully connected."""
SERVER_GET_SCENARIO_PATH = "get_scenario_path"
"""Gets path to the scenario to be used from the server."""
SERVER_GET_SYNC_DATA = "get_sync_data"
"""Gets data from the server to be used for task syncronisation."""
SERVER_PASS_NEW_INPUT = "pass_new_input"
"""Pass new input from the client for the server to handle."""
