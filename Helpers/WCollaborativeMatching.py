"""Defines the core Collaborative Matching task widget."""

# Python imports,
from typing import List

# External Imports.
from PySide2 import QtCore, QtWidgets, QtGui
import numpy as np

# Local Imports.
from Helpers import WCollaborativeMatchingView, WCollaborativeMatchingObject

class WCollaborativeMatching (QtWidgets.QWidget):
    """A widget that displays a Collaborative Matching task.

    Attributes:

    """

    def __init__(self, parent):
        """Initialises a Collaborative Matching task display.

        Args:
            parent (QWidget): The parent widget.
        """

        # Call the parent's init.
        super(WCollaborativeMatching, self).__init__(parent)

        # Margins around the widget. I can't find a way to get these, so they're
        # hard-coded for now. TODO: fix.
        left_parent_margin, top_parent_margin, right_parent_margin, \
            bottom_parent_margin = 18, 18, 18, 18

        # Multiplier for task width and height to avoid overlapping with
        # adjacent content.
        self.max_width_occupied_space = 0.9
        self.max_height_occupied_space = 1.0

        # The aspect ratio of the task area.
        self.aspect_ratio = 29 / 20

        # Get the parent widget's dimensions.
        parent_width = self.parent().width() - left_parent_margin - \
                       right_parent_margin
        parent_height = self.parent().height() - top_parent_margin - \
                        bottom_parent_margin

        # Define task area (width, height). Enforce the aspect ratio while
        # ensuring both dimensions fit within parent dim * occupied_space and
        # width fits within max_width_occupied_space * parent width.
        self.task_height: int = int(parent_height *
                                    self.max_height_occupied_space)
        self.task_width: int = int(parent_width * self.max_width_occupied_space)
        if self.task_width / self.task_height < self.aspect_ratio:
            self.task_height = int(self.task_width / self.aspect_ratio)
        else:
            self.task_width = int(self.task_height * self.aspect_ratio)

        # Determine the scale multiplier - how far has the size of the window
        # deviated from the 580 pixel baseline assumption.
        self.scale_multiplier = self.task_width / 580

        # The size of the area use to detect an object to select.
        self.select_area_size = 50.0 * self.scale_multiplier

        # Create the scene.
        self.scene = QtWidgets.QGraphicsScene(-1, -1, 1, 1)

        # Create the view widget.
        self.view = WCollaborativeMatchingView.WCollaborativeMatchingView(
                    self.scene, self.task_width, self.task_height,
                    self.scale_multiplier)
        self.view.setFocusPolicy(QtCore.Qt.NoFocus)

        # Make the non content parts of the view widget invisible.
        self.view.setStyleSheet("border: 0px; background: transparent;")
        self.view.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.view.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)

        # Add margins to put the view within the task area.
        margin_x = (parent_width - self.task_width) // 2
        margin_y = (parent_height - self.task_height) // 2
        self.view.setViewportMargins(margin_x, margin_y,
                                     margin_x, margin_y)

        # Create a layout for the widget
        layout = QtWidgets.QGridLayout()

        # Add the graphics view to the layout.
        layout.addWidget(self.view)

        # Set the layout.
        self.setLayout(layout)


    def add_object(self, image_name: str, x: float, y: float, type_id: int,
                  size_x: int, size_y: int):
        """Adds an object to the scene.

        Args:
            image_name (str): The file name of the image for this object.
            x (float): The x coordinate of the object's position in the scene.
            y (float): The y coordinate of the object's position in the scene.
            type_id (int): The type of the object.
            size_x (int): The scale of the object in the x direction.
            size_y (int): The scale of the object in the y direction.
        """

        # Multiply everything by the global scaling multiplier.
        x *= self.scale_multiplier
        y *= self.scale_multiplier
        size_x *= self.scale_multiplier
        size_y *= self.scale_multiplier

        # Create the object.
        new_object = WCollaborativeMatchingObject.WCollaborativeMatchingObject(
            image_name, x, y, type_id, size_x, size_y)

        # Add the object.
        self.scene.addItem(new_object)


    def get_xy(self) -> (float, float):
        """Returns the current position of the centre of the view in the scene.

        Returns:
            (float, float): The x and y coordinates of the centre of the view
                in the scene.
        """
        mapped_point = self.view.mapToScene(
                       self.view.viewport().rect().center())
        return mapped_point.x(), mapped_point.y()


    def move_view(self, x: float, y: float):
        """Moves the view by the given amount.

        Args:
            x (float): The amount to move the viewport in the x direction.
            y (float): The amount to move the viewport in the y direction.
        """
        x = x * self.scale_multiplier
        y = y * self.scale_multiplier
        self.view.centerOn(x, y)


    def set_time_offset(self, timeOffset):
        """Set the time for the purposes of calculating cursor motion.

        The offset is set such that the current time is considered to be 
        timeOffset in future cursor motion calculations.

        Args:
        timeOffset (float): The new time in seconds, to be treated as the 
        current time in future cursor motion calculations.
        """
        current_time_ms = int(self.parent().parent().totalElapsedTime_ms)
        self.timeOffset = current_time_ms - (timeOffset * 1000)


    def clear_scene(self):
        """Clears the scene of all objects."""
        self.scene.clear()


    def set_scene_size(self, x_min, x_max, y_min, y_max):
        """Sets the size of the scene.

        Sets the size of the scene. Adds extra padding to ensure the centre of
        the view can reach any part of the scene.

        Args:
            x_min (float): The minimum x coordinate of the scene.
            x_max (float): The maximum x coordinate of the scene.
            y_min (float): The minimum y coordinate of the scene.
            y_max (float): The maximum y coordinate of the scene.
        """

        # Multiply everything by the global scaling multiplier.
        x_min *= self.scale_multiplier
        x_max *= self.scale_multiplier
        y_min *= self.scale_multiplier
        y_max *= self.scale_multiplier

        # Add padding to the scene.
        x_min_padded = x_min - self.task_width / 2
        x_max_padded = x_max + self.task_width / 2
        y_min_padded = y_min - self.task_height / 2
        y_max_padded = y_max + self.task_height / 2

        # Set the scene size.
        self.scene.setSceneRect(x_min_padded, y_min_padded, x_max_padded -
                                x_min_padded, y_max_padded - y_min_padded)

        # Add the boundary lines.
        self.scene.addLine(x_min, y_min, x_max, y_min)
        self.scene.addLine(x_min, y_max, x_max, y_max)
        self.scene.addLine(x_min, y_min, x_min, y_max)
        self.scene.addLine(x_max, y_min, x_max, y_max)


    def get_current_target(self) -> \
            WCollaborativeMatchingObject.WCollaborativeMatchingObject:
        """Returns the current target object.

        Returns:
            WCollaborativeMatchingObject: The object currently at the centre of
                the view.
        """

        # Get the centre of the view in scene coordinates.
        mapped_point = self.get_xy()

        # Get all items near the centre of the view.
        area = self.select_area_size
        half_area = area / 2
        items: List[QtWidgets.QGraphicsItem] = self.scene.items(QtCore.QRectF(
            mapped_point[0]-half_area, mapped_point[1]-half_area, area, area))

        # Get the closest item to the centre of the view.
        if len(items) == 0:
            item = None
        else:
            closest_distance = np.inf
            item = None
            for cur_item in items:
                if type(cur_item) == QtWidgets.QGraphicsLineItem:
                    continue
                pos = cur_item.scenePos()
                pos = (pos.x() + cur_item.size_x/2, pos.y()+cur_item.size_y/2)
                distance = np.linalg.norm(np.array(pos) -
                               np.array([mapped_point[0], mapped_point[1]]))
                if distance < closest_distance:
                    closest_distance = distance
                    item = cur_item

        # Return the item found.
        return item


    def set_selection_image(self, image_name: str = None):
        """Sets the image to be used in the selection box.

        Args:
            image_name (str): The file name of the image to use in the selection
                box.
        """
        self.view.set_selection_image(image_name)


    def set_progress_bar_portion(self, portion: float):
        """Set the portion of the progress bar to be filled.

        Args:
            portion (float): The portion of the progress bar to be filled.
        """
        self.view.set_progress_bar_portion(portion)


    def set_over_task_blockout(self, blockout: bool, colour: str = "#FFFFFF"):
        """Set whether the task is inactive and should be blocked out.

        Sets whether the task is inactive and should be blocked out. If the
        task is blocked out, the colour of the blockout can be set.

        Args:
            blockout (bool): Whether the blockout should be applied.
            colour (str): The colour of the blockout.
        """
        self.view.set_over_task_blockout(blockout, colour)


    def set_success_marker(self, success: bool):
        """Set whether the success marker should be shown.

        Args:
            success (bool): Whether the success marker should be shown.
        """
        self.view.set_success_marker(success)
