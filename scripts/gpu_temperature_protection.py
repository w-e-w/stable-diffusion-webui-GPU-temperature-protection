from modules import scripts, shared, sd_samplers_common
from pathlib import Path
import urllib.request
import gradio as gr
import subprocess
import zipfile
import launch
import time
import re
import os

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


class TemperatureConfig:
    def __init__(self, sleep_temp, wake_temp, max_sleep_time):
        self.sleep_temp_key = sleep_temp
        self.wake_temp_key = wake_temp
        self.max_sleep_time_key = max_sleep_time

    @property
    def sleep_temp(self):
        return getattr(shared.opts, self.sleep_temp_key)

    @property
    def wake_temp(self):
        return getattr(shared.opts, self.wake_temp_key)

    @property
    def max_sleep_time(self):
        return getattr(shared.opts, self.max_sleep_time_key)


class GPUTemperatureProtection(scripts.Script):
    temperature_func = None

    def title(self):
        return "GPU temperature protection"

    def show(self, is_img2img):
        return scripts.AlwaysVisible

    def setup(self, p, *args):
        if shared.opts.gpu_temps_sleep_enable:
            GPUTemperatureProtection.temperature_func = GPUTemperatureProtection.get_temperature_src_function(shared.opts.gpu_temps_sleep_temperature_src)
            sd_samplers_common.store_latent = GPUTemperatureProtection.gpu_temperature_protection_decorator(sd_samplers_common.store_latent)
            p.close = GPUTemperatureProtection.gpu_temperature_close_decorator(p.close)

    @staticmethod
    def get_gpu_temperature_nvidia_smi():
        try:
            return int(subprocess.check_output(
                ['nvidia-smi', '--query-gpu=temperature.gpu', '--format=csv,noheader']).decode().strip().splitlines()[shared.opts.gpu_temps_sleep_gpu_index])
        except subprocess.CalledProcessError as e:
            print(f"\n[Error GPU temperature protection] nvidia-smi: {e.output.decode('utf-8').strip()}")
        except Exception as e:
            print(f'\n[Error GPU temperature protection] nvidia-smi: {e}')
        return 0

    amd_rocm_smi_regex = re.compile(r'Temperature \(Sensor edge\) \(C\): (\d+\.\d+)')

    @staticmethod
    def get_gpu_temperature_amd_rocm_smi():
        try:
            output = subprocess.check_output(['rocm-smi', '--showtemp']).decode().strip()
            match = GPUTemperatureProtection.amd_rocm_smi_regex.search(output)
            if match:
                return int(float(match.group(1)))
            else:
                print("\n[Error GPU temperature protection]: Couldn't parse temperature from rocm-smi output")
        except subprocess.CalledProcessError as e:
            print(f"\n[Error GPU temperature protection] rocm-smi: {e.output.decode('utf-8').strip()}")
        except Exception as e:
            print(f'\n[Error GPU temperature protection] rocm-smi: {e}')
        return 0

    computer = None
    sensors = None
    hardware = None

    @staticmethod
    def init_open_hardware_monitor():
        try:
            # install and import Python.NET module
            if not launch.is_installed("pythonnet"):
                launch.run_pip("install pythonnet==3.0.2", "Installing requirements for OpenHardwareMonitorLib")
            import clr  # noqa import pythonnet module.

            # download OpenHardwareMonitor if not found
            download_open_hardware_monitor()

            # initialize OpenHardwareMonitor
            if GPUTemperatureProtection.computer is None:
                clr.AddReference(str(OpenHardwareMonitorLib_path))
                from OpenHardwareMonitor.Hardware import Computer  # noqa
                GPUTemperatureProtection.computer = Computer()
                GPUTemperatureProtection.computer.CPUEnabled = False  # Disable CPU
                GPUTemperatureProtection.computer.GPUEnabled = True  # Enable GPU
                GPUTemperatureProtection.computer.Open()

            # find the first matching temperature sensor for the specified hardware
            if GPUTemperatureProtection.sensors is None or shared.opts.gpu_temps_sleep_gpu_name not in str(GPUTemperatureProtection.hardware.Name):
                for hardware in GPUTemperatureProtection.computer.Hardware:
                    if shared.opts.gpu_temps_sleep_gpu_name in str(hardware.Name):
                        for sensor in hardware.Sensors:
                            if '/temperature' in str(sensor.Identifier):
                                GPUTemperatureProtection.sensors = sensor
                                GPUTemperatureProtection.hardware = hardware
                                return  # sensor is found early return

            # sensor not found
            GPUTemperatureProtection.sensors = None
            GPUTemperatureProtection.hardware = None
            print(f"[Error GPU temperature protection] OpenHardwareMonitor Couldn't find temperature sensor for {shared.opts.gpu_temps_sleep_gpu_name}")

        except Exception as e:
            print(f"[Error GPU temperature protection] Failed to initialize OpenHardwareMonitor: {e}")

    @staticmethod
    def get_gpu_temperature_open_hardware_monitor():
        try:
            GPUTemperatureProtection.hardware.Update()
            return int(GPUTemperatureProtection.sensors.get_Value())
        except Exception as e:
            print(f"\n[Error GPU temperature protection] OpenHardwareMonitor: Couldn't read temperature{e}")
        return 0

    @staticmethod
    def on_change_temps_src():
        if shared.opts.gpu_temps_sleep_temperature_src == 'NVIDIA & AMD - OpenHardwareMonitor':
            if os.name == 'nt':
                GPUTemperatureProtection.init_open_hardware_monitor()
            else:
                assert False, "NVIDIA & AMD - OpenHardwareMonitor it's only supported on Windows"
        elif shared.opts.gpu_temps_sleep_temperature_src == 'AMD - ROCm-smi' and os.name == 'nt':
            assert False, "AMD - ROCm-smi is not supported on Windows"

    temperature_src_dict = {
        "NVIDIA - nvidia-smi": get_gpu_temperature_nvidia_smi,
        "AMD - ROCm-smi": get_gpu_temperature_amd_rocm_smi,
        "NVIDIA & AMD - OpenHardwareMonitor": get_gpu_temperature_open_hardware_monitor
    }

    @staticmethod
    def get_temperature_src_function(source_name):
        return GPUTemperatureProtection.temperature_src_dict.get(source_name, GPUTemperatureProtection.get_gpu_temperature_nvidia_smi)

    @staticmethod
    def gpu_temperature_protection(config: TemperatureConfig):
        if shared.opts.gpu_temps_sleep_enable:
            call_time = time.time()
            if call_time - GPUTemperatureProtection.last_call_time > shared.opts.gpu_temps_sleep_minimum_interval:
                gpu_core_temp = GPUTemperatureProtection.temperature_func()
                if gpu_core_temp > config.sleep_temp:
                    if shared.opts.gpu_temps_sleep_print:
                        print(f'\n\nGPU Temperature: {gpu_core_temp}')
                    time.sleep(shared.opts.gpu_temps_sleep_sleep_time)
                    gpu_core_temp = GPUTemperatureProtection.temperature_func()
                    while (gpu_core_temp > shared.opts.gpu_temps_sleep_wake_temp
                           and (not config.max_sleep_time or config.max_sleep_time > time.time() - call_time)
                           and shared.opts.gpu_temps_sleep_enable):
                        if shared.opts.gpu_temps_sleep_print:
                            print(f'GPU Temperature: {gpu_core_temp}')
                        if shared.state.interrupted or shared.state.skipped:
                            break
                        time.sleep(shared.opts.gpu_temps_sleep_sleep_time)
                        gpu_core_temp = GPUTemperatureProtection.temperature_func()

                    GPUTemperatureProtection.last_call_time = time.time()
                else:
                    GPUTemperatureProtection.last_call_time = call_time

    @staticmethod
    def gpu_temperature_protection_decorator(fun):
        config = TemperatureConfig(
            'gpu_temps_sleep_sleep_temp',
            'gpu_temps_sleep_wake_temp',
            'gpu_temps_sleep_max_sleep_time',
        )

        def wrapper(*args, **kwargs):
            GPUTemperatureProtection.gpu_temperature_protection(config)
            result = fun(*args, **kwargs)
            return result
        return wrapper

    @staticmethod
    def gpu_temperature_close_decorator(fun):
        def wrapper(*args, **kwargs):
            sd_samplers_common.store_latent = GPUTemperatureProtection.pre_decorate_store_latent
            result = fun(*args, **kwargs)
            return result
        return wrapper

    last_call_time = time.time()
    pre_decorate_store_latent = sd_samplers_common.store_latent


