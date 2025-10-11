# PLC Diagnostics

A diagnostic tool for [powerline communication](https://en.wikipedia.org/wiki/Power-line_communication) (PLC) network connections, like provided by the Blue Robotics [Fathom-X boards](https://bluerobotics.com/store/comm-control-power/tether-interface/fathom-x-tether-interface-board-set-copy/) (which use the HomePlug AV PLC protocol).

### Devices

The Device card should show the local device (onboard the vehicle), plus any others connected to the network (e.g. one remote device, in a normal tether setup).

<p align="center">
  <a href="doc/devices.png">
    <img src="https://github.com/Williangalvani/plc-extension/blob/main/doc/devices.png" width="50%" alt="connected local and remote devices">
  </a>
</p>

PLC operates with high frequency signals, so it is possible for a cable to be broken or unplugged but still close enough to form a capacitive or inductive connection (instead of a wired one). Seeing a detected remote device **does NOT** guarantee the connections are set up correctly, especially if bandwidth is substantially lower than expected.

## Bandwidth

> 💡 These diagnostics are most accurate when the network is under load, so it is recommended to **run a local network test** while viewing them.

### Directionality

The directionality plot shows transmit (TX) and receive (RX) bandwidths at the physical (PHY) layer of the network stack. Practical _usable_ bandwidth (measured by a network test) is lower, due to networking overheads.

![ideal, 200m tether, single-wire, and wrong pair connection plots](https://github.com/Williangalvani/plc-extension/blob/main/doc/bandwidth-examples.png)

- A healthy tether connection should have steady and roughly equal transmit and receive bandwidths
- Sharp dips indicate an intermittent connection
   - e.g. from a broken wire/connector, or brief bursts of strong electromagnetic noise (which is unlikely to occur if using twisted pair wires)
- A large separation (>~20Mbps) indicates an impedance mismatch between the wires of the tether pair (with the connection partially or fully being formed through capacitive coupling)
   - if RX is significantly above TX, one of the wires is likely not connected or broken
   - if TX is significantly above RX, the PLC boards are likely connected to separate wire pairs in the same cable
- Very low bandwidth could indicate the wires are completely unplugged, or broken with some length separation

### Channel Breakdown

Powerline communication involves splitting the signal over multiple frequency bands (like radio channels). The channel plot indicates usable capacity of each frequency channel.

![ideal, 200m tether, single-wire, and wrong pair channel plots](https://github.com/Williangalvani/plc-extension/blob/main/doc/channels-examples.png)

- A channel with a score of 49 is fully available for the current network connection
   - Lower scores may indicate sources of electrical noise, collisions with other devices on the same lines, or impedance issues with the cable.
   - Parabolic reductions in capacity indicate interference at that frequency (e.g. from other PLC devices communicating on the network, or nearby switching electronics)
      - It is expected that there are a few narrow regions of low capacity, which should have minimal effect on the overall bandwidth capacity
- Electrical signals attenuate more with cable length and at higher signal frequencies
    - Long tethers are expected to have reduced capacity in the high frequency bins
    - If the _low_ frequency bins have reduced capacity (e.g. consistently <40), at least one of the wires is likely disconnected 
    - If the channel capacities reduce gradually over time (across days/months), it may indicate corrosion of the wires

## Deeper Understanding

The following resources may be helpful for understanding how PLC works and can be analysed

- [A paper about PLC technology implementation](https://www.witpress.com/Secure/ejournals/papers/DNE130204f.pdf)
- [A paper about technologies and ideas involved in PLC's development and progress](https://www.researchgate.net/publication/330485829_Power_Line_Communications_PLC_Technology_More_Than_20_Years_of_Intense_Research)
- [The tools this Extension is based on](https://github.com/qca/open-plc-utils)
   - Specifically `plcstat`, `plctone`, and `plcrate`
