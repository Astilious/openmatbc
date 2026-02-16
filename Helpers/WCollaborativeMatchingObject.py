# Python imports.
import os.path

# External Imports.
from PySide2 import QtCore, QtWidgets, QtGui

class WCollaborativeMatchingObject(QtWidgets.QGraphicsPixmapItem):
    """A scene object for collaborative matching.

    An object that existing in a collaborative matching scene.

    Attributes:
        image_path (str): The path to the image used for this object
        type_id (int): The type of the object.
        size_x (int): The size of the object in the x direction.
        size_y (int): The size of the object in the y direction.
    """

    image_pixmaps = {}
    """dict: A dictionary of image pixmaps keyed by image path."""

    def __init__(self, image_name: str, x: float, y: float, type_id: int,
                 size_x: int, size_y: int):
        """Create a collaborative matching object with the image at image_path.

        Args:
            image_name (str): The path to the image to use.
            x (float): The x coordinate of the object's position in the scene.
            y (float): The y coordinate of the object's position in the scene.
            type_id (int): The type of the object.
            size_x (int): The size of the object in the x direction.
            size_y (int): The size of the object in the y direction.
        """

        # Record the image path.
        self.image_path = os.path.join("Images", image_name)

        # Check if the image has already been loaded.
        if self.image_path not in WCollaborativeMatchingObject.image_pixmaps:

            # Load the image.
            pixmap = QtGui.QPixmap(self.image_path)
            pixmap = pixmap.scaled(QtCore.QSize(size_x, size_y))

            # Check the image loaded successfully.
            if pixmap.isNull():
                raise ValueError("Image at {} could not be loaded.".format(
                    self.image_path))

            # Store the pixmap.
            WCollaborativeMatchingObject.image_pixmaps[self.image_path] = pixmap

        # If the image has already been loaded, use the stored pixmap.
        else:
            pixmap = WCollaborativeMatchingObject.image_pixmaps[self.image_path]

        # Call the parent's init.
        super(WCollaborativeMatchingObject, self).__init__(pixmap)

        # Set the position.
        self.setPos(x, y)

        # Set the type id.
        self.type_id = type_id

        # Record the size.
        self.size_x = size_x
        self.size_y = size_y