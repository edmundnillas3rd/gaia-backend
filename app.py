import os
import re
import cv2
import time
import shutil
import zipfile
import urllib.request
import numpy as np
import base64
import io
from PIL import Image
from os import listdir
from os.path import isfile, join
from random import randrange
import matplotlib.pyplot as plt
from tensorflow.keras.models import load_model
from tensorflow.keras.preprocessing import image
from tensorflow.keras.preprocessing.image import ImageDataGenerator
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import Dense, Activation, Flatten
from tensorflow.keras.layers import Conv2D, MaxPooling2D

from flask import Flask, flash, request, redirect, url_for, jsonify
from werkzeug.utils import secure_filename

UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif'}

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/')
def index():
    return 'Hello World'

def model_classify(cropped_img, model):
    classes = ['gravel', 'sand', 'silt']
    image_array = cropped_img / 255.
    img_batch = np.expand_dims(image_array, axis=0)
    prediction_array = model.predict(img_batch)[0]
    first_idx = np.argmax(prediction_array)
    first_class = classes[first_idx]
    return first_class

def make_prediction(image_fp, model):
    im = cv2.imread(image_fp) # load image
    plt.imshow(im[:,:,[2,1,0]])
    img = image.load_img(image_fp, target_size = (256,256))
    img = image.img_to_array(img)

    image_array = img / 255. # scale the image
    img_batch = np.expand_dims(image_array, axis = 0)
    
    class_ = ["gravel", "sand", "silt"] # possible output values
    predicted_value = class_[model.predict(img_batch).argmax()]
    # true_value = re.search(r'(gravel)|(sand)|(silt)', image_fp)[0]
    if re.search(r'(gravel)|(sand)|(silt)', image_fp) is not None:
        true_value = re.search(r'(gravel)|(sand)|(silt)', image_fp)[0]
    else:
        true_value = re.search(r'(gravel)|(sand)|(silt)', image_fp)    

    # f"""predicted soil type: {predicted_value}
    # true soil type: {true_value}
    # correct?: {predicted_value == true_value}"""

    correctness = predicted_value == true_value
    
    return {
        "predicted_value": predicted_value,
        "true_value": true_value,
        "correctness": correctness
    }

@app.route('/image/classify-image', methods=['POST'])
def classify_images():
    classes = ['gravel', 'sand', 'silt']
    gravel_count = 0
    sand_count = 0
    silt_count = 0

    model_fp = os.getcwd()+'/'+'soil.h5'
    print(model_fp)
    model = load_model(model_fp)


    image = request.files['image']
    if image and allowed_file(image.filename):
            filename = secure_filename(image.filename)
            image.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

    # test_data_directory = 'test'
    # image_fp = test_data_directory + r"/silt/5.jpg"
    # im = cv2.imread(image_fp) # load image
    # plt.imshow(im[:,:,[2,1,0]])

    image_fp = UPLOAD_FOLDER + '\\' + filename
    # image_fp = test_data_directory + r"/silt/5.jpg"
    print(image_fp)
    img = cv2.imread(image_fp)
    img = cv2.resize(img,(1024,1024))
    im_dim = 256
    # im_dim = 512 

    out = make_prediction(image_fp=image_fp, model=model)
    print("making prediction")
    print(out)

    if (out['true_value'] == None or out['correctness'] == False):
        return jsonify(data = {
            "Data": "Not a soil"
        })

    for r in range(0, img.shape[0], im_dim):
        for c in range(0, img.shape[1], im_dim):
            cropped_img = img[r:r + im_dim, c:c + im_dim, :]
            h, w, c = cropped_img.shape
            if h == im_dim and w == im_dim:
                classification = model_classify(cropped_img, model)
                if classification == classes[0]:
                    gravel_count += 1
                elif classification == classes[1]:
                    sand_count += 1
                elif classification == classes[2]:
                    silt_count += 1
            else:
                continue

    total_count = gravel_count + sand_count + silt_count
    proportion_array = [gravel_count / total_count, sand_count / total_count, silt_count / total_count]
    out = proportion_array
    # return proportion_array
    return jsonify( data = {
        "Data": f'''---
            percent gravel: {round(out[0] * 100, 2)}%)
            percent sand: {round(out[1] * 100, 2)}%)
            percent silt: {round(out[2] * 100, 2)}%)
        ---'''

    })



