cmake_minimum_required(VERSION 3.13)

include(pico_sdk_import.cmake)

project(firmware C CXX ASM)
set(CMAKE_C_STANDARD 11)
set(CMAKE_CXX_STANDARD 17)
pico_sdk_init()

add_executable(firmware firmware.c)

pico_enable_stdio_usb(firmware 1)
pico_enable_stdio_uart(firmware 1)

pico_set_binary_type(firmware no_flash)
pico_sign_binary(firmware ../ec_private_key.pem)
pico_hash_binary(firmware)
pico_set_otp_key_output_file(firmware ../otp.json)
pico_package_uf2_output(firmware 0x10000000)

pico_add_extra_outputs(firmware)
target_link_libraries(firmware pico_stdlib)
