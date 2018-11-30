import subprocess
import getpass

def run_command(cmd, ignore_stderr = False):
    proc = subprocess.Popen(cmd, shell=True, stdin=subprocess.PIPE, 
    stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        outs, errs = proc.communicate(timeout=2)
    except subprocess.TimeoutExpired:
        if 'sudo: no tty present and no askpass program specified' in str(
            proc.stderr.readline(),'UTF-8'):
            print('To change system parameters, please input sudo password')
            password = getpass.getpass()    
            cmd = cmd.replace('sudo', 'sudo -S')
            proc = subprocess.Popen(cmd, shell=True, stdin=subprocess.PIPE, stdout=subprocess.PIPE, 
                                    stderr=subprocess.PIPE)
            outs, errs = proc.communicate(bytes(password + '\n', 'UTF-8'))
            errs = str(errs,'UTF-8').split('\n')
            for line in errs:
                if '[sudo] password for' in line:
                    errs.remove(line)
            errs = bytes(''.join(errs), 'UTF-8')
            
        elif proc.stderr.readline() == b'':
            outs, errs = proc.communicate()            
        else:
            outs, errs = proc.communicate()
        
    return [str(outs,'UTF-8'), str(errs,'UTF-8')]

def get_hw_linux(hwclass, device_id):
    out, err = run_command('lshw -class ' + hwclass)
    HW_strs = out.split('  *-')
    HWs = []
    

    for HW_str in HW_strs[1:]:
        HW = {}
        for line in HW_str.splitlines()[1:]:
            prop = line.strip().split(':',1)            
            if prop[0] == 'bus info':                 
                prop[1] = str(device_id) + '@' + prop[1].strip()                
            else : prop[1].strip()

            HW[prop[0]] = prop[1]

            if 'driver=nvme' in prop[1]: 
                pci_addr = HW['bus info'].split('@')[-1].replace(':','\:')
                out,err = run_command('cat /sys/bus/pci/devices/{0}/nvme/nvme*/model'.format(pci_addr))
                if err != '':
                    raise Exception('failed to get NVMe model name' + err)
                HW['product'] = out.strip()

        if hwclass == 'cpu':
            HW['description'] = 'Central Processing Unit'
        if 'bus info' in HW:
            HWs.append(HW)    
    return HWs


if __name__ == "__main__":
    pass