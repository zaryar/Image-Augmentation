import mediapipe as mp
import cv2
import math
import numpy as np
import faceRec_MP.faceBlendCommon as fbc
import csv
#imports for stream
import os
import time

#variables for stream
PATH = "./local_version/front/public/images/input/"
FILENAME = './local_version/front/public/images/output/frame.jpg'
STOPP = "./local_version/front/public/stopStream.txt"
LOCKOUT = './local_version/front/public/images/output/lockOut'
FRAME = "frame.jpg"

CODEC = 'WMV1' #the codec is dependant on the machine you are using. You might have to try different CODECs on MacOS 

#if True landmarks are marked
VISUALIZE_FACE_POINTS = False

#dictionary for filter information
filters_config = {
    'clown':
        [{'path': "local_version/back/faceRec_MP/filters/clown.png",
          'anno_path': "local_version/back/faceRec_MP/filters/landmarks80.csv",
          'morph': True, 'animated': False, 'has_alpha': True}],
    'pandaFull':
        [{'path': "local_version/back/faceRec_MP/filters/panda.png",
          'anno_path': "local_version/back/faceRec_MP/filters/landmarks80.csv",
          'morph': True, 'animated': False, 'has_alpha': True}],
    'cat':
        [{'path': "local_version/back/faceRec_MP/filters/cat-ears.png",
          'anno_path': "local_version/back/faceRec_MP//filters/ears_annotations.csv",
          'morph': False, 'animated': False, 'has_alpha': True},
         {'path': "local_version/back/faceRec_MP/filters/cat-nose.png",
          'anno_path': "local_version/back/faceRec_MP//filters/nose_annotations.csv",
          'morph': False, 'animated': False, 'has_alpha': True}],
    'panda':
        [{'path': "local_version/back/faceRec_MP/filters/panda-ears.png",
          'anno_path': "local_version/back/faceRec_MP//filters/ears_annotations.csv",
          'morph': False, 'animated': False, 'has_alpha': True},
         {'path': "local_version/back/faceRec_MP/filters/panda-nose.png",
          'anno_path': "local_version/back/faceRec_MP//filters/nose_annotations.csv",
          'morph': False, 'animated': False, 'has_alpha': True}],
}

# detect facial landmarks in image
# returns 81 relevant landmarks if face found, else prints "face not detectd!!!"
def getLandmarks(img):
    mp_face_mesh = mp.solutions.face_mesh
    selected_keypoint_indices = [127, 93, 58, 136, 150, 149, 176, 148, 152, 377, 400, 378, 379, 365, 288, 323, 356, 70, 63, 105, 66, 55,
                 285, 296, 334, 293, 300, 168, 6, 195, 4, 64, 60, 94, 290, 294, 33, 160, 158, 173, 153, 144, 398, 385,
                 387, 466, 373, 380, 61, 40, 39, 0, 269, 270, 291, 321, 405, 17, 181, 91, 62, 81, 13, 311, 292, 402, 14,
                 178, 162, 54, 67, 10, 297, 284, 389, 117, 50, 205, 346, 280, 425
                 ]

    height, width = img.shape[:-1]

    with mp_face_mesh.FaceMesh(max_num_faces=1, static_image_mode=True, min_detection_confidence=0.5) as face_mesh:

        results = face_mesh.process(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))

        if not results.multi_face_landmarks:
            print('Face not detected!!!')
            return 0

        for face_landmarks in results.multi_face_landmarks:
            values = np.array(face_landmarks.landmark)
            face_keypnts = np.zeros((len(values), 2))

            for idx,value in enumerate(values):
                face_keypnts[idx][0] = value.x
                face_keypnts[idx][1] = value.y

            # Convert normalized points to image coordinates
            face_keypnts = face_keypnts * (width, height)
            face_keypnts = face_keypnts.astype('int')

            relevant_keypnts = []

            for i in selected_keypoint_indices:
                relevant_keypnts.append(face_keypnts[i])
            return relevant_keypnts
    return 0

# returns image with its alpha
def load_filter_img(img_path, has_alpha):
    # Read the image
    img = cv2.imread(img_path, cv2.IMREAD_UNCHANGED)

    alpha = None
    if has_alpha:
        b, g, r, alpha = cv2.split(img)
        img = cv2.merge((b, g, r))

    return img, alpha

