from PySide2 import QtCore, QtWidgets, QtGui
from PySide2.QtCore import QTimer
import os
from Helpers.Translator import translate as _


class Task(QtWidgets.QWidget):

    def __init__(self, parent):
        super(Task, self).__init__(parent)

        self.parameters = {
            'taskplacement': 'fullscreen',
            'taskupdatetime': None,
            'filename': '',
            'pointsize': 0,
            'durationsec': 0,
            'mindurationsec': 0,
            'image': '',
            'network': "as_host",
            'NETWORK_WHILE_PAUSED': True
        }

        self.screen_width = self.parent().screen_width
        self.screen_height = self.parent().screen_height

        self.font = QtGui.QFont("Times", round(self.screen_height/54.))
        self.font.setStyleStrategy(QtGui.QFont.PreferAntialias)

        # Check if in network mode.
        self.network_mode = self.parent().is_client or self.parent().is_server

        # Initialise the termination state.
        self.terminated = False
        self.partner_terminated = False
        self.partner_told_terminated = False
        self.active = False

    def onStart(self):
        if self.parameters['pointsize'] > 0:
            self.font.setPointSize(self.parameters['pointsize'])

        self.parent().onPause()
        self.LoadText(self.parameters['filename'])
        self.setLayout(self.layout)
        self.show()
        if self.parameters['durationsec'] > 0:
            durationms = self.parameters['durationsec'] * 1000
            QTimer.singleShot(durationms, self.terminate_event)
            self.parameters['durationsec'] = 0

        # Show the cursor.
        self.setCursor(QtCore.Qt.ArrowCursor)

        # Initialise the termination state.
        self.terminated = False
        self.partner_terminated = False
        self.partner_told_terminated = False
        self.active = True

    def LoadText(self, textfile):
        # Load scales from file
        if len(textfile) == 0:
            self.parent().showCriticalMessage(_("No file to load!"))
            return

        filepath = os.path.join(self.parent().instructions_directory, textfile)

        if not os.path.exists(filepath):
            self.parent().showCriticalMessage(
                _("Unable to find the text file: '%s'") % filepath)
            return

        with open(filepath, 'r') as txt:
            instructions = txt.read()
        instructions_ui = QtWidgets.QLabel(instructions)
        instructions_ui.setFont(self.font)
        instructions_ui.setWordWrap(True)
        instructions_ui.setAlignment(QtCore.Qt.AlignCenter)

        self.layout = QtWidgets.QVBoxLayout(self)
        hbox = QtWidgets.QHBoxLayout()
        hbox.addWidget(instructions_ui)
        self.layout.addLayout(hbox)

        self.layout.addStretch(1)

        if self.parameters['image'] != '':
            image = QtGui.QPixmap("./Images/" + self.parameters['image'])
            lbl = QtWidgets.QLabel()
            lbl.setPixmap(image)
            lbl.setAlignment(QtCore.Qt.AlignCenter)
            hbox = QtWidgets.QHBoxLayout()
            hbox.addWidget(lbl)
            self.layout.addLayout(hbox)
            self.parameters['image'] = ''

        if self.parameters['durationsec'] == 0:
            waitms = self.parameters['mindurationsec'] * 1000
            QTimer.singleShot(waitms, self.createButton)
            self.parameters['mindurationsec'] = 0

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
        
    def createButton(self):
        self.continue_button = QtWidgets.QPushButton(_('Continue'))
        self.continue_button.setMaximumWidth(0.25 * self.screen_width)
        self.continue_button.clicked.connect(self.terminate_event)
        self.continue_button.setAutoDefault(True)
        hbox = QtWidgets.QHBoxLayout()
        hbox.addWidget(self.continue_button)
        self.layout.addLayout(hbox)

    def terminate_event(self):
        self.terminated = True

        # If not in network mode just terminate.
        if not self.network_mode:
            self.terminate()

        # If in network mode we need to wait for the partner to finish.
        elif self.network_mode and not self.partner_terminated:
            self.continue_button.setEnabled(False)
            self.continue_button.setText(_('Waiting for partner...'))


    def terminate(self):
        if self.active:
            self.buildLog([self.parameters['filename'], 'END'])
            # Hide the cursor again.
            self.setCursor(QtCore.Qt.BlankCursor)
            # Force to reparent and destroy the layout
            QtWidgets.QWidget().setLayout(self.layout)
            self.parent().onResume()
            self.active = False

    def buildLog(self, thisList):
        thisList = ['INSTRUCTION'] + thisList
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
