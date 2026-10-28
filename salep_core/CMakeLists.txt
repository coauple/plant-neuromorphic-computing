cmake_minimum_required(VERSION 3.10)
project(npu_core LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# ARCHITECTURE.md §6: -Wall -Wextra + sanitizers geliştirme sırasında açık
add_compile_options(-Wall -Wextra -Wpedantic)

# Sanitizer'lar sadece Debug modunda (Release'de kapatılır)
if(CMAKE_BUILD_TYPE STREQUAL "Debug" OR NOT CMAKE_BUILD_TYPE)
    add_compile_options(-fsanitize=address,undefined -fno-omit-frame-pointer)
    add_link_options(-fsanitize=address,undefined)
endif()

add_executable(npu_sim src/main.cpp)
target_include_directories(npu_sim PRIVATE src)

add_executable(npu_branch src/main_branch.cpp)
target_include_directories(npu_branch PRIVATE src)

add_executable(npu_multi src/main_multi.cpp)
target_include_directories(npu_multi PRIVATE src)

add_executable(npu_sim_event src/main_event.cpp)
target_include_directories(npu_sim_event PRIVATE src)

add_executable(npu_synapse src/main_synapse.cpp)
target_include_directories(npu_synapse PRIVATE src)

add_executable(npu_network src/main_network.cpp)
target_include_directories(npu_network PRIVATE src)

add_executable(npu_phase_group src/main_phase_group.cpp)
target_include_directories(npu_phase_group PRIVATE src)

add_executable(npu_causality src/main_causality.cpp)
target_include_directories(npu_causality PRIVATE src)

add_executable(npu_fdm src/main_fdm.cpp)
target_include_directories(npu_fdm PRIVATE src)

add_executable(npu_plant_npu src/main_plant_npu.cpp)
target_include_directories(npu_plant_npu PRIVATE src)

add_executable(npu_sensory_lobe src/main_sensory_lobe.cpp)
target_include_directories(npu_sensory_lobe PRIVATE src)

add_executable(npu_sensory_plant src/main_sensory_plant.cpp)
target_include_directories(npu_sensory_plant PRIVATE src)

add_executable(npu_causal_afferent src/main_causal_afferent.cpp)
target_include_directories(npu_causal_afferent PRIVATE src)
