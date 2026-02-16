# Python imports.
import os

# External Imports.
from PySide2 import QtCore, QtWidgets, QtGui
import numpy as np

class WCollaborativeMatchingView(QtWidgets.QGraphicsView):
    """A widget that displays the Collaborative Matching task scene and overlay.

    Attributes:
        task_width (int): The width of the task display area.
        task_height (int): The height of the task display area.
        pen_size (float): The size of the pen to use for drawing.
        half_pen_size (int): Half the size of the pen to use for drawing.
        tick_length (int): The length of the ticks to draw.
        selection_box_size (int): The size of the selection box.
        selection_image_size (int): The size of the image in the selection box.
        plain_pen (QPen): A pen to use for drawing.
        selection_image_pixmaps (dict): A dictionary of selection image pixmaps
            keyed by image path.
        no_selection_name (str): The name of the image to use for when there is
            no selection.
        selection_pixmap (QPixmap): The pixmap to use in the selection box.
    """

    def __init__(self, parent: QtWidgets.QWidget, task_width: int,
                 task_height: int, scale_multiplier: float = 1.0):
        """Initialises a Collaborative Matching task display.

        Args:
            parent (QWidget): The parent widget.
            task_width (int): The width of the task display area.
            task_height (int): The height of the task display area.
            scale_multiplier (float): The scale multiplier to apply to the task
                display, resizing content.
        """

        # Call the parent's init.
        super(WCollaborativeMatchingView, self).__init__(parent)

        # Record the task width and height.
        self.task_width = task_width
        self.task_height = task_height

        # Define various sizes (lines, ticks, selection box, progress bar)
        self.pen_size = int(self.task_height / 150.)
        self.half_pen_size = int(np.ceil(self.pen_size / 2))
        self.tick_length = int(0.1 * self.task_height)
        self.selection_box_size = 100
        self.selection_image_size = self.selection_box_size - 2*self.pen_size
        self.progress_bar_width = self.task_width-2*self.pen_size
        self.progress_bar_height = int(0.02 * self.task_height)

        # Scale the sizes.
        self.pen_size = max(int(self.pen_size * scale_multiplier), 1)
        self.half_pen_size = max(int(self.half_pen_size * scale_multiplier), 1)
        self.tick_length = int(self.tick_length * scale_multiplier)
        self.selection_box_size = int(self.selection_box_size *
                                      scale_multiplier)
        self.selection_image_size = int(self.selection_image_size *
                                        scale_multiplier)

        # The percentage of the progress bar to fill.
        self.progress_bar_portion = 0.6

        # Create pens.
        self.plain_pen = QtGui.QPen(QtGui.QColor('#0000FF'), self.pen_size,
                                    QtCore.Qt.SolidLine)
        self.success_pen = QtGui.QPen(QtGui.QColor('#00FF00'), self.pen_size,
                                      QtCore.Qt.SolidLine)

        # Create dictionary to avoid reloading images.
        self.selection_image_pixmaps = {}

        # The no selection image name.
        self.no_selection_name = "no_selection.jpg"

        # Initialise the selection image.
        self.selection_pixmap = None
        self.set_selection_image()

        # Initialise the blockout settings.
        self.over_task_blockout = False
        self.over_task_blockout_colour = QtGui.QColor("#FFFFFF")

        # Whether the success marker should be drawn.
        self.success_marker = False


    def set_selection_image(self, image_name: str = None):
        """Set the image to show in the selected object box.

        Set the image to show in the selected object box. If the image name is
        not given or None reset the image to the no selection image.

        Args:
            image_name (str): The name of the image to show.
        """

        # If the image name is none reset the image to the no selection image.
        if image_name is None:
            image_name = self.no_selection_name
            image_path = os.path.join("Images", image_name)
        else:
            image_path = image_name

        # If the image is already loaded use it.
        if image_name in self.selection_image_pixmaps:
            self.selection_pixmap = self.selection_image_pixmaps[image_name]

        # Otherwise load the image.
        else:

            # Load the pixmap.
            self.selection_pixmap = QtGui.QPixmap(image_path)
            self.selection_pixmap = self.selection_pixmap.scaled(
                                    QtCore.QSize(self.selection_image_size,
                                                 self.selection_image_size))

            # Add the pixmap to the dictionary.
            self.selection_image_pixmaps[image_name] = self.selection_pixmap



    def drawForeground(self, qp: QtGui.QPainter, view_rect: QtCore.QRectF):
        """Draw the overlay.

        Overwrite of the QGraphicsView drawForeground function. Overwritten in
        order to draw the collaborative matching overlay on top of the scene
        view.

        Args:
            qp (QPainter): The foreground painter object. Draws in scene
                coordinates.
            view_rect (QRectF): Rectangle giving the area within the scene shown
                by the view area in scene coordinates.
        """

        self.drawOverlay(qp, view_rect)


    def drawOverlay(self, qp: QtGui.QPainter, view_rect: QtCore.QRectF):
        """Draws the overlay.

        Note: Based on the tracking task code.

        Args:
            qp (QtGui.QPainter): The painter object to use.
            view_rect (QtCore.QRectF): Rectangle giving the area within the
                scene shown by the view area in scene coordinates.
        """

        # Define the pen to use.
        if self.success_marker:
            qp.setPen(self.success_pen)
        else:
            qp.setPen(self.plain_pen)
        qp.setRenderHint(QtGui.QPainter.Antialiasing)

        # Offset to draw the overlay in the middle of the view.
        qp.translate(view_rect.x(), view_rect.y())

        # Draw the progress bar.
        progress_colour = QtGui.QColor('#00FF00')
        if self.progress_bar_portion < 2/3:
            progress_colour = QtGui.QColor('#FFFF00')
        if self.progress_bar_portion < 1/3:
            progress_colour = QtGui.QColor('#FF0000')
        qp.fillRect(self.pen_size, self.task_height - self.progress_bar_height -
                    self.pen_size, int(self.progress_bar_width *
                    self.progress_bar_portion),
                    self.progress_bar_height, progress_colour)

        # X axis
        qp.drawLine(0, self.task_height // 2,
                    self.task_width, self.task_height // 2)

        # Y axis
        qp.drawLine(self.task_width // 2, 0,
                    self.task_width // 2, self.task_height)

        # X and Y ticks
        how_many_ticks = 7
        coordinates_prop = np.linspace(0, 1, how_many_ticks+2)
        for t, this_tick in enumerate(coordinates_prop):
            tick_length = self.tick_length if t % 2 == 0 else \
                          self.tick_length / 2

            # X ticks
            qp.drawLine(this_tick * self.task_width, self.task_height //
                        2 - tick_length // 2, this_tick * self.task_width,
                        self.task_height // 2 + tick_length // 2)

            # Y ticks
            qp.drawLine(self.task_width // 2 - tick_length //
                        2, this_tick * self.task_height,
                        self.task_width // 2 + tick_length // 2,
                        this_tick * self.task_height)

        # Frame for the overlay (4 corners)
        qp.drawLine(0, 0, self.tick_length, 0)
        qp.drawLine(0, 0, 0, self.tick_length)
        qp.drawLine(self.task_width, 0, self.task_width - self.tick_length, 0)
        qp.drawLine(self.task_width, 0, self.task_width, self.tick_length)
        qp.drawLine(0, self.task_height, self.tick_length, self.task_height)
        qp.drawLine(0, self.task_height, 0, self.task_height - self.tick_length)
        qp.drawLine(self.task_width, self.task_height,
                    self.task_width, self.task_height - self.tick_length)
        qp.drawLine(self.task_width, self.task_height,
                    self.task_width - self.tick_length, self.task_height)

        # Draw a white background in the selection box.
        qp.fillRect(self.task_width - (self.selection_image_size +
                    4*self.half_pen_size), self.pen_size,
                    self.selection_image_size + 3*self.half_pen_size,
                    self.selection_image_size + 2*self.half_pen_size,
                    QtGui.QColor('#FFFFFF'))

        # Selected object box.
        qp.drawLine(self.task_width - self.half_pen_size, self.half_pen_size,
                    self.task_width - self.selection_box_size,
                    self.half_pen_size)
        qp.drawLine(self.task_width - (self.half_pen_size-1),
                    self.half_pen_size, self.task_width -
                    (self.half_pen_size-1), self.selection_box_size)
        qp.drawLine(self.task_width - self.selection_box_size,
                    self.half_pen_size, self.task_width -
                    self.selection_box_size, self.selection_box_size)
        qp.drawLine(self.task_width - self.half_pen_size,
                    self.selection_box_size, self.task_width -
                    self.selection_box_size, self.selection_box_size)

        # Draw the selection image.
        qp.drawPixmap(self.task_width - (self.selection_image_size +
                      self.pen_size + 1), self.pen_size + 1,
                      self.selection_pixmap)

        # If blockout is set, draw an appropriately coloured box over the task.
        if self.over_task_blockout:
            qp.fillRect(0, 0, self.task_width, self.task_height,
                        self.over_task_blockout_colour)


    def set_progress_bar_portion(self, portion: float):
        """Set the portion of the progress bar to be filled.

        Args:
            portion (float): The portion of the progress bar to be filled.
        """

        self.progress_bar_portion = portion
        self.update()


    def set_over_task_blockout(self, blockout: bool, colour: str = "#FFFFFF"):
        """Set whether the task is inactive and should be blocked out.

        Sets whether the task is inactive and should be blocked out. If the
        task is blocked out, the colour of the blockout can be set.

        Args:
            blockout (bool): Whether the blockout should be applied.
            colour (str): The colour of the blockout.
        """
        self.over_task_blockout = blockout
        self.over_task_blockout_colour = QtGui.QColor(colour)
        self.update()


    def set_success_marker(self, success: bool):
        """Set whether the success marker should be shown.

        Args:
            success (bool): Whether the success marker should be shown.
        """
        self.success_marker = success
        self.update()

