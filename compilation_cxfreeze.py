#!/usr/bin/python
# -*- coding: utf-8 -*-

import sys, os, zipfile


# get version number
_version = "unknown version"
for lineBuf in open('OpenMATBC.py', 'r'):
    s = lineBuf.replace(' ','').upper()
    pos = s.find('VERSION="')

    if pos>-1:
        _version = s[9:len(s)-2]
        break

def includedirectory(rootdir, extension):
    for subdir, dirs, files in os.walk(rootdir):
        for file in files:
            filepath = os.path.join(subdir, file)
            if filepath.endswith(extension):
                include_files.extend([(filepath, filepath)])
#############################################################################

include_files = ['config.txt', 'inpout32.dll']

includes = ['PySide2', 'pygame', 'wave', 'numpy', 'numpy.core._methods', 'numpy.lib.format', 'email', 'sounddevice', 'soundfile']

excludes = ['tcl', 'Tkconstants', 'Tkinter']

packages = []

path = []

includedirectory('Helpers', '.py')
includedirectory('Instructions', '.txt')
includedirectory('Plugins', '.py')
includedirectory('Scales', '.txt')
includedirectory('Scenarios', '.txt')
includedirectory('Sounds', '.wav')
includedirectory('Translations', '.txt')
includedirectory('Networking', '.py')

from cx_Freeze import setup, Executable

GUI2Exe_Target_1 = Executable(
   # what to build
   script = "OpenMATBC.py",
   initScript = None,
   base = 'Win32GUI',  # Hide the console
   targetName = "OpenMATBC.exe"
   )
setup(
    name = "OpenMATBC",
    version = _version,
    description = "OpenMATBC",
    author = "Julien Cegarra & Benoit Valery",
    options = {"build_exe": {"includes": includes,
                          "include_files": include_files,
                          "excludes": excludes,
                          "packages": packages,
                          "path": path,
                          "build_exe" : "OpenMATBC"
                          #"create_shared_zip": False,
                          }
            },

    executables = [GUI2Exe_Target_1]
)

# CREATE A ZIP FILE
def zipdir(path, ziph):
    # ziph is zipfile handle
    for root, dirs, files in os.walk(path):
        for file in files:
            ziph.write(os.path.join(root, file))

zipf = zipfile.ZipFile('OpenMATBC_v'+_version+'.zip', 'w', zipfile.ZIP_DEFLATED)
zipdir('OpenMATBC/', zipf)
zipf.close() 