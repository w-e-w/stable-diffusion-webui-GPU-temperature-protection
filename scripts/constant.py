import os
from pathlib import Path

#OpenHardwareMonitorLib download url
OpenHardwareMonitorLibDownloadUrl = "https://openhardwaremonitor.org/files/openhardwaremonitor-v0.9.6.zip"

extensionRootPath = os.path.join(Path().absolute(),'./extensions/stable-diffusion-webui-GPU-temperature-protection/')

# folder path
openHardwareMonitorDirPath = os.path.join(extensionRootPath,'./openHardwareMonitor')

#path to load openHardwareMonitorLib using pythonnet
openHardwareMonitorLibPath = os.path.join(openHardwareMonitorDirPath,'./OpenHardwareMonitorLib',)

#dll path need for openhardwaremonitor zip extact
OpenHardwareMonitorLibdllFilePath = os.path.join(openHardwareMonitorDirPath,'./OpenHardwareMonitorLib.dll')