import cv2
import numpy as np
import mediapipe as mp
from collections import defaultdict
from models import append_to_database, db
from flask import current_app, Flask
import time


live_feedback = ''
def calculate_angle(a, b, c):
    a = np.array(a)
    b = np.array(b)
    c = np.array(c)
    radians = np.arctan2(c[1] - b[1], c[0] - b[0]) - np.arctan2(a[1] - b[1], a[0] - b[0])
    angle = np.abs(radians * 180.0 / np.pi)
    if angle > 180.0:
        angle = 360 - angle
    return angle

def gen_frames():
    global live_feedback
    camera = cv2.VideoCapture(0)
    if not camera.isOpened():
        print("Error: Camera could not be opened.")
        return

    mp_drawing = mp.solutions.drawing_utils
    mp_pose = mp.solutions.pose

    max_angle = None
    min_angle = None
    prev_angle = None
    direction = None
    repetition_count = 0
    ex_info = defaultdict(dict)
    exercise_id = 1

    with mp_pose.Pose(min_detection_confidence=0.5, min_tracking_confidence=0.5) as pose:
        while True:
            success, frame = camera.read()
            if not success:
                print("Failed to read frame from camera.")
                break

            image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            image.flags.writeable = False
            results = pose.process(image)
            image.flags.writeable = True
            image = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)

            try:
                landmarks = results.pose_landmarks.landmark
                points = [mp_pose.PoseLandmark.RIGHT_HIP,
                          mp_pose.PoseLandmark.RIGHT_SHOULDER,
                          mp_pose.PoseLandmark.RIGHT_ELBOW]

                if points:
                    a = [landmarks[points[0].value].x, landmarks[points[0].value].y]
                    b = [landmarks[points[1].value].x, landmarks[points[1].value].y]
                    c = [landmarks[points[2].value].x, landmarks[points[2].value].y]
                    angle = calculate_angle(a, b, c)
                    color = (0, 255, 0) if 40 <= angle <= 140 else (0, 0, 255)
                    cv2.putText(image, str(int(angle)), tuple(np.multiply(b, [640, 480]).astype(int)),
                                cv2.FONT_HERSHEY_SIMPLEX, 1, color, 2, cv2.LINE_AA)

                    # Track angles and count reps
                    if prev_angle is not None:
                        if angle > 120 and direction != "up":
                            max_angle = angle
                            direction = "up"
                        elif angle < 50 and direction != "down":
                            if max_angle is not None:
                                repetition_count += 1
                                ex_info[repetition_count]['max'] = max_angle
                                ex_info[repetition_count]['min'] = angle
                                max_angle = None
                                direction = "down"

                    prev_angle = angle
                    mp_drawing.draw_landmarks(image, results.pose_landmarks, mp_pose.POSE_CONNECTIONS)

                    # Display feedback
                    max_val = ex_info[repetition_count].get('max')
                    min_val = ex_info[repetition_count].get('min')

                    if angle is not None:
                        if angle > 100:
                            if angle > 125:
                                live_feedback = 'Great Job!'
                            else:
                                live_feedback = 'Try to raise your shoulders higher!'
                        else:
                            live_feedback = ''
                        cv2.putText(image,live_feedback, (30, 50),
                                    cv2.FONT_HERSHEY_DUPLEX, 0.5, (0, 0, 255), 1, cv2.LINE_AA)

                    if angle is not None:
                        if angle < 50:
                            if angle < 45:
                                live_feedback = 'Great Job!'
                            else:
                                live_feedback = 'Try to go lower!'
                        else:
                            live_feedback = ''
                        cv2.putText(image, live_feedback, (30, 100),
                                    cv2.FONT_HERSHEY_DUPLEX, 0.5, (0, 0, 255), 1, cv2.LINE_AA)

                    # Display repetition count
                    cv2.putText(image, f'Rep {repetition_count}', (30, 150),
                                cv2.FONT_HERSHEY_DUPLEX, 0.75, (0, 0, 255), 2, cv2.LINE_AA)

                    # Check if 8 repetitions are completed
                    if repetition_count >= 8:
                        end_time = time.time() + 5  # Set the end time for the 5-second delay

                        while time.time() < end_time:
                            success, frame = camera.read()  # Continue reading frames from the camera
                            if not success:
                                print("Failed to read frame from camera.")
                                break

                            image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                            image.flags.writeable = False
                            results = pose.process(image)
                            image.flags.writeable = True
                            image = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)

                            # Display the loading message
                            cv2.putText(image, 'Great Job! '
                                               'Taking you to feedback page.', (30, 200),
                                        cv2.FONT_HERSHEY_DUPLEX, 0.75, (0, 0, 255), 1, cv2.LINE_AA)

                            ret, buffer = cv2.imencode('.jpg', image)
                            frame = buffer.tobytes()
                            yield (b'--frame\r\n'
                                   b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

                        # Commit to database within application context
                        try:
                            with current_app.app_context():
                                append_to_database(exercise_id, ex_info)
                                ex_info.clear()
                                repetition_count = 0
                        except Exception as e:
                            print(f"Error while appending to database: {e}")

                        # No need to break the loop here; the camera should remain open for further usage

            except Exception as e:
                print(f"Error during pose processing: {e}")

            ret, buffer = cv2.imencode('.jpg', image)
            frame = buffer.tobytes()
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

    camera.release()
