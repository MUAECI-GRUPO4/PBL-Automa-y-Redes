"""Utilidades para manejar la VM de TIA: capturas y clics (QMP input-send-event, ejes abs 0-32767)."""
import json, subprocess, sys, time
DOM = ['virsh', '-c', 'qemu:///system']
W, H = 1920, 1200

def qmp(cmd):
    return subprocess.run(DOM + ['qemu-monitor-command', 'tia-portal', '--cmd', json.dumps(cmd)], capture_output=True, text=True).stdout

def _abs(x, y):
    return int(x / W * 32767), int(y / H * 32767)

def move(x, y):
    ax, ay = _abs(x, y)
    qmp({"execute": "input-send-event", "arguments": {"events": [
        {"type": "abs", "data": {"axis": "x", "value": ax}}, {"type": "abs", "data": {"axis": "y", "value": ay}}]}})

def click(x, y, button='left', double=False):
    move(x, y); time.sleep(0.15)
    for _ in range(2 if double else 1):
        for down in (True, False):
            qmp({"execute": "input-send-event", "arguments": {"events": [{"type": "btn", "data": {"down": down, "button": button}}]}})
            time.sleep(0.06)
    time.sleep(0.6)

KEYS = {'esc': 'esc', 'enter': 'ret', 'f2': 'f2'}
def key(k):
    qmp({"execute": "send-key", "arguments": {"keys": [{"type": "qcode", "data": KEYS.get(k, k)}]}})
    time.sleep(0.4)

def shot(path):
    subprocess.run(DOM + ['screenshot', 'tia-portal', path], capture_output=True)

if __name__ == '__main__':
    a = sys.argv[1]
    if a == 'shot': shot(sys.argv[2])
    elif a == 'click': click(float(sys.argv[2]), float(sys.argv[3]), *(sys.argv[4:5] or ['left']))
    elif a == 'key': key(sys.argv[2])
