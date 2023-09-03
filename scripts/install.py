import launch
import os


# install pythonnet required for openHardwareMonitor Lib
if not launch.is_installed("pythonnet") and os.name == 'nt':
    launch.run_pip("install pythonnet==3.0.2", "requirements for windows OpenHardwareMonitorLib")