import os
from pathlib import Path

extensionRootPath = os.path.join(Path().absolute(),'./extensions/stable-diffusion-webui-GPU-temperature-protection/')

# folder path
openHardwareMonitorDirPath = os.path.join(extensionRootPath,'./openHardwareMonitor')

#path to load openHardwareMonitorLib using pythonnet
openHardwareMonitorLibPath = os.path.join(openHardwareMonitorDirPath,'./OpenHardwareMonitorLib',)