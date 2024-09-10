import psycopg2
import pygetwindow as gw
import time
import tobii_research as tr
from screeninfo import get_monitors
import json
import sys
import tkinter as tk
import uuid
import threading
from Fixed_Size_Queue import FixedSizeQueue
from BOX_CLUSTER import OverlayBox


with open('config.json', 'r') as config_file:
    config = json.load(config_file)

session_id = str(uuid.uuid4())
THRESHOLD = 40
previous_tab_id = None
overlay_widget = None
window_title_to_id = {}
connection = psycopg2.connect(dbname=config['dbname'], user=config['user'], password=config['password'], host=config['host'], port=config['port'])
cursor = connection.cursor()
gaze_data_queue_dict = {}
handle_tab_change_lock = threading.Lock()
insert_from_queue_lock = threading.Lock()
insert_most_common_point_lock = threading.Lock()
draw_box_lock = threading.Lock()
last_insert_time = time.time()


# def preprocessing(input_list):
#     filtered_list = [num for num in input_list if num[0] >= 0 and num[1] >= 0]
#     return filtered_list

def preprocessing(input_list):
    """Filter out points within the specified screen regions."""
    filtered_list = [num for num in input_list if not ((0 <= num[0] <= 1920 and 0 <= num[1] <= 55) or (0 <= num[0] <= 1920 and 1040 <= num[1] <= 2000))]
    return filtered_list

def get_screen_size():
    """Returns the screen resolution size (width, height)."""
    monitors = get_monitors()
    if monitors:
        return (monitors[0].width, monitors[0].height)

RESOLUTION = get_screen_size()

def get_current_tab_id():
    active_window = gw.getActiveWindow()
    if active_window:
        window_title = active_window.title
        if window_title not in window_title_to_id:
            window_title_to_id[window_title] = round(time.time() * 1000)
        return window_title_to_id[window_title]


def is_relevant_window(window_title):
    keywords = ["wordpad", "word", "pdf"]
    # Convert window_title to lower case and check if any keyword is in the title
    return any(keyword in window_title.lower() for keyword in keywords)


def delete_previous_tabs_data():
    cursor.execute("""DELETE FROM public."Previous_Tabs" """)
    connection.commit()


def gaze_data_callback(gaze_data):
    global session_id, last_insert_time
    try:
        current_tab_id = get_current_tab_id()
        active_window = gw.getActiveWindow()
        if active_window is None:
            return
        #if current_tab_id and gaze_data:
        active_window_title = gw.getActiveWindow().title if gw.getActiveWindow() else None
        username = "NIKOS"
        if gaze_data['left_gaze_point_validity'] and gaze_data['right_gaze_point_validity']:
            gaze_x = (gaze_data['left_gaze_point_on_display_area'][0] + gaze_data['right_gaze_point_on_display_area'][0]) / 2
            gaze_y = (gaze_data['left_gaze_point_on_display_area'][1] + gaze_data['right_gaze_point_on_display_area'][1]) / 2
            gaze_x = int(gaze_x * RESOLUTION[0])
            gaze_y = int(gaze_y * RESOLUTION[1])
            #print(gaze_x , gaze_y)
            # if current_time - last_insert_time >=1 :
            if current_tab_id not in gaze_data_queue_dict:
                gaze_data_queue_dict[current_tab_id] = FixedSizeQueue(1800)
            gaze_data_queue_dict[current_tab_id].enqueue((active_window_title, current_tab_id, session_id, gaze_x, gaze_y, username))
        #print(f"{current_tab_id}: ({active_window_title}, {current_tab_id}, {session_id}, {gaze_x}, {gaze_y}, {username})")
    except Exception as e:
        print(f"Error in gaze_data_callback: {e}")


def monitor_tabs():
    global previous_tab_id
    while not stop_monitoring.is_set():
        new_current_tab_id = get_current_tab_id()
        if new_current_tab_id and new_current_tab_id != previous_tab_id:
            with handle_tab_change_lock:
                handle_tab_change(new_current_tab_id)
        #time.sleep(0.1)


