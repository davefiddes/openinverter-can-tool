# Linux SocketCAN Configuration

## Manual Start

Before you can start using OpenInverter CAN Tool configured to use `socketcan` you need to bring up the system wide `socketcan` network interface. For test purposes this can be done manually. For example to start a 500kbps CAN interface:

```text
    sudo ip link set can0 up type can bitrate 500000
```

## Automatic Start

It is possible to have the `socketcan` interface started automatically at boot time. The method for doing this will depend on your Linux distribution.

### Configure systemd-networkd

On Debian, Ubuntu or Fedora you should create a configuration for your network in `/etc/systemd/network/80-can.network` with the following content:

```text
[Match]
Name=can*

[CAN]
BitRate=500K
```

Then enable the `systemd-networkd` service:

```text
    sudo systemctl enable systemd-networkd
```

### Configure kernel modules

You will need to configure the kernel modules to start the `socketcan` interface. This can be done by creating a file `/etc/modules-load.d/can.conf` with the following content:

```text
can
can_raw
```

Your Linux initramfs will now need to be regenerated to include the new modules.

On Debian or Ubuntu this can be done using:

```text
    sudo update-initramfs -u
```

On Fedora you can use:

```text
    sudo dracut --force
```

Reboot your system for the configuration to take effect. When USB CAN adapters are plugged in they should now automatically start the `socketcan` interface.

Note: Failure to regenerate the initramfs may result in your system appearing to hang on boot. Should this happen it will eventually boot allow you to carefully recheck the configuration

## Verify Configuration

You can see the status of the `socketcan` interfaces using:

```text
$ ip -details link show type can
2: can0: <NOARP,UP,LOWER_UP,ECHO> mtu 16 qdisc pfifo_fast state UP mode DEFAULT group default qlen 10
    link/can  promiscuity 0 allmulti 0 minmtu 0 maxmtu 0
    can state ERROR-ACTIVE restart-ms 0
          bitrate 500000 sample-point 0.875
          tq 125 prop-seg 6 phase-seg1 7 phase-seg2 2 sjw 1 brp 6
          gs_usb: tseg1 1..16 tseg2 1..8 sjw 1..4 brp 1..1024 brp_inc 1
          clock 48000000 numtxqueues 1 numrxqueues 1 gso_max_size 65536 gso_max_segs 65535 tso_max_size 65536 tso_max_segs 65535 gro_max_size 65536 gso_ipv4_max_size 65536 gro_ipv4_max_size 65536 parentbus usb parentdev 1-2:1.0
```

Other common Linux tools like [SavvyCAN](https://savvycan.com/) and [Wireshark](https://www.wireshark.org/) can also be used to verify the CAN interface is working correctly. These tools can be used at the same time as OpenInverter CAN Tool.
