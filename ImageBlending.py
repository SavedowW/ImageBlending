import dearpygui.dearpygui as dpg
import json
from os import listdir
from os.path import isfile, join, isdir
from os import mkdir
from PIL import Image
import numpy
from blend_modes import *
import pickle
import datetime
import sys

dpg.create_context()

# Info about layer names and default values
layersDefaultTuple = (
("Denoise", 0.5, ""),
("Direct", 0.1, "_02_Direct"),
("Indirect", 0.1, "_03_Indirect"),
("RawComponent", 0.1, "_04_RawComponent"),
("Reflect", 0.2, "_05_Reflect"),
("Raw_Reflect", 0.1, "_06_Raw_reflect"),
("Refract", 0.3, "_07_Refract"),
("AO", 0.2, "_08_AO"),
("Translucency", 0.3, "_09_Translucency"))

# Global var with folder path
folderPath = ""
deleteAlphaLayer = False

# Global vars with last keyboard press info for double click
lastChar = 0
lastDate = datetime.datetime.now()

sliderStep = 0.05

# For double clicks
def kbd_callback(sender, app_data):
    global lastChar, lastDate

    # Check if user is already enters numbers
    for el in (layersDefaultTuple):
        if dpg.is_item_focused("alpha" + el[0]):
            return

    # Check if window with layers data is already shown
    if (not dpg.is_item_shown("layer_properties_window")):
        return

    # Check for double click
    if (app_data >= ord('1') and app_data <= ord('9')): # If its an acceptable number
        curDate = datetime.datetime.now()
        if (lastChar == app_data): # If its the same number
            if (curDate - lastDate).total_seconds() < 0.3: # If the last click wasn't too long ago
                dpg.focus_item("alpha" + layersDefaultTuple[int(chr(app_data))-1][0])

        lastChar = app_data
        lastDate = curDate

# Keyboard handler
with dpg.handler_registry():
    dpg.add_key_press_handler(callback=kbd_callback)

# Clamp function
def clamp(num, min_value, max_value):
    return max(min(num, max_value), min_value)

# Callback to limit inputted floats
def float_callback(sender, app_data):
    dpg.set_value(sender, clamp(app_data, 0, 1))

# Send message to console
def addOutputMessage(str):
    dpg.set_value("outputMessage", dpg.get_value("outputMessage") + "\n" + str)

# Reset to default settings
def reset_to_default_callback():
    for el in range(0, len(layersDefaultTuple)):
        dpg.set_value("use" + layersDefaultTuple[el][0], True)
        dpg.set_value("alpha" + layersDefaultTuple[el][0], layersDefaultTuple[el][1])

# Load config
def load_config_callback():
    try:
        with open("config.cfg", "rb") as fp:
            configData = pickle.load(fp)
    except OSError:
        addOutputMessage("Failed to open config")
        return

    
    for el in range(0, len(configData)):
        dpg.set_value("use" + layersDefaultTuple[el][0], configData[el][0])
        dpg.set_value("alpha" + layersDefaultTuple[el][0], configData[el][1])

    addOutputMessage("Successfully loaded config")

# Save config
def save_config_callback():
    configData = getEnteredLayersData()
    with open("config.cfg", "wb") as fp:
        pickle.dump(configData, fp)

    addOutputMessage("Saved config")

# Parse entered data
def getEnteredLayersData():
    enteredLayersData = []
    for el in layersDefaultTuple:
        enteredLayersData.append((dpg.get_value("use" + el[0]), dpg.get_value("alpha" + el[0] )))
    return enteredLayersData

# Load image and blend with the base using blendFunction
def proceedLayer(layerId, base, segments, layersDefaultTuple, layerData, blendFunction):
    if (layerData[layerId][0]):
        layerfilename = folderPath + "\\" + segments[0] + layersDefaultTuple[layerId][2] + segments[1]
        layerRaw = loadImgRaw(layerfilename)
        if layerRaw == None:
            addOutputMessage("Failed to load '" + layerfilename + "', ignoring the layer")
            return base
        layerFloat = imgToFloatData(layerRaw)
        return blendFunction(base, layerFloat, layerData[layerId][1])
    else:
        return base

