import subprocess

from pydantic import BaseModel

class Device(BaseModel):
  mac: str
  firmware: str
  node: str
  is_local: bool

  @staticmethod
  def from_str(raw_str):
      # str is in the format:
      # LOC STA 003 00:03:9A:FB:AB:93 56:E1:6C:83:74:E0 n/a n/a QCA6410 MAC-QCA6410-1.1.0.852-03-20130128-FINAL
      print(raw_str)
      mac = raw_str.split()[3]
      firmware = raw_str.split()[8]
      node = raw_str.split()[2]
      local = raw_str.split()[0]
      is_local = local == "LOC"
      return Device(mac=mac, firmware=firmware, node=node, is_local=is_local)


  def __repr__(self):
    return f"{self.node} {self.mac} {self.firmware} {self.is_local}"



class PlcTester:

    def __init__(self):
        # TODO: auto-detect or try all
        self.interface = "eth0"
        self.devices = self.detect_devices()


    def detect_devices(self):
        try:
            command = f"plcstat -t -i {self.interface}"
            raw_output = subprocess.check_output(command, shell=True, stderr=subprocess.STDOUT).decode()
            entries = raw_output.splitlines()[1:]
            self.local = None
            self.remote = None
            self.devices = []
            for entry in entries:
                if entry.strip():  # Skip empty lines
                    self.devices.append(Device.from_str(entry))
                
            if len(entries) >= 1:
                self.local = Device.from_str(entries[0])
            if len(entries) >= 2:
                self.remote = Device.from_str(entries[1])
            return self.devices
        except subprocess.CalledProcessError as e:
            print(f"Error running plcstat: {e}")
            self.local = None
            self.remote = None
            self.devices = []
            return self.devices
        except Exception as e:
            print(f"Unexpected error in detect_devices: {e}")
            self.local = None
            self.remote = None
            self.devices = []
            return self.devices

    def read_tonemap(self):
        if not self.local or not self.remote:
            return None
        try:
            command = f"plctone -i {self.interface} -q {self.local.mac} {self.remote.mac}"
            raw_output = subprocess.check_output(command, shell=True, stderr=subprocess.STDOUT).decode()
            output = []
            for line in raw_output.splitlines():
                if line.strip():
                    parts = line.split(",")
                    if len(parts) >= 2:
                        offset = int(parts[0])
                        tone = int(line.split(" ")[1])
                        output.append((offset, tone))
            return output
        except subprocess.CalledProcessError as e:
            print(f"Error running plctone: {e}")
            return None
        except Exception as e:
            print(f"Unexpected error in read_tonemap: {e}")
            return None

    def read_rates(self):
        if not self.local or not self.remote:
            return None
        try:
            command = f"plcrate -q -i {self.interface} -q {self.local.mac} {self.remote.mac}"
            raw_output = subprocess.check_output(command, shell=True, stderr=subprocess.STDOUT).decode()
            output = []
            
            for line in raw_output.splitlines():
                if "TX" in line:
                    try:
                        rate = int(line.split("TX")[1].split()[0])
                        output.append(rate)
                    except (IndexError, ValueError):
                        pass
                if "RX" in line:
                    try:
                        rate = int(line.split("RX")[1].split()[0])
                        output.append(rate)
                    except (IndexError, ValueError):
                        pass
            return output
        except subprocess.CalledProcessError as e:
            print(f"Error running plcrate: {e}")
            return None
        except Exception as e:
            print(f"Unexpected error in read_rates: {e}")
            return None

    def read_snr(self):
        if not self.local or not self.remote:
            return None
        try:
            command = f"plcrate -i {self.interface} -qs{self.local.mac} {self.remote.mac}"
            raw_output = subprocess.check_output(command, shell=True, stderr=subprocess.STDOUT).decode()
            return raw_output
        except subprocess.CalledProcessError as e:
            print(f"Error running plcrate for SNR: {e}")
            return None
        except Exception as e:
            print(f"Unexpected error in read_snr: {e}")
            return None


if __name__ == "__main__": 
    tester = PlcTester()
    print(tester.devices)
    print(tester.read_tonemap())
    print(tester.read_rates())
    print(tester.read_snr())