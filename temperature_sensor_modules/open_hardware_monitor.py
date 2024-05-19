from modules import scripts, shared, errors
from pathlib import Path
import urllib.request
import gradio as gr
import zipfile
import launch
import os

ohm_hardware = None
ohm_computer = None
ohm_sensors = None

OpenHardwareMonitorLibDownloadUrl = "https://openhardwaremonitor.org/files/openhardwaremonitor-v0.9.6.zip"
OpenHardwareMonitor_path = Path(scripts.current_basedir).joinpath('OpenHardwareMonitor')
OpenHardwareMonitorLib_path = OpenHardwareMonitor_path.joinpath('OpenHardwareMonitorLib')
OpenHardwareMonitorLib_dll_path = OpenHardwareMonitor_path.joinpath('OpenHardwareMonitorLib.dll')


def download_open_hardware_monitor():
    if not OpenHardwareMonitorLib_dll_path.is_file():
        OpenHardwareMonitor_path.mkdir(parents=True, exist_ok=True)
        print("Downloading OpenHardwareMonitor")
        zip_path, _ = urllib.request.urlretrieve(OpenHardwareMonitorLibDownloadUrl)
        with zipfile.ZipFile(zip_path, "r") as z:
            with open(os.path.realpath(OpenHardwareMonitorLib_dll_path), 'wb') as f:
                f.write(z.read('OpenHardwareMonitor/OpenHardwareMonitorLib.dll'))


def init_open_hardware_monitor():
    global ohm_computer, ohm_sensors, ohm_hardware
    try:
        # install and import Python.NET module
        if not launch.is_installed("pythonnet"):
            launch.run_pip("install pythonnet==3.0.2", "Installing requirements for OpenHardwareMonitorLib")
        import clr  # noqa import pythonnet module.

        # download OpenHardwareMonitor if not found
        download_open_hardware_monitor()

        # initialize OpenHardwareMonitor
        if ohm_computer is None:
            clr.AddReference(str(OpenHardwareMonitorLib_path))
            from OpenHardwareMonitor.Hardware import Computer  # noqa
            ohm_computer = Computer()
            ohm_computer.CPUEnabled = False  # Disable CPU
            ohm_computer.GPUEnabled = True  # Enable GPU
            ohm_computer.Open()

        # find the first matching temperature sensor for the specified hardware
        if ohm_sensors is None or shared.opts.gpu_temps_sleep_gpu_name not in str(ohm_hardware.Name):
            for hardware in ohm_computer.Hardware:
                if shared.opts.gpu_temps_sleep_gpu_name in str(hardware.Name):
                    for sensor in hardware.Sensors:
                        if '/temperature' in str(sensor.Identifier):
                            ohm_sensors = sensor
                            ohm_hardware = hardware
                            return  # sensor is found early return

        # sensor not found
        ohm_sensors = None
        ohm_hardware = None
        error_message = f"OpenHardwareMonitor Couldn't find temperature sensor for {shared.opts.gpu_temps_sleep_gpu_name}"
        gr.Warning(error_message)
        print(f"[Error GPU temperature protection] {error_message}")

    except Exception as e:
        error_message = f"Failed to initialize OpenHardwareMonitor"
        errors.report(f'[Error GPU temperature protection] {error_message}')


def get_gpu_temperature_open_hardware_monitor():
    try:
        ohm_hardware.Update()
        return int(ohm_sensors.get_Value())
    except Exception as e:
        print(f"\n[Error GPU temperature protection] OpenHardwareMonitor: Couldn't read temperature{e}")
    return 0
