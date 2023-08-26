from modules.sd_samplers_kdiffusion import KDiffusionSampler
from modules import scripts, shared
import gradio as gr
import subprocess
import time
import re

if hasattr(shared, "OptionHTML"):  # < 1.6.0 support
    shared.options_templates.update(shared.options_section(('GPU_temperature_protection', "GPU Temperature"), {
        "gpu_temps_sleep_temperature_src_explanation": shared.OptionHTML("""<b>NVIDIA - nvidia-smi</b> is available on Windows and Linux.<br>
<b>AMD - ROCm-smi</b> is Linux only
        """)
    }))

shared.options_templates.update(shared.options_section(('GPU_temperature_protection', "GPU Temperature"), {
    "gpu_temps_sleep_temperature_src": shared.OptionInfo("NVIDIA - nvidia-smi", "Temperature source mode", gr.Radio, {"choices": ["NVIDIA - nvidia-smi", "AMD - ROCm-smi"]}),
    "gpu_temps_sleep_enable": shared.OptionInfo(True, "Enable GPU temperature protection"),
    "gpu_temps_sleep_print": shared.OptionInfo(True, "Print GPU Core temperature while sleeping in terminal"),
    "gpu_temps_sleep_minimum_interval": shared.OptionInfo(5.0, "GPU temperature monitor minimum interval", gr.Number).info("won't check the temperature again until this amount of seconds have passed"),
    "gpu_temps_sleep_sleep_time": shared.OptionInfo(1.0, "Sleep Time", gr.Number).info("seconds to pause before checking temperature again"),
    "gpu_temps_sleep_max_sleep_time": shared.OptionInfo(10.0, "Max sleep Time", gr.Number).info("max number of seconds that it's allowed to pause, 0=unlimited"),
    "gpu_temps_sleep_sleep_temp": shared.OptionInfo(75.0, "GPU sleep temperature", gr.Slider, {"minimum": 0, "maximum": 125}).info("generation will pause if GPU core temperature exceeds this temperature"),
    "gpu_temps_sleep_wake_temp": shared.OptionInfo(75.0, "GPU wake temperature", gr.Slider, {"minimum": 0, "maximum": 125}).info("generation will pause until GPU core temperature drops below this temperature"),
    "gpu_temps_sleep_gpu_index": shared.OptionInfo(0, "GPU device index", gr.Number, {"precision": 0}).info("selecting the correct temperature reading for multi GPU systems, for systems with 3 gpus the value should be an integer between 0~2, default 0"),
}))


class GPUTemperatureProtection(scripts.Script):
    def title(self):
        return "GPU temperature protection"

    def show(self, is_img2img):
        return scripts.AlwaysVisible

    def process(self, p, *args):
        if shared.opts.gpu_temps_sleep_enable:
            setattr(KDiffusionSampler, "callback_state", GPUTemperatureProtection.gpu_temperature_protection_decorator(
                KDiffusionSampler.callback_state,
                GPUTemperatureProtection.get_temperature_src_function(shared.opts.gpu_temps_sleep_temperature_src)
            ))
            setattr(p, "close", GPUTemperatureProtection.gpu_temperature_close_decorator(p.close))

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

    temperature_src_dict = {
        "NVIDIA - nvidia-smi": get_gpu_temperature_nvidia_smi,
        "AMD - ROCm-smi": get_gpu_temperature_amd_rocm_smi
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
            setattr(KDiffusionSampler, "callback_state", GPUTemperatureProtection.pre_decorate_callback_state)
            result = fun(*args, **kwargs)
            return result
        return wrapper

    last_call_time = time.time()
    pre_decorate_callback_state = KDiffusionSampler.callback_state
