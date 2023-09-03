import launch
import os
from modules import shared
from pathlib import Path
from scripts import constant
import urllib
import zipfile

# install pythonnet required for openHardwareMonitor Lib
if shared.opts.gpu_temps_sleep_temperature_src == 'NVIDIA & AMD - openHardwareMonitor' and os.name == 'nt':
    if not launch.is_installed("pythonnet"):
        launch.run_pip("install pythonnet==3.0.2", "requirements for windows OpenHardwareMonitorLib")
    
    # check and create OpenHardwareMonitor folder
    Path(constant.openHardwareMonitorDirPath).mkdir(parents=True, exist_ok=True)

    # check is OpenHardwareMonitorLib exist if not will download 
    if not os.path.isfile(constant.OpenHardwareMonitorLibdllFilePath):
        zip_path, _ = urllib.request.urlretrieve(constant.OpenHardwareMonitorLibDownloadUrl)
        with zipfile.ZipFile(zip_path, "r") as z:
            with open(os.path.realpath(constant.OpenHardwareMonitorLibdllFilePath) , 'wb') as f:
                f.write(z.read('OpenHardwareMonitor/OpenHardwareMonitorLib.dll'))
