from PySide2 import QtCore, QtWidgets, QtGui
import os
import re
from Helpers.Translator import translate as _


class Task(QtWidgets.QWidget):

    def __init__(self, parent):
        super(Task, self).__init__(parent)

        # GLOBAL VARS
        self.parameters = {
            'taskplacement': 'fullscreen',
            'taskupdatetime': None,
            'filename': '',
            'network': "as_host",
            'NETWORK_WHILE_PAUSED': True
        }

        self.screen_width = self.parent().screen_width
        self.screen_height = self.parent().screen_height

        # Scale files should by formated like:
        # ItemTitle;minLabel/maxLabel;minValue/maxValue/defaultValue
        self.regex_scale_pattern = r'(.*);(.*)/(.*);(\d*)/(\d*)/(\d*)'
        self.mainFont = QtGui.QFont("Times", round(self.screen_height/54.), italic = True)
        self.mainFont.setStyleStrategy(QtGui.QFont.PreferAntialias)
        self.scaleFont = QtGui.QFont("Times", round(self.screen_height/64.))

        # Check if in network mode.
        self.network_mode = self.parent().is_client or self.parent().is_server

        # Initialise the termination state.
        self.terminated = False
        self.partner_terminated = False
        self.partner_told_terminated = False
        self.active = False

    def onStart(self):
        self.parent().onPause()
        # Show the cursor.
        self.setCursor(QtCore.Qt.ArrowCursor)
        
        self.LoadScales(self.parameters['filename'])
        self.setLayout(self.layout)
        self.show()

        # Initialise the termination state.
        self.terminated = False
        self.partner_terminated = False
        self.partner_told_terminated = False
        self.active = True

    def LoadScales(self, scalefile):
        # Create dictionary to store scales information
        self.scales = {}

        # Load scales from file
        if not scalefile:
            self.parent().showCriticalMessage("No file to load!")
            return

        filename = os.path.join(self.parent().scales_directory, scalefile)

        if not os.path.exists(filename):
            self.parent().showCriticalMessage(
                _("Unable to find the scale file: '%s'") % filename)
            return

        self.scalesfile = open(filename, 'r')

        scale_number = -1
        for this_line in self.scalesfile:
            match = re.match(self.regex_scale_pattern, this_line)
            if match:
                scale_number += 1
                linecontent = this_line.split(';')
                self.scales[scale_number] = {}
                self.scales[scale_number]['label'] = linecontent[0]
                self.scales[scale_number]['title'] = linecontent[1]
                self.scales[scale_number]['minimumLabel'] = linecontent[2].split('/')[0]
                self.scales[scale_number]['maximumLabel'] = linecontent[2].split('/')[1]
                self.scales[scale_number]['minimumValue'] = int(linecontent[3].split('/')[0])
                self.scales[scale_number]['maximumValue'] = int(linecontent[3].split('/')[1])
                self.scales[scale_number]['defaultValue'] = int(linecontent[3].split('/')[2].replace('\n',''))

                if not self.scales[scale_number]['minimumValue'] < self.scales[scale_number]['defaultValue'] < self.scales[scale_number]['maximumValue']:
                    self.parent().showCriticalMessage(_("Error in scales. Default value must be comprised between minimum and maximum. See in file: ") + self.parameters['filename'])

        if len(self.scales) == 0:
            self.parent().showCriticalMessage(_("Error in scales. No correctly formatted line found in the following file:") + self.parameters['filename'])

        self.scalesfile.close()

        scale_width = self.screen_width / 3
        scale_height = (self.screen_height - (len(self.scales) * (50 + 30 + 40))) / 2
        scale_height = min(40, scale_height) # Minimal height is 40
        current_y = 0

        self.layout = QtWidgets.QVBoxLayout(self)
        for scale_number in self.scales.keys():
            self.scales[scale_number]['uis'] = dict()
            unicode_string = self.scales[scale_number]['title']
            self.scales[scale_number]['uis']['questionLabel'] = QtWidgets.QLabel(unicode_string)
            self.scales[scale_number]['uis']['questionLabel'].setFont(self.mainFont)
            self.scales[scale_number]['uis']['questionLabel'].setWordWrap(True)
            self.scales[scale_number]['uis']['questionLabel'].setAlignment(QtCore.Qt.AlignCenter)

            unicode_string = self.scales[scale_number]['minimumLabel']
            self.scales[scale_number]['uis']['minimumLabel'] = QtWidgets.QLabel(unicode_string)
            self.scales[scale_number]['uis']['minimumLabel'].setAlignment(QtCore.Qt.AlignRight)
            self.scales[scale_number]['uis']['minimumLabel'].setFont(self.scaleFont)


            self.scales[scale_number]['uis']['slider'] = QtWidgets.QSlider(QtCore.Qt.Horizontal)
            self.scales[scale_number]['uis']['slider'].setMinimum(self.scales[scale_number]['minimumValue'])
            self.scales[scale_number]['uis']['slider'].setMaximum(self.scales[scale_number]['maximumValue'])
            self.scales[scale_number]['uis']['slider'].setTickInterval(1)
            self.scales[scale_number]['uis']['slider'].setTickPosition(QtWidgets.QSlider.TicksBothSides)
            self.scales[scale_number]['uis']['slider'].setValue(self.scales[scale_number]['defaultValue'])
            self.scales[scale_number]['uis']['slider'].setSingleStep(1)
            self.scales[scale_number]['uis']['slider'].setMaximumWidth(0.5 * self.screen_width)


            unicode_string = self.scales[scale_number]['maximumLabel']
            self.scales[scale_number]['uis']['maximumLabel'] = QtWidgets.QLabel(unicode_string)
            self.scales[scale_number]['uis']['maximumLabel'].setAlignment(QtCore.Qt.AlignLeft)
            self.scales[scale_number]['uis']['maximumLabel'].setFont(self.scaleFont)

            hbox = QtWidgets.QHBoxLayout()
            hbox.addWidget(self.scales[scale_number]['uis']['questionLabel'])
            self.layout.addLayout(hbox)
            hbox = QtWidgets.QHBoxLayout()
            for this_element in ['minimumLabel','slider','maximumLabel']:
                vbox = QtWidgets.QVBoxLayout()
                vbox.addWidget(self.scales[scale_number]['uis'][this_element])
                vbox.setAlignment(QtCore.Qt.AlignVCenter)
                vbox.setContentsMargins(10,0,10,0)
                hbox.addLayout(vbox)
            self.layout.addLayout(hbox)
            self.layout.addStretch(1)


        self.questionnairebtn = QtWidgets.QPushButton(_('Validate'))
        self.questionnairebtn.setMaximumWidth(0.25 * self.screen_width)
        self.questionnairebtn.clicked.connect(self.terminate_event)

        hbox = QtWidgets.QHBoxLayout()
        hbox.addWidget(self.questionnairebtn)
        self.layout.addLayout(hbox)

    def onUpdate(self):
        pass

    def getSyncData(self):

        # If this is sent after termination we know the partner has been told
        # that this task has terminated.
        if self.terminated:
            self.partner_told_terminated = True

        # Pass on whether this task has terminated.
        return {
            "terminated": self.terminated,
        }

    def applySyncData(self, syncData, full_update=True):

        # Terminate if both have terminated.
        if self.terminated and (self.partner_terminated or
                       syncData["terminated"]) and self.partner_told_terminated:
            self.terminate()

        # Update whether the partner has terminated.
        self.partner_terminated = syncData["terminated"]

    def popNewInputs(self):

        # If this is sent after termination we know the partner has been told
        # that this task has terminated.
        if self.terminated:
            self.partner_told_terminated = True

        # Return whether the task has terminated.
        return {"terminated": self.terminated}

    def applyNewInputs(self, new_inputs):

        # Terminate if both have terminated.
        if self.terminated and (self.partner_terminated or
                     new_inputs["terminated"]) and self.partner_told_terminated:
            self.terminate()

        # Update whether the partner has terminated.
        self.partner_terminated = new_inputs["terminated"]

    def terminate_event(self):
        self.terminated = True

        # If not in network mode just terminate.
        if not self.network_mode:
            self.terminate()

        # If in network mode we need to wait for the partner to finish.
        elif self.network_mode and not self.partner_terminated:
            self.questionnairebtn.setEnabled(False)
            self.questionnairebtn.setText(_('Waiting for partner...'))

    def terminate(self):
        if self.active:
            for this_scale in self.scales.keys():
                self.buildLog(["INPUT", self.scales[this_scale]['label'], str(self.scales[this_scale]['uis']['slider'].value())])

            # Hide the cursor again.
            self.setCursor(QtCore.Qt.BlankCursor)

            # Force to reparent and destroy the layout
            QtWidgets.QWidget().setLayout(self.layout)

            self.parent().onResume()
            self.active = False

    def buildLog(self, thisList):
        thisList = ["SCALES"] + thisList
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