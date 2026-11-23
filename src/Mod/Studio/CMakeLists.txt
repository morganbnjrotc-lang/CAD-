# SPDX-License-Identifier: LGPL-2.1-or-later
#
# Studio: the fork's unified shell and services. Architecture: docs/adr/0002-layered-architecture.md

file(GLOB_RECURSE Studio_Package_SRCS
    RELATIVE ${CMAKE_CURRENT_SOURCE_DIR}
    CONFIGURE_DEPENDS
    studio/*.py
    studio/*.json
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
        TestStudioModelingGui.py
    )
endif(BUILD_GUI)

set(Studio_All ${Studio_Scripts} ${Studio_Package_SRCS})

if(BUILD_GUI)
    add_subdirectory(Gui)  # StudioGui C++ helpers
endif(BUILD_GUI)

# Icons of the command catalog's commands (docs/adr/0007): the catalog names each icon's source
# SVG ("icon": "src/Mod/..."). Copy them next to Studio so the palette can show icons of commands
# whose module isn't loaded yet (FreeCAD registers a module's icons only when it loads).
set(Studio_CATALOG ${CMAKE_CURRENT_SOURCE_DIR}/studio/services/command_catalog.json)
set_property(DIRECTORY APPEND PROPERTY CMAKE_CONFIGURE_DEPENDS ${Studio_CATALOG})
file(STRINGS ${Studio_CATALOG} Studio_ICON_LINES REGEX "\"icon\": \"src/")
set(Studio_ICONS "")
foreach(line ${Studio_ICON_LINES})
    string(REGEX REPLACE ".*\"icon\": \"src/([^\"]+)\".*" "\\1" icon "${line}")
    list(APPEND Studio_ICONS ${icon})
endforeach()
# Icons the tool groups show besides the catalog's (studio/viewmodels/tool_groups.py, PLAN 3.17): Part
# Design's primitives, which one command makes each for adding and for cutting.
foreach(kind Additive Subtractive)
    foreach(shape Box Cylinder Sphere Cone Ellipsoid Torus Prism Wedge)
        list(APPEND Studio_ICONS Mod/PartDesign/Gui/Resources/icons/PartDesign_${kind}${shape}.svg)
    endforeach()
endforeach()
list(REMOVE_DUPLICATES Studio_ICONS)
foreach(icon ${Studio_ICONS})
    configure_file(${CMAKE_SOURCE_DIR}/src/${icon}
                   ${CMAKE_BINARY_DIR}/Mod/Studio/Resources/command_icons/${icon} COPYONLY)
    get_filename_component(icon_dir ${icon} DIRECTORY)
    install(FILES ${CMAKE_SOURCE_DIR}/src/${icon} DESTINATION Mod/Studio/Resources/command_icons/${icon_dir})
endforeach()

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
    FILES_MATCHING PATTERN "*.py" PATTERN "*.json"
)
install(DIRECTORY Resources DESTINATION Mod/Studio)
install(FILES branding/branding.xml DESTINATION ${CMAKE_INSTALL_BINDIR})
