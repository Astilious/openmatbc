# -*- coding:utf-8 -*-

from PySide2 import QtCore, QtWidgets, QtGui
from Helpers import WTank, WPump
from Helpers.Translator import translate as _
import copy
import time

class Task(QtWidgets.QWidget):

    def __init__(self, parent):
        super(Task, self).__init__(parent)

        # RESMAN PARAMETERS ###
        self.parameters = {
            'taskplacement': 'bottommid',
            'taskupdatetime': 2000,
            'title': 'Resources management',
            'heuristicsolver': False,
            'assistedsolver': False,
            'displayautomationstate': False,
            'pumpcoloroff': '#AAAAAA',
            'pumpcoloron': '#00FF00',
            'pumpcolorfailure': '#FF0000',
            'tolerancelevel': 500,
            'displaytolerance': True,
            'resetperformance': None,

            'pump': {'1': {'flow': 800, 'state': 0, 'keys': [QtCore.Qt.Key_1], 'hide': 0},
                     '2': {'flow': 600, 'state': 0, 'keys': [QtCore.Qt.Key_2, 233], 'hide': 0},
                     '3': {'flow': 800, 'state': 0, 'keys': [QtCore.Qt.Key_3], 'hide': 0},
                     '4': {'flow': 600, 'state': 0, 'keys': [QtCore.Qt.Key_4],'hide': 0},
                     '5': {'flow': 600, 'state': 0, 'keys': [QtCore.Qt.Key_5], 'hide': 0},
                     '6': {'flow': 600, 'state': 0, 'keys': [QtCore.Qt.Key_6], 'hide': 0},
                     '7': {'flow': 400, 'state': 0, 'keys': [QtCore.Qt.Key_7, 232], 'hide': 0},
                     '8': {'flow': 400, 'state': 0, 'keys': [QtCore.Qt.Key_8], 'hide': 0}},

            'tank': {
                'a': {'level': 2500, 'max': 4000, 'target': 2500, 'depletable': 1, 'lossperminute': 800, 'hide': 0},
                'b': {'level': 2500, 'max': 4000, 'target': 2500, 'depletable': 1, 'lossperminute': 800, 'hide': 0},
                'c': {'level': 1000, 'max': 2000, 'target': None, 'depletable': 1, 'lossperminute': 0, 'hide': 0},
                'd': {'level': 1000, 'max': 2000, 'target': None, 'depletable': 1, 'lossperminute': 0, 'hide': 0},
                'e': {'level': 3000, 'max': 4000, 'target': None, 'depletable': 0, 'lossperminute': 0, 'hide': 0},
                'f': {'level': 3000, 'max': 4000, 'target': None, 'depletable': 0, 'lossperminute': 0, 'hide': 0}
            },
            'network': "no",
            'score': 0,
            'progresstimertime': 0
        }

        self.performance = {
            'total': {},
            'last': {}
        }

        for this_cat in self.performance:
            for this_tank in self.parameters['tank']:
                if self.parameters['tank'][this_tank]['target'] is not None:
                    self.performance[this_cat][this_tank+'_in'] = 0
                    self.performance[this_cat][this_tank+'_out'] = 0

        # Potentially translate task title
        self.parameters['title'] = _(self.parameters['title'])

        # Record of input for use with networked mode.
        self.input_record = {
            "key_events": []
        }

        # Record of recent logged events.
        self.event_record = []

        # The portion of the progress bar to fill.
        self.progress_bar_portion = 1.0

        # The time at which the current progress bar timer started.
        self.progress_bar_start_time = 0.0

    def onStart(self):
        # Define a QLabel object to display mode
        self.modeFont = QtGui.QFont("sans-serif", int(self.height() / 35.),
                                    QtGui.QFont.Bold)
        self.modeLabel = QtWidgets.QLabel(self)
        self.modeLabel.setGeometry(QtCore.QRect(self.width() * 0.42, self.height() * 0.40, self.width() * 0.20, int(self.height()/15)))
        self.modeLabel.setAlignment(QtCore.Qt.AlignCenter)
        self.modeLabel.setFont(self.modeFont)
        self.refreshModeLabel()
        self.update()

        # If there is any tank that has a target, log the tolerance value
        if self.parameters['displaytolerance']:
            self.buildLog(["STATE", "TANK", "TOLERANCE",
                           str(self.parameters['tolerancelevel'])])

        # For each defined tank
        for thisTank, tankValues in self.parameters['tank'].items():

            # Log its target value if it is set
            if tankValues['target'] is not None:
                self.buildLog(["STATE", "TANK" + thisTank.upper(), "TARGET",
                               str(tankValues['target'])])

                # Change tank initial level at the target level
                tankValues['level'] = tankValues['target']

            # Set a WTank Qt object
            tankValues['ui'] = WTank.WTank(self)
            tankValues['ui'].setMaxLevel(tankValues['max'])
            tankValues['ui'].locateAndSize(thisTank, tankValues['target'],
                                           tankValues['depletable'])
            tankValues['ui'].setLetter(thisTank.upper())

            # Display tank current capacity only if it is limited
            if tankValues['depletable']:
                tankValues['ui'].setLabel()

            # Display a target level when appropriate
            if tankValues['target'] is not None:
                tankValues['ui'].setTargetY(tankValues['target'],
                                            tankValues['max'])

            # Show the resulting Qt object
            tankValues['ui'].show()

        # For each defined pump
        for thisPump, pumpValues in self.parameters['pump'].items():

            # Preallocate a variable to signal that a given pump fail has
            # already been logged
            pumpValues['failLogged'] = 0

            # Set a WPump Qt object
            pumpValues['ui'] = WPump.WPump(self, thisPump)
            pumpValues['ui'].locateAndSize()
            pumpValues['ui'].lower()

            # Show the resulting Qt object
            pumpValues['ui'].show()

        # Refresh visual information in case some initial values have been
        # altered in the scenario
        for thisTank, tankValues in self.parameters['tank'].items():
            tankValues['ui'].refreshLevel(tankValues['level'])

        for thisPump, pumpValues in self.parameters['pump'].items():
            pumpValues['ui'].changeState(pumpValues['state'],
                                         pumpValues['hide'])

    def onUpdate(self):

        # Update the progress bar.
        finish_time = max(self.progress_bar_start_time + \
                          self.parameters["progresstimertime"],
                          self.progress_bar_start_time + 1)
        self.progress_bar_portion = max(0.0, 1.0 -
            ((time.time() - self.progress_bar_start_time) /
             (finish_time - self.progress_bar_start_time)))

        # Ignore keystrokes if this is a client.
        if self.is_client():
            return

        if self.parameters['displayautomationstate'] is True:
            self.refreshModeLabel()
        else:
            self.modeLabel.hide()

        if self.parameters['resetperformance'] in ['last', 'global']:
            for i in self.performance[self.parameters['resetperformance']]:
                self.performance[self.parameters['resetperformance'][i]] = 0
            self.parameters['resetperformance'] = None
        elif self.parameters['resetperformance'] is not None:
            self.parent().showCriticalMessage(_("%s : wrong argument in resman;resetperformance") % self.parameters['resetperformance'])

        time_resolution = (self.parameters['taskupdatetime'] / 1000) / 60.

        # 0. Compute automatic actions if heuristicsolver activated, three heuristics
        # Browse only woorking pumps (state != -1)

        if self.parameters['heuristicsolver'] or self.parameters['assistedsolver']:
            working_pumps = {p: v for p, v in self.parameters['pump'].items()
                             if v['state'] != -1}

            for thisPump, pumpValue in working_pumps.items():
                fromtank = self.parameters['tank'][
                            pumpValue['ui'].fromTank_label]
                totank = self.parameters['tank'][
                            pumpValue['ui'].toTank_label]

                # 0.1. Systematically activate pumps draining non-depletable tanks
                if not fromtank['depletable'] and pumpValue['state'] == 0:
                    pumpValue['state'] = 1

                # 0.2. Activate/deactivate pump whose target tank is too low/high
                # "Too" means level is out of a tolerance zone around the target level (2500 +/- 150)
                if totank['target'] is not None:
                    if totank['level'] <= totank['target'] - 150:
                        pumpValue['state'] = 1
                    elif totank['level'] >= totank['target'] + 150:
                        pumpValue['state'] = 0

                # 0.3. Equilibrate between the two A/B tanks if sufficient level
                if fromtank['target'] is not None and totank['target'] is not None:
                    if fromtank['level'] >= totank['target'] >= totank['level']:
                        pumpValue['state'] = 1
                    else:
                        pumpValue['state'] = 0


        # 1. Deplete tanks A and B
        for thisTank in ['a', 'b']:
            tankValue = self.parameters['tank'][thisTank]
            volume = int(tankValue['lossperminute'] * time_resolution)
            volume = min(volume, tankValue['level'])  # If level less than volume, deplete only available level
            tankValue['level'] -= volume

        # 2. For each pump
        for pumpNumber, pumpValues in self.parameters['pump'].items():

            # 2.a Transfer flow if pump is ON
            if pumpValues['state'] == 1:

                fromtank = self.parameters['tank'][
                    pumpValues['ui'].fromTank_label]
                totank = self.parameters['tank'][
                    pumpValues['ui'].toTank_label]

                # Compute volume
                volume = int(pumpValues['flow']) * time_resolution

                # Check if this volume is available
                volume = min(volume, fromtank['level'])

                # Drain it from tank (if its capacity is limited)...
                if fromtank['depletable']:
                    fromtank['level'] -= int(volume)

                # ...to tank (if it's not full)
                volume = min(volume, totank['max'] - totank['level'])
                totank['level'] += int(volume)

            # 2.b Modify flows according to pump states (OFF | FAIL => 0)
            elif pumpValues['state'] != 1 or pumpValues['hide']:
                if pumpValues['state'] == -1 and not pumpValues['failLogged']:
                    self.buildLog(["STATE", "PUMP" + pumpNumber, "FAIL"])
                    pumpValues['failLogged'] = True

                if pumpValues['state'] == 0 and pumpValues['failLogged']:
                    pumpValues['failLogged'] = False
                    self.buildLog(["STATE", "PUMP" + pumpNumber, "OFF"])

        # 3. For each tank
        for thisTank, tankValues in self.parameters['tank'].items():
            pumps_to_deactivate = []

            # If it is full, select incoming pumps for deactivation
            if tankValues['level'] >= tankValues['max']:
                pumps_to_deactivate.append(p for p, v in
                                           self.parameters['pump'].items()
                                           if v['ui'].toTank_label == thisTank)

            # Likewise, if it is empty, select outcome pumps for deactivation
            elif self.parameters['tank'][thisTank]['level'] <= 0:
                pumps_to_deactivate.append(p for p, v in
                                           self.parameters['pump'].items()
                                           if v['ui'].fromTank_label ==
                                           thisTank)

            # Deactivate selected pumps if not on failure
            for thesePumps in pumps_to_deactivate:
                for thisPump in thesePumps:
                    if not self.parameters['pump'][thisPump]['state'] == -1:
                        self.parameters['pump'][thisPump]['state'] = 0
                        self.buildLog(["STATE", "PUMP" + thisPump, "OFF"])

        # 4. Refresh visual information
        for thisPump, pumpValue in self.parameters['pump'].items():
            pumpValue['ui'].changeState(pumpValue['state'], pumpValue['hide'])

        for thisTank, tankValue in self.parameters['tank'].items():
            tankValue['ui'].refreshLevel(tankValue['level'])

        # 5. Log tank level if a target is set
            if tankValue['target'] is not None:
                self.buildLog(["STATE", "TANK" + thisTank.upper(), "LEVEL",
                               str(tankValue['level'])])

                for perf_cat, perf_val in self.performance.items():
                    local_dev = abs(tankValue['level'] - tankValue['target'])
                    if local_dev <= self.parameters['tolerancelevel']:
                        perf_val[thisTank.lower()+'_in'] += 1
                    else:
                        perf_val[thisTank.lower()+'_out'] += 1

        # 6. Update the score.
        for tank_data in self.parameters["tank"].values():
            if tank_data["target"] is not None:
                tolerance = self.parameters["tolerancelevel"]
                if tank_data["level"] >= tank_data["target"] - tolerance and \
                        tank_data["level"] <= tank_data["target"] + tolerance:
                    self.parameters["score"] += self.parameters["taskupdatetime"] // 10
                else:
                    self.parameters["score"] -= self.parameters["taskupdatetime"] // 10

        self.update()

    def onProgresstimerstart(self):
        self.progress_bar_start_time = time.time()

    def getScore(self):
        return self.parameters["score"]

    def getSyncData(self):

        # Get the pump data.
        pump_data = {}
        for pump_name, pump_values in self.parameters["pump"].items():
            pump_data[pump_name] = {}
            pump_data[pump_name]["state"] = pump_values["state"]
            pump_data[pump_name]["hide"] = pump_values["hide"]

        # Get the tank data.
        tank_data = {}
        for tank_name, tank_values in self.parameters["tank"].items():
            tank_data[tank_name] = {}
            tank_data[tank_name]["level"] = tank_values["level"]

        # Get the events that have been logged since the last sync.
        event_record = self.event_record
        self.event_record = []

        return {
            "pump_data": pump_data,
            "tank_data": tank_data,
            "event_record": event_record
        }


    def applySyncData(self, syncData, full_update=True):
        if full_update:

            # Update the pump states.
            for pump_name, pump_data in syncData["pump_data"].items():
                self.parameters["pump"][pump_name]["state"] = pump_data["state"]
                self.parameters["pump"][pump_name]["hide"] = pump_data["hide"]
                self.parameters["pump"][pump_name]['ui'].changeState(
                                          pump_data['state'], pump_data['hide'])

            # Update the tank states.
            for tank_name, tank_data in syncData["tank_data"].items():
                self.parameters["tank"][tank_name]["level"] = tank_data["level"]
                self.parameters["tank"][tank_name]['ui'].refreshLevel(
                                                             tank_data['level'])

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

        if self.parameters['heuristicsolver']:
            return
        else:
            # List accepted keys
            accepted_keys = [v['keys'] for p, v in
                             self.parameters['pump'].items()]
            accepted_keys = [i for s in accepted_keys for i in s]

            if key_pressed in accepted_keys:
                # Select pump(s) that corresponds to the key...
                pumps = {p: v for p, v in self.parameters['pump'].items()
                         if key_pressed in v['keys'] and v['state'] != -1}

                # ...and reverse its state if it is not on failure
                for thisPump, pumpValue in pumps.items():
                    pumpValue['state'] = abs(pumpValue['state'] - 1)
                    # Log any pump state change
                    if self.is_server():
                        self.buildLog(["STATE", "PUMP" + thisPump,
                            "CLIENT" if from_client else "SERVER",
                                    'ON' if pumpValue['state'] == 1 else 'OFF'])
                    else:
                        self.buildLog(["STATE", "PUMP" + thisPump,
                                   'ON' if pumpValue['state'] == 1 else 'OFF'])

                self.repaint()  # Refresh
            else:
                return

    def paintEvent(self, e):
        """Paint the progress bar"""

        # Define the size and position of the progress bar.
        self.pen_size = int(1)
        self.progress_bar_width: int = int(self.width()*0.85)
        self.progress_bar_height: int = int(self.height() * 0.02)
        self.progress_bar_left_margin: int = int(self.width()*0.1)
        self.progress_bar_right_margin: int = int(self.width()*0.2)
        self.progress_bar_bottom_margin: int = int(self.height()*0.01)
        self.progress_bar_distance_from_bottom: int = self.progress_bar_height \
            + self.progress_bar_bottom_margin

        # Set the progress bar colour.
        qp = QtGui.QPainter(self)
        progress_colour = QtGui.QColor('#00FF00')
        if self.progress_bar_portion < 2/3:
            progress_colour = QtGui.QColor('#FFFF00')
        if self.progress_bar_portion < 1/3:
            progress_colour = QtGui.QColor('#FF0000')

        # Calculate the progress bar corners.
        progress_bar_upper_left = (self.progress_bar_left_margin+self.pen_size,
            self.height() - self.progress_bar_distance_from_bottom)
        progress_bar_upper_right = (progress_bar_upper_left[0] +
            self.progress_bar_width, progress_bar_upper_left[1])
        progress_bar_lower_left = (progress_bar_upper_left[0],
            progress_bar_upper_left[1] + self.progress_bar_height)
        progress_bar_lower_right = (progress_bar_upper_right[0],
                                    progress_bar_lower_left[1])

        # Draw a border for the progress bar.
        qp.drawLine(progress_bar_upper_left[0]-1, progress_bar_upper_left[1]-1,
                    progress_bar_upper_right[0], progress_bar_upper_right[1]-1)
        qp.drawLine(progress_bar_upper_right[0], progress_bar_upper_right[1]-1,
                    progress_bar_lower_right[0], progress_bar_lower_right[1])
        qp.drawLine(progress_bar_lower_right[0], progress_bar_lower_right[1],
                    progress_bar_lower_left[0]-1, progress_bar_lower_left[1])
        qp.drawLine(progress_bar_lower_left[0]-1, progress_bar_lower_left[1],
                    progress_bar_upper_left[0]-1, progress_bar_upper_left[1]-1)

        # Draw the progress bar.
        qp.fillRect(progress_bar_upper_left[0], progress_bar_upper_left[1],
                    int(self.progress_bar_width * self.progress_bar_portion),
                    self.progress_bar_height, progress_colour)

    def refreshModeLabel(self):
        if self.parameters['heuristicsolver'] is True:
            self.modeLabel.setText("<b>%s</b>" % _('AUTO ON'))
        elif self.parameters['assistedsolver'] is True:
            self.modeLabel.setText("<b>%s</b>" % _('ASSIST ON'))
        else:
            self.modeLabel.setText("<b>%s</b>" % _('MANUAL'))
        self.modeLabel.show()

    def buildLog(self, thisList):
        thisList = ["RESMAN"] + thisList
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
