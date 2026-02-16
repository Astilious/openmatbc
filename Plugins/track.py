from PySide2 import QtWidgets, QtCore, QtGui
from Helpers import WTrack
from Helpers.Translator import translate as _
import pygame
import copy

class Task(QtWidgets.QWidget):

    def __init__(self, parent):
        super(Task, self).__init__(parent)

        self.my_joystick = None

        # TRACK PARAMETERS ###
        self.parameters = {
            'taskplacement': 'topmid',
            'taskupdatetime': 20,
            'title': 'Tracking',
            'cursorcolor': '#0000FF',
            'cursorcoloroutside': '#0000FF',
            'automaticsolver': False,
            'displayautomationstate': False,
            'assistedsolver': False,
            'targetradius': 0.1,
            'joystickforce': 1.0,
            'cutofffrequency': 0.06,
            'equalproportions': True,
            'resetperformance': None,
            'multiplier': 1.0,
            'setcursorx': -2.0,
            'setcursory': -2.0,
            'settime': -1.0,
            'network': "no"
        }

        self.performance = {
            'total' : {'time_in_ms':0, 'time_out_ms':0, 'points_number':0, 'deviation_mean':0},
            'last'  : {'time_in_ms':0, 'time_out_ms':0, 'points_number':0, 'deviation_mean':0}
        }

        # Potentially translate task title
        self.parameters['title'] = _(self.parameters['title'])

        # Record of input for use with networked mode.
        self.input_record = {
            "joystick": []
        }

        # Record of recent logged events.
        self.event_record = []


    def onStart(self):

        # Define a QLabel object to potentially display automation mode
        self.modeFont = QtGui.QFont("sans-serif", int(self.height() / 35.), QtGui.QFont.Bold)
        self.modeLabel = QtWidgets.QLabel(self)
        self.modeLabel.setGeometry(QtCore.QRect(0.60 * self.width(), 0.60 * self.height(), 0.40 * self.width(), 0.40 * self.height()))
        self.modeLabel.setAlignment(QtCore.Qt.AlignCenter)
        self.modeLabel.setFont(self.modeFont)

        self.parameters['displaytitle'] = True
        
        # Set a WTrack Qt object
        self.widget = WTrack.WTrack(self, self.parameters['equalproportions'])

        # Create a layout for the widget
        layout = QtWidgets.QGridLayout()

        # Add the WTrack object to the layout
        layout.addWidget(self.widget)
        self.setLayout(layout)

        pygame.joystick.init()

        # Check for a joystick device
        if pygame.joystick.get_count() == 0:
            self.parent().showCriticalMessage(
                _("Please plug a joystick for the '%s' task!") % (self.parameters['title']))
        else:
            self.my_joystick = pygame.joystick.Joystick(0)
            self.my_joystick.init()

        # Log some task information once
        self.buildLog(["STATE", "TARGET", "X", str(0.5)])
        self.buildLog(["STATE", "TARGET", "Y", str(0.5)])
        self.buildLog(["STATE", "TARGET", "RADIUS",
                       str(self.parameters['targetradius'])])
        msg = _('AUTO') if self.parameters['automaticsolver'] else _('MANUAL')
        self.buildLog(["STATE", "", "MODE", msg])


    def getScore(self):
        return int((self.performance['last']['time_in_ms'] -
                    self.performance['last']['time_out_ms']) / 10)

    def onUpdate(self):

        if self.parameters['displayautomationstate']:
            self.refreshModeLabel()
        else:
            self.modeLabel.hide()

        if self.parameters['resetperformance'] is not None:
            if self.parameters['resetperformance'] in ['last', 'global']:
                for i in self.performance[self.parameters['resetperformance']]:
                    self.performance[self.parameters['resetperformance']][i] = 0
            else:
                self.parent().showCriticalMessage(_("%s : wrong argument in track;resetperformance") % self.parameters['resetperformance'])
            self.parameters['resetperformance'] = None

        # Apply any forced cursor repositions.
        if self.parameters['setcursorx'] > -1.0:
            self.widget.setCursorX(self.parameters['setcursorx'])
            self.parameters['setcursorx'] = -2.0
        if self.parameters['setcursory'] > -1.0:
            self.widget.setCursorY(self.parameters['setcursory'])  
            self.parameters['setcursory'] = -2.0

        # Set the time for cursor motion calculations if requested.
        if self.parameters['settime'] >= 0.0:
            self.widget.setTimeOffset(self.parameters['settime'])
            self.parameters['settime'] = -1.0

        # If automatic solver : always correct cursor position
        if self.parameters['automaticsolver']:
            x_input, y_input = self.widget.getAutoCompensation()

        # Else record manual compensatory movements
        else:
            # Retrieve potentials joystick inputs (x,y)
            x_input, y_input = self.joystick_input()

            # If assisted solver : correct cursor position only if joystick
            # inputs something
            if self.parameters['assistedsolver']:
                if any([this_input != 0 for this_input in [x_input, y_input]]):
                    x_input, y_input = self.widget.getAutoCompensation()

        # Update the cursor position based on the calculated input.
        self.updateCursor(x_input, y_input)


    def updateCursor(self, x_input, y_input, from_client=False):

        # Compute next cursor coordinates (x,y)
        current_X, current_Y = self.widget.moveCursor(self.parameters['multiplier'])

        # Modulate cursor position with potentials joystick inputs
        current_X += x_input
        current_Y += y_input

        # Refresh the display
        self.widget.refreshCursorPosition(current_X, current_Y)

        # Log the joystick inputs
        self.buildLog(["ACTION", "JOYSTICK", "X", "CLIENT" if from_client else "SERVER", str(x_input)])
        self.buildLog(["ACTION", "JOYSTICK", "Y", "CLIENT" if from_client else "SERVER", str(y_input)])

        # Constantly log the cursor coordinates
        self.buildLog(["STATE", "CURSOR", "X", str(current_X)])
        self.buildLog(["STATE", "CURSOR", "Y", str(current_Y)])

        # Record performance
        for perf_cat, perf_val in self.performance.items():
            if self.widget.isCursorInTarget():
                perf_val['time_in_ms'] += self.parameters['taskupdatetime']
            else:
                perf_val['time_out_ms'] += self.parameters['taskupdatetime']

            current_deviation = self.widget.returnAbsoluteDeviation()
            perf_val['points_number'] += 1
            perf_val['deviation_mean'] = perf_val['deviation_mean'] * (
                        (perf_val['points_number'] - 1) / float(perf_val['points_number'])) + current_deviation * (
                                                     float(1) / perf_val['points_number'])

    def getSyncData(self):

        # Twisted seems to have a bad reaction to numpy types so convert to float before sending.
        cursorPos = self.widget.getXY()
        cursorPos = (float(cursorPos[0]), float(cursorPos[1]))

        # Get the events that have been logged since the last sync.
        event_record = self.event_record
        self.event_record = []

        return {
            "cursorPos": cursorPos,
            "event_record": event_record
        }

    def applySyncData(self, syncData, full_update=True):

        if full_update:
            cursorPos = syncData["cursorPos"]
            self.widget.refreshCursorPosition(cursorPos[0], cursorPos[1])

        # Record the new events.
        for event in syncData["event_record"]:
            self.parent().mainLog.addLine(event)


    def popNewInputs(self):
        temp = copy.deepcopy(self.input_record)
        self.input_record["joystick"] = []
        return temp


    def applyNewInputs(self, new_inputs):

        # Apply the new input as normal joystick events.
        joystick_inputs = new_inputs["joystick"]
        for event in joystick_inputs:
            self.updateCursor(event[0], event[1], from_client=True)

    def joystick_input(self):
        if self.my_joystick and self.parent().isActiveWindow():
            if self.is_client():
                if not self.parameters['automaticsolver']:
                    pygame.event.pump()
                    # Apply a joystickforce factor to joystick input to obtain a
                    # smoother movement
                    current_force = self.parent().PLUGINS_TASK["track"]["TIME_SINCE_UPDATE"] * (float(self.parameters['joystickforce']) / 1000)
                    self.input_record["joystick"].append((self.my_joystick.get_axis(0) * current_force, self.my_joystick.get_axis(1) * current_force))
                    return self.input_record["joystick"][-1]
                else:
                    return (0, 0)
            else:
                pygame.event.pump()
                # Apply a joystickforce factor to joystick input to obtain a
                # smoother movement
                current_force = self.parent().PLUGINS_TASK["track"]["TIME_SINCE_UPDATE"] * (float(self.parameters['joystickforce'])/1000)
                return self.my_joystick.get_axis(0) * current_force, self.my_joystick.get_axis(1) * current_force
        else:
            return (0, 0)


    def refreshModeLabel(self):
        if self.parameters['automaticsolver']:
            self.modeLabel.setText("<b>%s</b>" % _('AUTO ON'))
        elif self.parameters['assistedsolver']:
            self.modeLabel.setText("<b>%s</b>" % _('ASSIST ON'))
        else:
            self.modeLabel.setText("<b>%s</b>" % _('MANUAL'))
        self.modeLabel.show()


    def buildLog(self, thisList):
        thisList = ["TRACK"] + thisList
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
