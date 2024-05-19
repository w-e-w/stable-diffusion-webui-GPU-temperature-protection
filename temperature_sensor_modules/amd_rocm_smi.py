import subprocess
import re

amd_rocm_smi_regex = re.compile(r'Temperature \(Sensor edge\) \(C\): (\d+\.\d+)')


def get_gpu_temperature_amd_rocm_smi():
    try:
        output = subprocess.check_output(['rocm-smi', '--showtemp']).decode().strip()
        match = amd_rocm_smi_regex.search(output)
        if match:
            return int(float(match.group(1)))
        else:
            print("\n[Error GPU temperature protection]: Couldn't parse temperature from rocm-smi output")
    except subprocess.CalledProcessError as e:
        print(f"\n[Error GPU temperature protection] rocm-smi: {e.output.decode('utf-8').strip()}")
    except Exception as e:
        print(f'\n[Error GPU temperature protection] rocm-smi: {e}')
    return 0
