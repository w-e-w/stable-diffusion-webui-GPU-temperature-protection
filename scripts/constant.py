import os
from pathlib import Path

#OpenHardwareMonitorLib download url
OpenHardwareMonitorLibDownloadUrl = "https://openhardwaremonitor.org/files/openhardwaremonitor-v0.9.6.zip"

extensionRootPath = os.path.abspath(os.path.join(Path().absolute(),'./extensions/stable-diffusion-webui-GPU-temperature-protection/'))

#path of settings Storage
settingsStorageJsonPath = os.path.abspath(os.path.join(extensionRootPath,'./settingsStorage.json'))

# folder path
openHardwareMonitorDirPath = os.path.abspath(os.path.join(extensionRootPath,'./openHardwareMonitor'))

#path to load openHardwareMonitorLib using pythonnet
openHardwareMonitorLibPath = os.path.abspath(os.path.join(openHardwareMonitorDirPath,'./OpenHardwareMonitorLib'))

#dll path need for openhardwaremonitor zip extact
OpenHardwareMonitorLibdllFilePath = os.path.abspath(os.path.join(openHardwareMonitorDirPath,'./OpenHardwareMonitorLib.dll'))