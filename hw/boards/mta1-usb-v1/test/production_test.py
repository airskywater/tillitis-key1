#!/usr/bin/env python3
import hid_test
import time
import numpy
from subprocess import run
import usb.core
import uuid
import encode_usb_strings
import serial
import serial.tools.list_ports;
import shutil

# Locations for external utilities and files referenced by the test program
file_locations = {
    'iceprog':'/home/matt/Other-Repos/icestorm/iceprog/iceprog',
    'chprog':'/home/matt/Other-Repos/chprog/chprog',
    'app_gateware':'/home/matt/Other-Repos/mta1_mkdf/hw/boards/mta1-usb-v1/test/app_test/top.bin',
    'ch552_firmware':'/home/matt/Other-Repos/mta1_mkdf/hw/boards/mta1-usb-v1/ch552_fw/usb_device_cdc.bin',
    'ch552_firmware_injected':'/tmp/ch552_fw_injected.bin',
    'pico_bootloader_source':'/home/matt/Blinkinlabs-Repos/ice40_flasher/bin/main.uf2',
    'pico_bootloader_target':'/media/matt/RPI-RP2/main.uf2'
}

def measure_voltages(device, samples):
    """ Measure the voltage levels of the three mta1 power rails multiple times, and return the average values """
    adc_vals = numpy.array([0,0,0])
    for i in range(0,samples):
        adc_vals = adc_vals + device.adc_read_all()
    adc_vals = dict(zip(['1.2','2.5','3.3'],adc_vals/samples))
    return adc_vals

def voltage_test():
    """Turn on the device, delay, measure voltage, then turn it off"""
    d = hid_test.ice40_flasher()

    d.gpio_set_direction(7, True)
    d.gpio_put(7, True)
    time.sleep(.2)

    vals = measure_voltages(d,20)

    d.gpio_put(7, False)
    d.close()

    print('voltages:',vals)
    if (
        (abs(vals['1.2'] - 1.2) > .2)
        | (abs(vals['2.5'] - 2.5) > .2)
        | (abs(vals['3.3'] - 3.3) > .2)
        ):
        return False

    return True

def flash_validate_id():
    """ Read the ID from the flash, and verify that it's not all 0's or 1's (which would indicate a communications issue) """
    result = run([
        file_locations['iceprog'],
        '-t'
        ],
        capture_output=True)

    err = result.stderr.split(b'\n')
    for line in err:
        if line.startswith(b'flash ID:'):
            vals_b = line.split(b' 0x')[1:]
            flash_id = int(b''.join(vals_b),16)
            print(line, hex(flash_id))
            if (flash_id == 0) or (flash_id == 0xFFFFFFFF):
                return False
            return True
            
    return (result.returncode == 0)

def flash_program():
    """ Program and verify the SPI flash """
    result = run([
        file_locations['iceprog'],
        file_locations['app_gateware']
        ])
    print(result)

    return (result.returncode == 0)

def flash_check():
    """ Verify the contents of the SPI flash """
    result = run([
        file_locations['iceprog'],
        '-c',
        file_locations['app_gateware']
        ])
    print(result)

    return (result.returncode == 0)

def test_extra_io():
    """ Test the RTS, CTS, and GPIO1-4 lines by measuring a test pattern generated by the app_test gateware when RTS is toggled """
    time.sleep(.1)
    d = hid_test.ice40_flasher()

    d.gpio_put(16, False)
    d.gpio_set_direction(16, True)

    expected_results = [1<<(i%5) for i in range(9,-1,-1)]

    results = []
    for i in range(0,10):
        vals = d.gpio_get_all()
        pattern = (vals >> 17) & 0b11111
        results.append(pattern)

        d.gpio_put(16, True)
        d.gpio_put(16, False)

    d.gpio_set_direction(16, False)
    d.close()

    print(results,expected_results,results == expected_results)
    return results == expected_results

def disable_power():
    """ Disable power to the mta1-usb device """
    time.sleep(.1)
    d = hid_test.ice40_flasher()
    d.gpio_put(7, False)
    d.close()

def test_found_bootloader():
    """ Search for a CH552 in USB bootloader mode """
    print('\n\n\nSearching for CH552 bootloader, plug in USB cable now!')
    for trys in range(0,50):
        devices= usb.core.find(idVendor=0x4348, idProduct=0x55e0, find_all=True)
        count = len(list(devices))

        if count == 1:
            return True

        time.sleep(0.1)

    post = usb.core.find(idVendor=0x4348, idProduct=0x55e0, find_all=True)
    post_count = len(list(post))
    return (post_count == 1)

def inject_serial_number(infile, outfile, serial):
    """ Inject a serial number into the specified CH552 firmware file """
    magic = encode_usb_strings.string_to_descriptor("68de5d27-e223-4874-bc76-a54d6e84068f")
    replacement = encode_usb_strings.string_to_descriptor(serial)

    f = bytearray(open(infile, 'rb').read())
    
    pos = f.find(magic)
    
    if pos < 0:
        print('failed to find magic string')
        exit(1)
    
    f[pos:(pos+len(magic))] = replacement
    
    with open(outfile, 'wb') as of:
        of.write(f)
    
