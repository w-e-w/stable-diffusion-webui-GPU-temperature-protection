from modules import shared
import subprocess


def get_gpu_temperature_nvidia_smi():
    try:
        return int(subprocess.check_output(
            ['nvidia-smi', '--query-gpu=temperature.gpu', '--format=csv,noheader']).decode().strip().splitlines()[shared.opts.gpu_temps_sleep_gpu_index])
    except subprocess.CalledProcessError as e:
        print(f"\n[Error GPU temperature protection] nvidia-smi: {e.output.decode('utf-8').strip()}")
    except Exception as e:
        print(f'\n[Error GPU temperature protection] nvidia-smi: {e}')
    return 0
