#!/usr/bin/env python3
import ctypes
import time
import datetime
from importlib.machinery import SourceFileLoader
import ast
import sys
import os
import platform
from Helpers import Logger, Translator
from Helpers.Translator import translate as _
import Networking.server
import Networking.client
import Networking.message_types
import twisted.internet.protocol
import twisted.internet.reactor
import twisted.internet.task
import twisted.internet.defer
import twisted.spread.pb

# Force import for cxfreeze:
from Helpers import (QTExtensions, WLight, WPump, WCom,
                     WScale, WScheduler, WTank, WTrack, xeger)


VERSION = "1.0.000"
VERSIONTITLE = 'OpenMATBC v' + VERSION

# Default directories
PLUGINS_PATH = "Plugins"
LOGS_PATH = "Logs"
SCENARIOS_PATH = "Scenarios"
SCALES_PATH = "Scales"
INSTRUCTIONS_PATH = "Instructions"

# The name of variable used to interact with plugins.
# Do not touch or everything will break!
PARAMETERS_VARIABLE = "parameters"

# We wait at least one tenth millisecond to update tasks.This is sufficient!
# Will prevent hammering the main loop at <0.06 milliseconds
MAIN_SCHEDULER_INTERVAL = 1

global CONFIG
CONFIG = {}

def twisted_sleep(secs):
    return twisted.internet.task.deferLater(twisted.internet.reactor, secs, lambda: None)

def OSCriticalErrorMessage(title, msg):
    if platform.system() == "Windows":
        ctypes.windll.user32.MessageBoxW(None, _(msg),
                                         VERSIONTITLE + " - " + _(title), 0)
    else:
        print("{}:{}".format(_(title),_(msg)))
    sys.exit()


# Ensure that Pyside2, pygame, rstr, psutil and wave are available
try:
    from PySide2 import QtCore, QtWidgets, QtGui
    #we need to hide pygame message in order to precisely control the output log
    os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = "hide"
    import pygame
    import rstr
    import psutil
    import wave
except Exception as e:
    OSCriticalErrorMessage(_("Error"),
        _("Please check that all required libraries are installed:\n\n"+str(e)))


