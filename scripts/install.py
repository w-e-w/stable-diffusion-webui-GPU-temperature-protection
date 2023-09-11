import launch
import os
from pathlib import Path
from scripts import constant,settings_storage
import urllib
import zipfile


def downloadOpenHardwareMonitorLib():
    zip_path, _ = urllib.request.urlretrieve(constant.OpenHardwareMonitorLibDownloadUrl)
    with zipfile.ZipFile(zip_path, "r") as z:
        with open(os.path.realpath(constant.OpenHardwareMonitorLibdllFilePath) , 'wb') as f:
            f.write(z.read('OpenHardwareMonitor/OpenHardwareMonitorLib.dll'))

# install pythonnet required for openHardwareMonitor Lib
# shared.opts.gpu_temps_sleep_temperature_src == 'NVIDIA & AMD - openHardwareMonitor' and
if  os.name == 'nt'  :
  
    if settings_storage.settingsStorage.get("gpu_temps_sleep_temperature_src") == "NVIDIA & AMD - openHardwareMonitor":
        if not launch.is_installed("pythonnet"):
            launch.run_pip("install pythonnet==3.0.2", "requirements for windows OpenHardwareMonitorLib")
        
        # check and create OpenHardwareMonitor folder
        Path(constant.openHardwareMonitorDirPath).mkdir(parents=True, exist_ok=True)

        