# Handles main render cycle
def renderLayers(beauties, layerData):
    addOutputMessage("Rendering...")
    try:
        resFolder = folderPath + "\\blending result\\"
        if not isdir(resFolder):
            mkdir(resFolder)
        for baseStr in beauties:
            # Get file name and path data
            basefilepath = folderPath + "\\" + baseStr
            addOutputMessage("Rendering, beauty file: " + basefilepath)
            segments = getPattern(baseStr)

            # Load base
            base = loadImgRaw(basefilepath)

            # Denoise
            if (layerData[0][0]):
                denoiser = loadImgRaw(folderPath + "\\" + segments[0] + layersDefaultTuple[0][2] + segments[1])
                if (denoiser != None):
                    base = Image.blend(base, denoiser, layerData[0][1])
                else:
                    addOutputMessage("Failed to load '" + folderPath + "\\" + segments[0] + layersDefaultTuple[0][2] + segments[1] + "', ignoring the layer")

            # Convert base layer to float
            base = imgToFloatData(base)

            # Direct
            base = proceedLayer(1, base, segments, layersDefaultTuple, layerData, soft_light)

            # Indirect
            base = proceedLayer(2, base, segments, layersDefaultTuple, layerData, screen)

            # RawComponent
            base = proceedLayer(3, base, segments, layersDefaultTuple, layerData, soft_light)

            # Reflect
            base = proceedLayer(4, base, segments, layersDefaultTuple, layerData, screen)

            # RawReflect
            base = proceedLayer(5, base, segments, layersDefaultTuple, layerData, soft_light)

            # Refract
            base = proceedLayer(6, base, segments, layersDefaultTuple, layerData, screen)

            # AO
            base = proceedLayer(7, base, segments, layersDefaultTuple, layerData, multiply)

            # Translucency
            base = proceedLayer(8, base, segments, layersDefaultTuple, layerData, screen)

            # Save base
            blended_img = numpy.uint8(base)
            blended_img_raw = Image.fromarray(blended_img)
            if (deleteAlphaLayer):
                blended_img_raw = blended_img_raw.convert("RGB")
            blended_img_raw.save(resFolder + segments[0] + "_Result" + segments[1])
        
        addOutputMessage("Render complete!")
        addOutputMessage("Folder with results: '" + resFolder)

    except:
        addOutputMessage("Unexpected error: " + str(sys.exc_info()[0]))
        addOutputMessage("Interrupting render")


# Convert images to float arrays
def imgToFloatData(img):
    img_as_arr = numpy.array(img)  # Inputs to blend_modes need to be numpy arrays.
    img_as_arr_float = img_as_arr.astype(float)  # Inputs to blend_modes need to be floats.
    return img_as_arr_float

# Load images and convert them to suitable format
def loadImgRaw(filename):
    try:
        img_raw = Image.open(filename)  # RGBA image
    except FileNotFoundError:
        return None
    img_raw = img_raw.convert('RGBA')
    return img_raw

# Get unique parts from file name
def getPattern(beautyStr):
    basePos = beautyStr.find("_01_Beauty")
    return (beautyStr[:basePos], beautyStr[basePos+10:])

# Get all beauty file from file list
def listBeauties(files):
    beauties = []
    for el in files:
        if "_01_Beauty" in el:
            beauties.append(el)
    return beauties

def layers_render_callback(sender, app_data):
    # Get files in folder
    files = [f for f in listdir(folderPath) if isfile(join(folderPath, f))]

    # Get beauty files in folder
    lstbeauties = listBeauties(files)

    # Get data from interface
    enteredLayersData = getEnteredLayersData()

    # Render layers
    renderLayers(lstbeauties, enteredLayersData)

def layers_parse_callback(sender, app_data):
    global folderPath
    folderPath = app_data['file_path_name']
    dpg.show_item("layer_properties_window")
    addOutputMessage("Selected folder: '" + folderPath + "'")

def remove_alpha_callback(sender, app_data):
    global deleteAlphaLayer
    deleteAlphaLayer = app_data

# Folder select window
dpg.add_file_dialog(
    directory_selector=True, show=False, callback=layers_parse_callback, tag="file_dialog_id", width=700 ,height=400)

# Folder select button window
with dpg.window(label="Layers folder", width=200, height=50, pos=(20,20)):
    dpg.add_button(label="Select layers folder", callback=lambda: dpg.show_item("file_dialog_id"))

# Layers properties window
with dpg.window(label="Layer properties", tag="layer_properties_window", width=700, height=350, pos=(300, 20), show=False):
    # Fill table with widgets
    elId = 1
    with dpg.table(header_row=False, resizable=True, borders_innerV=True):
        dpg.add_table_column(width_fixed=True, width=100)
        dpg.add_table_column(width=500)
        for el in (layersDefaultTuple):
            with dpg.table_row():
                dpg.add_checkbox(label="#" + str(elId) + " " + el[0], tag="use" + el[0], default_value=True)
                dpg.add_input_float(tag="alpha"+el[0], min_value=0, max_value=1, default_value=el[1], step=0.05, step_fast=0.1, callback=float_callback)
                elId += 1

    # Buttons for config and render
    with dpg.group(horizontal=True):
        dpg.add_button(label="Save config", callback=save_config_callback)
        dpg.add_button(label="Load config", callback=load_config_callback)
        dpg.add_button(label="Reset to default", callback=reset_to_default_callback)
    dpg.add_checkbox(label="Remove alpha layer", callback=remove_alpha_callback)
    dpg.add_button(label="Run render", callback=layers_render_callback)

# Log window
with dpg.window(label="Log", width=1264, height=250, pos=(0, 430)):
    dpg.add_text(default_value="",tag="outputMessage")

dpg.create_viewport(title='Render blending', width=1280, height=720)
dpg.setup_dearpygui()
dpg.show_viewport()
dpg.start_dearpygui()
dpg.destroy_context()