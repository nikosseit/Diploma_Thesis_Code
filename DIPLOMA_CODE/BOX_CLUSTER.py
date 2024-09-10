import tkinter as tk
from tkinter import Toplevel, Frame
import random

class OverlayBox(Toplevel):
    def __init__(self, master, center_coordinates, box_size, frame_thickness=3, **kwargs):
        super().__init__(master, **kwargs)
        self.center_coordinates = center_coordinates
        self.box_size = box_size
        self.frame_thickness = frame_thickness

        self.configure(bg='black')  # Set the background to black for the frame effect
        self.overrideredirect(True)
        self.wm_attributes("-topmost", True)
        self.attributes("-alpha", 0.7)

        # Create the inner frame with a specific background color
        self.inner_frame = Frame(self, bg='red', width=self.box_size[0]-2*self.frame_thickness, height=self.box_size[1]-2*self.frame_thickness)
        self.inner_frame.pack(padx=self.frame_thickness, pady=self.frame_thickness)

        self.update_position(center_coordinates)

    def update_position(self, center_coordinates):
        self.center_coordinates = center_coordinates
        cx, cy = center_coordinates
        x = cx - self.box_size[0] // 2
        y = cy - self.box_size[1] // 2

        self.geometry(f"{self.box_size[0]}x{self.box_size[1]}+{x}+{y}")

    def show(self):
        self.deiconify()

    def hide(self):
        self.withdraw()

def main():
    root = tk.Tk()
    root.withdraw()

    # Example data: List of points
    # points = [(random.randint(0, 1000), random.randint(0, 1900)) for _ in range(100)]
    points = [(740,400)]

    # Calculate the average center coordinates
    if points:
        x_coords, y_coords = zip(*points)
        center_x = sum(x_coords) // len(x_coords)
        center_y = sum(y_coords) // len(y_coords)
        center_coordinates = (center_x, center_y)

    # Set a custom box size
    custom_box_size = (110, 45)  # You can modify this size as needed

    # Create and display the overlay box
    overlay = OverlayBox(root, center_coordinates, custom_box_size)
    overlay.show()

    root.mainloop()

if __name__ == "__main__":
    main()
