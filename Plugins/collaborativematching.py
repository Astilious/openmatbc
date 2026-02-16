from PySide2 import QtWidgets, QtCore, QtGui
from Helpers import WCollaborativeMatching
from Helpers.Translator import translate as _
import pygame
import copy
import math
import numpy as np

class Task(QtWidgets.QWidget):

    def __init__(self, parent):
        """Create a collaborative matching task."""

        # Call the parent's init.
        super(Task, self).__init__(parent)

        # Initialise collaborative matching task parameters.
        self.parameters = {
            'taskplacement': 'topmid',
            'taskupdatetime': 20,
            'title': 'Collaborative Matching',
            'joystickmovementmult': 500.0,
            'joystickaccelmult': 0.5,
            'joystickdeadzone': 0.05,
            'driftmultiplier': 1.0,
            'sceneminx': -2000,
            'scenemaxx': 2000,
            'sceneminy': -2000,
            'scenemaxy': 2000,
            'viewposx': 0.0,
            'viewposy': 0.0,
            'viewvelx': 0.0,
            'viewvely': 0.0,
            'nextobjectimage': '',
            'nextobjectposx': 0.0,
            'nextobjectposy': 0.0,
            'nextobjecttypeid': 0,
            'nextobjectsizex': 100,
            'nextobjectsizey': 100,
            'selectedobjectid': -1,
            'timelimit': 10000,
            'currenttime': 0,
            'score': 0,
            'network': 'no'
        }

        # Initialise the variables set on start.
        self.my_joystick = None
        self.widget: WCollaborativeMatching.WCollaborativeMatching = None

        # Potentially translate task title
        self.parameters['title'] = _(self.parameters['title'])

        # Whether the current task has been completed.
        self.cur_task_complete = False

        # Whether the current task was successful.
        self.cur_task_success = False

        # Record of input for use with networked mode.
        self.input_record = {
            "selection": []
        }

        # The time at which the last section for this task began.
        self.start_time = 0

        # The ID of the lastest object selected by the client.
        self.client_selection = -1

        # Post matching drift parameters.
        self.how_many_sinusoide = 3
        self.cutoff_frequency = 0.06
        self.cursor_speed_factor = 0.5
        self.amplitude_range = [0.2, 0.6]
        self.phase = {
            'x': np.linspace(0, 2 * math.pi, self.how_many_sinusoide),
            'y': np.linspace(math.pi / 5, math.pi / 5 + 2 * math.pi,
                               self.how_many_sinusoide)
        }
        self.amplitude = {
            'x': np.linspace(max(self.amplitude_range),
                 min(self.amplitude_range), self.how_many_sinusoide),
            'y': np.linspace(max(self.amplitude_range),
                 min(self.amplitude_range), self.how_many_sinusoide)
        }
        self.frequencies = {
            'x': np.linspace(0.01, self.cutoff_frequency,
                             self.how_many_sinusoide),
            'y': np.linspace(self.cutoff_frequency, 0.02,
                             self.how_many_sinusoide)
        }

        # The previous position in the drift.
        self.prev_drift_pos = {'x': 0, 'y': 0}

        # The number of resets. Used to ensure the drift is different each time.
        self.reset_count = 0

        # The ID of the true target (-1 if unknown).
        self.true_target_id = -1

        # The time at which the last frame occurred.
        self.last_update_time = 0


    def onStart(self):
        """Starts the task.

        This function is called when the task is started. It initialises the
        task and starts the timer.
        """

        # Create the collaborative matching widget.
        self.widget = WCollaborativeMatching.WCollaborativeMatching(self)

        # Create a layout and add the widget to it.
        layout = QtWidgets.QGridLayout()
        layout.addWidget(self.widget)
        self.setLayout(layout)

        # Initialise the joystick.
        pygame.joystick.init()

        # Check for a joystick device. Error if none are detected.
        if pygame.joystick.get_count() == 0:
            self.parent().showCriticalMessage(
                _("Please plug a joystick for the '%s' task!") %
                (self.parameters['title']))

        # Otherwise, initialise the joystick.
        else:
            self.my_joystick = pygame.joystick.Joystick(0)
            self.my_joystick.init()

        # Refresh the scene.
        self.onRefresh()


    def onRefresh(self):
        """Refreshes the scene, clearing the existing task."""

        # Clear the scene.
        self.widget.clear_scene()

        # Update the scene size.
        self.widget.set_scene_size(self.parameters['sceneminx'],
                                   self.parameters['scenemaxx'],
                                   self.parameters['sceneminy'],
                                   self.parameters['scenemaxy'])
        self.log(["SCENE", "MINX", self.parameters['sceneminx']])
        self.log(["SCENE", "MAXX", self.parameters['scenemaxx']])
        self.log(["SCENE", "MINY", self.parameters['sceneminy']])
        self.log(["SCENE", "MAXY", self.parameters['scenemaxy']])

        # Clear the selected object.
        self.parameters["selectedobjectid"] = -1
        self.widget.set_selection_image()
        self.log(["SELECTION", "LOCAL", "NONE"])

        # Zero the view position and velocity.
        self.parameters["viewposx"] = 0.0
        self.parameters["viewposy"] = 0.0
        self.parameters["viewvelx"] = 0.0
        self.parameters["viewvely"] = 0.0
        self.log(["VIEW", "X", self.parameters["viewposx"]])
        self.log(["VIEW", "Y", self.parameters["viewposy"]])
        self.log(["VIEW", "VX", self.parameters["viewvelx"]])
        self.log(["VIEW", "VY", self.parameters["viewvely"]])

        # Reset the timer.
        self.parameters['currenttime'] = 0.0
        self.start_time = self.parent().get_time()

        # Log the time limit for this reset.
        self.log(["TASK", "TIMELIMIT", self.parameters['timelimit']])

        # Reset the completion status.
        self.cur_task_complete = False
        self.cur_task_success = False

        # Reset the blackout.
        self.widget.set_over_task_blockout(False)

        # Reset client selection.
        self.client_selection = -1
        self.true_target_id = -1

        # Update the reset count.
        self.reset_count += 1

        # Log the reset.
        self.log(["TASK", "RESET"])

        # Reset the success marker.
        self.widget.set_success_marker(False)


    def getScore(self):
        """Returns the current total score."""
        return self.parameters["score"]


    def onUpdate(self):
        """Updates the task.

        This function is called every time the task is updated. It moves the
        view based on joystick input, selects object based on the joystick
        trigger and checks for task completion. If the task is complete and
        successful, it moves the view based on drift and applies score for
        remaining on the target.
        """

        # Get joystick input.
        x_input, y_input, button_pressed = self.joystick_input()

        # Update velocity based on input.
        velx_before = self.parameters["viewvelx"]
        vely_before = self.parameters["viewvely"]
        accel = float(self.parameters['joystickmovementmult']) * \
            0.000001 * self.parameters['joystickaccelmult'] * \
            self.parent().PLUGINS_TASK["collaborativematching"][
            "TIME_SINCE_UPDATE"]
        if x_input > self.parameters['viewvelx']:
            self.parameters['viewvelx'] = min(self.parameters['viewvelx'] +
                                              accel, x_input)
        elif x_input < self.parameters['viewvelx']:
            self.parameters['viewvelx'] = max(self.parameters['viewvelx'] -
                                              accel, x_input)
        if y_input > self.parameters['viewvely']:
            self.parameters['viewvely'] = min(self.parameters['viewvely'] +
                                              accel, y_input)
        elif y_input < self.parameters['viewvely']:
            self.parameters['viewvely'] = max(self.parameters['viewvely'] -
                                              accel, y_input)

        # Update position based on velocity.
        self.parameters['viewposx'] += self.parameters['viewvelx'] * \
            self.parent().PLUGINS_TASK["collaborativematching"][
            "TIME_SINCE_UPDATE"]
        self.parameters['viewposy'] += self.parameters['viewvely'] * \
            self.parent().PLUGINS_TASK["collaborativematching"][
            "TIME_SINCE_UPDATE"]

        # If the task is complete, move the view based on drift.
        if self.cur_task_complete:
            self.drift_view(self.parameters['driftmultiplier'])

        # Constrain the view position to the bounds of the scene.
        self.parameters['viewposx'] = max(self.parameters['sceneminx'],
                                          min(self.parameters['scenemaxx'],
                                              self.parameters['viewposx']))
        self.parameters['viewposy'] = max(self.parameters['sceneminy'],
                                          min(self.parameters['scenemaxy'],
                                              self.parameters['viewposy']))

        # Move the view to the new position.
        self.widget.move_view(self.parameters['viewposx'],
                              self.parameters['viewposy'])
        if self.parameters['viewvelx'] != 0.0 or \
                self.parameters['viewvely'] != 0.0 or \
                self.parameters['viewvelx'] != velx_before or \
                self.parameters['viewvely'] != vely_before:
            self.log(["VIEW", "X", self.parameters['viewposx']])
            self.log(["VIEW", "Y", self.parameters['viewposy']])
            self.log(["VIEW", "VX", self.parameters['viewvelx']])
            self.log(["VIEW", "VY", self.parameters['viewvely']])

        # Update the selected object if the button was pressed.
        if button_pressed and not self.cur_task_complete:
            target_object = self.widget.get_current_target()
            if target_object is not None and target_object.type_id != \
                    self.parameters["selectedobjectid"]:
                self.parameters["selectedobjectid"] = target_object.type_id
                self.widget.set_selection_image(target_object.image_path)
                self.log(["SELECTION", "LOCAL", target_object.type_id])
                self.input_record["selection"].append(target_object.type_id)

        # Update the timer.
        self.parameters["currenttime"] = self.parent().get_time() - \
                                         self.start_time

        # If the task was completed successfully score based on whether the
        # target object is still in the middle of the screen.
        if self.cur_task_complete and self.cur_task_success:
            target_object = self.widget.get_current_target()
            if target_object is not None and target_object.type_id == \
                    self.true_target_id:
                new_score = int(self.parameters["currenttime"] -
                                self.last_update_time)
                self.parameters['score'] += new_score
                self.log(["TRACKING", "ONTARGETMS", int(new_score)])
                self.widget.set_selection_image(target_object.image_path)
            else:
                self.widget.set_selection_image()

        # Update the progress bar.
        self.widget.set_progress_bar_portion(max(0.0, 1.0 -
                                             (self.parameters["currenttime"] /
                                              self.parameters["timelimit"])))

        # Check if the task is complete.
        self.check_completion()

        # Update the last update time.
        self.last_update_time = self.parameters["currenttime"]


    def check_completion(self):
        """Checks whether the task is complete.
        """

        # First check for success.
        if self.client_selection == self.parameters["selectedobjectid"] \
                and self.parameters["selectedobjectid"] != -1 and not \
                self.cur_task_complete:
            self.true_target_id = self.parameters["selectedobjectid"]
            self.cur_task_complete = True
            self.cur_task_success = True
            self.initialise_drift()
            self.widget.set_success_marker(True)
            self.log(["TASK", "SUCCESS"])

        # If there isn't success check for failure.
        if not self.cur_task_complete and \
                (self.is_server() or self.is_local()) and \
                self.parameters["currenttime"] >= self.parameters["timelimit"]:
            self.cur_task_complete = True
            self.log(["TASK", "TIMEOUT"])
            self.parameters["score"] -= 1000
            self.widget.set_over_task_blockout(True, "#FF0000")


    def onAddobject(self):
        """Adds an object with the current specs to the current scene.
        """
        self.widget.add_object(self.parameters['nextobjectimage'],
                               self.parameters['nextobjectposx'],
                               self.parameters['nextobjectposy'],
                               self.parameters['nextobjecttypeid'],
                               self.parameters['nextobjectsizex'],
                               self.parameters['nextobjectsizey'])


    def getSyncData(self):
        """Returns the data required to sync with the client.

        This function returns a dictionary containing the data required to sync
        with the client. The data is as follows:
            cur_task_complete: True if the current task is complete.
            cur_task_success: True if the current task was successful.
            selections: A list of the selections made by the server.
        """

        # Get the selections.
        temp = copy.deepcopy(self.input_record)
        self.input_record["selection"] = []

        # Return the data.
        return {
            "cur_task_complete": self.cur_task_complete,
            "cur_task_success": self.cur_task_success,
            "selections": temp["selection"]
        }


    def applySyncData(self, syncData, full_update=True):
        """Applies the data from the server.

        This function applies the data from the server. The data is as follows:
            cur_task_complete: True if the current task is complete.
            cur_task_success: True if the current task was successful.
            selections: A list of the selections made by the server.

        Server selections are logged and (if appropriate) the task is completed
        based on this data.
        """

        # Log the selections.
        for selection_id in syncData["selections"]:
            self.log(["SELECTION", "REMOTE", selection_id])

        # If the task is complete, set the success flag.
        if syncData["cur_task_complete"] and not self.cur_task_complete:

            # Record the completion state.
            self.cur_task_complete = True

            # Act and log as appropriate for the type of completion.
            if syncData["cur_task_success"]:
                self.cur_task_success = True
                self.true_target_id = self.parameters["selectedobjectid"]
                self.initialise_drift()
                self.widget.set_success_marker(True)
                self.log(["TASK", "SUCCESS"])
            else:
                self.log(["TASK", "TIMEOUT"])
                self.parameters["score"] -= 1000
                self.widget.set_over_task_blockout(True, "#FF0000")


    def popNewInputs(self) -> dict:
        """Returns the new inputs since the last call to this function.

        Returns:
            dict: The new inputs since the last call to this function.
        """
        temp = copy.deepcopy(self.input_record)
        self.input_record["selection"] = []
        return temp


    def applyNewInputs(self, new_inputs):
        """Applies the new client inputs to the task.

        Args:
            new_inputs (dict): The new inputs to apply. The inputs are as
                follows:
                    selection: A list of the selected object ids.
        """

        # Log the new remote selections.
        for selection_id in new_inputs["selection"]:
            self.log(["SELECTION", "REMOTE", selection_id])

        # Check if the latest selection completes the task.
        if len(new_inputs["selection"]) > 0:
            self.client_selection = new_inputs["selection"][-1]
            self.check_completion()


    def joystick_input(self) -> tuple:
        """Returns the joystick input for the current update.

        Returns:
            tuple: The x and y joystick input plus 0 if the trigger has not been
                pulled and 1 if it has.
        """

        # Check if we have a joystick and if the window is active.
        if self.my_joystick and self.parent().isActiveWindow():

            # Pump the joystick event queue.
            pygame.event.pump()

            # Check if we're in the joystick deadzone.
            joystick_movement = (0, 0)
            if not (-self.parameters['joystickdeadzone'] <
                    self.my_joystick.get_axis(0) <
                    self.parameters['joystickdeadzone'] and
                    -self.parameters['joystickdeadzone'] <
                    self.my_joystick.get_axis(1) <
                    self.parameters['joystickdeadzone']):

                # Calculate multiplier for joystick movement.
                current_force = float(self.parameters['joystickmovementmult']) \
                                / 1000

                # Calculate the joystick movement.
                joystick_movement = \
                    (self.my_joystick.get_axis(0) * current_force,
                     self.my_joystick.get_axis(1) * current_force)

                # Log the joystick movement.
                self.log(["JOYSTICK", "X", joystick_movement[0]])
                self.log(["JOYSTICK", "Y", joystick_movement[1]])

            # Check if the joystick trigger has been pulled.
            button_pressed = 0
            for event in pygame.event.get():
                if event.type == pygame.JOYBUTTONDOWN:
                    if event.button == 0:
                        button_pressed = 1
                        self.log(["JOYSTICK", "TRIGGER", "PRESSED"])

            # Return the joystick movement.
            return joystick_movement + (button_pressed,)

        # If the window isn't active don't move the view.
        else:
            return 0, 0, 0


    def initialise_drift(self):
        """Initialises the drift system.

        Initialises the drift system to prevent a sudden position jump when
        drift begins.
        """

        # Record the positions before now.
        x = self.parameters["viewposx"]
        y = self.parameters["viewposy"]

        # Do the first drift. This will set the previous drift to an appropriate
        # value, so future calls won't result in sudden position jumps.
        self.drift_view(self.parameters["driftmultiplier"])

        # Reset the positions.
        self.parameters["viewposx"] = x
        self.parameters["viewposy"] = y

    def drift_view(self, multiplier=1.0):
        """Causes the view to drift around pseudo-randomly.

        Causes the view to drift around pseudo-randomly. This is done after the
        primary matching objective is complete so that the task continues to
        provide an appropriate amount of load.

        The drift is a sum of sinusoids with random frequencies, amplitudes, and
        phases. It is calculated this way to ensure the drift is the same each
        time the task is run.

        Based on the drift used in the tracking task.

        Args:
            multiplier (float): The multiplier for the drift speed.
        """

        # Calculate the effective current time based on the true time and the
        # time offset.
        current_time_ms = int(self.parent().totalElapsedTime_ms) - \
                          self.start_time + self.reset_count * 1000000

        # Avoid absolute positioning (t-1 -> t)
        pos_change = {'x': 0, 'y': 0}
        for this_coord in ['x', 'y']:

            # Calculate the current sinusoid values.
            current_sinus = []
            for this_phase in range(0, self.how_many_sinusoide):
                phase_value = (
                    2 * math.pi * self.frequencies[this_coord][this_phase] *
                    ((current_time_ms * self.cursor_speed_factor) / 1000.) +
                    self.phase[this_coord][this_phase]) % 2 * math.pi
                current_sinus.append(math.sin(phase_value))

            # Calculate the current position in the sinusoid pattern.
            sinosoid_pos = np.mean([self.amplitude[this_coord][this_phase] *
                                    current_sinus[this_phase] for this_phase in
                                    range(0, self.how_many_sinusoide)])

            # Calculate the difference between the current position and the one
            # at the previous update.
            translation = sinosoid_pos - self.prev_drift_pos[this_coord]

            # Calculate the final position change.
            pos_change[this_coord] = 1000.0*translation*multiplier

            # Store the current position for the next update.
            self.prev_drift_pos[this_coord] = sinosoid_pos

        # Apply the position change.
        self.parameters['viewposx'] += pos_change['x']
        self.parameters['viewposy'] += pos_change['y']


    def log(self, log_list: list):
        """Logs an event to the main log.

        Args:
            log_list (list): The list of strings that make up the log entry.
        """

        # Add the task name to the log message.
        log_list = ["COLLABMATCH"] + log_list

        # Log the message.
        self.parent().mainLog.addLine(log_list)


    def is_client(self):
        """Returns whether the task is running as a client.

        Returns:
            bool: True if the task is running as a client, False otherwise.
        """
        return self.parameters['network'] == "client" or \
            (self.parameters['network'] == "as_host" and self.parent().is_client)


    def is_server(self):
        """Returns whether the task is running as a server.

        Returns:
            bool: True if the task is running as a server, False otherwise.
        """
        return self.parameters['network'] == "server" or \
            (self.parameters['network'] == "as_host" and self.parent().is_server)


    def is_local(self):
        """Returns whether the task is running as a local only task.

        Returns:
            bool: True if the task is running as a local only task, False
                otherwise.
        """
        return self.parameters['network'] == "no" or \
            (self.parameters['network'] == "as_host" and
             not (self.parent().is_server or self.parent().is_client))
