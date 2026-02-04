from class_soil_EC_RK500 import SensorSoilECRK500_23

sensor = SensorSoilECRK500_23(port="/dev/ttyS4", slave_address=0x58)

# # อ่านข้อมูลทั้งหมด
data = sensor.read_data()
if data["success"]:
    print(f"EC: {data['ec_value']:.3f} mS/cm")
    print(f"Salinity: {data['salinity']:.1f} PPM")

# # อ่านเฉพาะค่า EC
# ec_value = sensor.read_ec_only()
# print(f"EC: {ec_value:.3f} mS/cm")

# # จำแนกความเค็มดิน
# classification = SensorSoilECRK500_23.classify_soil_salinity(ec_value)
# print(f"Soil level: {classification['level']}")

#เปลี่ยน addrress sensor
# success = sensor.set_address(0x58)

# if success:
#     print("✅ เปลี่ยน address สำเร็จ!")
#     print(f"Address ใหม่: 0x{sensor.slave_address:02X}")
# else:
#     print("❌ เปลี่ยน address ล้มเหลว")