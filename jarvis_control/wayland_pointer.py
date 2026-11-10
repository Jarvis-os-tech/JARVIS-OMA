"""One bounded, observed-window click using Wayland's virtual-pointer protocol.

Wire contract: swaywm/wlr-protocols, wlr-virtual-pointer-unstable-v1 (MIT).
No root device, guessed target, or unobserved background click is admitted.
"""
import ctypes as c
import json
import re
import subprocess
import sys
import time

try:
    from .wayland_keyboard import Interface, Message, _function
except ImportError:
    from wayland_keyboard import Interface, Message, _function


def validate_click(address, pid, x, y, button='left', count=1):
    if not re.fullmatch(r'0x[0-9a-fA-F]+',address) or int(address,16)<=0:
        raise ValueError('An exact compositor address is required')
    if type(pid) is not int or pid<=0 or any(type(v) is not int for v in (x,y)):
        raise ValueError('An exact process and integer coordinates are required')
    if button not in ('left','right','middle') or count not in (1,2):
        raise ValueError('Invalid pointer action')


def query(kind):
    result=subprocess.run(['hyprctl','-j',kind],capture_output=True,timeout=2,check=True)
    return json.loads(result.stdout)


def click(address,pid,x,y,button='left',count=1):
    validate_click(address,pid,x,y,button,count)
    def verify():
        windows=query('clients')
        target=next((w for w in windows if w.get('address')==address and w.get('pid')==pid),None)
        active=query('activewindow')
        if not target or active.get('address')!=address or active.get('pid')!=pid:
            raise RuntimeError('Exact target is no longer focused; no further click was dispatched')
        at,size=target.get('at'),target.get('size')
        if not at or not size or not(at[0]<=x<at[0]+size[0] and at[1]<=y<at[1]+size[1]):
            raise RuntimeError('Point is outside the current exact target window')
    verify()
    wl=c.CDLL('libwayland-client.so.0')
    ptr,uint=c.c_void_p,c.c_uint
    connect=_function(wl,'wl_display_connect',ptr,c.c_char_p)
    disconnect=_function(wl,'wl_display_disconnect',None,ptr)
    roundtrip=_function(wl,'wl_display_roundtrip',c.c_int,ptr)
    marshal=_function(wl,'wl_proxy_marshal_flags',ptr,ptr,uint,c.POINTER(Interface),uint,uint)
    listen=_function(wl,'wl_proxy_add_listener',c.c_int,ptr,ptr,ptr)
    registry_i=Interface.in_dll(wl,'wl_registry_interface')
    seat_i=Interface.in_dll(wl,'wl_seat_interface')
    methods=(Message*9)(Message(b'motion',b'uff',None),Message(b'motion_absolute',b'uuuuu',None),
        Message(b'button',b'uuu',None),Message(b'axis',b'uuf',None),Message(b'frame',b'',None),
        Message(b'axis_source',b'u',None),Message(b'axis_stop',b'uu',None),
        Message(b'axis_discrete',b'uufi',None),Message(b'destroy',b'',None))
    pointer_i=Interface(b'zwlr_virtual_pointer_v1',1,9,methods,0,None)
    types=(c.POINTER(Interface)*2)(c.pointer(seat_i),c.pointer(pointer_i))
    create=(Message*2)(Message(b'create_virtual_pointer',b'?on',types),Message(b'destroy',b'',None))
    manager_i=Interface(b'zwlr_virtual_pointer_manager_v1',1,2,create,0,None)
    objects={}
    global_cb=c.CFUNCTYPE(None,ptr,ptr,uint,c.c_char_p,uint)
    remove_cb=c.CFUNCTYPE(None,ptr,ptr,uint)
    @global_cb
    def found(_,registry,name,interface,version):
        if interface==manager_i.name and 'manager' not in objects:
            objects['manager']=marshal(registry,0,c.byref(manager_i),1,0,uint(name),manager_i.name,uint(1),ptr())
    @remove_cb
    def removed(*_):pass
    callbacks=(ptr*2)(c.cast(found,ptr),c.cast(removed,ptr))
    display=connect(None)
    pointer=None
    if not display:raise RuntimeError('Wayland connection failed')
    try:
        registry=marshal(display,1,c.byref(registry_i),1,0,ptr())
        if listen(registry,callbacks,None)!=0 or roundtrip(display)<0 or not objects.get('manager'):
            raise RuntimeError('Desktop virtual pointer protocol is unavailable')
        pointer=marshal(objects['manager'],0,c.byref(pointer_i),1,0,ptr(),ptr())
        if not pointer:raise RuntimeError('Could not create virtual pointer')
        subprocess.run(['hyprctl','dispatch',f'hl.dsp.cursor.move({{ x = {x}, y = {y} }})'],
                       capture_output=True,timeout=2,check=True)
        verify()
        position=query('cursorpos')
        if abs(position.get('x',-10000)-x)>4 or abs(position.get('y',-10000)-y)>4:
            raise RuntimeError('Pointer position changed; click was not dispatched')
        code={'left':272,'right':273,'middle':274}[button]
        for _ in range(count):
            verify()
            for state in (1,0):
                marshal(pointer,2,None,1,0,uint(int(time.monotonic()*1000)&0xffffffff),uint(code),uint(state))
                marshal(pointer,4,None,1,0)
                if roundtrip(display)<0:raise RuntimeError('Pointer delivery outcome is unknown')
                time.sleep(.02)
        time.sleep(.03)
    finally:
        if pointer:
            marshal(pointer,8,None,1,1)
            roundtrip(display)
        disconnect(display)


if __name__=='__main__':
    try:
        if len(sys.argv) not in (6,8) or sys.argv[1]!='--click':raise ValueError('Expected an exact click target')
        click(sys.argv[2],int(sys.argv[3]),int(sys.argv[4]),int(sys.argv[5]),
              sys.argv[6] if len(sys.argv)==8 else 'left',int(sys.argv[7]) if len(sys.argv)==8 else 1)
        print(json.dumps({'status':'dispatched_unverified','verified':False,'route':'wayland_virtual_pointer'}))
    except (OSError,RuntimeError,ValueError,subprocess.SubprocessError) as error:
        print(str(error),file=sys.stderr);sys.exit(1)