def handle_tab_change(new_current_tab_id):
    global previous_tab_id
    if previous_tab_id is not None:
        # Fetch the title of the previous tab from the stored IDs
        previous_tab_title = None
        for title, id in window_title_to_id.items():
            if id == previous_tab_id:
                previous_tab_title = title
                break
        if previous_tab_title and is_relevant_window(previous_tab_title):
            with insert_from_queue_lock:
                time.sleep(0.2)
                dequeued_records = insert_gaze_data_from_queue(previous_tab_id)
            with insert_most_common_point_lock:
                time.sleep(0.2)
                insert_gaze_points_from_cluster(previous_tab_id, dequeued_records)
    previous_tab_id = new_current_tab_id
    current_tab_title = gw.getActiveWindow().title if gw.getActiveWindow() else ""
    if is_relevant_window(current_tab_title):
        with draw_box_lock:
            time.sleep(0.2)
            draw_overlay_if_previous_tab_exists(new_current_tab_id)


def insert_gaze_data_from_queue(previous_tab_id):
    print("1")
    # print(get_current_tab_id(), " || ",previous_tab_id)
    try:
        if previous_tab_id in gaze_data_queue_dict and not gaze_data_queue_dict[previous_tab_id].empty():
            records_to_insert = []
            while not gaze_data_queue_dict[previous_tab_id].empty():
                dequeued_data = gaze_data_queue_dict[previous_tab_id].dequeue()

                # Check if dequeued_data is not None before proceeding
                if dequeued_data is not None:
                    active_window_title, previous_tab_id, session_id, gaze_x, gaze_y, username = dequeued_data
                    # Optionally print the gaze X and Y values for verification
                    # print(f"Gaze coordinates being prepared for insertion: X={gaze_x}, Y={gaze_y}")
                    records_to_insert.append(dequeued_data)
                else:
                    # If dequeued_data is None, the queue is empty and you can break the loop
                    break

            if records_to_insert:  # Check if there are records to insert
                query = """INSERT INTO public."Future_Work_Data" ("AppName", "TabID", "SessionID", "Axis_x", "Axis_y", "Username")
                           VALUES (%s, %s, %s, %s, %s, %s)"""
                cursor.executemany(query, records_to_insert)
                connection.commit()
                print(f"Batch inserted {len(records_to_insert)} records for tab ID: {previous_tab_id}")
            # del gaze_data_queue_dict[previous_tab_id]
        print("2")
        return records_to_insert
        # print(get_current_tab_id(), " || ",previous_tab_id)
    except Exception as e:
        print(f"Error in insert_gaze_data_from_queue: {e}")


def insert_gaze_points_from_cluster(previous_tab_id, dequeued_records):
    print("3")
    try:
        points = preprocessing([(item[3], item[4]) for item in dequeued_records])
        if not points:
            print("No valid points available after preprocessing.")
            return

        clusters = []
        deviation = 30  # Threshold for clustering based on proximity
        threshold_for_y_coords = 50  # Significant Y-coordinate change threshold
        last_valid_cluster = None
        current_cluster = []

        for i in range(len(points)):
            gaze_x, gaze_y = points[i]
            if not current_cluster:
                current_cluster.append((gaze_x, gaze_y))
            else:
                last_x, last_y = current_cluster[-1]
                if abs(last_y - gaze_y) >= threshold_for_y_coords:
                    # If a significant Y change is detected between two sequential points
                    if len(current_cluster) >= THRESHOLD:
                        last_valid_cluster = current_cluster.copy()
                        print(f"Detected significant Y change between points, captured cluster size: {len(current_cluster)}")
                    clusters.append(current_cluster)  # Store the completed cluster
                    current_cluster = [(gaze_x, gaze_y)]
                elif ((last_x - gaze_x) ** 2 + (last_y - gaze_y) ** 2) ** 0.5 <= deviation:
                    # Continue adding to the current cluster if within deviation and no significant Y change
                    current_cluster.append((gaze_x, gaze_y))
                else:
                    # Start a new cluster if the point is too far from the last point in the current cluster
                    clusters.append(current_cluster)  # Store the completed cluster before starting a new one
                    print(f"Cluster completed with size: {len(current_cluster)}")
                    current_cluster = [(gaze_x, gaze_y)]

        # Add the last cluster if it meets the threshold and was not added previously
        if current_cluster and len(current_cluster) >= THRESHOLD:
            last_valid_cluster = current_cluster
            clusters.append(current_cluster)
            print(f"Final cluster captured with size: {len(current_cluster)}")

        # Process each valid cluster
        for cluster in clusters:
            if len(cluster) >= THRESHOLD:
                for gaze_x, gaze_y in cluster:
                    cursor.execute("""
                        INSERT INTO public."Previous_Tabs" ("TabID", "Axis_x_point", "Axis_y_point")
                        VALUES (%s, %s, %s)
                        ON CONFLICT ("TabID") DO UPDATE
                        SET "Axis_x_point" = EXCLUDED."Axis_x_point",
                            "Axis_y_point" = EXCLUDED."Axis_y_point"
                    """, (previous_tab_id, gaze_x, gaze_y))
                connection.commit()
                print(f"Inserted {len(cluster)} points for TabID {previous_tab_id}")

    except Exception as e:
        print(f"Error in insert_gaze_points_from_cluster: {e}")

    print("4")