# read annotaton file and return landmarks with corresponding filter annotations
def load_landmarks(annotation_file):
    with open(annotation_file) as csv_file:
        csv_reader = csv.reader(csv_file, delimiter=",")
        points = {}
        for i, row in enumerate(csv_reader):
            # skip head or empty line if it's there
            try:
                x, y = int(row[1]), int(row[2])
                points[row[0]] = (x, y)
            except ValueError:
                continue
        return points

def find_convex_hull(points):

    hull = []
    hullIndex = cv2.convexHull(np.array(list(points.values())), clockwise=False, returnPoints=False)
    addPoints = [
        [48], [49], [50], [51], [52], [53], [54], [55], [56], [57], [58], [59],  # Outer lips
        [60], [61], [62], [63], [64], [65], [66], [67],  # Inner lips
        [27], [28], [29], [30], [31], [32], [33], [34], [35],  # Nose
        [36], [37], [38], [39], [40], [41], [42], [43], [44], [45], [46], [47],  # Eyes
        [17], [18], [19], [20], [21], [22], [23], [24], [25], [26]  # Eyebrows
        ,[75], [76], [77], [78], [79], [80] #cheeks
        
    ]
    hullIndex = np.concatenate((hullIndex, addPoints))
    for i in range(0, len(hullIndex)):
        hull.append(points[str(hullIndex[i][0])])

    return hull, hullIndex

# prepares filters to be used
def load_filter(filter_name):

    filters = filters_config[filter_name]

    multi_filter_runtime = []

    for filter in filters:
        temp_dict = {}

        img1, img1_alpha = load_filter_img(filter['path'], filter['has_alpha'])

        temp_dict['img'] = img1
        temp_dict['img_a'] = img1_alpha

        points = load_landmarks(filter['anno_path'])

        temp_dict['points'] = points

        if filter['morph']:
            # Find convex hull for delaunay triangulation using the landmark points
            hull, hullIndex = find_convex_hull(points)

            # Find Delaunay triangulation for convex hull points
            sizeImg1 = img1.shape
            rect = (0, 0, sizeImg1[1], sizeImg1[0])
            dt = fbc.calculateDelaunayTriangles(rect, hull)

            temp_dict['hull'] = hull
            temp_dict['hullIndex'] = hullIndex
            temp_dict['dt'] = dt

            if len(dt) == 0:
                continue

        if filter['animated']:
            filter_cap = cv2.VideoCapture(filter['path'])
            temp_dict['cap'] = filter_cap

        multi_filter_runtime.append(temp_dict)

    return filters, multi_filter_runtime