class Main(QtWidgets.QMainWindow):

    def __init__(self, scenario_fullpath, is_client : bool = False, is_server : bool = False, host : str = "localhost", port : int = 31415):
        super(Main, self).__init__(parent=None)
        self.registeredTaskTimer = []
        self.parameters = {
            'showlabels': True,
            'allowescape': True,
            'messagetolog': '',
            'allowaltf4': True
        }

        # Preallocate a dictionary to store plugins information
        self.PLUGINS_TASK = {}

        # Store working directory and scenario names
        # Use correct directory if running in cxFreeze (frozen)
        if getattr(sys, 'frozen', False):
            self.working_directory = os.getcwd()
        else:
            self.working_directory = os.path.dirname(os.path.abspath(__file__))

        # Record whether this is a client or a server.
        self.is_client = is_client
        self.is_server = is_server

        # Initialise scenario variables.
        self.scenario_shortfilename = None
        self.scenario_directory = None

        # Initialise networking variables.
        self.am_connected = False

        # Set the scenario path if it's available.
        if not is_client or scenario_fullpath is not None:
            self.set_scenario_path(scenario_fullpath)

        # Initialise the scales and instructions paths.
        self.scales_directory = os.path.join(self.working_directory, SCALES_PATH)
        self.instructions_directory = os.path.join(self.working_directory, INSTRUCTIONS_PATH)

        # Initialise the factory.
        if is_client:
            self.client_factory = Networking.client.start_client(self, host, port)
            self.host = host
            self.port = port
            self.server_communicator = None
        if is_server:
            self.server_factory = Networking.server.start_server(self)
            self.port = port

        # Initialize timing variables
        self.scenarioTimeStr = None
        self.totalElapsedTime_ms = 0
        self.last_client_sync = 0
        self.connection_timeout = 5

        # Compute screen dimensions
        # Screen index can be changed just below

        screen_idx = 0  # Here, you can change the screen index
        screen = QtGui.QGuiApplication.screens()[screen_idx]
        self.screen_width = screen.geometry().width()
        self.screen_height = screen.geometry().height()

        self.setFixedSize(self.screen_width, self.screen_height)

        #  The following dictionary contains all the information about sizes and placements.
        #  control_top/left is the top/left margin
        #  control_height/width defines the plugin height/width
        self.placements = {
            'fullscreen': {'control_top': 0, 'control_left': 0, 'control_height': self.screen_height,
                           'control_width': self.screen_width},

            'topleft': {'control_top': 0, 'control_left': 0, 'control_height': self.screen_height / 2,
                        'control_width': self.screen_width * (7.0 / 20.1)},

            'topmid': {'control_top': 0, 'control_left': self.screen_width * (
                    5.9 / 20.1), 'control_height': self.screen_height / 2,
                       'control_width': self.screen_width * (10.7 / 20.1)},

            'topright': {'control_top': 0, 'control_left': self.screen_width * (5.9 / 20.1) + self.screen_width * (
                    10.6 / 20.1), 'control_height': self.screen_height / 2,
                         'control_width': self.screen_width * (3.6 / 20.1)},

            'bottomleft': {'control_top': self.screen_height / 2, 'control_left': 0, 'control_height':
                self.screen_height / 2, 'control_width': self.screen_width * (5.9 / 20.1)},

            'bottommid': {'control_top': self.screen_height / 2, 'control_left': self.screen_width * (
                    5.9 / 20.1), 'control_height': self.screen_height / 2,
                          'control_width': self.screen_width * (10.7 / 20.1)},

            'bottomright': {'control_top': self.screen_height / 2, 'control_left': self.screen_width * (5.9 / 20.1) +
                                                                                   self.screen_width * (10.6 / 20.1),
                            'control_height': self.screen_height / 2,
                            'control_width': self.screen_width * (3.6 / 20.1)}
        }

        # Turn off Caps Lock and on Num Lock (for resman)... if possible (only Windows until now)
        if platform.system() == "Windows":
            self.turnKey(0x14, False)  # Caps Lock Off
            self.turnKey(0x90, True)  # Num Lock On

        # Hide the cursor.
        self.setCursor(QtCore.Qt.BlankCursor)

        # Preallocate variables to handle experiment pauses and termination
        self.experiment_pause = False
        self.experiment_running = True
        self.termination_message_sent = False
        self.ended_time = 0

        # Initialise the list of loaded tasks.
        self.loadedTasks = []

        # Init things that primarily load in continued_init
        self.LOG_FILE_PATH = None
        self.mainLog = None
        self.scenariocontents = None

        # Initialise the system to call the main loop.
        self.main_loop_caller = twisted.internet.task.LoopingCall(self.mainLoop)
        self.already_a_main_loop_running = False


    @twisted.internet.defer.inlineCallbacks
    def continued_init(self):

        # If this is a client, start the client and wait for the server to provide the scenario.
        if self.is_client:
            print("Client waiting for connection...")
            self.server_communicator = yield self.client_factory.getRootObject()
            yield self.server_communicator.callRemote(Networking.message_types.SERVER_CONFIRM_CONNECTED)
            if self.scenario_shortfilename is None:
                scenario_fullpath = yield self.server_communicator.callRemote(Networking.message_types.SERVER_GET_SCENARIO_PATH)
                self.set_scenario_path(scenario_fullpath)
            print("Connection confirmed")
        
        # Recreate the scenario fullpath.
        scenario_fullpath = os.path.join(self.scenario_directory, self.scenario_shortfilename)

        # Check that the plugins folder exists
        if not os.path.exists(os.path.join(self.working_directory, PLUGINS_PATH)):
            self.showCriticalMessage(
                _("Plugins directory does not exist. Check that its name is correct"))

        # Create a ./Logs folder if it does not exist
        if not os.path.exists(os.path.join(self.working_directory, LOGS_PATH)):
            os.mkdir(os.path.join(self.working_directory, LOGS_PATH))

        # Create a filename for the log file
        # Corresponds to : scenario name + client/server + date + .log
        client_server_append = "client" if self.is_client else "server"
        LOG_FILE_NAME = os.path.join(self.scenario_shortfilename.replace(".txt", "").replace(
            " ", "_") + "_" + client_server_append + "_" + datetime.datetime.now().strftime("%Y%m%d_%H%M") + ".log")
        self.LOG_FILE_PATH = os.path.join(self.working_directory, LOGS_PATH, LOG_FILE_NAME)

        # Initialize a Logger instance with this log filename (see Helpers/Logger.py)
        self.mainLog = Logger.Logger(self, self.LOG_FILE_PATH)
        self.mainLog.addLine(['MAIN', 'INFO', 'SCENARIO', 'FILENAME', self.scenario_shortfilename])

        # Log the computed screen size values
        self.mainLog.addLine(
            ['MAIN', 'INFO', 'SCREENSIZE', 'WIDTH', str(self.screen_width)])
        self.mainLog.addLine(
            ['MAIN', 'INFO', 'SCREENSIZE', 'HEIGHT', str(self.screen_height)])

        # Initialize plugins
        self.load_plugins()
        self.place_plugins_on_screen()

        # Load scenario file
        self.scenariocontents = self.loadScenario(scenario_fullpath)

        # If this is a server, start the server and wait for a client to connect.
        if self.is_server:
            print("Server waiting for connection...")
            while not self.get_connected():
                yield twisted_sleep(0.01)
            print("Connection confirmed")

        # Update time once to take first scenario instructions (0:00:00) into account
        yield self.scenarioUpdateTime()
        self.last_time_microsec = self.default_timer()

        # Start the main loop.
        thing = self.main_loop_caller.start(0.0001)
        def on_main_loop_error(failure):
            print("Main loop error:", failure)
        thing.addErrback(on_main_loop_error)
        self.already_a_main_loop_running = False

    def get_connected(self):
        temp_am_connected = self.am_connected
        return temp_am_connected


    def set_connected(self, new_connected):
        self.am_connected = new_connected


    def get_time(self):
        temp_time = self.totalElapsedTime_ms
        return temp_time


    def set_time(self, new_time):
        self.totalElapsedTime_ms = new_time


    def set_scenario_path(self, scenario_fullpath):
        self.scenario_shortfilename = os.path.split(scenario_fullpath)[1]
        self.scenario_directory = os.path.split(scenario_fullpath)[0]


    def turnKey(self, k, value):
        """On Windows, use this method to turn off/on a key defined by the k variable"""
        KEYEVENTF_EXTENTEDKEY = 0x1
        KEYEVENTF_KEYUP = 0x2
        KEYEVENTF_KEYDOWN = 0x0

        dll = ctypes.WinDLL('User32.dll')
        if value and not dll.GetKeyState(k):
            dll.keybd_event(k, 0x45, KEYEVENTF_EXTENTEDKEY, 0)
            #dll.keybd_event(
            #    k, 0x45, KEYEVENTF_EXTENTEDKEY | KEYEVENTF_KEYDOWN, 0)
            dll.keybd_event(
                k, 0x45, KEYEVENTF_EXTENTEDKEY | KEYEVENTF_KEYDOWN, 0)
        elif not value and dll.GetKeyState(k):
            dll.keybd_event(k, 0x45, KEYEVENTF_EXTENTEDKEY, 0)
            dll.keybd_event(
                k, 0x45, KEYEVENTF_EXTENTEDKEY | KEYEVENTF_KEYDOWN, 0)


    def load_plugins(self):
        """Inform the Main() class with plugins information"""

        # For each plugin that is present in the ./Plugins directory
        for thisfile in os.listdir(PLUGINS_PATH):

            # If it is a python file...
            if thisfile.endswith(".py"):

                # Retrieve the plugin name
                plugin_name = thisfile.replace(".py", "")
                module = SourceFileLoader(plugin_name,
                                          os.path.join(self.working_directory,
                                                       PLUGINS_PATH,
                                                       thisfile)).load_module()

                # If the plugin has defined a Task class, log it
                if hasattr(module, "Task"):
                    task = module.Task(self)

                    # Check if a parameters dictionary is present
                    if not hasattr(task, 'parameters'):
                        print(_("Plugin '%s' is invalid (no parameters data)") % (plugin_name))
                        continue

                    # Initialize a dictionary to store plugin information
                    plugin_name = plugin_name.lower()
                    self.PLUGINS_TASK[plugin_name] = {}
                    self.PLUGINS_TASK[plugin_name]['class'] = task
                    self.PLUGINS_TASK[plugin_name]['TIME_SINCE_UPDATE'] = 0
                    self.PLUGINS_TASK[plugin_name]['taskRunning'] = False
                    self.PLUGINS_TASK[plugin_name]['taskPaused'] = False
                    self.PLUGINS_TASK[plugin_name]['taskVisible'] = False

                    # Store potential plugin information
                    if 'taskupdatetime' in task.parameters:
                        self.PLUGINS_TASK[plugin_name]["UPDATE_TIME"] = task.parameters['taskupdatetime']
                    else:
                        self.PLUGINS_TASK[plugin_name]["UPDATE_TIME"] = None

                    if hasattr(task, "keyEvent"):
                        self.PLUGINS_TASK[plugin_name]["RECEIVE_KEY"] = True
                    else:
                        self.PLUGINS_TASK[plugin_name]["RECEIVE_KEY"] = False
                    self.PLUGINS_TASK[plugin_name]["NEED_LOG"] = True if hasattr(task, "onLog") else False

                    task.hide()
                else:
                    print(_("Plugin '%s' is not recognized") % plugin_name)


    def place_plugins_on_screen(self):
        """Compute size and position of each plugin, in a 2 x 3 canvas,
        as a function of the taskplacement variable of each plugin"""

        # Compute some sizes as a function of screen height
        LABEL_HEIGHT = self.screen_height / 27
        font_size_pt = int(LABEL_HEIGHT / (5 / 2))

        # Adapt top margin and height to the presence/absence of plugin labels
        if self.parameters['showlabels']:
            for k in self.placements.keys():
                self.placements[k]['control_top'] += LABEL_HEIGHT
                self.placements[k]['control_height'] -= LABEL_HEIGHT

        # Browse plugins to effectively size and place them
        for plugin_name in self.PLUGINS_TASK:
            plugin = self.getPluginClass(plugin_name)

            # Check if the plugin has a taskplacement parameter
            if 'taskplacement' not in plugin.parameters or not plugin.parameters['taskplacement']:
                print(_("Plugin '%s' has no placement data. It will not be displayed") % plugin_name)
                continue

            # If so, retrieve it
            placement = plugin.parameters['taskplacement']

            # Plugin placement must match one value of the self.placement dictionary
            if placement in self.placements.keys():
                self.control_top = self.placements[placement]['control_top']
                self.control_left = self.placements[placement]['control_left']
                self.control_height = self.placements[
                    placement]['control_height']
                self.control_width = self.placements[
                    placement]['control_width']

                # If the plugin is not displayed in fullscreen, log information about its area of interest (AOI)
                if placement != 'fullscreen':
                    thisPlacement = self.placements[placement]
                    AOIx = [int(thisPlacement['control_left']), int(
                        thisPlacement['control_left'] + thisPlacement['control_width'])]
                    AOIy = [int(thisPlacement['control_top']), int(
                        thisPlacement['control_top'] + thisPlacement['control_height'])]

                    self.mainLog.addLine(
                        ['MAIN', 'INFO', plugin_name.upper(), 'AOI_X', AOIx])
                    self.mainLog.addLine(
                        ['MAIN', 'INFO', plugin_name.upper(), 'AOI_Y', AOIy])

                    # For each non-fullscreen plugin, show its label if needed
                    if self.parameters['showlabels']:
                        self.PLUGINS_TASK[plugin_name]['ui_label'] = QtWidgets.QLabel(self)
                        self.PLUGINS_TASK[plugin_name]['ui_label'].setStyleSheet("font: " + str(font_size_pt) + "pt \"MS Shell Dlg 2\"; background-color: black; color: white;")
                        self.PLUGINS_TASK[plugin_name]['ui_label'].setAlignment(QtCore.Qt.AlignCenter)
                        self.PLUGINS_TASK[plugin_name]['ui_label'].resize(self.control_width, LABEL_HEIGHT)
                        self.PLUGINS_TASK[plugin_name]['ui_label'].move(self.control_left, self.control_top - LABEL_HEIGHT)

            else:
                self.showCriticalMessage(
                    _("Placement '%s' is not recognized!") % placement)

            # Resize, place and show the plugin itself
            plugin.resize(self.control_width, self.control_height)
            plugin.move(self.control_left, self.control_top)
            plugin.show()


    @twisted.internet.defer.inlineCallbacks
    def mainLoop(self):

        # Make sure only one copy of the loop runs at a time.
        if not self.already_a_main_loop_running:
            self.already_a_main_loop_running = True

            # Run the loop functions.
            yield self.scheduler()
            QtCore.QCoreApplication.processEvents()

            # Start the loop up again.
            self.already_a_main_loop_running = False


    def runExperiment(self):
        # Initialize a general timer
        if sys.platform == 'win32':
            self.default_timer = time.perf_counter
        else:
            self.default_timer = time.time

        # Set to high priority
        try:
            p = psutil.Process(os.getpid())
            p.nice(psutil.HIGH_PRIORITY_CLASS)
        except Exception:
            pass

        # Launch experiment
        print("Connecting...")
        if self.is_server:
            twisted.internet.reactor.listenTCP(self.port, self.server_factory)
        if self.is_client:
            twisted.internet.reactor.connectTCP(self.host, self.port, self.client_factory, timeout=1000.0)
        
        twisted.internet.reactor.callLater(0.0, self.continued_init)
        twisted.internet.reactor.run()

        sys.exit()

    def showCriticalMessage(self, msg):
        """Display a critical message (msg) in a QMessageBox Qt object before exiting"""

        flags = QtWidgets.QMessageBox.Abort
        flags |= QtWidgets.QMessageBox.StandardButton.Ignore

        result = QtWidgets.QMessageBox.critical(self, VERSIONTITLE + " "+_("Error"),
                                            msg,
                                            flags)

        if result == QtWidgets.QMessageBox.Abort:
            self.onEnd()
            sys.exit()


    def getPluginClass(self, plugin):
        """Return the Task instance of the given plugin"""
        if plugin == "__main__":
            return self
        else:
            return self.PLUGINS_TASK[plugin]["class"]


    def updateLabels(self):
        # If loaded plugins have an ui_label, display it
        for plugin_name in self.loadedTasks:
            if plugin_name != "__main__":
                if 'ui_label' in self.PLUGINS_TASK[plugin_name]:
                    if not self.PLUGINS_TASK[plugin_name]['taskVisible']:
                        self.PLUGINS_TASK[plugin_name]['ui_label'].hide()
                    else:
                        self.PLUGINS_TASK[plugin_name]['ui_label'].setText(self.PLUGINS_TASK[plugin_name]['class'].parameters['title'].upper())
                        self.PLUGINS_TASK[plugin_name]['ui_label'].show()

    def timerRegister(self, timer):
        self.registeredTaskTimer.append(timer)


    def loadScenario(self, scenario_file):
        """Convert the scenario file into a dictionary : dict[time][task][listOfcommand]"""

        # Create a dictionary
        scenario_content = {}

        # Read the scenario text file
        with open(scenario_file, 'r') as f:

            # Browse lines
            for lineNumber, scenario_line in enumerate(f):

                # Remove blank lines
                scenario_line = scenario_line.strip()

                # Only consider lines that do not begin with a #
                if not scenario_line.startswith("#") and scenario_line:

                    # Extract information from line : time, task and command (see getCommand below)
                    time, task, command, priority = self.getCommand(lineNumber, scenario_line)

                    # Add the task to the list of loadedTasks
                    if not task in self.loadedTasks and task is not None:
                        self.loadedTasks.append(task)

                    # If the extracted time is not yet present in the scenario dictionary...
                    if time and time not in scenario_content:
                        # ...add it
                        scenario_content[time] = {}

                    # Likewise, if task not in scenario, add it
                    if task and task not in scenario_content[time]:
                        scenario_content[time][task] = []

                    # Finally, add the command at the correct location in the scenario dictionary
                    if command and time and task:
                        scenario_content[time][task].append((command, priority))

        # If scenario is not valid, exit (see validateScenario below)
        if not self.validateScenario(scenario_content):
            sys.exit()

        return scenario_content

    def validateScenario(self, scenario_content):
        """Check that the scenario follows a set of criteria. Output the corresponding boolean value"""

        # Browse the loaded task, ignoring the __main__ one
        for checktask in self.loadedTasks:
            if checktask == "__main__":
                continue

            else:
                howmanyentries = 0
                entries = []
                for k in scenario_content.keys():
                    if checktask in scenario_content[k]:
                        for t in scenario_content[k][checktask]:
                            howmanyentries += 1
                            entries.append(t)

                # Does the scenario contains one or more commands for the task at hand ?
                if howmanyentries == 0:
                    self.showCriticalMessage(_("No entry has been found for the '%s' plugin. Check the scenario file") % checktask )
                    return False

                # Are the start/stop commands present ?
                for thiscommand in ['start']:
                    if thiscommand not in [thisentry[0][0] for thisentry in entries]:
                        self.showCriticalMessage(_("The '%s' plugin does not admit a %s command. Please fix that") % (checktask, thiscommand))
                        return False

        # Check that the last command of the scenario is an 'end'
        try:
            lasttime, lasttask = [(k, v) for k, v in
                                  sorted(scenario_content.items())][-1]
            lasttask, lastcmd = [(k, v) for k, v in lasttask.items()][-1]

            # Is there more than one task?
            if (len(scenario_content[lasttime].keys()) > 1):
                raise Exception()

            if 'end' not in lastcmd[0][0]:
                raise Exception()
        except Exception:
            self.showCriticalMessage(_("The scenario should terminate with a 'end' command"))
            return False

        # Check there is at least one task in the scenario
        # Do not take into account the special case of the "__main__" task
        if len(self.loadedTasks) <= 1:
            self.showCriticalMessage(_("No task is started!"))
            return False

        return True

    def getCommand(self, lineNumber, lineContent):
        """Parse lineContent to time, task and command variables.
            There are 3 possible syntax:
            0:00:00;end => call onEnd in main script
            0:00:00;track;start => call onStart in the track plugins
            0:00:00;track;variable;value=> modify the parameters in the track plugins
            Any of these may include a priority value with the time:
            0:00:00-0;end => call onEnd in main script
            0:00:00-0;track;start => call onStart in the track plugins
            0:00:00-0;track;variable;value=> modify the parameters in the track plugins
         """

        # Retrieve line content, removing white space and using semi-colon as delimiter
        lineList = lineContent.strip().split(';')

        # Check if the length of lineList is correct
        if not 1 < len(lineList) < 5:
            self.showCriticalMessage(_("Error. Number of value is incorrect. See line")+" " + str(lineNumber) + ' (' + str(lineContent) + ')')
            return None, None, None

        # Manage the special case of main (0:00:00;start)
        elif len(lineList) == 2 or lineList[1] in self.parameters.keys():
            lineList.insert(1, "__main__")
        time, task, command = lineList[0], lineList[1], lineList[2:]

        # manage deprecated command:
        if task=="sysmon" and command[0]=="feedbackduration":
            command[0] = "feedbacks-positive-duration"

        if task == "__main__":
            taskclass = self
        elif task in self.PLUGINS_TASK:
            taskclass = self.getPluginClass(task)
        else:
            self.showCriticalMessage(
                _("'%s' plugin: unknown\n\nLINE: %s") % (task, str(lineNumber)))
            return None, None, None

        if len(time)!=7:
            # Check if there is a priority number.
            splitTime = time.split('-')
            if len(splitTime) == 2 and len(splitTime[0]) == 7 and splitTime[1].isnumeric():
                time = splitTime[0]
                priority = int(splitTime[1])
            else:
                self.showCriticalMessage(
                    _("'%s' plugin: wrong time format\n\nLINE: %s") % (task, str(lineNumber)))
        else:
            priority = 0

        # When only one command, concatenate it with the 'on' chain (e.g. start leads to onStart)
        # onCommand functions are called into the plugins
        if len(command) == 1:
            functionname = "on" + command[0].capitalize()

            # If the onCommand does not exist...
            if not hasattr(taskclass, functionname) and functionname not in ["onStart", "onStop", "onHide", "onPause", "onShow", "onResume"]:

                # signal it.
                errorcaller = ""
                if task != "__main__":
                    errorcaller = "' in '" + task

                self.showCriticalMessage(
                    _("'%s' not found!\n\nLINE: %s") % (functionname + errorcaller, str(lineNumber)))
                return None, None, None
            else:
                return time, task, command, priority

        # For the other variables, check that there are corrects (available in the plugin)
        else:
            if not hasattr(taskclass, PARAMETERS_VARIABLE):
                self.showCriticalMessage(
                    _("'%s' should have a parameters dictionary!\n\nLINE: %s") % (task, str(lineNumber)))
                return None, None, None

            if not self.testParameterVariable(task, taskclass, command[0]):
                self.showCriticalMessage(
                    _("Variable '%s' unknown in task '%s'\n\nLINE: %s") % (str(command [0]), task, str(lineNumber)))
                return None, None, None

        return time, task, command, priority


    def testParameterVariable(self, task, taskclass, adress):
        """Check that a given variable is present in the parameters dictionary of the plugin"""

        current = getattr(taskclass, PARAMETERS_VARIABLE)

        if not current:
            return False

        adress = adress.split('-')

        for i in range(0, len(adress)):
            k = str(adress[i])
            if isinstance(current, dict):
                if k in current:
                    current = current.get(k, None)  # getattr(current, k)

                else:
                    self.showCriticalMessage(
                        _("Variable '%s' unknown in task '%s'") % (k, task))
                    return False
            else:
                # Requires a dictionary...
                self.showCriticalMessage(
                    _("Plugin '%s' has a malformed '%s' variable") % (task, PARAMETERS_VARIABLE))
                return False

        return True

    def setParameterVariable(self, task, taskclass, variable, value):
        """Set a variable to its value, after having convert it to the correct type"""
        current = getattr(taskclass, PARAMETERS_VARIABLE)

        if not current:
            return False

        command = variable.split("-")

        for e in range(0, len(command) - 1):  # range(0,0) = []
            current = current.get(command[e], None)

        t = type(current[command[-1]])

        # Must test booleen first because booleen are also int (e.g., True == 1 is True)
        if isinstance(current[command[-1]], bool):
            if value.lower() == 'true':
                current[command[-1]] = True
            elif value.lower() == 'false':
                current[command[-1]] = False
        elif isinstance(current[command[-1]], int):
            current[command[-1]] = int(value)
        elif isinstance(current[command[-1]], float):
            current[command[-1]] = float(value)
        elif isinstance(current[command[-1]], str) or current[command[-1]] is None:
            current[command[-1]] = value
        else:
            try:
                current[command[-1]] = ast.literal_eval(value)
            except Exception:
                self.showCriticalMessage(
                    _("Unable to evaluate a value! This should not happen!"))

        # Retrieve changing value that are handled by MATB.py (e.g., title, taskupdatetime)
        if variable == 'title':
            self.PLUGINS_TASK[task]['ui_label'].setText(value)
        elif variable == 'taskupdatetime' and isinstance(current[command[-1]], int):
            self.PLUGINS_TASK[task]['UPDATE_TIME'] = int(value)

    @twisted.internet.defer.inlineCallbacks
    def executeScenario(self, time):
        """Interpret and execute commands for the current time value"""

        # Check if the current time has entry in the scenario
        if time in self.scenariocontents:

            # Gather the priorities used at this time.
            priorities = []
            for task in self.scenariocontents[time]:
                for _, priority in self.scenariocontents[time][task]:
                    if priority not in priorities:
                        priorities.append(priority)
            priorities.sort(reverse=True)

            # Go from highest priority to lowest.
            for cur_priority in priorities:

                # If so, browse all the task that are involved (or the main script)
                for task in self.scenariocontents[time]:

                    # Store an instance of the Task class of the plugin
                    taskclass = self.getPluginClass(task)

                    # For each command that is found
                    for command, priority in self.scenariocontents[time][task]:

                        # Skip commands not at the current priority for now.
                        if priority != cur_priority:
                            continue

                        # If action command, determine which and execute according actions
                        if len(command) == 1:
                            functionname = "on" + command[0].capitalize()

                            msg = ''
                            if functionname == "onStart": # = onResume + onShow
                                self.PLUGINS_TASK[task]['taskRunning'] = True
                                self.PLUGINS_TASK[task]['taskVisible'] = True
                                self.PLUGINS_TASK[task]['taskPaused'] = False
                                taskclass.show()
                                msg = 'START'
                            elif functionname == "onStop": # = onPause + onHide
                                self.PLUGINS_TASK[task]['taskRunning'] = False
                                self.PLUGINS_TASK[task]['taskPaused'] = True
                                self.PLUGINS_TASK[task]['taskVisible'] = False
                                taskclass.hide()
                                msg = 'STOP'
                            elif functionname == "onShow":
                                self.PLUGINS_TASK[task]['taskVisible'] = True
                                taskclass.show()
                                msg = 'SHOW'
                            elif functionname == "onHide":
                                self.PLUGINS_TASK[task]['taskVisible'] = False
                                taskclass.hide()
                                msg = 'HIDE'
                            elif functionname == "onPause":
                                if not self.PLUGINS_TASK[task]['taskPaused']:
                                    self.PLUGINS_TASK[task]['taskPaused'] = True
                                    msg = 'PAUSE'
                            elif functionname == "onResume":
                                if self.PLUGINS_TASK[task]['taskPaused']:
                                    self.PLUGINS_TASK[task]['taskPaused'] = False
                                    msg = 'RESUME'

                            # Call the onXXX command from the task
                            if hasattr(taskclass, functionname):
                                getattr(taskclass, functionname)()

                            if len(msg):
                                self.mainLog.addLine(['MAIN', 'STATE', task.upper(), msg])

                            yield self.waitEndofPause()

                            if self.parameters['showlabels']:
                                self.updateLabels()

                        else:
                            # If longer command, set as a parameter variable (see setParameterVariable above)
                            self.setParameterVariable(task, taskclass, command[0], command[1])
                            self.mainLog.addLine(['MAIN', 'SCENARIO', task.upper(), command[0].upper(), command[1]])

    @twisted.internet.defer.inlineCallbacks
    def waitEndofPause(self):

        # if the task asked for a pause. Wait for the end of the pause
        # this is necessary to prevent racing conditions between tasks
        # started at the same time event
        while self.experiment_pause:

            # Do the network communications so that plugins that run during
            # pause can still communicate between client and server.
            sync_data = yield self.doNetworkCommunications()
            for plugin_name in self.PLUGINS_TASK:
                if plugin_name in self.loadedTasks and "NETWORK_WHILE_PAUSED" \
                        in self.PLUGINS_TASK[plugin_name]["class"].parameters \
                        and self.PLUGINS_TASK[plugin_name]["class"].parameters[
                                                        "NETWORK_WHILE_PAUSED"]:
                    if self.is_client and plugin_name in sync_data and \
                            hasattr(self.PLUGINS_TASK[plugin_name]["class"],
                                                               "applySyncData"):
                        if self.PLUGINS_TASK[plugin_name]["class"].is_client():
                            self.PLUGINS_TASK[plugin_name]["class"].applySyncData(sync_data[plugin_name])
                        else:
                            self.showCriticalMessage(
                                _("Plugin '%s' has sync data but is not a client!") % plugin_name)
                    elif self.is_client and plugin_name in sync_data:
                        self.showCriticalMessage(
                            _("Plugin '%s' has sync data but no applySyncData() function!") % plugin_name)

            # Process QT events.
            QtCore.QCoreApplication.processEvents()

            yield twisted_sleep(0.001)

        self.last_time_microsec = self.default_timer()

    @twisted.internet.defer.inlineCallbacks
    def doNetworkCommunications(self):

        # Send new inputs to server if this is a client.
        if self.is_client:
            new_input = {}
            for plugin_name, plugin in self.PLUGINS_TASK.items():
                plugin_class = plugin['class']
                pop_new_inputs = getattr(plugin_class, "popNewInputs", None)
                if callable(pop_new_inputs) and plugin_class.is_client():
                    new_input[plugin_name] = pop_new_inputs()
            yield self.server_communicator.callRemote(Networking.message_types.SERVER_PASS_NEW_INPUT, new_input)

        # Get task sync data from the server if this is a client.
        if self.is_client:
            sync_data = yield self.server_communicator.callRemote(Networking.message_types.SERVER_GET_SYNC_DATA)
        else:
            sync_data = None

        # Check for a termination signal.
        if sync_data is not None and "terminate" in sync_data:
            self.onEnd()

        return sync_data

    @twisted.internet.defer.inlineCallbacks
    def scenarioUpdateTime(self):
        """Increment time (h,m,s) and get the corresponding string chain (H:MM:SS)"""
        m, s = divmod(self.get_time() / 1000.0, 60)
        h, m = divmod(m, 60)

        if h > 9:
            self.showCriticalMessage(_("Timing overflow. This should not happen!"))

        s = "%d:%02d:%02d" % (h, m, s)

        # If scenarioTimeStr need to be updated (1 second passed), update it
        # and try to execute scenario contents again (see the executeScenario fucntion above)
        if s != self.scenarioTimeStr:
            self.scenarioTimeStr = s
            yield self.executeScenario(self.scenarioTimeStr)

    @twisted.internet.defer.inlineCallbacks
    def scheduler(self):
        """Manage the passage of time. Block time during pauses"""
        current_time_microsec = self.default_timer()
        elapsed_time_ms = (current_time_microsec - self.last_time_microsec) * 1000.0

        if elapsed_time_ms < MAIN_SCHEDULER_INTERVAL:
            return

        self.last_time_microsec = current_time_microsec

        # Do a network update.
        sync_data = yield self.doNetworkCommunications()
        
        # If this is a server, the experiment is not running and the termination
        # signal has been sent to the client, terminate the experiment.
        if self.is_server and ((not self.experiment_running and
                (self.termination_message_sent or
                self.ended_time - time.time() > 10.0)) or \
                time.time() - self.last_client_sync > self.connection_timeout):
            yield twisted_sleep(0.1)
            if time.time() - self.last_client_sync > self.connection_timeout:
                print("Exiting: connection to client lost.")
            self.end()

        # The main experiment is in pause, so do not increment time
        if self.experiment_pause or not self.experiment_running:
            return

        # Time increment in case the experiment is running
        if not self.is_client:
            cur_time = self.get_time()
            self.set_time(cur_time + elapsed_time_ms)
        else:
            old_time = self.get_time()
            new_time = yield self.server_communicator.callRemote(Networking.message_types.SERVER_GET_TIME)
            self.set_time(new_time)
            elapsed_time_ms = self.get_time() - old_time

        # If experiment is effectively running, browse plugins and refresh them (execute their onUpdate() method) as a function of their own UPDATE_TIME
        for plugin_name in self.PLUGINS_TASK:
            if plugin_name in self.loadedTasks:
                if self.PLUGINS_TASK[plugin_name]["UPDATE_TIME"] is not None and not self.PLUGINS_TASK[plugin_name]['taskPaused']:
                    self.PLUGINS_TASK[plugin_name]["TIME_SINCE_UPDATE"] += elapsed_time_ms

                    # The plugin is ready to be updated
                    if self.PLUGINS_TASK[plugin_name]["TIME_SINCE_UPDATE"] >= self.PLUGINS_TASK[plugin_name]["UPDATE_TIME"]:

                        # Update the plugin.
                        if hasattr(self.PLUGINS_TASK[plugin_name]["class"], "onUpdate"):
                            self.PLUGINS_TASK[plugin_name]["class"].onUpdate()
                        else:
                            self.showCriticalMessage(_("Plugin '%s' requires an onUpdate() function!") % plugin_name)

                        # Apply sync data if this is a client.
                        if self.is_client and plugin_name in sync_data and hasattr(self.PLUGINS_TASK[plugin_name]["class"], "applySyncData"):
                            if self.PLUGINS_TASK[plugin_name]["class"].is_client():
                                self.PLUGINS_TASK[plugin_name]["class"].applySyncData(sync_data[plugin_name])
                            else:
                                self.showCriticalMessage(_("Plugin '%s' has sync data but is not a client!") % plugin_name)
                        elif self.is_client and plugin_name in sync_data:
                            self.showCriticalMessage(_("Plugin '%s' has sync data but no applySyncData() function!") % plugin_name)

                        # Reset the timer for the next update.
                        self.PLUGINS_TASK[plugin_name]["TIME_SINCE_UPDATE"] = 0

                    # The plugin is not ready to be updated, pass the on the data but flag that this isn't a full update.
                    elif self.is_client and plugin_name in sync_data and hasattr(self.PLUGINS_TASK[plugin_name]["class"], "applySyncData"):
                        if self.PLUGINS_TASK[plugin_name]["class"].is_client():
                            self.PLUGINS_TASK[plugin_name]["class"].applySyncData(sync_data[plugin_name], full_update=False)
                        else:
                            self.showCriticalMessage(_("Plugin '%s' has sync data but is not a client!") % plugin_name)


        # Potentially logs an arbitrary message in 'messagetolog'
        if len(self.parameters['messagetolog']) > 0:
            msg = ["MAIN", "LOG", self.parameters['messagetolog']]
            self.mainLog.addLine(msg)
            self.parameters['messagetolog'] = ''

        yield self.scenarioUpdateTime()

    def eventFilter(self, source, event):
        """Filter key inputs, and launch task keyEvent methods if not paused"""
        if (event.type() == QtCore.QEvent.KeyPress):
            key = event.key()
            self.mainLog.addLine(["MAIN", "INPUT", "KEY_PRESS", str(key)])

        if (event.type() == QtCore.QEvent.KeyRelease):
            key = event.key()

            # End experiment if key=ESC
            if key == QtCore.Qt.Key_Escape:
                self.mainLog.addLine(["MAIN", "INPUT", "KEY_RELEASE", "ESC"])
                if self.parameters['allowescape']:
                    self.onEnd()
                return True

            self.mainLog.addLine(["MAIN", "INPUT", "KEY_RELEASE", str(key)])

            for task in self.PLUGINS_TASK:
                if self.PLUGINS_TASK[task]["RECEIVE_KEY"] and \
                        not self.PLUGINS_TASK[task]['taskPaused'] and \
                        self.PLUGINS_TASK[task]['taskRunning']:
                    self.getPluginClass(task).keyEvent(key)

            return True
        else:
            return QtWidgets.QMainWindow.eventFilter(self, source, event)

    def sendLogToPlugins(self, stringLine):
        if hasattr(self, 'loadedTasks'):
            for plugin_name in self.PLUGINS_TASK:
                if plugin_name in self.loadedTasks:
                    if self.PLUGINS_TASK[plugin_name]["NEED_LOG"] == True:
                        self.PLUGINS_TASK[plugin_name]["class"].onLog(stringLine)

    def closeEvent(self, e):
        """Defines what happens when close button or ALT-F4 is hit"""
        if self.parameters['allowaltf4']:
            self.hide()
            self.onEnd()
            e.accept()
        else:
            e.ignore()

    def onEnd(self):
        """Defines what happens for the experiment to end"""

        self.experiment_running = False

        # If this is a server, wait for the end message to be sent to the
        # client before closing the experiment.
        if not self.is_server:
            self.end()
        else:
            self.ended_time = time.time()

    def end(self):

        # Start the onEnd() method of each loaded plugin
        for plugin in self.PLUGINS_TASK:
            if plugin != '__main__':
                classplugin = self.getPluginClass(plugin)

                if hasattr(self.getPluginClass(plugin), "onEnd"):
                    self.getPluginClass(plugin).onEnd()

        self.mainLog.addLine(["MAIN", "STATE", "", "END"])
        self.close()
        if self.is_server:
            twisted.internet.reactor.stop()
        else:
            sys.exit()

    def onPause(self, hide_ui=True):
        """Defines what happens when the experiment is paused, for instance when a generic scale is presented"""
        self.mainLog.addLine(["MAIN", "STATE", "", "PAUSE"])
        self.experiment_pause = True

        # The timer is paused
        for timer in self.registeredTaskTimer:
            timer.pause()

        # The onPause() method of each plugin is started, if present
        for plugin in self.PLUGINS_TASK:
            if plugin != '__main__':
                classplugin = self.getPluginClass(plugin)

                self.PLUGINS_TASK[plugin]['taskPreviouslyPaused'] = \
                    self.PLUGINS_TASK[plugin]['taskPaused']
                if not self.PLUGINS_TASK[plugin]['taskPaused']:
                    self.PLUGINS_TASK[plugin]['taskPaused'] = True

                    if hasattr(self.getPluginClass(plugin), "onPause"):
                        self.getPluginClass(plugin).onPause()

                # Running plugins must be hidden
                if hide_ui:
                    if 'ui_label' in self.PLUGINS_TASK[plugin]:
                        self.PLUGINS_TASK[plugin]['ui_label'].hide()
                classplugin.hide()

    def onResume(self):
        """Defines what happens when resuming from a pause"""
        self.mainLog.addLine(["MAIN", "STATE", "", "RESUME"])
        self.experiment_pause = False

        # The timer is resumed
        for timer in self.registeredTaskTimer:
            timer.resume()

        # And the onResume() method of each plugin is started, if present
        for plugin in self.PLUGINS_TASK:
            if plugin != '__main__':
                classplugin = self.getPluginClass(plugin)

                # Finally, the plugin is displayed back if running
                if self.PLUGINS_TASK[plugin]['taskRunning'] and \
                        not self.PLUGINS_TASK[plugin]['taskPreviouslyPaused']:
                    self.PLUGINS_TASK[plugin]['taskPaused'] = False
                    if hasattr(self.getPluginClass(plugin), "onResume"):
                        self.getPluginClass(plugin).onResume()
                    if 'ui_label' in self.PLUGINS_TASK[plugin]:
                        self.PLUGINS_TASK[plugin]['ui_label'].show()
                    classplugin.show()


