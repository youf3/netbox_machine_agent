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

def get_speed(iface):
    out,err = run_command('ethtool ' + iface)
    if err != None:
        if err == 'Cannot get wake-on-lan settings: Operation not permitted\n':
            pass
        else:
            raise Exception('Failed to run ethtool : {}'.format(err))
    
    for line in out.split('\n'):
        if 'Speed: ' in line:
            speed = line.split(':')[1].replace('Mb/s','')
            speed = int(speed)            
            return speed
    raise Exception('NIC speed not found')    

def get_form_factor(iface):
    out,err = run_command('sudo ethtool -m ' + iface)
    if 'Cannot get module EEPROM information' in err:
        raise Exception(err)
    for line in out.split('\n'):
        if 'Identifier                                :' in line:
            formfactor = line.split(" ")[-1]            
            return formfactor[1:-1]
    raise Exception('Cannot find the formfactor')

def get_formfactor_id(ifname):
    speed = formfactor = None

    try:
        speed = get_speed(ifname)
        formfactor = get_form_factor(ifname)
    except Exception:
        pass

    if speed == None: return 0
    elif formfactor == None:
        if speed == 1000: return 1000
        else: return 800
    elif formfactor == 'SFP':  return 1100
    elif formfactor == 'QSFP28' : return 1600
    else : return 0

if __name__ == "__main__":
    pass