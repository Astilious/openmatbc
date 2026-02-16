from PySide2 import QtWidgets
from Helpers.Translator import translate as _

class Task(QtWidgets.QWidget):


    def __init__(self, parent):
        super(Task, self).__init__(parent)

        # SCORE PARAMETERS ###
        self.parameters = {
            'title': 'Scoreboard',
            'taskplacement': "topright",
            'taskupdatetime': 1000
        }

        # Potentially translate task title
        self.parameters['title'] = _(self.parameters['title'])


    def onStart(self):

        # Set a Qt layout
        layout = QtWidgets.QGridLayout()

        # Create a label for the scores.
        self.widget = QtWidgets.QLabel(self)
        layout.addWidget(self.widget)
        self.setLayout(layout)

        # Set the scores label font.
        font = self.widget.font()
        font.setPointSize(14)
        self.widget.setFont(font)

        # Set the initial text for the scores label.
        self.widget.setText(self.getScoresText())


    def onUpdate(self):
        """Updates the scores text and visual display."""

        # Update the label with the current scores.
        self.widget.setText(self.getScoresText())

        # And refresh visual display
        self.update()


    def getScoresText(self) -> str:
        """Gets text that shows the scores of all tasks that have one.

        Returns:
            str: A string with the scores of all tasks that have one.
        """

        # Get the scores of all tasks that have one.
        scores = self.getScores()

        # Initialise the scores text.
        scores_text = ""

        # Add the scores of all tasks that have one to the scores text.
        for task_name, score in scores.items():
            scores_text += f"{task_name}:\n {score}\n\n"

        return scores_text


    def getScores(self) -> dict:
        """Get the scores of any task that has one.

        Returns:
            dict: A dictionary of scores, with the task name as key and the
                score as value.
        """

        # Initialise the scores.
        scores = {}

        # Get scores for all tasks with a getScore function.
        for task_name, task_data in self.parent().PLUGINS_TASK.items():
            if hasattr(task_data["class"], "getScore"):
                task_nice_name = task_data["class"].parameters["title"]
                scores[task_nice_name] = task_data["class"].getScore()

        # Return the collected scores.
        return scores