if hasattr(shared, "OptionHTML"):  # < 1.6.0 support
    shared.options_templates.update(shared.options_section(('GPU_temperature_protection', "GPU Temperature"), {
        "gpu_temps_sleep_temperature_src_explanation": shared.OptionHTML("""<b>NVIDIA - nvidia-smi</b> is available on both Windows and Linux.<br>
<b>AMD - ROCm-smi</b> is Linux only and does not support specifying GPU device index.<br>
<b>NVIDIA & AMD - OpenHardwareMonitor</b> is Windows only supports NVIDIA and AMD.
        """)
    }))


shared.options_templates.update(shared.options_section(('GPU_temperature_protection', "GPU Temperature"), {
    "gpu_temps_sleep_temperature_src": shared.OptionInfo("NVIDIA - nvidia-smi", "Temperature source", gr.Radio, {"choices": list(GPUTemperatureProtection.temperature_src_dict.keys())}, GPUTemperatureProtection.on_change_temps_src),
    "gpu_temps_sleep_enable": shared.OptionInfo(True, "Enable GPU temperature protection"),
    "gpu_temps_sleep_print": shared.OptionInfo(True, "Print GPU Core temperature while sleeping in terminal"),
    "gpu_temps_sleep_minimum_interval": shared.OptionInfo(5.0, "GPU temperature monitor minimum interval", gr.Number).info("won't check the temperature again until this amount of seconds have passed"),
    "gpu_temps_sleep_sleep_time": shared.OptionInfo(1.0, "Sleep Time", gr.Number).info("seconds to pause before checking temperature again"),
    "gpu_temps_sleep_max_sleep_time": shared.OptionInfo(10.0, "Max sleep Time", gr.Number).info("max number of seconds that it's allowed to pause, 0=unlimited"),
    "gpu_temps_sleep_sleep_temp": shared.OptionInfo(75.0, "GPU sleep temperature", gr.Slider, {"minimum": 0, "maximum": 125}).info("generation will pause if GPU core temperature exceeds this temperature"),
    "gpu_temps_sleep_wake_temp": shared.OptionInfo(75.0, "GPU wake temperature", gr.Slider, {"minimum": 0, "maximum": 125}).info("generation will pause until GPU core temperature drops below this temperature"),
    "gpu_temps_sleep_gpu_index": shared.OptionInfo(0, "GPU device index - nvidia-smi", gr.Number, {"precision": 0}).info("selecting the correct temperature reading for multi GPU systems, for systems with 3 gpus the value should be an integer between 0~2, default 0"),
}))

if os.name == 'nt':
    try:
        all_lines = subprocess.check_output(['cmd.exe', '/c', 'wmic path win32_VideoController get name']).decode().strip("\nName").splitlines()
        video_controller_filter = re.compile(r"^\s+$")
        names_list = [name.strip() for name in all_lines if not video_controller_filter.match(name) and name != '']
        shared.options_templates.update(shared.options_section(('GPU_temperature_protection', "GPU Temperature"), {
            "gpu_temps_sleep_gpu_name": shared.OptionInfo("None" if len(names_list) == 0 else names_list[0], "GPU Name - OpenHardwareMonitor", gr.Radio, {"choices": names_list}, GPUTemperatureProtection.on_change_temps_src).info("select your gpu"),
        }))
    except Exception as _e:
        if shared.opts.gpu_temps_sleep_temperature_src == 'NVIDIA & AMD - OpenHardwareMonitor':
            print(f'[Error GPU temperature protection] Failed to retrieve list of video controllers: \n{_e}')

if shared.opts.gpu_temps_sleep_temperature_src == 'NVIDIA & AMD - OpenHardwareMonitor':
    GPUTemperatureProtection.init_open_hardware_monitor()
