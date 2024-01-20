from temperature_sensor_modules import nvidia_smi, amd_rocm_smi, open_hardware_monitor
from modules import scripts, shared, sd_samplers_common, patches, script_callbacks, errors
from typing import Callable
import gradio as gr
import subprocess
import time
import re
import os

temperature_func: Callable[[], float]
temperature_src_dict = {
    "NVIDIA - nvidia-smi": nvidia_smi.get_gpu_temperature_nvidia_smi,
    "AMD - ROCm-smi": amd_rocm_smi.get_gpu_temperature_amd_rocm_smi,
    "NVIDIA & AMD - OpenHardwareMonitor": open_hardware_monitor.get_gpu_temperature_open_hardware_monitor
}


def init_temps_src():
    global temperature_func
    temperature_func = temperature_src_dict.get(shared.opts.gpu_temps_sleep_temperature_src, nvidia_smi.get_gpu_temperature_nvidia_smi)
    if shared.opts.gpu_temps_sleep_temperature_src == 'NVIDIA & AMD - OpenHardwareMonitor':
        if os.name != 'nt':
            assert False, "NVIDIA & AMD - OpenHardwareMonitor it's only supported on Windows"
        open_hardware_monitor.init_open_hardware_monitor()
    elif shared.opts.gpu_temps_sleep_temperature_src == 'AMD - ROCm-smi' and os.name == 'nt':
        assert False, "AMD - ROCm-smi is not supported on Windows"


if hasattr(shared, "OptionHTML"):  # < 1.6.0 support
    shared.options_templates.update(shared.options_section(('GPU_temperature_protection', "GPU Temperature"), {
        "gpu_temps_sleep_temperature_src_explanation": shared.OptionHTML("""<b>NVIDIA - nvidia-smi</b> available on both Windows and Linux.<br>
<b>AMD - ROCm-smi</b> - Linux only and does not support specifying GPU device index.<br>
<b>NVIDIA & AMD - OpenHardwareMonitor</b> - Windows only supports NVIDIA and AMD.""")}))


shared.options_templates.update(shared.options_section(('GPU_temperature_protection', "GPU Temperature"), {
    "gpu_temps_sleep_temperature_src": shared.OptionInfo("NVIDIA - nvidia-smi", "Temperature source", gr.Radio, {"choices": list(temperature_src_dict.keys())}, init_temps_src),
}))

if os.name == 'nt':
    try:
        all_lines = subprocess.check_output(['cmd.exe', '/c', 'wmic path win32_VideoController get name']).decode().strip("\nName").splitlines()
        video_controller_filter = re.compile(r"^\s+$")
        names_list = [name.strip() for name in all_lines if not video_controller_filter.match(name) and name != '']
        shared.options_templates.update(shared.options_section(('GPU_temperature_protection', "GPU Temperature"), {
            "gpu_temps_sleep_gpu_name": shared.OptionInfo("None" if len(names_list) == 0 else names_list[0], "GPU Name - OpenHardwareMonitor", gr.Radio, {"choices": names_list}, init_temps_src).info("select your gpu"),
        }))
    except Exception as e:
        if shared.opts.gpu_temps_sleep_temperature_src == 'NVIDIA & AMD - OpenHardwareMonitor':
            print(f'[Error GPU temperature protection] Failed to retrieve list of video controllers: \n{e}')

shared.options_templates.update(shared.options_section(('GPU_temperature_protection', "GPU Temperature"), {
    "gpu_temps_sleep_gpu_index": shared.OptionInfo(0, "GPU device index - nvidia-smi", gr.Number, {"precision": 0}).info("selecting the correct temperature reading for multi GPU systems, for systems with 3 gpus the value should be an integer between 0~2, default 0"),
    "gpu_temps_sleep_enable": shared.OptionInfo(True, "Enable GPU temperature protection"),
    "gpu_temps_sleep_print": shared.OptionInfo(True, "Print GPU Core temperature while sleeping in terminal"),
    "gpu_temps_sleep_minimum_interval": shared.OptionInfo(5.0, "GPU temperature monitor minimum interval", gr.Number).info("won't check the temperature again until this amount of seconds have passed"),
    "gpu_temps_sleep_sleep_time": shared.OptionInfo(1.0, "Sleep Time", gr.Number).info("seconds to pause before checking temperature again"),
    "gpu_temps_sleep_max_sleep_time": shared.OptionInfo(10.0, "Max sleep Time", gr.Number).info("max number of seconds that it's allowed to pause, 0=unlimited"),
    "gpu_temps_sleep_sleep_temp": shared.OptionInfo(75.0, "GPU sleep temperature", gr.Slider, {"minimum": 0, "maximum": 125}).info("generation will pause if GPU core temperature exceeds this temperature"),
    "gpu_temps_sleep_wake_temp": shared.OptionInfo(75.0, "GPU wake temperature", gr.Slider, {"minimum": 0, "maximum": 125}).info("generation will pause until GPU core temperature drops below this temperature"),
}))


class TemperatureProtection:
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

    def temperature_protection(self):
        if not shared.opts.gpu_temps_sleep_enable:
            return

        global last_call_time
        call_time = time.time()
        if call_time - last_call_time < shared.opts.gpu_temps_sleep_minimum_interval:
            return

        gpu_core_temp = temperature_func()
        if gpu_core_temp > self.sleep_temp:
            if shared.opts.gpu_temps_sleep_print:
                print(f'\n\nGPU Temperature: {gpu_core_temp}')
            time.sleep(shared.opts.gpu_temps_sleep_sleep_time)
            gpu_core_temp = temperature_func()
            while (gpu_core_temp > self.wake_temp
                   and (not self.max_sleep_time or self.max_sleep_time > time.time() - call_time)
                   and shared.opts.gpu_temps_sleep_enable):
                if shared.opts.gpu_temps_sleep_print:
                    print(f'GPU Temperature: {gpu_core_temp}')
                if shared.state.interrupted or shared.state.skipped:
                    break
                time.sleep(shared.opts.gpu_temps_sleep_sleep_time)
                gpu_core_temp = temperature_func()
            last_call_time = time.time()
        else:
            last_call_time = call_time


def gpu_temperature_protection_decorator(fun, config):
    def wrapper(*args, **kwargs):
        config.temperature_protection()
        result = fun(*args, **kwargs)
        return result
    return wrapper


def patch_temperature_protection(obj, field, config):
    try:
        patches.patch(__name__, obj, field, gpu_temperature_protection_decorator(sd_samplers_common.store_latent, config))

        def undo_hijack():
            patches.undo(__name__, obj, field)

        script_callbacks.on_script_unloaded(undo_hijack)
    except RuntimeError:
        errors.report(f"patch_temperature_protection {field} is already applied")


config_store_latent = TemperatureProtection(
        'gpu_temps_sleep_sleep_temp',
        'gpu_temps_sleep_wake_temp',
        'gpu_temps_sleep_max_sleep_time',
)


patch_temperature_protection(sd_samplers_common, 'store_latent', config_store_latent)
last_call_time = time.time()
init_temps_src()