# base function for using face-recognition on videos
# takes video_path, filter and output_path and writes video with filter applied
def filter_on_video (video, overlay, filename) :
    # process input from video file
    cap = video

    #setup video writer
    WIDTH = int( cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    HEIGHT= int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS)

    fourcc = cv2.VideoWriter_fourcc(* CODEC )
    output_vid = cv2.VideoWriter(filename, fourcc, fps, (WIDTH,  HEIGHT))

    # Some variables
    isFirstFrame = True
    sigma = 50

    filters, multi_filter_runtime = load_filter(overlay)

    # The main loop
    while True:

        ret, frame = cap.read()
        if not ret:
            break
        else:

            points2 = getLandmarks(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))

            # if face is partially detected
            if not points2 or (len(points2) != 81):
                continue

            ################ Optical Flow and Stabilization Code #####################
            img2Gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

            if isFirstFrame:
                points2Prev = np.array(points2, np.float32)
                img2GrayPrev = np.copy(img2Gray)
                isFirstFrame = False

            lk_params = dict(winSize=(101, 101), maxLevel=15,
                            criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 20, 0.001))
            points2Next, st, err = cv2.calcOpticalFlowPyrLK(img2GrayPrev, img2Gray, points2Prev,
                                                            np.array(points2, np.float32),
                                                            **lk_params)

            # Final landmark points are a weighted average of detected landmarks and tracked landmarks

            for k in range(0, len(points2)):
                d = cv2.norm(np.array(points2[k]) - points2Next[k])
                alpha = math.exp(-d * d / sigma)
                points2[k] = (1 - alpha) * np.array(points2[k]) + alpha * points2Next[k]
                points2[k] = fbc.constrainPoint(points2[k], frame.shape[1], frame.shape[0])
                points2[k] = (int(points2[k][0]), int(points2[k][1]))

            # Update variables for next pass
            points2Prev = np.array(points2, np.float32)
            img2GrayPrev = img2Gray
            ################ End of Optical Flow and Stabilization Code ###############

            if VISUALIZE_FACE_POINTS:
                for idx, point in enumerate(points2):
                    cv2.circle(frame, point, 2, (255, 0, 0), -1)
                    cv2.putText(frame, str(idx), point, cv2.FONT_HERSHEY_SIMPLEX, .3, (255, 255, 255), 1)
                cv2.imshow("landmarks", frame)

            for idx, filter in enumerate(filters) :
                filter_runtime = multi_filter_runtime[idx]
                img1 = filter_runtime['img']
                points1 = filter_runtime['points']
                img1_alpha = filter_runtime['img_a']

                if filter['morph']:

                    hullIndex = filter_runtime['hullIndex']
                    dt = filter_runtime['dt']
                    hull1 = filter_runtime['hull']

                    # create copy of frame
                    warped_img = np.copy(frame)

                    # Find convex hull
                    hull2 = []
                    for i in range(0, len(hullIndex)):
                        hull2.append(points2[hullIndex[i][0]])

                    mask1 = np.zeros((warped_img.shape[0], warped_img.shape[1]), dtype=np.float32)
                    mask1 = cv2.merge((mask1, mask1, mask1))
                    img1_alpha_mask = cv2.merge((img1_alpha, img1_alpha, img1_alpha))

                    # Warp the triangles
                    for i in range(0, len(dt)):
                        t1 = []
                        t2 = []

                        for j in range(0, 3):
                            t1.append(hull1[dt[i][j]])
                            t2.append(hull2[dt[i][j]])

                        fbc.warpTriangle(img1, warped_img, t1, t2)
                        fbc.warpTriangle(img1_alpha_mask, mask1, t1, t2)

                    # Blur the mask before blending
                    mask1 = cv2.GaussianBlur(mask1, (3, 3), 10)

                    mask2 = (255.0, 255.0, 255.0) - mask1

                    # Perform alpha blending of the two images
                    temp1 = np.multiply(warped_img, (mask1 * (1.0 / 255)))
                    temp2 = np.multiply(frame, (mask2 * (1.0 / 255)))
                    output = temp1 + temp2
                else:
                    dst_points = [points2[int(list(points1.keys())[0])], points2[int(list(points1.keys())[1])]]
                    tform = fbc.similarityTransform(list(points1.values()), dst_points)
                    # Apply similarity transform to input image
                    trans_img = cv2.warpAffine(img1, tform, (frame.shape[1], frame.shape[0]))
                    trans_alpha = cv2.warpAffine(img1_alpha, tform, (frame.shape[1], frame.shape[0]))
                    mask1 = cv2.merge((trans_alpha, trans_alpha, trans_alpha))

                    # Blur the mask before blending
                    mask1 = cv2.GaussianBlur(mask1, (3, 3), 10)

                    mask2 = (255.0, 255.0, 255.0) - mask1

                    # Perform alpha blending of the two images
                    temp1 = np.multiply(trans_img, (mask1 * (1.0 / 255)))
                    temp2 = np.multiply(frame, (mask2 * (1.0 / 255)))
                    output = temp1 + temp2

                frame = output = np.uint8(output)
            output_vid.write(output)