def draw_overlay_if_previous_tab_exists(current_tab_id):
    global overlay_widget
    print("5")
    try:
        cursor.execute("""
            SELECT "Axis_x_point", "Axis_y_point"
            FROM public."Previous_Tabs"
            WHERE "TabID" = %s
        """, (current_tab_id,))
        points = cursor.fetchall()

        if points:
            box_size = (100, 45)
            x_coords, y_coords = zip(*points)
            center_x = sum(x_coords) // len(x_coords)
            center_y = sum(y_coords) // len(y_coords)
            center_coordinates = (center_x, center_y)
            print("POINT SELECTED FROM PREVIOUS TABS: ", current_tab_id, "->", points)
            if overlay_widget is not None:
                overlay_widget.destroy()

            root = tk.Tk()
            root.withdraw()
            overlay_widget = OverlayBox(root, center_coordinates, box_size)
            overlay_widget.show()
            overlay_widget.update_idletasks()
            overlay_widget.update()

            time.sleep(2.2)  # time for the box to appear before hiding it
            overlay_widget.hide()
        else:
            # No points available, do not draw or update overlay
            print("No data available to draw the overlay for TabID", current_tab_id)
            if overlay_widget is not None:
                overlay_widget.destroy()

        # Clean up by deleting entries from the database
        cursor.execute("""DELETE FROM public."Previous_Tabs" WHERE "TabID" = %s """, (current_tab_id,))
        connection.commit()

    except Exception as e:
        print(f"Error in draw_overlay_if_previous_tab_exists: {e}")


# def calculate_box_size(points, min_size = (100,60), max_size=(150, 80)):
#     if not points:
#         return min_size  # Return the minimum size if no points are provided

#     x_coords, y_coords = zip(*points)
#     width = max(x_coords) - min(x_coords)
#     height = max(y_coords) - min(y_coords)

#     # Apply minimum and maximum constraints
#     width = max(min_size[0], min(width, max_size[0]))
#     height = max(min_size[1], min(height, max_size[1]))

#     return (width, height)


if __name__ == '__main__':
    my_eyetracker = None
    try:
        current_tab_id = get_current_tab_id()
        delete_previous_tabs_data()
        found_eyetrackers = tr.find_all_eyetrackers()
        if found_eyetrackers:
            my_eyetracker = found_eyetrackers[0]
            my_eyetracker.subscribe_to(tr.EYETRACKER_GAZE_DATA, gaze_data_callback, as_dictionary=True)
            print("Subscribed to eye tracker gaze data.")
        else:
            print("No eye tracker found. Try running the program again.")
            sys.exit()
        stop_monitoring = threading.Event()
        thread_one = threading.Thread(target=monitor_tabs)
        thread_one.start()
        thread_one.join()

    except Exception as e:
        print(f"Error occurred: {e}")
    except KeyboardInterrupt:
        print("Program stopped by the user.")
    finally:
        if my_eyetracker is not None:
            my_eyetracker.unsubscribe_from(tr.EYETRACKER_GAZE_DATA, gaze_data_callback)
            print("Unsubscribed from eye tracker gaze data.")

        cursor.close()
        connection.close()