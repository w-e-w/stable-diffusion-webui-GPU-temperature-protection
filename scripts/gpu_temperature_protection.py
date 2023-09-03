from modules import scripts, shared, sd_samplers_common
import gradio as gr
import subprocess
import time
import re
import os
from scripts import constant
import launch

if shared.opts.gpu_temps_sleep_temperature_src == 'NVIDIA & AMD - openHardwareMonitor' and os.name == 'nt' and launch.is_installed("pythonnet"):
    import clr # the pythonnet module.
    clr.AddReference(constant.openHardwareMonitorLibPath)
    from OpenHardwareMonitor.Hardware import Computer 


class GPUTemperatureProtection(scripts.Script):
    def title(self):
        return "GPU temperature protection"

    def show(self, is_img2img):
        return scripts.AlwaysVisible

    def setup(self, p, *args):
        if shared.opts.gpu_temps_sleep_enable:
            sd_samplers_common.store_latent = GPUTemperatureProtection.gpu_temperature_protection_decorator(
                sd_samplers_common.store_latent,
                GPUTemperatureProtection.get_temperature_src_function(shared.opts.gpu_temps_sleep_temperature_src)
            )
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
    def get_gpu_temperature_open_hardware_monitor():
        if not launch.is_installed("pythonnet"):
            print("\n[Error GPU temperature protection] openHardwareMonitor : you need restart to install and download requirement")
        if os.name != "nt":
            print("\n[Error GPU temperature protection] openHardwareMonitor : only works on windows")
            return 0
        _computer = GPUTemperatureProtection.computer
        _sensors = GPUTemperatureProtection.sensors
        _hardware = GPUTemperatureProtection.hardware
        try:
            if _computer is None:
                _computer = Computer()
                _computer.CPUEnabled = True # get the Info about CPU
                _computer.GPUEnabled = True # get the Info about GPU
                _computer.Open()
            if _sensors is None:
                for a in range(0, len(_computer.Hardware)):
                    if shared.opts.gpu_temps_sleep_gpu_name in str(_computer.Hardware[a].Name):
                        for b in range(0, len(_computer.Hardware[a].Sensors)):
                            if "/temperature" in str(_computer.Hardware[a].Sensors[b].Identifier):
                                _sensors = _computer.Hardware[a].Sensors[b]
                                _hardware = _computer.Hardware[a]
                if _sensors is None:
                    print("\n[Error GPU temperature protection] openHardwareMonitor : Couldn't read temperature from OpenHardwareMonitorLib")
                    return 0

            _hardware.Update()
            return int(_sensors.get_Value())
        except Exception as e:
            print(f'\n[Error GPU temperature protection] openHardwareMonitor : {e}')
        return 0


    temperature_src_dict = {
        "NVIDIA - nvidia-smi": get_gpu_temperature_nvidia_smi,
        "AMD - ROCm-smi": get_gpu_temperature_amd_rocm_smi,
        "NVIDIA & AMD - openHardwareMonitor": get_gpu_temperature_open_hardware_monitor
    }

    @staticmethod
    def get_temperature_src_function(source_name):
        return GPUTemperatureProtection.temperature_src_dict.get(source_name, GPUTemperatureProtection.get_gpu_temperature_nvidia_smi)

    @staticmethod
    def gpu_temperature_protection(temperature_src_fun):
        if shared.opts.gpu_temps_sleep_enable:
            call_time = time.time()
            if call_time - GPUTemperatureProtection.last_call_time > shared.opts.gpu_temps_sleep_minimum_interval:
                gpu_core_temp = temperature_src_fun()
                if gpu_core_temp > shared.opts.gpu_temps_sleep_sleep_temp:

                    if shared.opts.gpu_temps_sleep_print:
                        print(f'\n\nGPU Temperature: {gpu_core_temp}')

                    time.sleep(shared.opts.gpu_temps_sleep_sleep_time)
                    gpu_core_temp = temperature_src_fun()
                    while gpu_core_temp > shared.opts.gpu_temps_sleep_wake_temp and (not shared.opts.gpu_temps_sleep_max_sleep_time or shared.opts.gpu_temps_sleep_max_sleep_time > time.time() - call_time) and shared.opts.gpu_temps_sleep_enable:
                        if shared.opts.gpu_temps_sleep_print:
                            print(f'GPU Temperature: {gpu_core_temp}')

                        time.sleep(shared.opts.gpu_temps_sleep_sleep_time)
                        gpu_core_temp = temperature_src_fun()

                    GPUTemperatureProtection.last_call_time = time.time()
                else:
                    GPUTemperatureProtection.last_call_time = call_time

    @staticmethod
    def gpu_temperature_protection_decorator(fun, temperature_src_fun):
        def wrapper(*args, **kwargs):
            result = fun(*args, **kwargs)
            GPUTemperatureProtection.gpu_temperature_protection(temperature_src_fun)
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
<b>NVIDIA & AMD - openHardwareMonitor</b> is windows only suport NVIDIA and AMD.
        """)
    }))

shared.options_templates.update(shared.options_section(('GPU_temperature_protection', "GPU Temperature"), {
    "gpu_temps_sleep_temperature_src": shared.OptionInfo("NVIDIA - nvidia-smi", "Temperature source", gr.Radio, {"choices": list(GPUTemperatureProtection.temperature_src_dict.keys())}).needs_restart(),
    "gpu_temps_sleep_enable": shared.OptionInfo(True, "Enable GPU temperature protection"),
    "gpu_temps_sleep_print": shared.OptionInfo(True, "Print GPU Core temperature while sleeping in terminal"),
    "gpu_temps_sleep_minimum_interval": shared.OptionInfo(5.0, "GPU temperature monitor minimum interval", gr.Number).info("won't check the temperature again until this amount of seconds have passed"),
    "gpu_temps_sleep_sleep_time": shared.OptionInfo(1.0, "Sleep Time", gr.Number).info("seconds to pause before checking temperature again"),
    "gpu_temps_sleep_max_sleep_time": shared.OptionInfo(10.0, "Max sleep Time", gr.Number).info("max number of seconds that it's allowed to pause, 0=unlimited"),
    "gpu_temps_sleep_sleep_temp": shared.OptionInfo(75.0, "GPU sleep temperature", gr.Slider, {"minimum": 0, "maximum": 125}).info("generation will pause if GPU core temperature exceeds this temperature"),
    "gpu_temps_sleep_wake_temp": shared.OptionInfo(75.0, "GPU wake temperature", gr.Slider, {"minimum": 0, "maximum": 125}).info("generation will pause until GPU core temperature drops below this temperature"),
    "gpu_temps_sleep_gpu_index": shared.OptionInfo(0, "GPU device index", gr.Number, {"precision": 0}).info("selecting the correct temperature reading for multi GPU systems, for systems with 3 gpus the value should be an integer between 0~2, default 0"),
}))

if os.name == 'nt':
    all_lines = subprocess.check_output(['cmd.exe', '/c', 'wmic path win32_VideoController get name']).decode().strip("\nName").splitlines()
    names_list = [name.rstrip() for name in all_lines if not re.compile("^ +$").match(name) and name != '']
    shared.options_templates.update(shared.options_section(('GPU_temperature_protection', "GPU Temperature"), {
        "gpu_temps_sleep_gpu_name": shared.OptionInfo( "none" if names_list.count() == 0 else names_list[0] , "GPU Name", gr.Radio, {"choices": names_list, "interactive":shared.opts.gpu_temps_sleep_temperature_src == 'NVIDIA & AMD - openHardwareMonitor'  }, refresh=GPUTemperatureProtection.getGPU_Names).info("select your gpu, only for openHardwareMonitor"),
    }))