# base function for using face-recognition on images
# takes image, filter and saves processed image
def filter_on_image (frame, overlay) :

    filters, multi_filter_runtime = load_filter(overlay)

    points2 = getLandmarks(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))

    for idx, filter in enumerate(filters) :
        filter_runtime = multi_filter_runtime[idx]
        img1 = filter_runtime['img']
        points1 = filter_runtime['points']
        img1_alpha = filter_runtime['img_a']

        if filter['morph']:

            hullIndex = filter_runtime['hullIndex']
            dt = filter_runtime['dt']
            hull1 = filter_runtime['hull']

            # create copy of frame
            warped_img = np.copy(frame)

            # Find convex hull
            hull2 = []
            for i in range(0, len(hullIndex)):
                hull2.append(points2[hullIndex[i][0]])

            mask1 = np.zeros((warped_img.shape[0], warped_img.shape[1]), dtype=np.float32)
            mask1 = cv2.merge((mask1, mask1, mask1))
            img1_alpha_mask = cv2.merge((img1_alpha, img1_alpha, img1_alpha))

            # Warp the triangles
            for i in range(0, len(dt)):
                t1 = []
                t2 = []

                for j in range(0, 3):
                    t1.append(hull1[dt[i][j]])
                    t2.append(hull2[dt[i][j]])

                fbc.warpTriangle(img1, warped_img, t1, t2)
                fbc.warpTriangle(img1_alpha_mask, mask1, t1, t2)

            # Blur the mask before blending
            mask1 = cv2.GaussianBlur(mask1, (3, 3), 10)
            mask2 = (255.0, 255.0, 255.0) - mask1

            # Perform alpha blending of the two images
            temp1 = np.multiply(warped_img, (mask1 * (1.0 / 255)))
            temp2 = np.multiply(frame, (mask2 * (1.0 / 255)))
            output = temp1 + temp2
        else:
            dst_points = [points2[int(list(points1.keys())[0])], points2[int(list(points1.keys())[1])]]
            tform = fbc.similarityTransform(list(points1.values()), dst_points)
            # Apply similarity transform to input image
            trans_img = cv2.warpAffine(img1, tform, (frame.shape[1], frame.shape[0]))
            trans_alpha = cv2.warpAffine(img1_alpha, tform, (frame.shape[1], frame.shape[0]))
            mask1 = cv2.merge((trans_alpha, trans_alpha, trans_alpha))

            # Blur the mask before blending
            mask1 = cv2.GaussianBlur(mask1, (3, 3), 10)

            mask2 = (255.0, 255.0, 255.0) - mask1

            # Perform alpha blending of the two images
            temp1 = np.multiply(trans_img, (mask1 * (1.0 / 255)))
            temp2 = np.multiply(frame, (mask2 * (1.0 / 255)))
            output = temp1 + temp2

        frame = output = np.uint8(output)
    return output

# takes image and applies clown filter
def filter_clown(img):
    image = filter_on_image(img, "clown")
    return image

# takes image and applies pandaFull filter
def filter_pandaFull(img):
    image = filter_on_image(img, "pandaFull")
    return image

# takes image and applies cat filter
def filter_cat(img):
    image = filter_on_image(img, "cat")
    return image

# takes image and applies panda filter
def filter_panda(img):
    image = filter_on_image(img, "panda")
    return image