def loadConfig():
    config_filename = 'config.txt'

    if os.path.exists(config_filename):
        with open(config_filename, 'r') as lines:
            for line in lines:
                split = line.split('=')
                if len(split) == 2:
                    CONFIG[split[0]] = (split[1])
    Translator._lang = CONFIG.get('language')


def getConfigValue(key, defaultvalue):
    value = CONFIG.get(key)
    if value is not None:
        return value
    else:
        return defaultvalue


if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    
    loadConfig()

    # Read in any arguments
    path_from_args = None
    is_client = False
    is_server = False
    host = "localhost"
    port = 31415
    for arg in range(1, len(sys.argv)):
        if sys.argv[arg][0] != '-':
            path_from_args = sys.argv[arg]
            print("Scenario:", path_from_args)
        elif sys.argv[arg] == "--client" or sys.argv[arg] == "-c":
            print("Running as client...")
            is_client = True
        elif sys.argv[arg] == "--server" or sys.argv[arg] == "-s":
            print("Running as server...")
            is_server = True
        elif sys.argv[arg].startswith("--host=") or sys.argv[arg].startswith("-h="):
            host = sys.argv[arg].split('=')[1]
            print("Targeting host", host)
        elif sys.argv[arg].startswith("--port=") or sys.argv[arg].startswith("-p="):
            port = int(sys.argv[arg].split('=')[1])
            print("Using port", port)

    # Get the path.
    if path_from_args is not None:
        scenario_FullPath = os.path.join(SCENARIOS_PATH, path_from_args)
    elif not is_client:
        scenario_FullPath, none = QtWidgets.QFileDialog.getOpenFileName(
            None, VERSIONTITLE + ' - ' + _('Select a scenario'), SCENARIOS_PATH, "(*.txt)")
    else:
        scenario_FullPath = None

    if is_client or os.path.exists(scenario_FullPath):
        pygame.init()
        window = Main(scenario_FullPath, is_client, is_server, host, port)
        if is_client:
            window.setWindowTitle(VERSIONTITLE + " client")
        elif is_server:
            window.setWindowTitle(VERSIONTITLE + " server")
        else:
            window.setWindowTitle(VERSIONTITLE)

        window.showFullScreen()
        app.installEventFilter(window)
        window.runExperiment()

    else:
        # Cannot use OSCriticalErrorMessage as language isn't set yet.
        ctypes.windll.user32.MessageBoxW(None, "Scenario not found: " +
            scenario_FullPath, VERSIONTITLE + " - Error", 0)
        sys.exit()

    sys.exit(app.exec_())
