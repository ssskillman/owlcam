import shutil
import subprocess
import time

ADDR = "0x76"
BUS = "1"
I2CTRANSFER = shutil.which("i2ctransfer") or "/usr/sbin/i2ctransfer"


def run_i2c(args, retries=10, delay=0.05):
    last_error = None

    for _ in range(retries):
        result = subprocess.run(
            [I2CTRANSFER, "-y", BUS] + args,
            capture_output=True,
            text=True,
        )

        if result.returncode == 0:
            return result.stdout.strip()

        last_error = result.stderr.strip()
        time.sleep(delay)

    raise RuntimeError(
        f"I2C failed after {retries} attempts: {last_error}"
    )


def read_reg(register, length=1):
    output = run_i2c([
        f"w1@{ADDR}",
        hex(register),
        f"r{length}",
    ])

    return [int(x, 16) for x in output.split()]


def write_reg(register, value):
    run_i2c([
        f"w2@{ADDR}",
        hex(register),
        hex(value),
    ])


def u16_le(data, offset):
    return data[offset] | (data[offset + 1] << 8)


def s16_le(data, offset):
    value = u16_le(data, offset)

    if value & 0x8000:
        value -= 65536

    return value


def read_bme280():
    # Reset
    write_reg(0xE0, 0xB6)
    time.sleep(0.1)

    # Wait for calibration copy
    for _ in range(50):
        status = read_reg(0xF3, 1)[0]

        if not (status & 0x01):
            break

        time.sleep(0.01)
    else:
        raise RuntimeError(
            "BME280 calibration copy timed out"
        )

    # Confirm chip
    chip_id = read_reg(0xD0, 1)[0]

    if chip_id != 0x60:
        raise RuntimeError(
            f"Unexpected BME280 chip ID: 0x{chip_id:02X}"
        )

    # Calibration data
    cal1 = read_reg(0x88, 26)

    dig_T1 = u16_le(cal1, 0)
    dig_T2 = s16_le(cal1, 2)
    dig_T3 = s16_le(cal1, 4)

    dig_P1 = u16_le(cal1, 6)
    dig_P2 = s16_le(cal1, 8)
    dig_P3 = s16_le(cal1, 10)
    dig_P4 = s16_le(cal1, 12)
    dig_P5 = s16_le(cal1, 14)
    dig_P6 = s16_le(cal1, 16)
    dig_P7 = s16_le(cal1, 18)
    dig_P8 = s16_le(cal1, 20)
    dig_P9 = s16_le(cal1, 22)

    dig_H1 = cal1[25]

    cal2 = read_reg(0xE1, 7)

    dig_H2 = s16_le(cal2, 0)
    dig_H3 = cal2[2]

    dig_H4 = (
        (cal2[3] << 4)
        | (cal2[4] & 0x0F)
    )

    if dig_H4 & 0x800:
        dig_H4 -= 4096

    dig_H5 = (
        (cal2[5] << 4)
        | (cal2[4] >> 4)
    )

    if dig_H5 & 0x800:
        dig_H5 -= 4096

    dig_H6 = cal2[6]

    if dig_H6 & 0x80:
        dig_H6 -= 256

    # Configure sensor
    write_reg(0xF2, 0x01)  # humidity x1
    write_reg(0xF5, 0x00)  # no filter
    write_reg(0xF4, 0x25)  # temp x1, pressure x1, forced mode

    # Wait for measurement
    for _ in range(100):
        status = read_reg(0xF3, 1)[0]

        if not (status & 0x08):
            break

        time.sleep(0.01)
    else:
        raise RuntimeError(
            "BME280 measurement timed out"
        )

    time.sleep(0.02)

    # Raw measurement
    data = read_reg(0xF7, 8)

    adc_P = (
        (data[0] << 12)
        | (data[1] << 4)
        | (data[2] >> 4)
    )

    adc_T = (
        (data[3] << 12)
        | (data[4] << 4)
        | (data[5] >> 4)
    )

    adc_H = (
        (data[6] << 8)
        | data[7]
    )

    # Reject invalid readings
    if adc_T == 0x80000:
        raise RuntimeError("Invalid temperature reading")

    if adc_P == 0x80000:
        raise RuntimeError("Invalid pressure reading")

    if adc_H == 0x8000:
        raise RuntimeError("Invalid humidity reading")

    # Temperature compensation
    var1 = (
        (
            adc_T / 16384.0
            - dig_T1 / 1024.0
        )
        * dig_T2
    )

    var2 = (
        (
            (
                adc_T / 131072.0
                - dig_T1 / 8192.0
            )
            ** 2
        )
        * dig_T3
    )

    t_fine = var1 + var2

    temperature_c = t_fine / 5120.0
    temperature_f = temperature_c * 9 / 5 + 32

    # Pressure compensation
    var1 = t_fine / 2.0 - 64000.0

    var2 = (
        var1
        * var1
        * dig_P6
        / 32768.0
    )

    var2 = (
        var2
        + var1
        * dig_P5
        * 2.0
    )

    var2 = (
        var2 / 4.0
        + dig_P4 * 65536.0
    )

    var1 = (
        (
            dig_P3
            * var1
            * var1
            / 524288.0
        )
        + (
            dig_P2
            * var1
        )
    ) / 524288.0

    var1 = (
        1.0
        + var1 / 32768.0
    ) * dig_P1

    if var1 == 0:
        raise RuntimeError(
            "Invalid pressure calibration"
        )

    pressure = 1048576.0 - adc_P

    pressure = (
        (
            pressure
            - var2 / 4096.0
        )
        * 6250.0
        / var1
    )

    var1 = (
        dig_P9
        * pressure
        * pressure
        / 2147483648.0
    )

    var2 = (
        pressure
        * dig_P8
        / 32768.0
    )

    pressure = (
        pressure
        + (
            var1
            + var2
            + dig_P7
        )
        / 16.0
    )

    pressure_hpa = pressure / 100.0

    # Humidity compensation
    humidity = t_fine - 76800.0

    humidity = (
        adc_H
        - (
            dig_H4 * 64.0
            + dig_H5
            / 16384.0
            * humidity
        )
    ) * (
        dig_H2
        / 65536.0
        * (
            1.0
            + dig_H6
            / 67108864.0
            * humidity
            * (
                1.0
                + dig_H3
                / 67108864.0
                * humidity
            )
        )
    )

    humidity = (
        humidity
        * (
            1.0
            - dig_H1
            * humidity
            / 524288.0
        )
    )

    humidity = max(
        0.0,
        min(100.0, humidity)
    )

    return {
        "temperature_c": round(temperature_c, 2),
        "temperature_f": round(temperature_f, 2),
        "humidity_pct": round(humidity, 2),
        "pressure_hpa": round(pressure_hpa, 2),
    }


if __name__ == "__main__":
    data = read_bme280()

    print(f"Temperature: {data['temperature_f']:.2f} °F")
    print(f"Humidity:    {data['humidity_pct']:.2f} %")
    print(f"Pressure:    {data['pressure_hpa']:.2f} hPa")
