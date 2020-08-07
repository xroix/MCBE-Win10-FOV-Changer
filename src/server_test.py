import time
import string

import pypresence

import pymem
from pymem.ptypes import RemotePointer

server_p = [0x036DB9B8, 0x8, 0x8, 0x1F8, 0x4F0, 0x18, 0x50, 0x370]
client_id = "733376215737434204"


def read_p(manager: pymem.Pymem, pointer):
    # Find the address
    temp = RemotePointer(manager.process_handle, manager.process_base.lpBaseOfDll + pointer[0])

    for offset in pointer[1:-1]:
        temp = RemotePointer(manager.process_handle, temp.value + offset)

    return temp.value + pointer[-1]


pm = pymem.Pymem()
pm.open_process_from_name("Minecraft.Windows.exe")

rpc = pypresence.Presence(client_id=client_id)
rpc.connect()


def update_presence(state):
    rpc.update(state=state, large_image="mc", large_text="Minecraft Bedrock",
               small_image="logo-full", small_text="Using FOV Changer",
               start=int(time.time()))


def is_domain(domain: str):
    if "." not in domain or not set(domain).issubset(set(string.ascii_letters + string.digits + "-.")):
        return False

    return True


def get_server():
    # The main address
    addr = read_p(pm, server_p)
    print(f"Original address: {hex(addr)}")

    # and its text
    try:
        original_text = pm.read_string(addr, 253)
        print(f"Original text: {original_text}")

    except (pymem.exception.MemoryReadError, UnicodeDecodeError):
        original_text = None
        print("Original address is invalid, cant be read!")

    print()

    # However it can change ...
    guess = pm.read_uint(addr)
    guess2 = pm.read_uint(addr + 0x4)
    print(f"Guesses: {hex(guess)}, {hex(guess2)}")

    # So that's the alternate address
    alternate_addr = int(str(hex(guess2))[2:] + str(hex(guess))[2:], 16)
    print(f"Alternate address: {hex(alternate_addr)}")

    # and its address
    try:
        alternate_text = pm.read_string(alternate_addr, 253)
        print(f"Alternate text: {alternate_text}")

    except pymem.exception.MemoryReadError:
        alternate_text = None
        print("Alternate address is invalid, cant be read!")

    print()

    # So choose
    if original_text and not alternate_text:
        return original_text

    elif not original_text and alternate_text:
        return alternate_text

    else:
        return None


while True:
    server = get_server()

    if server:
        update_presence(f"Playing on {server}")

    else:
        update_presence("Idle")

    time.sleep(15)
# print(pm.read_string(0x273A186AF60, 253))