@app.route('/image/upload-image', methods=['POST'])
def upload_image():
    training_data_directory = 'train'
    test_data_directory = 'test'

    # download soil_photos.zip
    if not os.path.exists('test') and not os.path.exists('train'):
        file = 'soil_photos.zip'
        url = 'http://apmonitor.com/pds/uploads/Main/'+file
        urllib.request.urlretrieve(url, file)

        # extract archive and remove soil_photos.zip
        with zipfile.ZipFile(file, 'r') as zip_ref:
            zip_ref.extractall('./')
        os.remove(file)

    training_data_processor = ImageDataGenerator(
        rescale = 1./255,
        horizontal_flip = True,
        zoom_range = 0.2,
        rotation_range = 10,
        shear_range = 0.2,
        height_shift_range = 0.1,
        width_shift_range = 0.1
    )

    test_data_processor = ImageDataGenerator(rescale = 1./255)

    # Load data into Python
    training_data = training_data_processor.flow_from_directory(
        training_data_directory,
        target_size = (256, 256),
        batch_size = 32,
        class_mode = 'categorical',
    )

    testing_data = test_data_processor.flow_from_directory(
        test_data_directory,
        target_size = (256 ,256),
        batch_size = 32,
        class_mode = 'categorical',
        shuffle = False
    )

    num_conv_layers = 2
    num_dense_layers = 1
    layer_size = 64
    num_training_epochs = 20
    MODEL_NAME = 'soil'

    # Initiate model variable
    model = Sequential()

    # begin adding properties to model variable
    # e.g. add a convolutional layer
    model.add(Conv2D(layer_size, (3, 3), input_shape=(256,256, 3)))
    model.add(Activation('relu'))
    model.add(MaxPooling2D(pool_size=(2, 2)))

    # add additional convolutional layers based on num_conv_layers
    for _ in range(num_conv_layers-1):
        model.add(Conv2D(layer_size, (3, 3)))
        model.add(Activation('relu'))
        model.add(MaxPooling2D(pool_size=(2, 2)))

    # reduce dimensionality
    model.add(Flatten())

    # add fully connected "dense" layers if specified
    for _ in range(num_dense_layers):
        model.add(Dense(layer_size))
        model.add(Activation('relu'))

    # add output layer
    model.add(Dense(3))
    model.add(Activation('softmax'))

    # compile the sequential model with all added properties
    model.compile(loss='categorical_crossentropy',
                    optimizer='adam',
                    metrics=['accuracy'],
                    
                    )

    # use the data already loaded previously to train/tune the model
    model.fit(training_data,
                epochs=num_training_epochs,
                validation_data = testing_data)

    # save the trained model
    model.save(f'{MODEL_NAME}.h5')

    def make_prediction(image_fp):
        im = cv2.imread(image_fp) # load image
        plt.imshow(im[:,:,[2,1,0]])
        img = image.load_img(image_fp, target_size = (256,256))
        img = image.img_to_array(img)

        image_array = img / 255. # scale the image
        img_batch = np.expand_dims(image_array, axis = 0)
        
        class_ = ["gravel", "sand", "silt"] # possible output values
        predicted_value = class_[model.predict(img_batch).argmax()]
        true_value = re.search(r'(gravel)|(sand)|(silt)', image_fp)[0]
        
        out = f"""predicted soil type: {predicted_value}
        true soil type: {true_value}
        correct?: {predicted_value == true_value}"""
        
        return out

    test_image_filepath = test_data_directory + r'/sand/0.jpg'
    print(make_prediction(test_image_filepath))

    percentage_photo = test_data_directory + r"/silt/5.jpg"
    im = cv2.imread(percentage_photo) # load image
    plt.imshow(im[:,:,[2,1,0]])

    def split_images(image_dir, save_dir):
        classification_list = ['gravel', 'sand', 'silt']
        for classification in classification_list:
            folder = image_dir + '/' + classification + '/'
            save_folder = save_dir + '/' + classification + '/'
            files = [f for f in listdir(folder) if isfile(join(folder, f))]

            for file in files:
                if '.ini' in file:
                    continue
                fp = folder + file
                img = cv2.imread(fp)
                h,w,c = img.shape
                im_dim = 64
                # for cropping images
                for r in range(0,img.shape[0],im_dim):
                    for c in range(0,img.shape[1],im_dim):
                        cropped_img = img[r:r+im_dim, c:c+im_dim,:]
                        ch, cw, cc = cropped_img.shape
                        if ch == im_dim and cw == im_dim:
                            write_path = f"{save_folder + str(randrange(100000))}img{r}_{c}.jpg"
                            cv2.imwrite(write_path,cropped_img)
                        else:
                            pass

    try:
        parent = training_data_directory.replace('train', '')
        dirs = ['train_divided', 'test_divided']
        class_ = ["gravel", "sand", "silt"]
        for dir in dirs:
            os.mkdir(os.path.join(parent, dir))
            for classification in class_:
                os.mkdir(os.path.join(parent, dir, classification))

        # split training images
        split_images(image_dir=training_data_directory,
                    save_dir=training_data_directory.replace('train', 'train_divided'))
        # split test images
        split_images(image_dir=test_data_directory,
                    save_dir=test_data_directory.replace('test', 'test_divided'))
    except fileexistserror:
        pass

    model_fp = os.getcwd()+'/'+'soil.h5'
    print(model_fp)
    model = load_model(model_fp)

    def classify_images(image_fp, model):
        classes = ['gravel', 'sand', 'silt']
        gravel_count = 0
        sand_count = 0
        silt_count = 0

        img = cv2.imread(image_fp)
        img = cv2.resize(img,(1024,1024))
        im_dim = 256

        for r in range(0, img.shape[0], im_dim):
            for c in range(0, img.shape[1], im_dim):
                cropped_img = img[r:r + im_dim, c:c + im_dim, :]
                h, w, c = cropped_img.shape
                if h == im_dim and w == im_dim:
                    classification = model_classify(cropped_img, model)
                    if classification == classes[0]:
                        gravel_count += 1
                    elif classification == classes[1]:
                        sand_count += 1
                    elif classification == classes[2]:
                        silt_count += 1
                else:
                    continue
        total_count = gravel_count + sand_count + silt_count
        proportion_array = [gravel_count / total_count, sand_count / total_count, silt_count / total_count]
        return proportion_array


    def model_classify(cropped_img, model):
        classes = ['gravel', 'sand', 'silt']
        image_array = cropped_img / 255.
        img_batch = np.expand_dims(image_array, axis=0)
        prediction_array = model.predict(img_batch)[0]
        first_idx = np.argmax(prediction_array)
        first_class = classes[first_idx]
        return first_class

    def classify_percentage(image_fp):
        start = time.time()
        out = classify_images(image_fp=image_fp, model=model)
        finish = str(round(time.time() - start, 5))
        
        im = cv2.imread(image_fp) # load image
        plt.imshow(im[:,:,[2, 1, 0]])

        print(f'''---
            percent gravel: {round(out[0] * 100, 2)}%)
            percent sand: {round(out[1] * 100, 2)}%)
            percent silt: {round(out[2] * 100, 2)}%)
            time to classify: {finish} seconds
        ---''')

        return f'''---
            percent gravel: {round(out[0] * 100, 2)}%)
            percent sand: {round(out[1] * 100, 2)}%)
            percent silt: {round(out[2] * 100, 2)}%)
            time to classify: {finish} seconds
        ---'''

    return jsonify(data = {
        "Data": classify_percentage(image_fp=percentage_photo)
    })