# SPDX-License-Identifier: LGPL-2.1-or-later
#
# Studio: the fork's unified shell and services. Architecture: docs/adr/0002-layered-architecture.md

file(GLOB_RECURSE Studio_Package_SRCS
    RELATIVE ${CMAKE_CURRENT_SOURCE_DIR}
    CONFIGURE_DEPENDS
    studio/*.py
    StudioTests/*.py
    Resources/icons/*.svg
)

set(Studio_Scripts
    Init.py
    TestStudioApp.py
)
if(BUILD_GUI)
    list(APPEND Studio_Scripts
        InitGui.py
        TestStudioGui.py
    )
endif(BUILD_GUI)

set(Studio_All ${Studio_Scripts} ${Studio_Package_SRCS})

add_custom_target(StudioScripts ALL
    SOURCES ${Studio_All}
)
fc_copy_sources(StudioScripts "${CMAKE_BINARY_DIR}/Mod/Studio" ${Studio_All})

# Product configuration: FreeCAD reads <AppHomePath>/bin/branding.xml at startup
# (src/App/Application.cpp). Copied at configure time; CMake re-runs when the file changes.
configure_file(branding/branding.xml "${CMAKE_BINARY_DIR}/bin/branding.xml" COPYONLY)

install(FILES ${Studio_Scripts} DESTINATION Mod/Studio)
install(
    DIRECTORY studio StudioTests
    DESTINATION Mod/Studio
    FILES_MATCHING PATTERN "*.py"
)
install(DIRECTORY Resources DESTINATION Mod/Studio)
install(FILES branding/branding.xml DESTINATION ${CMAKE_INSTALL_BINDIR})
