from PySide2 import QtCore, QtWidgets, QtGui
from Helpers import QTExtensions, WScale, WLight
from numpy import median
import random
from Helpers.Translator import translate as _
from functools import partial
import copy

class Task(QtWidgets.QWidget):

    def __init__(self, parent):
        super(Task, self).__init__(parent)

        # SYSMON PARAMETERS ###
        self.parameters = {
            'title': 'System monitoring',
            'taskplacement': 'topleft',
            'taskupdatetime': 200,
            'alerttimeout': 10000,
            'automaticsolver': False,
            'automaticsolverdelay': 1 * 1000,
            'displayautomationstate': False,
            'allowanykey': False,
            'scalesnumofboxes': 11,  # Must be odd (to admit a middle position)
            'safezonelength': 3,
            'scalestyle': 1,  # could be defined at the scale level
            'resetperformance': None,

            'feedbacks': {'positive': {'active': True,
                                       'color': '#ffff00',
                                       'duration': 1.5 * 1000,
                                       'trigger': 0},
                          'negative': {'active': True,
                                       'color': '#ff0000',
                                       'duration': 1.5 * 1000,
                                       'trigger': 0}},
            'lights': {
                '1': {'name': 'F5', 'failure': False, 'on': True, 'default':
                      'on', 'oncolor': "#009900", 'keys': [QtCore.Qt.Key_F5]},
                '2': {'name': 'F6', 'failure': False, 'on': False, 'default':
                      'off', 'oncolor': "#FF0000", 'keys': [QtCore.Qt.Key_F6]}
                      },
            'scales': {'1': {'name': 'F1', 'failure': 'no', 'keys':
                             [QtCore.Qt.Key_F1]},
                       '2': {'name': 'F2', 'failure': 'no', 'keys':
                             [QtCore.Qt.Key_F2]},
                       '3': {'name': 'F3', 'failure': 'no', 'keys':
                             [QtCore.Qt.Key_F3]},
                       '4': {'name': 'F4', 'failure': 'no', 'keys':
                             [QtCore.Qt.Key_F4]}},
            'network': "no",
            'score': 0
            }

        self.performance = {
            'total': {'hit_number': 0, 'miss_number': 0, 'fa_number': 0},
            'last': {'hit_number': 0, 'miss_number': 0, 'fa_number': 0}
        }

        # Potentially translate task title
        self.parameters['title'] = _(self.parameters['title'])

        # Set the initial position of the cursor (middle)
        for thisScale, scaleValue in self.parameters['scales'].items():
            scaleValue['position'] = self.parameters['scalesnumofboxes'] / 2

        # Define two failures zones (up, down)
        totalRange = tuple(range(self.parameters['scalesnumofboxes']))

        self.zones = dict()
        self.zones['no'] = [int(median(totalRange))]
        while len(self.zones['no']) < self.parameters['safezonelength']:
            self.zones['no'].insert(0, min(self.zones['no']) - 1)
            self.zones['no'].insert(len(self.zones['no']),
                                    max(self.zones['no']) + 1)

        self.zones['up'] = [r for r in totalRange if r < min(self.zones['no'])]
        self.zones['down'] = [r for r in totalRange if
                              r > max(self.zones['no'])]

        # Set a list of accepted keys depending on lights and scales parameters
        scales_keys = [v['keys'][0] for s, v in
                       self.parameters['scales'].items()]
        lights_keys = [v['keys'][0] for l, v in
                       self.parameters['lights'].items()]
        self.accepted_keys = scales_keys + lights_keys

        # Record of input for use with networked mode.
        self.input_record = {
            "key_events": []
        }

        # Record of recent logged events.
        self.event_record = []

    def checkForFailure(self):
        failure = False
        for gauge_type in ['lights', 'scales']:
            for gauge, gaugeValue in self.parameters[gauge_type].items():

                # If a failure is to be initiated
                if (gauge_type == 'scales' and gaugeValue['failure'] in
                        ['up', 'down']) or (gauge_type == 'lights' and
                        gaugeValue['failure']):
                    failure = True
        return(failure)

    def onStart(self):

        # Define a QLabel object to potentially display automation mode
        self.modeFont = QtGui.QFont("sans-serif", int(self.height() / 35.), QtGui.QFont.Bold)
        self.modeLabel = QtWidgets.QLabel(self)
        self.modeLabel.setGeometry(QtCore.QRect(0, 0.2 * self.height(), self.width(), 0.08 * self.height()))
        self.modeLabel.setAlignment(QtCore.Qt.AlignCenter)
        self.modeLabel.setFont(self.modeFont)
        index = -1

        # For each light button
        for thisLight, lightValues in self.parameters['lights'].items():
            index += 1
            # Set a WLight Qt object
            lightValues['ui'] = WLight.WLight(self, lightValues['on'],
                                              lightValues['oncolor'],
                                              lightValues['name'], index)

            lightValues['ui'].show()  # Show the WLight Qt object

        # For each scale gauge
        for thisScale, scaleValues in self.parameters['scales'].items():

            # Set a WScale Qt object
            scaleValues['ui'] = WScale.WScale(
                self, scaleValues['name'], self.parameters['scalesnumofboxes'],
                thisScale, self.parameters['scalestyle'])
            scaleValues['ui'].show()  # Show the WScale Qt object

        # Define timers to handle failure and feedback durations
        self.failuretimeoutTimers = {}
        self.feedbackTimers = {}
        for gauge_type in ['lights', 'scales']:
            self.failuretimeoutTimers[gauge_type] = {}
            self.feedbackTimers[gauge_type] = {}
            for gauge, gaugeValue in self.parameters[gauge_type].items(): 
                self.failuretimeoutTimers[gauge_type][gauge] = \
                                              QTExtensions.QTimerWithPause(self)
                self.failuretimeoutTimers[gauge_type][gauge].timeout.connect(
                                    partial(self.endFailure, gauge_type, gauge))
                self.feedbackTimers[gauge_type][gauge] = \
                                              QTExtensions.QTimerWithPause(self)
                self.feedbackTimers[gauge_type][gauge].timeout.connect(partial(
                                      self.endFeedBackTimer, gauge_type, gauge))

    def onUpdate(self):

        if self.parameters['displayautomationstate']:
            self.refreshModeLabel()
        else:
            self.modeLabel.hide()

        if self.parameters['resetperformance'] is not None:
            if self.parameters['resetperformance'] in ['last', 'global']:
                for i in self.performance[self.parameters['resetperformance']]:
                    self.performance[self.parameters['resetperformance']][i] = 0
            elif self.parameters['resetperformance'] is not None:
                self.parent().showCriticalMessage(_("%s : wrong argument in sysmon;resetperformance") % self.parameters['resetperformance'])
            self.parameters['resetperformance'] = None

        # For each light button, refresh name
        for thisLight, lightValues in self.parameters['lights'].items():
            lightValues['ui'].light.setText(lightValues['name'])

        # For each scale gauge, refresh name
        for thisScale, scaleValues in self.parameters['scales'].items():
            scaleValues['ui'].label.setText(scaleValues['name'])

        # 1. Check failures
        for gauge_type in ['lights', 'scales']:
            for gauge, gaugeValue in self.parameters[gauge_type].items():

                # If a failure is to be initiated
                if ((gauge_type == 'scales' and gaugeValue['failure'] in
                        ['up', 'down']) or (gauge_type == 'lights' and
                        gaugeValue['failure'])) and not \
                        self.failuretimeoutTimers[gauge_type][gauge].isActive():

                    # Start it...
                    self.startFailure(gauge_type, gauge)

        # 2. Vary position of each scale, depending on its state (up, down, no)
        for thisScale, scaleValues in self.parameters['scales'].items():
            scaleValues['position'] = self.computeNextPosition(thisScale)

        # 3. Refresh visual display
            if 'ui' in scaleValues:
                scaleValues['ui'].style = self.parameters['scalestyle']
                scaleValues['ui'].position = scaleValues['position']
                scaleValues['ui'].update()

        for thisLight, lightValues in self.parameters['lights'].items():
            if 'ui' in lightValues:
                lightValues['ui'].refreshState(lightValues['on'])
                lightValues['ui'].update()

        # 4. Check for arbitrary feedbacks
        for f, v in self.parameters['feedbacks'].items():
            if v['trigger'] != 0:
                ui_idx = str(v['trigger'])
                if any([ui_idx == idx for idx, val
                        in self.parameters['scales'].items()]):
                    trigger_ui = self.parameters['scales'][ui_idx]['ui']
                    self.trigger_feedback('scales', ui_idx, trigger_ui, f)
                    v['trigger'] = None


    def getScore(self) -> int:
        """Return the current score for this task.

        Returns:
            int: The current score.
        """
        return self.parameters['score']


    def getSyncData(self):

        # Get the gauge data.
        gauge_data = {}
        for gauge_type in ['lights', 'scales']:
            gauge_data[gauge_type] = {}
            for gauge_name, gauge_values in self.parameters[gauge_type].items():
                gauge_data[gauge_type][gauge_name] = {}
                gauge_dict = gauge_data[gauge_type][gauge_name]
                gauge_dict["failure"] = gauge_values["failure"]
                if "on" in gauge_values:
                    gauge_dict["on"] = gauge_values["on"]

        # Get the feedback data.
        feedback_data = {"scales": {}}
        for gauge_name, gauge_values in self.parameters["scales"].items():
            feedback_data["scales"][gauge_name] = {}
            gauge_dict = feedback_data["scales"][gauge_name]
            gauge_dict["feedback"] = self.parameters["scales"][gauge_name]["ui"].feedback
            gauge_dict["feedbackColor"] = self.parameters["scales"][gauge_name]["ui"].feedbackColor

        # Get the events that have been logged since the last sync.
        event_record = self.event_record
        self.event_record = []

        return {
            "gauge_data": gauge_data,
            "feedback_data": feedback_data,
            "event_record": event_record
        }


    def applySyncData(self, syncData, full_update=True):

        # Only update the task if this is a full update.
        if full_update:

            # Populate the gauge data with the new values.
            for gauge_type, gauge_type_data in syncData["gauge_data"].items():
                for gauge_name, gauge_data in gauge_type_data.items():
                    for key, value in gauge_data.items():
                        self.parameters[gauge_type][gauge_name][key] = value

            # Sync up the feedback status.
            for gauge_type, gauge_type_data in syncData["feedback_data"].items():
                for gauge_name, gauge_data in gauge_type_data.items():
                    self.parameters[gauge_type][gauge_name]["ui"].set_feedback(gauge_data["feedback"], gauge_data["feedbackColor"])

        # Record the new events.
        for event in syncData["event_record"]:
            self.parent().mainLog.addLine(event)

    def popNewInputs(self):
        temp = copy.deepcopy(self.input_record)
        self.input_record["key_events"] = []
        return temp


    def applyNewInputs(self, new_inputs):

        # Apply the new input as normal key events.
        key_inputs = new_inputs["key_events"]
        for event in key_inputs:
            self.keyEvent(event, from_client=True)


    def keyEvent(self, key_pressed, from_client=False):

        # Ignore keystrokes if this is a client.
        if self.is_client():
            self.input_record["key_events"].append(key_pressed)
            return

        # If automaticsolver on, do not listen for keyboard inputs
        if (self.parameters['automaticsolver'] is True
                or key_pressed not in self.accepted_keys):
            return

        # If no failure is occuring, any keypress is a false alarm
        if not self.checkForFailure():
            for t in ['lights', 'scales']:
                for g, v in self.parameters[t].items():
                    if key_pressed in v['keys']:
                        self.record_performance(v['name'], 'fa', from_client)
                        if (self.parameters['feedbacks']['negative']['active']
                                is True):
                            self.trigger_feedback(t, g, v['ui'], 'negative')
            return

        # If a failure is occuring, key press is evaluated further
        else:
            key_fixed_something = False
            for gauge_type in ['lights', 'scales']:
                for g, gaugeValues in self.parameters[gauge_type].items():
                    if (gaugeValues['failure'] in ['up', 'down'] or
                            gaugeValues['failure'] is True):

                        # Correct key pressed -> end failure
                        if key_pressed in gaugeValues['keys']:
                            self.endFailure(gauge_type, g, True, from_client)
                            key_fixed_something = True

            # The key press didn't fix any failures, so send negative feedback.
            if not key_fixed_something:
                for gauge_type in ['lights', 'scales']:
                    for g, gaugeValues in self.parameters[gauge_type].items():
                        if key_pressed in gaugeValues['keys']:
                            self.record_performance(gaugeValues['name'] + '_NA',
                                                              'fa', from_client)
                            if(self.parameters['feedbacks']['negative'][
                                                                     'active']):
                                self.trigger_feedback(gauge_type, g,
                                                  gaugeValues['ui'], 'negative')

    def endFeedBackTimer(self, gauge_type, gauge):
        self.feedbackTimers[gauge_type][gauge].stop()
        self.parameters[gauge_type][gauge]['ui'].set_feedback(0)

    def startFailure(self, gauge_type, gauge):

        gaugeValues = self.parameters[gauge_type][gauge]

        if gauge_type == 'lights':
            gaugeValues['on'] = not gaugeValues['default'] == 'on'

        self.buildLog(['STATE', gaugeValues['name'], 'FAILURE'])

        # If automatic solver on, start a timer that will automatically stop
        # failure after an automaticsolverdelay duration
        if self.parameters['automaticsolver']:
            self.failuretimeoutTimers[gauge_type][gauge].start(
                                        self.parameters['automaticsolverdelay'])

        # If automatic solver off, start a timer the will stop failure after an
        # alerttimeout duration
        elif not self.is_client():
            self.failuretimeoutTimers[gauge_type][gauge].start(
                                                self.parameters['alerttimeout'])

    def endFailure(self, gauge_type, gauge, success=False, from_client=False):

        gauge_feedback = self.parameters[gauge_type][gauge]
        self.failuretimeoutTimers[gauge_type][gauge].stop()

        # If automatic solver on and failure occuring, send the good key
        # response
        if self.parameters['automaticsolver']:
            self.buildLog(['STATE', gauge_feedback['name'], 'AUTOMATIC-SOLVER'])

            if self.parameters['feedbacks']['positive']['active'] is True:
                self.trigger_feedback(gauge_type, gauge, gauge_feedback['ui'],
                                                                     'positive')

        # If automatic solver off and good key pressed (success), log a HIT,
        # send a positive feedback, start the corresponding timer
        elif success:
            self.record_performance(gauge_feedback['name'], 'hit', from_client)
            if self.parameters['feedbacks']['positive']['active'] is True:
                self.trigger_feedback(gauge_type, gauge, gauge_feedback['ui'],
                                                                     'positive')

        # If failure ends with neither automatic solver nor good key pressed,
        # log a MISS
        else:
            self.record_performance(gauge_feedback['name'], 'miss', from_client)
            if self.parameters['feedbacks']['negative']['active'] is True:
                self.trigger_feedback(gauge_type, gauge, gauge_feedback['ui'],
                                                                     'negative')

        # In any case, reset the 'failure' variable
        if gauge_type == 'scales':
            gauge_feedback['failure'] = 'no'
        elif gauge_type == 'lights':
            gauge_feedback['failure'] = False
            gauge_feedback['on'] = gauge_feedback['default'] == 'on'

        # Log the end of the failure
        self.buildLog(['STATE', gauge_feedback['name'], 'SAFE'])

    def computeNextPosition(self, whatScale):

        # Retrieve the current cursor position for a specific scale gauge
        actualPosition = self.parameters['scales'][whatScale]['position']

        # Retrieve the current scale state (up, down, no)
        whatZone = self.parameters['scales'][whatScale]['failure']

        # If current position does not match the current scale state, move the
        # cursor in the propoer zone
        if actualPosition not in self.zones[whatZone]:
            actualPosition = random.sample(self.zones[whatZone], 1)[0]

        # If it does match...
        else:
            # ...choose up/down direction randomly
            direction = random.sample([-1, 1], 1)[0]

            # Once a new direction is computed, if the pointer remains in the
            # correct zone...
            if actualPosition + direction in self.zones[whatZone]:
                # ...apply movement
                actualPosition += direction

            # If not...
            else:
                # ...move in the opposite direction
                actualPosition -= direction

        # Finally, return the new computed cursor position
        return actualPosition

    def refreshModeLabel(self):

        if 'automaticsolver' in self.parameters and self.parameters['automaticsolver']:
            self.modeLabel.setText("<b>%s</b>" % _('AUTO ON'))
        elif 'assistedsolver' in self.parameters and self.parameters['assistedsolver']:
            self.modeLabel.setText("<b>%s</b>" % _('ASSIST ON'))
        else:
            self.modeLabel.setText("<b>%s</b>" % _('MANUAL'))
        self.modeLabel.show()

    def trigger_feedback(self, gauge_type, gauge, trigger_ui, type):
        if hasattr(trigger_ui, 'set_feedback'):
            color = self.parameters['feedbacks'][type]['color']
            duration = self.parameters['feedbacks'][type]['duration']
            trigger_ui.set_feedback(1, color)
            self.feedbackTimers[gauge_type][gauge].start(duration)

    def record_performance(self, light_scale_name, event, from_client):

        # Log the event.
        for this_cat in self.performance.keys():
            self.performance[this_cat][event+'_number'] += 1
        if from_client:
            self.buildLog(["ACTION", "CLIENT", light_scale_name, event.upper()])
        elif self.is_server():
            self.buildLog(["ACTION", "SERVER", light_scale_name, event.upper()])
        else:
            self.buildLog(["ACTION", light_scale_name, event.upper()])

        # Update the score.
        if event.upper() == "HIT":
            self.parameters['score'] += 100
        elif event.upper() == "MISS":
            self.parameters['score'] -= 100
        elif event.upper() == "FA":
            self.parameters['score'] -= 100


    def buildLog(self, thisList):
        thisList = ["SYSMON"] + thisList
        if self.is_server():
            self.parent().mainLog.addLine(thisList)
            self.event_record.append(thisList)
        elif self.is_local():
            self.parent().mainLog.addLine(thisList)


    def is_client(self):
        return self.parameters['network'] == "client" or \
            (self.parameters['network'] == "as_host" and self.parent().is_client)


    def is_server(self):
        return self.parameters['network'] == "server" or \
            (self.parameters['network'] == "as_host" and self.parent().is_server)


    def is_local(self):
        return self.parameters['network'] == "no" or \
            (self.parameters['network'] == "as_host" and
             not (self.parent().is_server or self.parent().is_client))

