# SPDX-License-Identifier: LGPL-2.1-or-later
#
# StudioGui: Studio's C++ helpers for the shell, only where FreeCAD has no Python API
# (docs/adr/0007-lazy-loading-command-catalog.md). Built next to Studio's Python files
# (build/Mod/Studio/StudioGui.pyd) by SET_BIN_DIR.

add_library(StudioGui SHARED AppStudioGui.cpp)

target_include_directories(
    StudioGui
    PRIVATE
    ${CMAKE_BINARY_DIR}
    ${CMAKE_SOURCE_DIR}/src
    ${CMAKE_BINARY_DIR}/src
    ${CMAKE_CURRENT_BINARY_DIR}
    ${QtSvg_INCLUDE_DIRS}
)
target_link_libraries(StudioGui FreeCADGui ${QtSvg_LIBRARIES})
if(MSVC)
    target_compile_options(StudioGui PRIVATE /wd4251 /wd4273)
endif()
target_compile_warn_error(StudioGui)

SET_BIN_DIR(StudioGui)
SET_PYTHON_PREFIX_SUFFIX(StudioGui)

install(TARGETS StudioGui DESTINATION ${CMAKE_INSTALL_LIBDIR})