def flash_ch552(serial):
    """ Flash an attached CH552 device (in bootloader mode) with the USB CDC firmware, injected with the given serial number """

    print(serial)
    inject_serial_number(
        file_locations['ch552_firmware'],
        file_locations['ch552_firmware_injected'],
        serial)
    
    # Program the CH552 using CHPROG
    result = run([
        file_locations['chprog'],
        file_locations['ch552_firmware_injected']
        ])
    print(result)
    return (result.returncode == 0)

def find_serial_device(desc):
    """ Look for a serial device that has the given attributes """

    for port in serial.tools.list_ports.comports():
        matched = True
        for key, value in desc.items():
            if not getattr(port, key) == value:
                matched = False

        if matched:
            print(port.device)
            return port.device

    return None

def test_found_ch552(serial):
    """ Search all serial devices for one that has the correct description and serial number """
    time.sleep(1)

    description = {
        'vid':0x1207,
        'pid':0x8887,
        'manufacturer':'Tillitis',
        'product':'MTA1-USB-V1',
        'serial_number':serial
    }
    
    if find_serial_device(description) == None:
        return False

    return True

def ch552_find_and_program():
    """ Load the CDC ACM firmware onto a CH552 with a randomly generated serial number, and verify that it boots correctly """
    if not test_found_bootloader():
        print('Error finding CH552!')
        return False
    
    serial = str(uuid.uuid4())
    
    if not flash_ch552(serial):
        print('Error flashing CH552!')
        return False
    
    if not test_found_ch552(serial):
        print('Error finding flashed CH552!')
        return False

    return True



def test_txrx_touchpad():
    """ Test UART communication by asking the operator to interact with the touch pad """
    description = {
        'vid':0x1207,
        'pid':0x8887,
        'manufacturer':'Tillitis',
        'product':'MTA1-USB-V1'
    }
    
    s = serial.Serial(find_serial_device(description),9600, timeout=.2)

    if not s.isOpen():
        print('couldn\'t find/open serial device')
        return False
        

    s.write(b'0123')
    time.sleep(0.1)
    s.read(20)

    try:
        s.write(b'0')
        [count, touch_count] = s.read(2)
        print(count,touch_count)
    
        input('\n\n\nPress touch pad once and check LED, then press Enter')
        s.write(b'0')
        [count_post, touch_count_post] = s.read(2)
        print(count_post,touch_count_post)
    
        if (count_post - count != 1) or (touch_count_post - touch_count !=1):
            return False
    
        return True
    except ValueError as e:
        print(e)
        return False

def production_test(args):
    """ mta1-usb-v1 production test. Specify --noflash to skip flashing the gateware to the SPI flash, and --noch552 to skip programming the USB CDC firmware to the CH552 """
    if not voltage_test():    
        print('voltage out of range')
        return False

    if not flash_validate_id():    
        print('Error reading flash ID')
        return False

    if not args.noflash:
        if not flash_program():    
            print('Error programming flash')
            return False
    else:
        if not flash_check():
            print('Error checking flash')
            return False

    if not test_extra_io():
        print('Error testing io')
        return False

    if not args.noch552:
        disable_power()

        if not ch552_find_and_program(): 
            return False

    if not test_txrx_touchpad():
        print('Error reading touchpad!')
        return False

    return True

def program_pico():
    """ Load the ice40 flasher firmware onto an rpi pico in bootloader mode """
    print('Attach test rig to USB')
    for trys in range(0,50):
        try:
            shutil.copyfile(
                file_locations['pico_bootloader_source'],
                file_locations['pico_bootloader_target']
                )
            return True
        except FileNotFoundError:
            time.sleep(0.1)
        except PermissionError:
            time.sleep(0.1)
    
    return False

def programmer_production_test(args):
    """ mta1-usb-v1-programmer production test. Place a (programmed) mta1-usb-v1 into the programmer, connect the programmer to the PC, then start the test. """

    if not program_pico():
        print('error programming the pico')
        return False
    
    # Let the board start
    time.sleep(2)

    if not voltage_test():    
        print('voltage out of range')
        return False

    if not flash_validate_id():    
        print('Error reading flash ID')
        return False

    if not flash_check():    
        print('Error programming flash')
        return False

    if not test_extra_io():
        print('Error testing io')
        return False

    return True

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='GPIO short connector test')
    parser.add_argument('--noch552', action='store_true', help='Skip programming the CH552. Used for re-testing an mta1-usb-v1 board.')
    parser.add_argument('--noflash', action='store_true', help='Skip programming the SPI flash. Used for re-testing an mta1-usb-v1 board')
    parser.add_argument('--programmer', action='store_true', help='Program/test the programmer')
    parser.add_argument('--ch552', action='store_true', help='Program/test (only) the CH552.')
    args = parser.parse_args()

    while True:
        input('\n\n\nPress Enter to start')
        if args.programmer:
            result = programmer_production_test(args)
        elif args.ch552:
            result = ch552_find_and_program()
        else:
            result = production_test(args)

        if result:
            print('\n\n\nDONE')
        else:
            print('\n\n\nFAIL')

        try: 
            disable_power()
        except AttributeError as e:
            print(e)
