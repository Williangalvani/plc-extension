import subprocess

class Device():
  def __init__(self, raw_str):
    # str is in the format:
    # LOC STA 003 00:03:9A:FB:AB:93 56:E1:6C:83:74:E0 n/a n/a QCA6410 MAC-QCA6410-1.1.0.852-03-20130128-FINAL
    self.mac = raw_str.split()[3]
    self.firmware = raw_str.split()[8]
    self.node = raw_str.split()[2]
    local = raw_str.split()[0]
    self.is_local = local == "LOC"

  def __repr__(self):
    return f"{self.node} {self.mac} {self.firmware} {self.is_local}"



class PlcTester:

    def __init__(self):
        # TODO: auto-detect or try all
        self.interface = "eth0"
        self.devices = self.detect_devices()


    def detect_devices(self):
        command = f"plcstat -t -i {self.interface}"
        raw_output = subprocess.check_output(command, shell=True).decode()
        entries = raw_output.splitlines()[1:]
        self.local = None
        self.remote = None
        self.devices = []
        for entry in entries:
            self.devices.append(Device(entry))
            
        if len(entries) >= 1:
            self.local = Device(entries[0])
        if len(entries) >= 2:
            self.remote = Device(entries[1])
        return self.devices

    def read_tonemap(self):
        command = f"plctone -i {self.interface} -q {self.local.mac} {self.remote.mac}"
        raw_output = subprocess.check_output(command, shell=True).decode()
        output = []
        for line in raw_output.splitlines():
            offset = int(line.split(",")[0])
            tone = int(line.split(" ")[1])
            output.append((offset, tone))
        return output

    def read_rates(self):
        command = f"plcrate -q -i {self.interface} -q {self.local.mac} {self.remote.mac}"
        raw_output = subprocess.check_output(command, shell=True).decode()
        output = []
        
        for line in raw_output.splitlines():
            if "TX" in line:
                rate = int(line.split("TX")[1].split()[0])
                output.append(rate)
            if "RX" in line:
                rate = int(line.split("RX")[1].split()[0])
                output.append(rate)
        return output

if __name__ == "__main__": 
    tester = PlcTester()
    print(tester.devices)
    print(tester.read_tonemap())
    print(tester.read_bw())