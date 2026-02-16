import os
import time

import twisted.internet.protocol
import twisted.internet.reactor
import twisted.internet.task
import twisted.internet.defer
import twisted.spread.pb

import OpenMATBC

class OpenMATBCServerPerspectiveBroker(twisted.spread.pb.Root):

    def __init__(self, window : OpenMATBC.Main):
        self.window = window
        self.error_counter = 0

    def remote_get_time(self):
        return self.window.get_time()

    def remote_confirm_connected(self):
        self.window.set_connected(True)
        self.window.last_client_sync = time.time()
        return True

    def remote_get_scenario_path(self):
        return os.path.join(self.window.scenario_directory, self.window.scenario_shortfilename)

    def remote_pass_user_input(self, user_input : list):
        # Do something with the new user data.
        return True

    def remote_get_sync_data(self):

        # Get syncronisation data from all plugins that have it.
        sync_data = {}
        for plugin_name, plugin in self.window.PLUGINS_TASK.items():
            plugin_class = plugin['class']
            get_sync_data = getattr(plugin_class, "getSyncData", None)
            if callable(get_sync_data) and plugin_class.is_server():
                sync_data[plugin_name] = get_sync_data()

        # Check for termination.
        if not self.window.experiment_running:
            sync_data['terminate'] = True
            self.window.termination_message_sent = True

        # Update the record of the last client syncronisation.
        self.window.last_client_sync = time.time()

        # Return the syncronisation data.
        return sync_data

    def remote_pass_new_input(self, new_input):

        # Pass the new input to the relevant plugins.
        counter_before = self.error_counter
        for plugin_name, input_data in new_input.items():
            if plugin_name in self.window.PLUGINS_TASK:
                plugin_class = self.window.PLUGINS_TASK[plugin_name]['class']
                apply_new_inputs = getattr(plugin_class, "applyNewInputs", None)
                if callable(apply_new_inputs):
                    if plugin_class.is_server():
                        apply_new_inputs(input_data)
                    elif self.error_counter > 10:
                        self.window.showCriticalMessage("Received input data for plugin that is not a server (" + str(plugin_name) + ")!")
                    else:
                        self.error_counter += 1
                else:
                    self.window.showCriticalMessage("Received input data for plugin without a \"applyNewInputs\" function (" + str(plugin_name) + ")!")
            else:
                self.window.showCriticalMessage("Received input data for plugin without that does not exist on the server (" + str(plugin_name) + ")!")
        if counter_before == self.error_counter:
            self.error_counter = 0


def start_server(window):
    factory = twisted.spread.pb.PBServerFactory(OpenMATBCServerPerspectiveBroker(window))
    return factory