# base function for using face-recognition on streams
# takes frame_path, filter and output_path and saves frames
def stream_face_recognition(path, filter, outputImg):

    if (filter == filter_clown):
        overlay = "clown"
    elif (filter == filter_pandaFull):
        overlay = "pandaFull"
    elif (filter == filter_cat):
        overlay = "cat"
    elif (filter == filter_panda):
        overlay = "panda"

    # Some variables
    isFirstFrame = True
    sigma = 50

    filters, multi_filter_runtime = load_filter(overlay)
    
    stream_active = True

    while stream_active:
        path = PATH + FRAME
        if os.path.exists(path) and cv2.imread(path) is not None: #is file ready?
            if not os.path.exists(LOCKOUT): #did we already display the last image?
                print(path, FILENAME, filter)     

                frame = cv2.imread(path)

                if frame is None:
                    print("frame is None-type")
                    continue

                points2 = getLandmarks(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))

                # if face is partially detected
                if points2 and (len(points2) == 81):
                    ################ Optical Flow and Stabilization Code #####################
                    img2Gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

                    if isFirstFrame:
                        points2Prev = np.array(points2, np.float32)
                        img2GrayPrev = np.copy(img2Gray)
                        isFirstFrame = False

                    lk_params = dict(winSize=(101, 101), maxLevel=15,
                                    criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 20, 0.001))
                    points2Next, st, err = cv2.calcOpticalFlowPyrLK(img2GrayPrev, img2Gray, points2Prev,
                                                                    np.array(points2, np.float32),
                                                                    **lk_params)

                    # Final landmark points are a weighted average of detected landmarks and tracked landmarks

                    for k in range(0, len(points2)):
                        d = cv2.norm(np.array(points2[k]) - points2Next[k])
                        alpha = math.exp(-d * d / sigma)
                        points2[k] = (1 - alpha) * np.array(points2[k]) + alpha * points2Next[k]
                        points2[k] = fbc.constrainPoint(points2[k], frame.shape[1], frame.shape[0])
                        points2[k] = (int(points2[k][0]), int(points2[k][1]))

                    # Update variables for next pass
                    points2Prev = np.array(points2, np.float32)
                    img2GrayPrev = img2Gray
                    ################ End of Optical Flow and Stabilization Code ###############

                    if VISUALIZE_FACE_POINTS:
                        for idx, point in enumerate(points2):
                            cv2.circle(frame, point, 2, (255, 0, 0), -1)
                            cv2.putText(frame, str(idx), point, cv2.FONT_HERSHEY_SIMPLEX, .3, (255, 255, 255), 1)
                        cv2.imshow("landmarks", frame)

                    for idx, filter in enumerate(filters) :
                        filter_runtime = multi_filter_runtime[idx]
                        img1 = filter_runtime['img']
                        points1 = filter_runtime['points']
                        img1_alpha = filter_runtime['img_a']

                        if filter['morph']:

                            hullIndex = filter_runtime['hullIndex']
                            dt = filter_runtime['dt']
                            hull1 = filter_runtime['hull']

                            # create copy of frame
                            warped_img = np.copy(frame)

                            # Find convex hull
                            hull2 = []
                            for i in range(0, len(hullIndex)):
                                hull2.append(points2[hullIndex[i][0]])

                            mask1 = np.zeros((warped_img.shape[0], warped_img.shape[1]), dtype=np.float32)
                            mask1 = cv2.merge((mask1, mask1, mask1))
                            img1_alpha_mask = cv2.merge((img1_alpha, img1_alpha, img1_alpha))

                            # Warp the triangles
                            for i in range(0, len(dt)):
                                t1 = []
                                t2 = []

                                for j in range(0, 3):
                                    t1.append(hull1[dt[i][j]])
                                    t2.append(hull2[dt[i][j]])

                                fbc.warpTriangle(img1, warped_img, t1, t2)
                                fbc.warpTriangle(img1_alpha_mask, mask1, t1, t2)

                            # Blur the mask before blending
                            mask1 = cv2.GaussianBlur(mask1, (3, 3), 10)

                            mask2 = (255.0, 255.0, 255.0) - mask1

                            # Perform alpha blending of the two images
                            temp1 = np.multiply(warped_img, (mask1 * (1.0 / 255)))
                            temp2 = np.multiply(frame, (mask2 * (1.0 / 255)))
                            output = temp1 + temp2
                        else:
                            dst_points = [points2[int(list(points1.keys())[0])], points2[int(list(points1.keys())[1])]]
                            tform = fbc.similarityTransform(list(points1.values()), dst_points)
                            # Apply similarity transform to input image
                            trans_img = cv2.warpAffine(img1, tform, (frame.shape[1], frame.shape[0]))
                            trans_alpha = cv2.warpAffine(img1_alpha, tform, (frame.shape[1], frame.shape[0]))
                            mask1 = cv2.merge((trans_alpha, trans_alpha, trans_alpha))

                            # Blur the mask before blending
                            mask1 = cv2.GaussianBlur(mask1, (3, 3), 10)

                            mask2 = (255.0, 255.0, 255.0) - mask1

                            # Perform alpha blending of the two images
                            temp1 = np.multiply(trans_img, (mask1 * (1.0 / 255)))
                            temp2 = np.multiply(frame, (mask2 * (1.0 / 255)))
                            output = temp1 + temp2

                        frame = output = np.uint8(output)      

                cv2.imwrite(outputImg, frame)
                open(LOCKOUT, "x")
                file = FRAME
                os.remove(os.path.join(PATH, file))

            else:
                print("lockOut already there | not worked with on canvis")
        else:
            print("input file cant be found")
        stream_active = os.path.exists(STOPP) == False
        if os.path.exists(STOPP):
            os.remove(STOPP)
            return
        time.sleep(0.04)

# this function takes a path, a filter and output_path and applies filter to the video given
def apply_faceRec_video(video_path, apply, filename):
    video = cv2.VideoCapture(video_path)
    if (apply == filter_clown):
        overlay = "clown"
    elif (apply == filter_pandaFull):
        overlay = "pandaFull"
    elif (apply == filter_cat):
        overlay = "cat"
    elif (apply == filter_panda):
        overlay = "panda"

    vid = filter_on_video(video, overlay, filename)

    return vid