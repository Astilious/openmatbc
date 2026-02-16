from PySide2 import QtWidgets

class Task(QtWidgets.QWidget):

    def __init__(self, parent):
        super(Task, self).__init__(parent)

        self.parameters = {
        'taskupdatetime' : 1000,
        'flag' : 'none'
        }

    def onStart(self):
        pass

    def onUpdate(self):
        pass

    def onStop(self):
        pass
